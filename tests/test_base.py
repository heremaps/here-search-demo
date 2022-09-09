import pytest

from unittest.mock import Mock, patch
from unittest.mock import AsyncMock, patch
from asyncio import Future
from uuid import uuid1
from here_search.base import OneBoxSimple
from here_search.api import API


@pytest.mark.asyncio
@pytest.mark.parametrize("query_text", ["r", "re", "res"])
async def test_wait_for_text_extension(app, query_text):
    future = Future()
    future.set_result(query_text)
    with patch.object(OneBoxSimple, "wait_for_text_extension", return_value=future):
        query_text2 = await app.wait_for_text_extension()
    assert query_text == query_text2


@pytest.mark.asyncio
@pytest.mark.parametrize("query_text", ["r", "re", "res"])
async def test_wait_handle_key_stroke_with_text(app, autosuggest_request, query_text):

    future = Future()
    future.set_result(query_text)
    autosuggest_request.params["q"] = query_text
    mock_session = Mock()
    response = f"{uuid1()}"

    latitude, longitude = map(float, autosuggest_request.params["at"].split(","))
    app.search_center = latitude, longitude

    with patch.object(OneBoxSimple, "wait_for_text_extension", return_value=future), \
         patch.object(API, "autosuggest", return_value=response) as autosuggest, \
         patch.object(OneBoxSimple, "handle_suggestion_list") as hsl, \
         patch.object(OneBoxSimple, "handle_empty_text_submission") as het:
        await app.handle_key_stroke(mock_session)

    autosuggest.assert_called_once()
    assert autosuggest.call_args.args[:3] == (autosuggest_request.params["q"], latitude, longitude)
    hsl.assert_called_once_with(response)
    het.assert_not_called()


@pytest.mark.asyncio
async def test_wait_handle_key_stroke_without_text(app):
    query_text = ""
    future = Future()
    future.set_result(query_text)
    mock_session = Mock()
    with patch.object(OneBoxSimple, "wait_for_text_extension", return_value=future), \
            patch.object(API, "autosuggest") as autosuggest, \
            patch.object(OneBoxSimple, "handle_suggestion_list") as hsl, \
            patch.object(OneBoxSimple, "handle_empty_text_submission") as het:
        await app.handle_key_stroke(mock_session)
    autosuggest.assert_not_called()
    hsl.assert_not_called()
    het.assert_called_once()
