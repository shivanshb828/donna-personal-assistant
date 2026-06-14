from __future__ import annotations

import asyncio
import json
import time

import websockets


async def broadcast_event(dashboard_ws: str, event: dict) -> None:
    event.setdefault("ts", int(time.time()))
    try:
        async with websockets.connect(dashboard_ws, open_timeout=1) as ws:
            await ws.send(json.dumps(event))
    except Exception:
        pass


def broadcast_event_sync(dashboard_ws: str, event: dict) -> None:
    try:
        asyncio.run(broadcast_event(dashboard_ws, event))
    except RuntimeError:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            loop.create_task(broadcast_event(dashboard_ws, event))
        else:
            loop.run_until_complete(broadcast_event(dashboard_ws, event))
