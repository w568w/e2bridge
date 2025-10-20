import logging
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI, Request, HTTPException, Depends, Header
from fastapi.responses import JSONResponse, StreamingResponse

from app.core.config import settings
from app.providers.enginelabs_provider import EngineLabsProvider

# --- 日志配置 ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# --- 全局 Provider 实例 ---
provider = EngineLabsProvider()

# --- FastAPI Lifespan 管理 ---
@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info(f"{settings.APP_NAME} v{settings.APP_VERSION} started")
    yield
    logger.info("Application shutdown")

# --- FastAPI 应用实例 ---
app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description=settings.DESCRIPTION,
    lifespan=lifespan
)

# --- 依赖项：API Key 验证 ---
async def verify_api_key(authorization: Optional[str] = Header(None)):
    if settings.API_MASTER_KEY:
        if not authorization or "bearer" not in authorization.lower():
            raise HTTPException(status_code=401, detail="需要提供 Master API Key 进行认证 (Bearer Token)。")
        token = authorization.split(" ")[-1]
        if token != settings.API_MASTER_KEY:
            raise HTTPException(status_code=403, detail="无效的 Master API Key。")

# --- API 路由 ---
@app.post("/v1/chat/completions", dependencies=[Depends(verify_api_key)])
async def chat_completions(request: Request):
    """Handle chat completion requests"""
    try:
        request_data = await request.json()
        return await provider.chat_completion(request_data)

    except HTTPException as e:
        raise e
    except Exception as e:
        logger.error(f"处理聊天请求时发生顶层错误: {e}", exc_info=True)
        return JSONResponse(status_code=500, content={"error": {"message": f"内部服务器错误: {str(e)}", "type": "internal_server_error"}})

@app.get("/v1/models", dependencies=[Depends(verify_api_key)], response_class=JSONResponse)
async def list_models():
    return await provider.get_models()

@app.get("/", summary="根路径", include_in_schema=False)
def root():
    return {"message": f"欢迎来到 {settings.APP_NAME} v{settings.APP_VERSION}. 服务运行正常。"}
