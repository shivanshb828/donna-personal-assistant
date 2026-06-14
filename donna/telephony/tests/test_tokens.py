from donna.telephony.tokens import StreamTokenStore


def test_stream_token_issue_and_consume():
    store = StreamTokenStore(ttl_seconds=30)
    token = store.issue("CA123")
    assert store.consume("CA123", token)
    assert not store.consume("CA123", token)


def test_stream_token_rejects_wrong_call_sid():
    store = StreamTokenStore()
    token = store.issue("CA123")
    assert not store.consume("CA999", token)
