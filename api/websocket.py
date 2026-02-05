"""WebSocket handler for real-time job updates."""
import asyncio
import json
from typing import Set, Dict
from fastapi import WebSocket, WebSocketDisconnect
import redis.asyncio as redis
from shared.config import settings


class ConnectionManager:
    """Manages WebSocket connections for job updates."""

    def __init__(self):
        # Map of job_id to set of WebSocket connections
        self.active_connections: Dict[str, Set[WebSocket]] = {}
        # All connections (for broadcast)
        self.all_connections: Set[WebSocket] = set()

    async def connect(self, websocket: WebSocket, job_id: str = None):
        """Accept a new WebSocket connection."""
        await websocket.accept()
        self.all_connections.add(websocket)

        if job_id:
            if job_id not in self.active_connections:
                self.active_connections[job_id] = set()
            self.active_connections[job_id].add(websocket)

    def disconnect(self, websocket: WebSocket, job_id: str = None):
        """Remove a WebSocket connection."""
        self.all_connections.discard(websocket)

        if job_id and job_id in self.active_connections:
            self.active_connections[job_id].discard(websocket)
            if not self.active_connections[job_id]:
                del self.active_connections[job_id]

    async def send_to_job(self, job_id: str, message: dict):
        """Send message to all connections watching a specific job."""
        if job_id in self.active_connections:
            disconnected = set()
            for connection in self.active_connections[job_id]:
                try:
                    await connection.send_json(message)
                except Exception:
                    disconnected.add(connection)

            # Clean up disconnected clients
            for conn in disconnected:
                self.disconnect(conn, job_id)

    async def broadcast(self, message: dict):
        """Send message to all connected clients."""
        disconnected = set()
        for connection in self.all_connections:
            try:
                await connection.send_json(message)
            except Exception:
                disconnected.add(connection)

        # Clean up disconnected clients
        for conn in disconnected:
            self.all_connections.discard(conn)


# Global connection manager
manager = ConnectionManager()


async def redis_subscriber(redis_client: redis.Redis):
    """Subscribe to Redis channel and forward updates to WebSocket clients."""
    pubsub = redis_client.pubsub()
    await pubsub.subscribe(settings.redis_result_channel)

    try:
        async for message in pubsub.listen():
            if message["type"] == "message":
                try:
                    data = json.loads(message["data"])
                    job_id = data.get("job_id")

                    if job_id:
                        # Send to clients watching this specific job
                        await manager.send_to_job(job_id, data)

                    # Also broadcast to all connections
                    await manager.broadcast(data)
                except json.JSONDecodeError:
                    pass
    except asyncio.CancelledError:
        pass
    finally:
        await pubsub.unsubscribe(settings.redis_result_channel)
        await pubsub.close()


async def websocket_endpoint(websocket: WebSocket, job_id: str = None):
    """WebSocket endpoint for job updates."""
    await manager.connect(websocket, job_id)

    try:
        while True:
            # Keep connection alive with heartbeat
            try:
                data = await asyncio.wait_for(
                    websocket.receive_text(),
                    timeout=settings.ws_heartbeat_interval
                )
                # Handle ping/pong
                if data == "ping":
                    await websocket.send_text("pong")
            except asyncio.TimeoutError:
                # Send heartbeat
                await websocket.send_json({"type": "heartbeat"})
    except WebSocketDisconnect:
        manager.disconnect(websocket, job_id)
