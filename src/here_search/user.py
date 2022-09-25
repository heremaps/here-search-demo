from .http import HTTPSession
from .api import API
from .entity.constants import paris, chicago, berlin

from typing import Tuple
import asyncio
import uuid


class Profile:
    preferred_languages: dict
    current_latitude: float
    current_longitude: float
    current_country_code: str

    default_name = "default"
    default_current_position = berlin
    default_country_code = "DEU"
    default_profile_languages = {default_name: "en"}

    def __init__(self, use_positioning: bool, start_position: Tuple[float, float]=None, languages: dict = None, name: str = None):
        """
        :param use_position: Mandatory opt-in/out about position usage
        :param api: Optional API instance
        :param languages: Optional user language preferences
        :param name: Optional user name
        """
        self.name = name or Profile.default_name
        self.id = str(uuid.uuid5(uuid.NAMESPACE_DNS, f"{self.name}{uuid.getnode()}"))

        self.__use_positioning = use_positioning

        self.preferred_languages = languages or {}
        self.has_country_preferences = not (
            self.preferred_languages == {}
            or list(self.preferred_languages.keys()) == [Profile.default_name]
        )

        self.language = Profile.default_profile_languages[Profile.default_name]
        self.current_latitude, self.current_longitude = start_position or Profile.default_current_position
        self.current_country_code = Profile.default_country_code


    @property
    def use_positioning(self):
        return self.__use_positioning

    def send_signal(self, body: list):
        pass

    def set_position(self, latitude, longitude) -> "Profile":
        self.current_latitude = latitude
        self.current_longitude = longitude
        (
            self.current_country_code,
            self.language,
        ) = asyncio.get_running_loop().run_until_complete(
            self.get_preferred_locale(latitude, longitude)
        )
        return self

    def get_preferred_language(self, country_code: str):
        return self.preferred_languages.get(
            country_code,
            self.preferred_languages.get(self.__class__.default_name, None),
        )

    async def get_preferred_locale(
        self, latitude: float, longitude: float
    ) -> Tuple[str, str]:
        country_code, language = None, None
        async with HTTPSession(raise_for_status=True) as session:
            api = API()
            local_addresses = await asyncio.ensure_future(
                api.reverse_geocode(
                    latitude=latitude, longitude=longitude, session=session
                )
            )

            if (
                local_addresses
                and "items" in local_addresses.data
                and len(local_addresses.data["items"]) > 0
            ):
                country_code = local_addresses.data["items"][0]["address"][
                    "countryCode"
                ]
                address_details = await asyncio.ensure_future(
                    api.lookup(
                        id=local_addresses.data["items"][0]["id"], session=session
                    )
                )
                language = address_details.data["language"]

            return country_code, language

    def get_current_language(self):
        if self.current_country_code in self.preferred_languages:
            return self.preferred_languages[self.current_country_code]
        return self.preferred_languages[Profile.default_name]

    def __repr__(self):
        languages = self.preferred_languages or self.language
        return f"{self.__class__.__name__}(name={self.name}, id={self.id}, lang={languages}, opt_in={self.__use_positioning}/{self.__share_experience})"


class Default(Profile):
    def __init__(self, **kwargs):
        Profile.__init__(self, use_positioning=True, **kwargs)
