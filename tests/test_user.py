###############################################################################
#
# Copyright (c) 2025 HERE Europe B.V.
#
# SPDX-License-Identifier: MIT
# License-Filename: LICENSE
#
###############################################################################


import pytest
from unittest.mock import AsyncMock, patch

from here_search.demo.user import UserProfile, DefaultUser


def test_userprofile_init_defaults():
    user = UserProfile(use_positioning=True, share_experience=False)
    assert user.name == UserProfile.default_name
    assert user.use_positioning is True
    assert user.share_experience is False
    assert user.current_latitude == UserProfile.default_current_position[0]
    assert user.current_longitude == UserProfile.default_current_position[1]
    assert user.current_position_country == UserProfile.default_country_code


def test_userprofile_custom_init():
    langs = {"DEU": "de", "default": "en"}
    pos = (52.5, 13.4)
    user = UserProfile(
        use_positioning=False, share_experience=True, start_position=pos, preferred_languages=langs, name="tester"
    )
    assert user.name == "tester"
    assert user.preferred_languages == langs
    assert user.current_latitude == pos[0]
    assert user.current_longitude == pos[1]


def test_get_preferred_country_language():
    langs = {"DEU": "de", "default": "en"}
    user = UserProfile(use_positioning=True, share_experience=True, preferred_languages=langs)
    assert user.get_preferred_country_language("DEU") == "de"
    assert user.get_preferred_country_language("FRA") == "en"


def test_get_current_language():
    langs = {"DEU": "de", "default": "en"}
    user = UserProfile(use_positioning=True, share_experience=True, preferred_languages=langs)
    user.current_position_country = "DEU"
    assert user.get_current_language() == "de"
    user.current_position_country = "FRA"
    assert user.get_current_language() == "en"
    user.preferred_languages = {}
    assert user.get_current_language() == UserProfile.default_language


@pytest.mark.asyncio
async def test_set_position_and_get_preferred_locale():
    mock_api = AsyncMock()
    mock_api.reverse_geocode.return_value.data = {"items": [{"address": {"countryCode": "DEU"}, "id": "123"}]}
    mock_api.lookup.return_value.data = {"language": "de"}

    user = UserProfile(use_positioning=True, share_experience=True, api=mock_api)

    class AsyncSessionMock:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            pass

    with patch("here_search.demo.user.HTTPSession", AsyncSessionMock):
        await user.set_position(52.5, 13.4)
        assert user.current_latitude == 52.5
        assert user.current_longitude == 13.4
        assert user.current_position_country == "DEU"
        assert user.preferred_language == "de"


def test_userprofile_repr():
    user = UserProfile(use_positioning=True, share_experience=True)
    r = repr(user)
    assert "UserProfile" in r
    assert "opt_in=True/True" in r


def test_defaultuser_inherits_userprofile():
    user = DefaultUser()
    assert isinstance(user, UserProfile)
    assert user.use_positioning is True
    assert user.share_experience is True
