"""全局异常处理中间件注册。

【为什么单独成模块】
原先异常兜底直接写在 `main.py` 里，与入口的路由装配混在一起。
按分层规范「入口只装配」，异常处理属于横切关注点，收敛到本模块，
由 `main` 在装配阶段一行注册。

【为什么失败响应也要同构】
前端对响应统一做 `ok` 判断。若 401/400/404 返回 FastAPI 默认的
`{"detail": ...}`，前端就得为两类错误写两套解析逻辑，容易漏判。
这里统一成 `{ok: false, reason}`，与项目其它接口保持一致。
"""

import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from .schemas import PredictResponse

logger = logging.getLogger("agriguard")


def register_error_handlers(app: FastAPI) -> None:
    """注册全局异常处理器（幂等，可重复调用）。"""

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception):
        logger.exception("未捕获异常：%s %s", request.method, request.url.path)
        return JSONResponse(
            status_code=200,  # 业务层用 ok=false 表达失败，避免前端 r.json() 解析失败
            content=PredictResponse(
                ok=False,
                reason="服务内部异常，请重试。若持续出现请联系维护者查看后端日志。",
            ).model_dump(),
        )

    @app.exception_handler(StarletteHTTPException)
    async def http_exception_handler(request: Request, exc: StarletteHTTPException):
        # 认证/越权等失败必须有明确状态码（Spec AC-05 要求 401、AC-13 要求 404），
        # 同时把响应体统一成 ok/reason，前端不必为两类错误写两套解析。
        if request.url.path.startswith("/api/"):
            return JSONResponse(
                status_code=exc.status_code,
                content={"ok": False, "reason": str(exc.detail)},
            )
        return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError):
        errors = exc.errors() or []
        first = errors[0] if errors else {}
        loc = ".".join(str(x) for x in first.get("loc", []) if x not in ("body", "query"))
        msg = first.get("msg") or "请求参数不正确"
        reason = f"请求参数不正确：{loc} {msg}".strip() if loc else f"请求参数不正确：{msg}"
        return JSONResponse(status_code=400, content={"ok": False, "reason": reason})
