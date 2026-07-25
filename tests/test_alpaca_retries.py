import requests

from aml.alpaca_rest import AlpacaREST
from aml.settings import Settings


class Response:
    status_code = 200
    headers = {}
    text = ""

    def json(self):
        return {"ok": True}


def test_transient_network_failure_retries_then_succeeds(monkeypatch):
    calls = []

    def request(*args, **kwargs):
        calls.append(1)
        if len(calls) == 1:
            raise requests.ConnectionError("temporary DNS failure")
        return Response()

    monkeypatch.setattr("requests.get", request)
    client = AlpacaREST(
        Settings("key", "secret"), max_retries=2, retry_backoff_seconds=0
    )
    assert client._get("https://example.test") == {"ok": True}
    assert len(calls) == 2


def test_exhausted_network_failure_records_retry_count(monkeypatch):
    monkeypatch.setattr(
        "requests.get",
        lambda *args, **kwargs: (_ for _ in ()).throw(requests.ConnectionError("down")),
    )
    client = AlpacaREST(
        Settings("key", "secret"), max_retries=2, retry_backoff_seconds=0
    )
    try:
        client._get("https://example.test")
    except RuntimeError as exc:
        assert "after 3 attempts" in str(exc)
        assert exc.retry_count == 2
    else:  # pragma: no cover
        raise AssertionError("Expected retry exhaustion")
