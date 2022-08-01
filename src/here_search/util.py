from aiohttp import ClientSession
try:
    from pyinstrument import Profiler
except ImportError:
    Profiler = None

from importlib import reload
import logging
reload(logging)
from logging import getLogger, basicConfig, DEBUG, INFO
from typing import Tuple

logger = getLogger('here_search')


def setLevel(level: int):
    basicConfig()
    logger.setLevel(level)
    client_logger = getLogger('aiohttp.client')
    client_logger.setLevel(level)


async def get_lat_lon(session: ClientSession) -> Tuple[float, float]:
    async with session.get('https://get.geojs.io/v1/ip/geo.json') as response:
        geo = await response.json()
        return float(geo["latitude"]), float(geo["longitude"])


