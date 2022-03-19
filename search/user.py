from aiohttp import ClientSession
import nest_asyncio

from .util import get_lat_lon
from .api import API

from dataclasses import dataclass
from typing import Tuple
import asyncio
import uuid
import json


class UserProfile:
    languages: dict
    current_latitude: float
    current_longitude: float
    current_country_code: str

    default_name = "default"
    default_current_latitude = 52.518333
    default_current_longitude = 13.408333
    default_country_code = "DEU"
    default_all_countries = "all"
    default_profile_languages = {default_all_countries: "en"}
    
    def __init__(self,
                 use_my_position: bool,
                 store_my_activity: bool,
                 api: API=None,
                 languages: dict=None,
                 name: str=None):
        """
        :param use_my_position: Mandatory opt-in/out about position usage
        :param store_my_activity: Mandatory opt-in/out about activity usage
        :param api: Optional API instance
        :param languages: Optional user language preferences
        :param name: Optional user name
        """
        self.name = name or UserProfile.default_name
        self.id = str(uuid.uuid5(uuid.NAMESPACE_DNS, f'{self.name}{uuid.getnode()}'))

        self.__use_my_position = use_my_position
        self.__store_my_activity = store_my_activity

        self.api = api or API()
        self.languages = languages or {}

        nest_asyncio.apply()
        asyncio.get_running_loop().run_until_complete(self.__init_locale())

    @property
    def use_my_position(self):
        return self.__use_my_position

    @property
    def store_my_activity(self):
        return self.__store_my_activity

    def send_signal(self, body: list):
        pass

    def set_position(self, latitude, longitude):
        self.current_latitude = latitude
        self.current_longitude = longitude
        self.current_country_code, language = asyncio.get_running_loop().run_until_complete(self.__get_position_locale())
        return self

    async def __get_position_locale(self) -> Tuple[str, str]:        
        country_code, language = None, None
        async with ClientSession(raise_for_status=True) as session:

            local_addresses = await asyncio.ensure_future(self.api.reverse_geocode(
                session,
                latitude=self.current_latitude,
                longitude=self.current_longitude))

            if local_addresses and "items" in local_addresses.data and len(local_addresses.data["items"]) > 0:
                country_code = local_addresses.data["items"][0]["address"]["countryCode"]
                address_details = await asyncio.ensure_future(self.api.lookup(session,
                                                                              id=local_addresses.data["items"][0]["id"]))
                language = address_details.data["language"]
                    
            return country_code, language

    async def __init_locale(self):
        if not self.__use_my_position:
            self.current_latitude = UserProfile.default_current_latitude
            self.current_longitude = UserProfile.default_current_longitude
            self.current_country_code = UserProfile.default_country_code
            if UserProfile.default_all_countries not in self.languages:
                self.languages.update(self.__class__.default_profile_languages)
        else:
            async with ClientSession(raise_for_status=True) as session:
                self.current_latitude, self.current_longitude = await get_lat_lon(session)
            self.current_country_code, language = await self.__get_position_locale()
            if UserProfile.default_all_countries not in self.languages:
                self.languages.update({self.__class__.default_all_countries: language})

    def get_current_language(self):
        if self.current_country_code in self.languages:
            return self.languages[self.current_country_code]
        return self.languages[UserProfile.default_all_countries]


permissive = UserProfile(use_my_position=True, store_my_activity=True)
restricted = UserProfile(use_my_position=False, store_my_activity=False)