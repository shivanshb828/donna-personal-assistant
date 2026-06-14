"""
Donna email approval server.

Tiny HTTP server (aiohttp) that M1's dashboard POSTs to when the lawyer
approves or rejects an outbound email draft.

Endpoints:
  POST /email/approve/{draft_id}?case_id={case_id}
  POST /email/reject/{draft_id}?case_id={case_id}   body: {"reason": "..."}
  GET  /email/drafts/{case_id}

Run alongside the main email server:
  python -m donna.email_server.approval_server
"""

import asyncio
import json
import logging
from aiohttp import web

from . import config
from .sender import approve_and_send, reject_draft, list_drafts

log = logging.getLogger(__name__)


async def handle_approve(request: web.Request) -> web.Response:
    draft_id = request.match_info["draft_id"]
    case_id = request.rel_url.query.get("case_id", "")
    if not case_id:
        return web.json_response({"error": "case_id required"}, status=400)

    result = await approve_and_send(draft_id, case_id)
    status = 200 if result["status"] == "sent" else 422
    return web.json_response(result, status=status)


async def handle_reject(request: web.Request) -> web.Response:
    draft_id = request.match_info["draft_id"]
    case_id = request.rel_url.query.get("case_id", "")
    if not case_id:
        return web.json_response({"error": "case_id required"}, status=400)

    body = {}
    try:
        body = await request.json()
    except Exception:
        pass

    result = await reject_draft(draft_id, case_id, reason=body.get("reason", ""))
    return web.json_response(result)


async def handle_list_drafts(request: web.Request) -> web.Response:
    case_id = request.match_info["case_id"]
    drafts = list_drafts(case_id)
    return web.json_response({"drafts": drafts})


def build_app() -> web.Application:
    app = web.Application()
    app.router.add_post("/email/approve/{draft_id}", handle_approve)
    app.router.add_post("/email/reject/{draft_id}", handle_reject)
    app.router.add_get("/email/drafts/{case_id}", handle_list_drafts)
    return app


def run():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s — %(message)s",
    )
    app = build_app()
    log.info(
        "Donna approval server on %s:%s",
        config.APPROVAL_HOST,
        config.APPROVAL_PORT,
    )
    web.run_app(app, host=config.APPROVAL_HOST, port=config.APPROVAL_PORT, print=None)


if __name__ == "__main__":
    run()
