from aiohttp import ClientSession
import nest_asyncio

from .util import get_lat_lon
from .api import API

from dataclasses import dataclass
import asyncio

class UserProfile:
    languages: dict
    current_latitude: float
    current_longitude: float
    current_country_code: str

    default_all_countries = "all"
    default_profile_languages = {default_all_countries: "en"}
    
    def __init__(self,
                 api: API=None,
                 languages: dict=None,
                 current_latitude: float=None,
                 current_longitude: float=None):
        self.api = api or API()
        self.languages = languages
        self.current_latitude = current_latitude
        self.current_longitude = current_longitude

        nest_asyncio.apply()
        asyncio.get_running_loop().run_until_complete(self.__ainit())
        
    async def __ainit(self):
        async with ClientSession(raise_for_status=True) as session:

            if self.current_latitude is None or self.current_latitude is None:
                    self.current_latitude, self.current_longitude = await get_lat_lon(session)

            local_addresses = await asyncio.ensure_future(self.api.reverse_geocode(
                session,
                latitude=self.current_latitude,
                longitude=self.current_longitude))

            if local_addresses and "items" in local_addresses and len(local_addresses["items"]) > 0:
                self.current_country_code = local_addresses["items"][0]["address"]["countryCode"]
                if self.languages is None:
                    address_details = await asyncio.ensure_future(self.api.lookup(session,
                                                                                  id=local_addresses["items"][0]["id"]))
                    self.languages = {self.__class__.default_all_countries: address_details["language"]}
                    
            if self.languages is None:
                self.languages = {}
            if UserProfile.default_all_countries not in self.languages:
                self.languages.update(self.__class__.default_profile_languages)

    def get_current_language(self):
        if self.current_country_code in self.languages:
            return self.languages[self.current_country_code]
        return self.languages[UserProfile.default_all_countries]
