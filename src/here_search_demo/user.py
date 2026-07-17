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

from here_search_demo.api import API
from here_search_demo.api_options import APIOptions
from here_search_demo.http import HTTPSession


class UserProfile:
    """User preferences and runtime context for one-box interactions.

    The profile stores consent flags, language preferences and the latest
    known user position. It can resolve locale information from coordinates
    through reverse geocoding and lookup calls.

    :ivar str name: Human-readable profile name.
    :ivar str id: Stable profile identifier derived from name and host node.
    :ivar API api: API adapter used for locale lookup operations.
    :ivar dict preferred_languages: Mapping of country code (or ``None``) to language.
    :ivar bool has_country_preferences: Whether country-specific preferences exist.
    :ivar APIOptions api_options: Extra API options associated with this profile.
    :ivar str preferred_language: Default language fallback for the profile.
    :ivar float current_latitude: Latest latitude associated with the profile.
    :ivar float current_longitude: Latest longitude associated with the profile.
    :ivar str current_position_country: Latest resolved country code.
    """

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
        api: API | None = None,
        start_position: Tuple[float, float] | None = None,
        api_options: APIOptions | None = None,
        preferred_languages: dict | None = None,
        name: str | None = None,
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
        """Whether the user has opted in to position usage."""
        return self.__use_positioning

    @property
    def share_experience(self):
        """Whether the user has opted in to experience sharing."""
        return self.__share_experience

    def send_signal(self, body: list):
        """Send a user signal payload.

        :param body: Signal payload.
        """
        pass

    async def set_position(self, latitude, longitude) -> "UserProfile":
        """Update current position and refresh locale-derived preferences.

        :param latitude: Current latitude.
        :param longitude: Current longitude.
        :return: Current profile instance.
        :rtype: UserProfile
        """
        self.current_latitude = latitude
        self.current_longitude = longitude
        self.current_position_country, self.preferred_language = await self.get_preferred_locale(latitude, longitude)
        return self

    def get_preferred_country_language(self, country_code: str):
        """Return preferred language for a specific country.

        Falls back to the default profile entry when no country match exists.

        :param country_code: ISO-like country code.
        :return: Preferred language for the country, or ``None``.
        """
        return self.preferred_languages.get(
            country_code,
            self.preferred_languages.get(self.__class__.default_name, None),
        )

    async def get_preferred_locale(self, latitude: float, longitude: float) -> Tuple[str, str]:
        """Resolve country and language for a coordinate pair.

        :param latitude: Latitude to resolve.
        :param longitude: Longitude to resolve.
        :return: ``(country_code, language)`` from HERE responses.
        :rtype: tuple[str | None, str | None]
        """
        country_code, language = None, None
        async with HTTPSession(raise_for_status=True) as session:
            local_addresses = await self.api.reverse_geocode(session=session, latitude=latitude, longitude=longitude)

            if local_addresses and "items" in local_addresses.data and len(local_addresses.data["items"]) > 0:
                country_code = local_addresses.data["items"][0]["address"]["countryCode"]
                address_details = await self.api.lookup(session=session, id=local_addresses.data["items"][0]["id"])
                language = address_details.data["language"]

            return country_code, language

    def get_current_language(self):
        """Return effective language for the current position context."""
        if not self.preferred_languages:
            return self.default_language
        elif self.current_position_country in self.preferred_languages:
            return self.preferred_languages[self.current_position_country]
        elif None in self.preferred_languages:
            return self.preferred_languages[None]
        else:
            return self.default_language

    def __repr__(self):
        languages = self.preferred_languages or self.preferred_language
        return f"{self.__class__.__name__}(name={self.name}, id={self.id}, lang={languages}, opt_in={self.__use_positioning}/{self.__share_experience})"


class DefaultUser(UserProfile):
    """Convenience profile with positioning enabled and sharing disabled."""

    def __init__(self, **kwargs):
        UserProfile.__init__(self, use_positioning=True, share_experience=False, **kwargs)
