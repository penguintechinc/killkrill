"""
KillKrill API - WebSocket Blueprint
Real-time updates via WebSocket
"""

import asyncio
import json
from datetime import datetime
from typing import Any, Dict, Set

import structlog
from quart import Blueprint, websocket

logger = structlog.get_logger(__name__)

websocket_bp = Blueprint("websocket", __name__)

# Connected clients per channel
_clients: Dict[str, Set] = {
    "dashboard": set(),
    "logs": set(),
    "metrics": set(),
    "sensors": set(),
    "alerts": set(),
}

# Lock for client management
_lock = asyncio.Lock()


@websocket_bp.websocket("/connect")
async def ws_connect():
    """
    WebSocket connection handler

    Client messages:
        {"type": "subscribe", "channel": "dashboard"}
        {"type": "unsubscribe", "channel": "dashboard"}
        {"type": "ping"}

    Server messages:
        {"type": "subscribed", "channel": "dashboard", "timestamp": "..."}
        {"type": "unsubscribed", "channel": "dashboard"}
        {"type": "pong", "timestamp": "..."}
        {"type": "message", "channel": "dashboard", "data": {...}, "timestamp": "..."}
    """
    client = websocket._get_current_object()
    subscribed_channels: Set[str] = set()

    logger.info("websocket_connected", client_id=id(client))

    try:
        while True:
            # Receive message from client
            data = await websocket.receive()

            try:
                message = json.loads(data)
            except json.JSONDecodeError:
                await websocket.send(
                    json.dumps({"type": "error", "message": "Invalid JSON"})
                )
                continue

            msg_type = message.get("type")

            # Handle subscription
            if msg_type == "subscribe":
                channel = message.get("channel")
                if channel in _clients:
                    async with _lock:
                        _clients[channel].add(client)
                        subscribed_channels.add(channel)

                    await websocket.send(
                        json.dumps(
                            {
                                "type": "subscribed",
                                "channel": channel,
                                "timestamp": datetime.utcnow().isoformat(),
                            }
                        )
                    )
                    logger.debug("websocket_subscribed", channel=channel)
                else:
                    await websocket.send(
                        json.dumps(
                            {"type": "error", "message": f"Unknown channel: {channel}"}
                        )
                    )

            # Handle unsubscription
            elif msg_type == "unsubscribe":
                channel = message.get("channel")
                if channel in _clients:
                    async with _lock:
                        _clients[channel].discard(client)
                        subscribed_channels.discard(channel)

                    await websocket.send(
                        json.dumps({"type": "unsubscribed", "channel": channel})
                    )

            # Handle ping
            elif msg_type == "ping":
                await websocket.send(
                    json.dumps(
                        {"type": "pong", "timestamp": datetime.utcnow().isoformat()}
                    )
                )

    except asyncio.CancelledError:
        pass
    except Exception as e:
        logger.error("websocket_error", error=str(e))
    finally:
        # Cleanup: remove from all channels
        async with _lock:
            for channel in subscribed_channels:
                _clients[channel].discard(client)

        logger.info("websocket_disconnected", client_id=id(client))


async def broadcast(channel: str, data: Dict[str, Any]) -> int:
    """
    Broadcast message to all clients subscribed to a channel

    Args:
        channel: Channel name
        data: Data to broadcast

    Returns:
        Number of clients message was sent to
    """
    if channel not in _clients:
        return 0

    message = json.dumps(
        {
            "type": "message",
            "channel": channel,
            "data": data,
            "timestamp": datetime.utcnow().isoformat(),
        }
    )

    dead_clients = set()
    sent_count = 0

    async with _lock:
        for client in _clients[channel]:
            try:
                await client.send(message)
                sent_count += 1
            except Exception:
                dead_clients.add(client)

        # Remove dead clients
        for client in dead_clients:
            _clients[channel].discard(client)

    if dead_clients:
        logger.debug(
            "websocket_dead_clients_removed", channel=channel, count=len(dead_clients)
        )

    return sent_count


async def broadcast_service_status(status: Dict[str, Any]) -> None:
    """Broadcast service status update"""
    await broadcast("dashboard", {"type": "service_status", "services": status})


async def broadcast_sensor_result(result: Dict[str, Any]) -> None:
    """Broadcast sensor check result"""
    await broadcast("sensors", {"type": "sensor_result", "result": result})


async def broadcast_alert(alert: Dict[str, Any]) -> None:
    """Broadcast alert notification"""
    await broadcast("alerts", {"type": "alert", "alert": alert})


def get_connected_clients() -> Dict[str, int]:
    """Get count of connected clients per channel"""
    return {channel: len(clients) for channel, clients in _clients.items()}
