from __future__ import annotations

import base64
import hashlib
import hmac
from urllib.parse import parse_qsl, urljoin


def validate_twilio_signature(
    *,
    auth_token: str,
    url: str,
    form_data: dict[str, str],
    signature: str | None,
) -> bool:
    if not auth_token or not signature:
        return False
    data = url
    for key in sorted(form_data.keys()):
        data += key + form_data[key]
    digest = hmac.new(auth_token.encode("utf-8"), data.encode("utf-8"), hashlib.sha1).digest()
    expected = base64.b64encode(digest).decode("utf-8")
    return hmac.compare_digest(expected, signature)


async def read_twilio_form(request) -> dict[str, str]:
    body = await request.body()
    return {key: value for key, value in parse_qsl(body.decode("utf-8"), keep_blank_values=True)}


def request_url(request, public_url: str, path: str) -> str:
    forwarded_proto = request.headers.get("x-forwarded-proto")
    if forwarded_proto and public_url.startswith("http://localhost"):
        return urljoin(f"{forwarded_proto}://{request.headers.get('host', '')}", path)
    return urljoin(public_url.rstrip("/") + "/", path.lstrip("/"))
