from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from . import auth, curriculum, student_api, student_management, teacher_api, tests_api, textbook_management
from .config import get_settings
from .errors import install_error_handlers


settings = get_settings()
app = FastAPI(title=settings.app_name, version="1.0.0", docs_url="/docs" if not settings.is_production else None)
install_error_handlers(app)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_origin],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "X-Requested-With"],
)


@app.middleware("http")
async def enforce_origin(request: Request, call_next):
    if request.method in {"POST", "PUT", "PATCH", "DELETE"}:
        origin = request.headers.get("origin")
        if origin and origin.rstrip("/") != settings.frontend_origin.rstrip("/"):
            return JSONResponse(status_code=403, content={"error": {"code": "invalid_origin", "message": "Request origin is not allowed"}})
    return await call_next(request)

app.include_router(auth.router, prefix=settings.api_prefix)
app.include_router(curriculum.router, prefix=settings.api_prefix)
app.include_router(tests_api.router, prefix=settings.api_prefix)
app.include_router(student_api.router, prefix=settings.api_prefix)
app.include_router(teacher_api.router, prefix=settings.api_prefix)
app.include_router(student_management.router, prefix=settings.api_prefix)
app.include_router(textbook_management.router, prefix=settings.api_prefix)

# Keep database/bootstrap tooling usable if optional provider dependencies are
# intentionally omitted from an operator-only environment.
try:
    from .generation.router import router as generation_router
except ModuleNotFoundError:
    generation_router = None
if generation_router is not None:
    app.include_router(generation_router, prefix=settings.api_prefix)


@app.get("/health")
async def health():
    return {"status": "ok"}
