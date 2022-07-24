from aiohttp import ClientSession

from typing import Tuple
import asyncio


async def get_lat_lon(session: ClientSession) -> Tuple[float, float]:
    async with session.get('https://get.geojs.io/v1/ip/geo.json') as response:
        geo = await response.json()
        return float(geo["latitude"]), float(geo["longitude"])
