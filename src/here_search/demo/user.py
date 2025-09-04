###############################################################################
#
# Copyright (c) 2023 HERE Europe B.V.
#
# SPDX-License-Identifier: MIT
# License-Filename: LICENSE
#
###############################################################################

import uuid
from typing import Tuple

from here_search.demo.api import API
from here_search.demo.api_options import APIOptions
from here_search.demo.http import HTTPSession


class UserProfile:
    preferred_languages: dict
    current_latitude: float
    current_longitude: float
    current_position_country: str

    default_name = "default"
    from .entity.constants import berlin

    default_current_position = berlin
    default_country_code = "DEU"
    default_language = "en"
    default_profile_languages = {default_name: default_language}

    def __init__(
        self,
        use_positioning: bool,
        share_experience: bool,
        api: API = None,
        start_position: Tuple[float, float] = None,
        api_options: APIOptions = None,
        preferred_languages: dict = None,
        name: str = None,
    ):
        """
        :param use_position: Mandatory opt-in/out about position usage
        :param share_experience: Mandatory opt-in/out about activity usage (UNUSED)
        :param api: Optional API instance
        :param start_position: Optional start lat/lon float tuple
        :param api_options: User level API options to be considered in each API call
        :param preferred_languages: Optional user language preferences
        :param name: Optional user name
        """
        self.name = name or UserProfile.default_name
        self.id = str(uuid.uuid5(uuid.NAMESPACE_DNS, f"{self.name}{uuid.getnode()}"))
        self.api = api or API()

        self.__use_positioning = use_positioning
        self.__share_experience = share_experience

        self.preferred_languages = preferred_languages or {}
        self.has_country_preferences = not (
            self.preferred_languages == {} or list(self.preferred_languages.keys()) == [UserProfile.default_name]
        )
        self.api_options = api_options or {}

        self.preferred_language = UserProfile.default_profile_languages[UserProfile.default_name]
        self.current_latitude, self.current_longitude = start_position or UserProfile.default_current_position
        self.current_position_country = UserProfile.default_country_code

    @property
    def use_positioning(self):
        return self.__use_positioning

    @property
    def share_experience(self):
        return self.__share_experience

    def send_signal(self, body: list):
        pass

    async def set_position(self, latitude, longitude) -> "UserProfile":
        self.current_latitude = latitude
        self.current_longitude = longitude
        self.current_position_country, self.preferred_language = await self.get_preferred_locale(latitude, longitude)
        return self

    def get_preferred_country_language(self, country_code: str):
        return self.preferred_languages.get(
            country_code,
            self.preferred_languages.get(self.__class__.default_name, None),
        )

    async def get_preferred_locale(self, latitude: float, longitude: float) -> Tuple[str, str]:
        country_code, language = None, None
        async with HTTPSession(raise_for_status=True) as session:
            local_addresses = await self.api.reverse_geocode(latitude=latitude, longitude=longitude, session=session)

            if local_addresses and "items" in local_addresses.data and len(local_addresses.data["items"]) > 0:
                country_code = local_addresses.data["items"][0]["address"]["countryCode"]
                address_details = await self.api.lookup(id=local_addresses.data["items"][0]["id"], session=session)
                language = address_details.data["language"]

            return country_code, language

    def get_current_language(self):
        if self.current_position_country in self.preferred_languages:
            return self.preferred_languages[self.current_position_country]
        elif not self.preferred_languages:
            return UserProfile.default_language
        else:
            return self.preferred_languages[UserProfile.default_name]

    def __repr__(self):
        languages = self.preferred_languages or self.preferred_language
        return f"{self.__class__.__name__}(name={self.name}, id={self.id}, lang={languages}, opt_in={self.__use_positioning}/{self.__share_experience})"


class DefaultUser(UserProfile):
    def __init__(self, **kwargs):
        UserProfile.__init__(self, use_positioning=True, share_experience=True, **kwargs)
