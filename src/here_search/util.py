from aiohttp import ClientSession, ClientConnectorError

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
    geojs = 'https://get.geojs.io/v1/ip/geo.json'
    try:
        async with session.get(geojs) as response:
            geo = await response.json()
            return float(geo["latitude"]), float(geo["longitude"])
    except ClientConnectorError as e:
        logger.warning(f"Error connecting to {geojs}")
        return



