###############################################################################
#
# Copyright (c) 2023 HERE Europe B.V.
#
# SPDX-License-Identifier: MIT
# License-Filename: LICENSE
#
###############################################################################

import logging

import pytest

import here_search_demo.util as util_module
from here_search_demo.util import (
    berlin,
    get_lat_lon,
    log_signature,
    set_dict_values,
    setLevel,
)


def test_log_signature_sync_logs_entry_and_return(capsys):
    @log_signature
    def add(a, b):
        return a + b

    assert add(2, 3) == 5
    out = capsys.readouterr().out
    assert "Entering" in out
    assert "(a=2, b=3)" in out
    assert "-> 5" in out


def test_log_signature_sync_logs_and_reraises_exception(capsys):
    @log_signature
    def boom():
        raise ValueError("nope")

    with pytest.raises(ValueError, match="nope"):
        boom()
    out = capsys.readouterr().out
    assert "Entering" in out
    assert "Exception in" in out
    assert "boom" in out


@pytest.mark.asyncio
async def test_log_signature_async_logs_entry_and_return(capsys):
    @log_signature
    async def aadd(a, b):
        return a + b

    assert await aadd(1, 2) == 3
    out = capsys.readouterr().out
    assert "Entering" in out
    assert "(a=1, b=2)" in out
    assert "-> 3" in out


@pytest.mark.asyncio
async def test_log_signature_async_logs_and_reraises_exception(capsys):
    @log_signature
    async def aboom():
        raise KeyError("bad")

    with pytest.raises(KeyError):
        await aboom()
    out = capsys.readouterr().out
    assert "Exception in" in out
    assert "aboom" in out


def test_set_dict_values():
    assert set_dict_values({"a": 1, "b": {"c": None, "d": {"e": True}}}, [["a"], ["b", "d"]], [2, False]) == {
        "a": 2,
        "b": {"c": None, "d": False},
    }


def test_set_dict_values1():
    assert set_dict_values({}, [["a"]], [1, 2]) == {"a": 1}


def test_set_dict_values2():
    assert set_dict_values({}, [["a", "b"]], [1, 2]) == {"a": {"b": 1}}


def test_set_dict_values3():
    assert set_dict_values({}, [["a"], ["b"]], [1]) == {"a": 1}


def test_set_dict_values4():
    with pytest.raises(TypeError):
        set_dict_values({}, [["a"], ["a", "b"]], [1, None])


def test_set_dict_values5():
    assert set_dict_values({}, [["a"], ["a", "b"]], [{"c": None}, 2]) == {"a": {"c": None, "b": 2}}


def test_set_level_configures_loggers():
    setLevel(logging.DEBUG)
    assert logging.getLogger("here_search_demo").level == logging.DEBUG
    assert logging.getLogger("aiohttp.client").level == logging.DEBUG


class _DummyResponse:
    async def json(self):
        return {"latitude": "51.5", "longitude": "-0.1"}


class _DummyResponseCM:
    async def __aenter__(self):
        return _DummyResponse()

    async def __aexit__(self, *args):
        pass


class _DummySession:
    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        pass

    def get(self, url):
        return _DummyResponseCM()


@pytest.mark.asyncio
async def test_get_lat_lon_returns_geojs_coordinates(monkeypatch):
    monkeypatch.setattr(util_module, "HTTPSession", _DummySession)
    lat, lon = await get_lat_lon()
    assert isinstance(lat, float)
    assert lat == 51.5
    assert lon == -0.1


class _FailingSession:
    async def __aenter__(self):
        raise util_module.HTTPConnectionError()

    async def __aexit__(self, *args):
        pass


@pytest.mark.asyncio
async def test_get_lat_lon_falls_back_to_berlin(monkeypatch, caplog):
    class _SimpleHTTPConnectionError(Exception):
        pass

    monkeypatch.setattr(util_module, "HTTPSession", _FailingSession)
    monkeypatch.setattr(util_module, "HTTPConnectionError", _SimpleHTTPConnectionError)
    caplog.set_level(logging.WARNING)
    result = await get_lat_lon()
    assert result == berlin
    assert any("Error connecting" in record.message for record in caplog.records)
