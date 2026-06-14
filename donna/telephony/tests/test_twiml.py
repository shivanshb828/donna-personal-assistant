from donna.telephony.twiml import build_hangup_twiml, build_stream_twiml


def test_build_stream_twiml_contains_stream_url():
    twiml = build_stream_twiml(
        media_stream_ws_url="wss://example.ngrok.app/media-stream",
        call_sid="CA123",
        stream_token="tok",
    )
    assert "wss://example.ngrok.app/media-stream" in twiml
    assert "CA123" in twiml
    assert "tok" in twiml


def test_build_hangup_twiml_escapes_message():
    twiml = build_hangup_twiml("Sorry & goodbye")
    assert "&amp;" in twiml
    assert "<Hangup/>" in twiml
