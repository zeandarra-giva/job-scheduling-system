"""Main FastAPI application."""
import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI, WebSocket, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from database.connection import DatabaseConnection, get_redis
from api.routes import jobs_router
from api.websocket import websocket_endpoint, redis_subscriber
from shared.config import settings


# Background task for Redis subscriber
subscriber_task = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    global subscriber_task

    # Startup
    await DatabaseConnection.init_mongo()
    await DatabaseConnection.init_redis()

    # Start Redis subscriber for WebSocket updates
    redis_client = await get_redis()
    subscriber_task = asyncio.create_task(redis_subscriber(redis_client))

    yield

    # Shutdown
    if subscriber_task:
        subscriber_task.cancel()
        try:
            await subscriber_task
        except asyncio.CancelledError:
            pass

    await DatabaseConnection.close_connections()


# Create FastAPI app
app = FastAPI(
    title="Distributed Job Scheduling System",
    description="A distributed job scheduling and processing system for web scraping",
    version="1.0.0",
    lifespan=lifespan
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Exception handler
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Global exception handler."""
    return JSONResponse(
        status_code=500,
        content={"error": "Internal server error", "detail": str(exc)}
    )


# Include routers
app.include_router(jobs_router)


# WebSocket endpoints
@app.websocket("/ws")
async def websocket_all(websocket: WebSocket):
    """WebSocket endpoint for all job updates."""
    await websocket_endpoint(websocket)


@app.websocket("/ws/jobs/{job_id}")
async def websocket_job(websocket: WebSocket, job_id: str):
    """WebSocket endpoint for specific job updates."""
    await websocket_endpoint(websocket, job_id)


# Health check endpoint
@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy"}


@app.get("/")
async def root():
    """Root endpoint with API info."""
    return {
        "name": "Distributed Job Scheduling System",
        "version": "1.0.0",
        "docs": "/docs",
        "health": "/health"
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=settings.api_debug
    )
