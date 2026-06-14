"""WebSocket server for real-time dashboard events.

Dashboard (React) connects to ws://localhost:3001 and receives events:
- donna_activated: wake word triggered
- user_speech: user said something (includes transcript)
- donna_speech: donna responded (includes text)
- tool_call: donna called a tool (includes name + result)
- case_created: new case file created
- calendar_booked: new event scheduled
"""

import asyncio
import json
from typing import Set

import websockets
from websockets.server import WebSocketServerProtocol

connected: Set[WebSocketServerProtocol] = set()


async def broadcast(event: dict):
    """Send event to all connected dashboard clients."""
    if not connected:
        return
    message = json.dumps(event)
    await asyncio.gather(
        *[ws.send(message) for ws in connected],
        return_exceptions=True,
    )


async def handler(websocket: WebSocketServerProtocol):
    connected.add(websocket)
    try:
        await websocket.wait_closed()
    finally:
        connected.discard(websocket)


async def start_server(host: str = "localhost", port: int = 3001):
    print(f"Dashboard WebSocket server on ws://{host}:{port}")
    async with websockets.serve(handler, host, port):
        await asyncio.Future()


if __name__ == "__main__":
    asyncio.run(start_server())
