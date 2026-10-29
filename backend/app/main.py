from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .exc import BizError
from .api import auth, users, conversations, messages, models
from .database import init_db


def create_app() -> FastAPI:
    app = FastAPI(title="AI 聊天对话系统", version="0.1.0")

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.on_event("startup")
    def _on_startup():
        init_db()

    # 统一业务异常 → 统一响应
    @app.exception_handler(BizError)
    async def handle_biz_error(request: Request, e: BizError):
        return JSONResponse(
            status_code=e.http_status,
            content={"code": e.code, "message": e.message, "data": None},
        )

    # 未捕获异常兜底
    @app.exception_handler(Exception)
    async def handle_any_error(request: Request, e: Exception):
        return JSONResponse(
            status_code=500,
            content={"code": 5000, "message": f"服务内部错误: {e}", "data": None},
        )

    app.include_router(auth.router, prefix="/api")
    app.include_router(users.router, prefix="/api")
    app.include_router(conversations.router, prefix="/api")
    app.include_router(messages.router, prefix="/api")
    app.include_router(models.router, prefix="/api")

    @app.get("/health")
    def health():
        return {"ok": True}

    return app


app = create_app()
