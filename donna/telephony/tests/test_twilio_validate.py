from donna.telephony.twilio_validate import validate_twilio_signature


def test_validate_twilio_signature_known_vector():
    # Twilio docs example shape — validates HMAC wiring, not a live request.
    params = {"CallSid": "CA123", "From": "+14085550101"}
    url = "https://example.com/voice"
    token = "test_auth_token"
    import base64
    import hashlib
    import hmac

    data = url + "CallSidCA123" + "From+14085550101"
    sig = base64.b64encode(hmac.new(token.encode(), data.encode(), hashlib.sha1).digest()).decode()
    assert validate_twilio_signature(auth_token=token, url=url, form_data=params, signature=sig)
