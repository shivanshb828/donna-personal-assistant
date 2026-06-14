from __future__ import annotations


def _xml_attr(value: str) -> str:
    return (
        value.replace("&", "&amp;")
        .replace('"', "&quot;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )


def _xml_text(value: str) -> str:
    return value.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def build_stream_twiml(*, media_stream_ws_url: str, call_sid: str, stream_token: str) -> str:
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
  <Connect>
    <Stream url="{_xml_attr(media_stream_ws_url)}">
      <Parameter name="callSid" value="{_xml_attr(call_sid)}" />
      <Parameter name="streamToken" value="{_xml_attr(stream_token)}" />
    </Stream>
  </Connect>
</Response>"""


def build_hangup_twiml(message: str | None = None) -> str:
    say = f"<Say>{_xml_text(message)}</Say>" if message else ""
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
  {say}
  <Hangup/>
</Response>"""
