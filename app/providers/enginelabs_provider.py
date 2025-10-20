import json
import time
import logging
import uuid
import jwt
import cloudscraper
import websockets
import hashlib
from typing import Dict, Any, AsyncGenerator, Optional

from fastapi import HTTPException
from fastapi.responses import StreamingResponse, JSONResponse

from app.core.config import settings
from app.providers.base_provider import BaseProvider
from app.utils.sse_utils import create_sse_data, create_chat_completion_chunk, DONE_CHUNK

logger = logging.getLogger(__name__)

class EngineLabsProvider(BaseProvider):
    """Provider for EngineLabs API"""

    def __init__(self):
        if not settings.CLERK_COOKIE:
            raise ValueError("CLERK_COOKIE must be set in .env file")

        self.scraper = cloudscraper.create_scraper()
        self.chat_url = "https://api.enginelabs.ai/engine-agent/chat"

        self.clerk_cookie = settings.CLERK_COOKIE.strip()

        self.session_id = "sess_34CF6rxgHrvboCirm3k5sVJL2LF"
        self.organization_id = "org_34CG0TGEYHYPPUEVC6xiY7qAFUO"

        self.token_url = f"https://clerk.cto.new/v1/client/sessions/{self.session_id}/tokens?__clerk_api_version=2025-04-10"

        self.conversation_cache: Dict[str, str] = {}

        logger.info("EngineLabsProvider initialized")

    async def _get_fresh_jwt(self) -> str:
        logger.info("Requesting new JWT token...")
        headers = {
            "Cookie": self.clerk_cookie,
            "Content-Type": "application/x-www-form-urlencoded",
            "Origin": "https://cto.new",
            "Referer": "https://cto.new/",
        }
        form_data = { "organization_id": self.organization_id }
        try:
            response = self.scraper.post(self.token_url, headers=headers, data=form_data)
            response.raise_for_status()
            data = response.json()
            new_jwt = data.get("jwt")
            if not new_jwt:
                raise ValueError("Missing 'jwt' field in response")
            logger.info("Successfully obtained JWT token")
            return new_jwt
        except Exception as e:
            logger.error(f"Failed to get JWT token: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail=f"Failed to get auth token from Clerk: {e}")

    def _get_conversation_fingerprint(self, messages: list) -> str:
        if not messages:
            return "empty"
        history_str = json.dumps(messages, sort_keys=True)
        return hashlib.md5(history_str.encode('utf-8')).hexdigest()

    async def chat_completion(self, request_data: Dict[str, Any]) -> StreamingResponse:
        
        jwt_token = await self._get_fresh_jwt()
        user_id = jwt.decode(jwt_token, options={"verify_signature": False}).get("sub")
        
        model = request_data.get("model", settings.DEFAULT_MODEL)
        messages = request_data.get("messages", [])
        
        history_messages = messages[:-1]
        fingerprint = self._get_conversation_fingerprint(history_messages)
        
        if fingerprint in self.conversation_cache:
            chat_history_id = self.conversation_cache[fingerprint]
            logger.info(f"Reusing cached conversation: {chat_history_id}")
        else:
            chat_history_id = str(uuid.uuid4())
            self.conversation_cache[fingerprint] = chat_history_id
            logger.info(f"Created new conversation: {chat_history_id}")

        async def stream_generator() -> AsyncGenerator[bytes, None]:
            request_id = f"chatcmpl-{uuid.uuid4()}"
            websocket_uri = f"wss://api.enginelabs.ai/engine-agent/chat-histories/{chat_history_id}/buffer/stream?token={user_id}"
            
            try:
                last_user_message = messages[-1]["content"]
                
                headers = {
                    "Authorization": f"Bearer {jwt_token}",
                    "Content-Type": "application/json",
                    "Origin": "https://cto.new",
                    "Referer": f"https://cto.new/{chat_history_id}",
                }
                
                payload = {
                    "prompt": last_user_message,
                    "chatHistoryId": chat_history_id,
                    "adapterName": model,
                }

                logger.info(f"Sending request with chatHistoryId: {chat_history_id}")
                trigger_response = self.scraper.post(self.chat_url, headers=headers, json=payload, allow_redirects=False)

                trigger_response.raise_for_status()
                logger.info(f"Request successful: {trigger_response.status_code}")

                logger.info(f"Connecting to WebSocket: {websocket_uri}")
                async with websockets.connect(websocket_uri, origin="https://cto.new") as websocket:
                    logger.info("WebSocket connected, streaming response...")
                    
                    initial_chunk = create_chat_completion_chunk(request_id, model, "")
                    yield create_sse_data(initial_chunk)

                    while True:
                        message = await websocket.recv()
                        logger.debug(f"Received WebSocket message: {message}")

                        data = json.loads(message)

                        if data.get("type") == "state" and not data.get("state", {}).get("inProgress"):
                            logger.info("Stream ended")
                            break

                        if data.get("type") == "update":
                            buffer_str = data.get("buffer", "{}")
                            try:
                                buffer_data = json.loads(buffer_str)
                                if buffer_data.get("type") == "chat":
                                    content = buffer_data.get("chat", {}).get("content")
                                    if content:
                                        logger.debug(f"Sending content: {content}")
                                        chunk = create_chat_completion_chunk(request_id, model, content)
                                        yield create_sse_data(chunk)
                            except json.JSONDecodeError:
                                logger.warning(f"Failed to parse WebSocket buffer: {buffer_str}")
                                continue

            except Exception as e:
                logger.error(f"Stream error: {e}", exc_info=True)
                error_message = f"Internal error: {str(e)}"
                error_chunk = create_chat_completion_chunk(request_id, model, error_message, "stop")
                yield create_sse_data(error_chunk)
            finally:
                final_chunk = create_chat_completion_chunk(request_id, model, "", "stop")
                yield create_sse_data(final_chunk)
                logger.info("Stream completed")

        return StreamingResponse(stream_generator(), media_type="text/event-stream")

    async def get_models(self) -> JSONResponse:
        model_data = {
            "object": "list",
            "data": [
                {"id": name, "object": "model", "created": int(time.time()), "owned_by": "lzA6"}
                for name in settings.KNOWN_MODELS
            ]
        }
        return JSONResponse(content=model_data)
