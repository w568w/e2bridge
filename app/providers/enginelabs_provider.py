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
    """
    Provider for EngineLabs API.
    v10.0: The Final Truth. This version combines all successful learnings:
    - Autonomous JWT refresh using cookies.
    - Server-side context memory using a message hash cache.
    - Reverted to the simple 'prompt' string format, which is the only one accepted by the server.
    This is the definitive, stable, and fully functional version.
    """
    def __init__(self):
        if not settings.CLERK_COOKIE:
            raise ValueError("配置错误: CLERK_COOKIE 必须在 .env 文件中设置。")
        
        self.scraper = cloudscraper.create_scraper()
        self.chat_url = "https://api.enginelabs.ai/engine-agent/chat"
        
        self.clerk_cookie = settings.CLERK_COOKIE.strip()
        
        self.session_id = "sess_34CF6rxgHrvboCirm3k5sVJL2LF"
        self.organization_id = "org_34CG0TGEYHYPPUEVC6xiY7qAFUO"
        
        self.token_url = f"https://clerk.cto.new/v1/client/sessions/{self.session_id}/tokens?__clerk_api_version=2025-04-10"
        
        self.conversation_cache: Dict[str, str] = {}
        
        logger.info("EngineLabsProvider 已初始化 (真理协议 v10.0)，服务已就绪。")

    async def _get_fresh_jwt(self) -> str:
        logger.info("正在请求新的 JWT 令牌...")
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
            if not new_jwt: raise ValueError("响应中缺少 'jwt' 字段。")
            logger.info("成功获取新的 JWT 令牌。")
            return new_jwt
        except Exception as e:
            logger.error(f"获取新 JWT 令牌失败: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail=f"无法从 Clerk 自动获取认证令牌: {e}")

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
            logger.info(f"在缓存中找到对话指纹 '{fingerprint}'，复用 chatHistoryId: {chat_history_id}")
        else:
            chat_history_id = str(uuid.uuid4())
            self.conversation_cache[fingerprint] = chat_history_id
            logger.info(f"未找到对话指纹 '{fingerprint}'，创建新 chatHistoryId: {chat_history_id}")

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
                
                # 【【【 最终、真正的核心修正 】】】
                # 回归到被证明是正确的、简单的 payload 结构
                payload = {
                    "prompt": last_user_message, # prompt 必须是简单的字符串
                    "chatHistoryId": chat_history_id,
                    "adapterName": model,
                }
                
                logger.info(f"发送 POST 请求，使用 chatHistoryId: {chat_history_id}")
                trigger_response = self.scraper.post(self.chat_url, headers=headers, json=payload, allow_redirects=False)
                
                trigger_response.raise_for_status()
                logger.info(f"POST 请求成功，状态码: {trigger_response.status_code}")

                logger.info(f"正在连接到 WebSocket: {websocket_uri}")
                async with websockets.connect(websocket_uri, origin="https://cto.new") as websocket:
                    logger.info("WebSocket 连接成功，开始监听上游数据...")
                    
                    initial_chunk = create_chat_completion_chunk(request_id, model, "")
                    yield create_sse_data(initial_chunk)

                    while True:
                        message = await websocket.recv()
                        logger.info(f"收到 WebSocket 原始消息: {message}")
                        
                        data = json.loads(message)
                        
                        if data.get("type") == "state" and not data.get("state", {}).get("inProgress"):
                            logger.info("检测到上游任务结束信号，主动关闭流。")
                            break

                        if data.get("type") == "update":
                            buffer_str = data.get("buffer", "{}")
                            try:
                                buffer_data = json.loads(buffer_str)
                                if buffer_data.get("type") == "chat":
                                    content = buffer_data.get("chat", {}).get("content")
                                    if content:
                                        logger.info(f"解析并发送内容: {content}")
                                        chunk = create_chat_completion_chunk(request_id, model, content)
                                        yield create_sse_data(chunk)
                            except json.JSONDecodeError:
                                logger.warning(f"无法解析 WebSocket buffer: {buffer_str}")
                                continue
            
            except Exception as e:
                logger.error(f"处理流时发生错误: {e}", exc_info=True)
                error_message = f"内部错误: {str(e)}"
                error_chunk = create_chat_completion_chunk(request_id, model, error_message, "stop")
                yield create_sse_data(error_chunk)
            finally:
                final_chunk = create_chat_completion_chunk(request_id, model, "", "stop")
                yield create_sse_data(final_chunk)
                logger.info("SSE 流已发送 [DONE] 标志，请求处理完毕。")

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
