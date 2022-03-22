from aiohttp import ClientSession
import nest_asyncio

from .util import get_lat_lon
from .api import API

from typing import Tuple
import asyncio
import uuid


class UserProfile:
    languages: dict
    current_latitude: float
    current_longitude: float
    current_country_code: str

    default_name = "default"
    default_current_latitude = 52.518333
    default_current_longitude = 13.408333
    default_country_code = "DEU"
    default_profile_languages = {default_name: "en"}
    
    def __init__(self,
                 use_positioning: bool,
                 share_experience: bool,
                 api: API=None,
                 languages: dict=None,
                 name: str=None):
        """
        :param use_position: Mandatory opt-in/out about position usage
        :param share_experience: Mandatory opt-in/out about activity usage
        :param api: Optional API instance
        :param languages: Optional user language preferences
        :param name: Optional user name
        """
        self.name = name or UserProfile.default_name
        self.id = str(uuid.uuid5(uuid.NAMESPACE_DNS, f'{self.name}{uuid.getnode()}'))

        self.__use_positioning = use_positioning
        self.__share_experience = share_experience

        self._api = api
        self.languages = languages or {}

        nest_asyncio.apply()
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
        loop.run_until_complete(self.__init_locale())

    @property
    def use_positioning(self):
        return self.__use_positioning

    @property
    def share_experience(self):
        return self.__share_experience

    @property
    def api(self) -> API:
        if self._api is None:
            self._api = API()
        return self._api

    def send_signal(self, body: list):
        pass

    def set_position(self, latitude, longitude):
        self.current_latitude = latitude
        self.current_longitude = longitude
        self.current_country_code, language = asyncio.get_running_loop().run_until_complete(self.get_preferred_locale(latitude, longitude))

    async def get_preferred_locale(self, latitude: float, longitude: float) -> Tuple[str, str]:
        country_code, language = None, None
        async with ClientSession(raise_for_status=True) as session:

            local_addresses = await asyncio.ensure_future(self.api.reverse_geocode(
                session,
                latitude=latitude,
                longitude=longitude))

            if local_addresses and "items" in local_addresses.data and len(local_addresses.data["items"]) > 0:
                country_code = local_addresses.data["items"][0]["address"]["countryCode"]
                address_details = await asyncio.ensure_future(self.api.lookup(session,
                                                                              id=local_addresses.data["items"][0]["id"]))
                language = address_details.data["language"]

            return country_code, language

    async def __init_locale(self):
        if not self.__use_positioning:
            self.current_latitude = UserProfile.default_current_latitude
            self.current_longitude = UserProfile.default_current_longitude
            self.current_country_code = UserProfile.default_country_code
            if UserProfile.default_name not in self.languages:
                self.languages.update(self.__class__.default_profile_languages)
        else:
            async with ClientSession(raise_for_status=True) as session:
                self.current_latitude, self.current_longitude = await get_lat_lon(session)
            self.current_country_code, language = await self.get_preferred_locale(self.current_latitude, self.current_longitude)
            if UserProfile.default_name not in self.languages:
                self.languages.update({self.__class__.default_name: language})

    def get_current_language(self):
        if self.current_country_code in self.languages:
            return self.languages[self.current_country_code]
        return self.languages[UserProfile.default_name]


class Permissive(UserProfile):
    def __init__(self, api: API=None):
        UserProfile.__init__(self, use_positioning=True, share_experience=True, api=api)
