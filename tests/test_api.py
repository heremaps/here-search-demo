###############################################################################
#
# Copyright (c) 2023 HERE Europe B.V.
#
# SPDX-License-Identifier: MIT
# License-Filename: LICENSE
#
###############################################################################

from unittest.mock import patch

import orjson
import pytest

from here_search_demo.api import API
from here_search_demo.auth import Credentials
from here_search_demo.entity.request import Request
from here_search_demo.entity.endpoint import Endpoint


@pytest.fixture
def api(monkeypatch, tmp_path):
    import http.client
    import json
    from unittest.mock import MagicMock

    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.delenv("HERE_ACCESS_KEY_ID", raising=False)
    monkeypatch.delenv("HERE_ACCESS_KEY_SECRET", raising=False)
    monkeypatch.delenv("HERE_TOKEN_ENDPOINT_URL", raising=False)
    monkeypatch.delenv("HERE_API_KEY", raising=False)
    monkeypatch.setenv("API_KEY", "api_key")
    monkeypatch.chdir(tmp_path)
    # Credentials._config() only sets _api_key when it finds a credentials
    # file containing all mandatory fields (url, key id, key secret, api key).
    creds_file = tmp_path / "credentials.properties"
    creds_file.write_text(
        "here.token.endpoint.url=https://account.api.here.com/oauth2/token\n"
        "here.access.key.id=dummy_id\n"
        "here.access.key.secret=dummy_secret\n"
        "here.api.key=api_key\n"
    )
    # Patch HTTPS so token() never makes a real network call.
    mock_conn = MagicMock()
    mock_resp = MagicMock()
    mock_resp.status = 200
    mock_resp.read.return_value = json.dumps({"accessToken": "test_token", "expiresIn": 3600}).encode()
    mock_conn.getresponse.return_value = mock_resp
    monkeypatch.setattr(http.client, "HTTPSConnection", lambda *a, **kw: mock_conn)
    return API(credentials=Credentials())


@pytest.fixture
def session():
    # Configure a response object with the expected interface.
    class _Response:
        def __init__(self, payload):
            self.headers = {
                "X-Request-Id": "userid",
                "X-Correlation-ID": "correlationId",
                "Content-Type": "application/json",
            }
            self._text = orjson.dumps(payload).decode("utf-8")
            self.url = "url"

        async def text(self) -> str:
            return self._text

        async def bytes(self) -> bytes:
            return self._text.encode("utf-8")

        def raise_for_status(self) -> None:
            # Synchronous no-op for tests
            return None

    payload = {"items": []}
    response = _Response(payload)

    class _CM:
        async def __aenter__(self):
            return response

        async def __aexit__(self, exc_type, exc, tb):
            return False

    # Create a simple object with a request() method that returns an async
    # context manager instance; this mimics the aiohttp/HTTPSession API that
    # api.do_send expects.
    class _Session:
        def __init__(self, cm):
            self._cm = cm

        def request(self, *args, **kwargs):  # type: ignore[no-untyped-def]
            return self._cm

    return _Session(_CM())


@pytest.fixture
def a_dummy_request():
    return Request(
        endpoint=Endpoint.AUTOSUGGEST,
        base_url="url",
        params={"p1": "v1", "p2": "v2"},
        data=None,
        x_headers={"X-Request-Id": "userid", "X-Correlation-ID": "correlationId"},
    )


@pytest.mark.asyncio
async def test_get(api, a_dummy_request, session):
    response = await api.send(session, "GET", a_dummy_request)

    assert response.data == {"items": []}
    assert response.req is a_dummy_request
    assert response.x_headers["X-Request-Id"] == "userid"


@pytest.mark.asyncio
async def test_get_uncache(api, a_dummy_request, session):
    # First call populates the cache
    first = await api.send(session, "GET", a_dummy_request)
    # Second call should return a cached Response with the same data
    second = await api.send(session, "GET", a_dummy_request)

    assert second.data == first.data == {"items": []}
    assert second.req is first.req is a_dummy_request


@pytest.mark.asyncio
async def test_send_invokes_on_request_sent_only_for_network_calls(api, a_dummy_request, session):
    seen = []
    api.on_request_sent = lambda request: seen.append(request.endpoint)

    await api.send(session, "GET", a_dummy_request)
    await api.send(session, "GET", a_dummy_request)  # cached

    assert seen == [Endpoint.AUTOSUGGEST]


@pytest.mark.asyncio
async def test_uncache(api, a_dummy_request, session):
    # Populate cache
    _ = await api.send(session, "GET", a_dummy_request)
    # Directly uncache and ensure we still get a Response with same data
    cached = api._API__uncache(a_dummy_request.key)
    assert cached.data == {"items": []}
    assert cached.req == a_dummy_request


def test_build_autosuggest_request(api, autosuggest_request):
    latitude, longitude = map(float, autosuggest_request.params["at"].split(","))
    method, request = api._build_autosuggest_request(
        q=autosuggest_request.params["q"],
        latitude=latitude,
        longitude=longitude,
        x_headers=autosuggest_request.x_headers,
    )
    assert method == "GET"
    assert request == autosuggest_request


def test_build_autosuggest_href_request(api, autosuggest_href_request):
    method, request = api._build_autosuggest_href_request(
        href=autosuggest_href_request.full,
        x_headers=autosuggest_href_request.x_headers,
    )
    assert method == "GET"
    assert request == autosuggest_href_request


def test_build_discover_request(api, discover_request):
    latitude, longitude = map(float, discover_request.params["at"].split(","))
    method, request = api._build_discover_request(
        q=discover_request.params["q"],
        latitude=latitude,
        longitude=longitude,
        x_headers=discover_request.x_headers,
    )
    assert method == "GET"
    assert request == discover_request


def test_build_browse_request(api, browse_request):
    latitude, longitude = map(float, browse_request.params["at"].split(","))
    method, request = api._build_browse_request(
        latitude=latitude,
        longitude=longitude,
        x_headers=browse_request.x_headers,
    )
    assert method == "GET"
    assert request == browse_request


def test_build_browse_request_with_categories(api, browse_categories_request):
    latitude, longitude = map(float, browse_categories_request.params["at"].split(","))
    method, request = api._build_browse_request(
        latitude=latitude,
        longitude=longitude,
        categories=browse_categories_request.params["categories"].split(","),
        x_headers=browse_categories_request.x_headers,
    )
    assert method == "GET"
    assert request == browse_categories_request


def test_build_browse_request_with_foodtypes(api, browse_cuisines_request):
    latitude, longitude = map(float, browse_cuisines_request.params["at"].split(","))
    method, request = api._build_browse_request(
        latitude=latitude,
        longitude=longitude,
        food_types=sorted(browse_cuisines_request.params["foodTypes"].split(",")),
        x_headers=browse_cuisines_request.x_headers,
    )
    assert method == "GET"
    assert request == browse_cuisines_request


def test_build_browse_request_with_chains(api, browse_chains_request):
    latitude, longitude = map(float, browse_chains_request.params["at"].split(","))
    method, request = api._build_browse_request(
        latitude=latitude,
        longitude=longitude,
        chains=browse_chains_request.params["chains"].split(","),
        x_headers=browse_chains_request.x_headers,
    )
    assert method == "GET"
    assert request == browse_chains_request


def test_build_lookup_request(api, lookup_request):
    method, request = api._build_lookup_request(
        id=lookup_request.params["id"],
        x_headers=lookup_request.x_headers,
    )
    assert method == "GET"
    assert request == lookup_request


def test_build_reverse_geocode_request(api, revgeocode_request):
    latitude, longitude = map(float, revgeocode_request.params["at"].split(","))
    method, request = api._build_reverse_geocode_request(
        latitude=latitude,
        longitude=longitude,
        x_headers=revgeocode_request.x_headers,
    )
    assert method == "GET"
    assert request == revgeocode_request


def test_autosuggest_href_applies_options(monkeypatch, tmp_path):
    """Options configured for AUTOSUGGEST_HREF (e.g. tripadvisor) are included
    in the follow-up request triggered by chainQuery/categoryQuery selection."""
    from here_search_demo.api_options import build_api_options, default_options_config, tripadvisorDetails

    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.delenv("HERE_ACCESS_KEY_ID", raising=False)
    monkeypatch.delenv("HERE_ACCESS_KEY_SECRET", raising=False)
    monkeypatch.delenv("HERE_TOKEN_ENDPOINT_URL", raising=False)
    monkeypatch.delenv("HERE_API_KEY", raising=False)
    monkeypatch.setenv("API_KEY", "api_key")
    monkeypatch.chdir(tmp_path)

    options = build_api_options(default_options_config, extra_options=[tripadvisorDetails])
    ta_api = API(credentials=Credentials(), options=options)

    # Realistic href as returned by the autosuggest API: no "show" param.
    href = "https://discover.search.hereapi.com/v1/discover?q=Starbucks&at=52.52%2C13.37&limit=20"

    _, request = ta_api._build_autosuggest_href_request(href=href)
    show_values = set(request.params["show"].split(","))
    assert "tripadvisor" in show_values, f"tripadvisor missing from show: {show_values}"
    assert "tripadvisorImageVariants" in show_values, f"tripadvisorImageVariants missing: {show_values}"


@pytest.mark.asyncio
async def test_send_uses_credentials_api_key(api, monkeypatch, a_dummy_request, session):
    """send() injects the credential-derived api_key into params."""
    monkeypatch.setenv("API_KEY", "creds_api_key")
    response = await api.send(session, "GET", a_dummy_request)
    assert response.data == {"items": []}


def test_build_display_urls_simple(api):
    """Test _build_display_urls with simple params."""
    request = Request(
        endpoint=Endpoint.DISCOVER,
        base_url="https://discover.search.hereapi.com/v1/discover",
        params={"q": "coffee", "at": "52.5,13.4"},
        data=None,
        x_headers=None,
    )
    log_url, browser_url = api._build_display_urls(request)
    assert log_url == "/discover?q=coffee&at=52.5,13.4"
    assert "q=coffee" in browser_url
    assert "at=52.5" in browser_url
    assert "apiKey=api_key" in browser_url


def test_build_display_urls_with_route(api):
    """Test _build_display_urls with route parameter."""
    request = Request(
        endpoint=Endpoint.AUTOSUGGEST,
        base_url="https://autosuggest.search.hereapi.com/v1/autosuggest",
        params={"q": "gas", "route": "52.5,13.4;52.6,13.5"},
        data=None,
        x_headers=None,
    )
    log_url, browser_url = api._build_display_urls(request)
    assert "route=..." in log_url
    assert "route=" in browser_url


def test_build_display_urls_with_fuel_prices(api):
    """Test _build_display_urls strips fuelPrices from show parameter."""
    request = Request(
        endpoint=Endpoint.BROWSE,
        base_url="https://browse.search.hereapi.com/v1/browse",
        params={"at": "52.5,13.4", "show": "fuelPrices,phonemes"},
        data=None,
        x_headers=None,
    )
    log_url, browser_url = api._build_display_urls(request)
    assert "show=phonemes" in log_url
    assert "fuelPrices" not in log_url


def test_build_display_urls_fuel_prices_only(api):
    """Test _build_display_urls when show only has fuelPrices."""
    request = Request(
        endpoint=Endpoint.BROWSE,
        base_url="https://browse.search.hereapi.com/v1/browse",
        params={"at": "52.5,13.4", "show": "fuelPrices"},
        data=None,
        x_headers=None,
    )
    log_url, browser_url = api._build_display_urls(request)
    assert "show" not in log_url


def test_do_log_with_log_fn():
    """Test do_log calls the log function when configured."""
    logged_calls = []

    def mock_log_fn(url, extra):
        logged_calls.append((url, extra))

    api_with_log = API(credentials=Credentials(), log_fn=mock_log_fn)
    request = Request(
        endpoint=Endpoint.AUTOSUGGEST,
        base_url="https://autosuggest.search.hereapi.com/v1/autosuggest",
        params={"q": "test"},
        data=None,
        x_headers=None,
    )
    api_with_log.do_log(request, extra_columns=["extra"])
    assert len(logged_calls) == 1
    assert "test" in logged_calls[0][0]
    assert logged_calls[0][1] == ["extra"]


def test_build_autosuggest_request_with_route(session):
    """Test _build_autosuggest_request with route parameter produces POST."""
    from here_search_demo.api_options import build_api_options, default_options_config

    api_with_opts = API(credentials=Credentials(), options=build_api_options(default_options_config))
    route = "52.5,13.4;52.6,13.5;52.7,13.6"

    method, request = api_with_opts._build_autosuggest_request(q="gas", latitude=52.5, longitude=13.4, polyline=route)
    assert method == "POST"
    assert request.data == f"route={route}"
    assert "Content-Type" in request.x_headers


def test_build_autosuggest_request_with_route_and_all_along():
    """Test _build_autosuggest_request with route and all_along parameters."""
    api = API(credentials=Credentials())
    route = "52.5,13.4;52.6,13.5"

    method, request = api._build_autosuggest_request(
        q="gas", latitude=52.5, longitude=13.4, polyline=route, all_along=True
    )
    assert method == "POST"
    assert request.params["ranking"] == "excursionDistance"


def test_build_autosuggest_href_request_with_route():
    """Test _build_autosuggest_href_request with route parameter."""
    api = API(credentials=Credentials())
    href = "https://discover.search.hereapi.com/v1/discover?q=Starbucks&at=52.52,13.37"
    route = "52.5,13.4;52.6,13.5"

    method, request = api._build_autosuggest_href_request(href=href, polyline=route)
    assert method == "POST"
    assert request.data == f"route={route}"


def test_build_autosuggest_href_request_with_route_and_all_along():
    """Test _build_autosuggest_href_request with route and all_along parameters."""
    api = API(credentials=Credentials())
    href = "https://discover.search.hereapi.com/v1/discover?q=Starbucks&at=52.52,13.37"
    route = "52.5,13.4;52.6,13.5"

    method, request = api._build_autosuggest_href_request(href=href, polyline=route, all_along=True)
    assert method == "POST"
    assert request.params["ranking"] == "excursionDistance"


def test_build_discover_request_with_route():
    """Test _build_discover_request with route parameter."""
    api = API(credentials=Credentials())
    route = "52.5,13.4;52.6,13.5"

    method, request = api._build_discover_request(q="coffee", latitude=52.5, longitude=13.4, polyline=route)
    assert method == "POST"
    assert request.data == f"route={route}"


def test_build_discover_request_with_route_and_all_along():
    """Test _build_discover_request with route and all_along parameters."""
    api = API(credentials=Credentials())
    route = "52.5,13.4;52.6,13.5"

    method, request = api._build_discover_request(
        q="coffee", latitude=52.5, longitude=13.4, polyline=route, all_along=True
    )
    assert method == "POST"
    assert request.params["ranking"] == "excursionDistance"


def test_build_discover_request_route_encodes_width():
    """The corridor width must be appended to the route body as ``;w=<width>``."""
    api = API(credentials=Credentials())
    route = "52.5,13.4;52.6,13.5"

    _, request = api._build_discover_request(q="coffee", latitude=52.5, longitude=13.4, polyline=route, width=250)
    assert request.data == f"route={route};w=250"


def test_build_autosuggest_request_route_encodes_width():
    api = API(credentials=Credentials())
    route = "52.5,13.4;52.6,13.5"

    _, request = api._build_autosuggest_request(q="gas", latitude=52.5, longitude=13.4, polyline=route, width=75)
    assert request.data == f"route={route};w=75"


def test_build_discover_request_route_without_width_has_no_suffix():
    """When width is None the route body must not contain a ``;w=`` suffix."""
    api = API(credentials=Credentials())
    route = "52.5,13.4;52.6,13.5"

    _, request = api._build_discover_request(q="coffee", latitude=52.5, longitude=13.4, polyline=route, width=None)
    assert request.data == f"route={route}"


@pytest.mark.asyncio
async def test_send_width_change_bypasses_cache(api, session):
    """Regression: changing the corridor width must issue a fresh network call.

    The width is carried in the POST body (``route=...;w=<width>``), not in the
    query params, so the request cache key must incorporate ``data``. Otherwise
    a width change returns the stale response cached for the previous width.
    """
    sent_keys = []
    api.on_request_sent = lambda req: sent_keys.append(req.key)
    route = "52.5,13.4;52.6,13.5"

    _, narrow = api._build_discover_request(q="coffee", latitude=52.5, longitude=13.4, polyline=route, width=100)
    _, wide = api._build_discover_request(q="coffee", latitude=52.5, longitude=13.4, polyline=route, width=500)

    assert narrow.key != wide.key

    await api.send(session, "POST", narrow)
    await api.send(session, "POST", wide)
    await api.send(session, "POST", narrow)  # served from cache — no new call

    assert len(sent_keys) == 2
    assert sent_keys == [narrow.key, wide.key]


def test_build_browse_request_with_route():
    """Test _build_browse_request with route parameter."""
    api = API(credentials=Credentials())
    route = "52.5,13.4;52.6,13.5"

    method, request = api._build_browse_request(latitude=52.5, longitude=13.4, polyline=route)
    assert method == "POST"
    assert request.data == f"route={route}"


def test_build_browse_request_with_route_and_all_along():
    """Test _build_browse_request with route and all_along parameters."""
    api = API(credentials=Credentials())
    route = "52.5,13.4;52.6,13.5"

    method, request = api._build_browse_request(latitude=52.5, longitude=13.4, polyline=route, all_along=True)
    assert method == "POST"
    assert request.params["ranking"] == "excursionDistance"


@pytest.mark.asyncio
async def test_signals_success(api, session):
    """Test signals endpoint successfully sends signal."""
    with patch.object(api, "do_send") as mock_do_send:
        mock_do_send.return_value = ("url", {}, "OK", {"X-Request-Id": "test-id"})

        response = await api.signals(
            session=session,
            resource_id="test-resource-id",
            correlation_id="test-corr-id",
            rank=1,
            action="here:gs:action:view",
        )

    assert response is not None
    assert response.data == {"text": "OK"}
    assert mock_do_send.call_count == 1


@pytest.mark.asyncio
async def test_signals_with_x_headers(api, session):
    """Test signals with custom x_headers."""
    with patch.object(api, "do_send") as mock_do_send:
        mock_do_send.return_value = ("url", {}, "OK", {"X-Request-Id": "test-id"})

        response = await api.signals(
            session=session,
            resource_id="test-resource-id",
            correlation_id="test-corr-id",
            rank=1,
            action="here:gs:action:view",
            x_headers={"X-User-ID": "user-123"},
        )

    assert response is not None
    call_args = mock_do_send.call_args
    headers = call_args[0][5]
    assert "X-User-ID" in headers
    assert headers["X-User-ID"] == "user-123"


@pytest.mark.asyncio
async def test_signals_with_kwargs(api, session):
    """Test signals with extra kwargs."""
    with patch.object(api, "do_send") as mock_do_send:
        mock_do_send.return_value = ("url", {}, "OK", {})

        await api.signals(
            session=session,
            resource_id="test-resource-id",
            correlation_id="test-corr-id",
            rank=1,
            action="here:gs:action:view",
            userId="user-123",
            asSessionId="session-456",
        )

    call_args = mock_do_send.call_args
    body = call_args[0][4]
    assert "userId=user-123" in body
    assert "asSessionId=session-456" in body


@pytest.mark.asyncio
async def test_signals_failure(api, session):
    """Test signals returns None on exception."""
    with patch.object(api, "do_send") as mock_do_send:
        mock_do_send.side_effect = Exception("Network error")

        response = await api.signals(
            session=session,
            resource_id="test-resource-id",
            correlation_id="test-corr-id",
            rank=1,
            action="here:gs:action:view",
        )

    assert response is None
