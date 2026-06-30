"""Shared pytest fixtures for the yfinance provider tests."""

import pytest


@pytest.fixture
def reset_yfinance_session():
    """Clear yfinance's shared crumb/cookie singleton before a test runs.

    yfinance caches the auth crumb on a process-wide ``YfData`` singleton. A
    cassette-backed test that records its own handshake needs that singleton
    empty, otherwise a crumb left cached by an earlier test makes it skip the
    recorded handshake and send a request the cassette can't match.
    """
    from yfinance.data import YfData

    data = YfData(session=None)
    data._crumb = None
    data._cookie = None
    data._cookie_strategy = "basic"
    yield
