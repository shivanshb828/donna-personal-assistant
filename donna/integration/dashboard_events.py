"""WebSocket relay hub for real-time dashboard events.

Accepts two kinds of connections on the same port:
- Backend pushers (telephony server, voice pipeline): connect, send one event, disconnect.
- Dashboard clients (React app): connect, receive a stream of events, stay connected.

Any message received from any connection is relayed to ALL currently connected clients.
Because the React app never sends messages it only receives; because backend pushers
disconnect immediately after sending they are gone before any echo could reach them.
"""

import asyncio
import json
import logging
from typing import Set

import websockets
from websockets.server import WebSocketServerProtocol

log = logging.getLogger(__name__)
connected: Set[WebSocketServerProtocol] = set()


async def broadcast(event: dict) -> None:
    """Send event to all connected dashboard clients."""
    if not connected:
        return
    message = json.dumps(event)
    await asyncio.gather(
        *[ws.send(message) for ws in list(connected)],
        return_exceptions=True,
    )


async def handler(websocket: WebSocketServerProtocol) -> None:
    connected.add(websocket)
    try:
        async for raw in websocket:
            # Relay every incoming message to all connected clients (including self).
            await asyncio.gather(
                *[ws.send(raw) for ws in list(connected)],
                return_exceptions=True,
            )
    except websockets.exceptions.ConnectionClosed:
        pass
    finally:
        connected.discard(websocket)


async def start_server(host: str = "localhost", port: int = 3001) -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s — %(message)s")
    log.info("Dashboard WS relay on ws://%s:%d — waiting for connections", host, port)
    async with websockets.serve(handler, host, port):
        await asyncio.Future()


if __name__ == "__main__":
    asyncio.run(start_server())
