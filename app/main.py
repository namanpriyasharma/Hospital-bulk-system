"""Main FastAPI application entrypoint."""

from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import settings
from app.routers import bulk, status as status_router, websocket
from app.utils.logger import logger


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan event handler for startup and shutdown procedures."""
    logger.info(f"Starting {settings.APP_TITLE} v{settings.APP_VERSION}")
    logger.info(f"Connected to Directory API: {settings.DIRECTORY_API_BASE_URL}")
    yield
    logger.info(f"Shutting down {settings.APP_TITLE}")


app = FastAPI(
    title=settings.APP_TITLE,
    description=settings.APP_DESCRIPTION,
    version=settings.APP_VERSION,
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount API routers
app.include_router(bulk.router)
app.include_router(status_router.router)
app.include_router(websocket.router)


@app.get("/", tags=["Health"])
async def root():
    """Root metadata endpoint."""
    return {
        "service": settings.APP_TITLE,
        "version": settings.APP_VERSION,
        "status": "online",
        "docs": "/docs",
        "directory_api_url": settings.DIRECTORY_API_BASE_URL,
    }


@app.get("/health", tags=["Health"])
async def health_check():
    """Health check endpoint for container and deployment monitors."""
    return {"status": "healthy"}


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Fallback exception handler for unhandled errors."""
    logger.exception(f"Unhandled error processing {request.method} {request.url}: {exc}")
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "An internal server error occurred.", "error": str(exc)},
    )
