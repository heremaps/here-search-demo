from aiohttp import ClientSession, ClientConnectorError

from importlib import reload
import logging

reload(logging)
from logging import getLogger, basicConfig, DEBUG, INFO
from typing import Tuple, Sequence
from functools import reduce
from collections import defaultdict

logger = getLogger("here_search")


def setLevel(level: int):
    basicConfig()
    logger.setLevel(level)
    client_logger = getLogger("aiohttp.client")
    client_logger.setLevel(level)


def set_dict_values(source: dict, target_keys: Sequence[Sequence[str]], target_values: list) -> dict:
    """
    Return a modified version of a nested dict for which
    values have been changed according to a set of paths.

    :param source: Nested dict
    :param target_keys: sequence of successive keys in the nested dict
    :param target_values: list of target values
    """
    result = source.copy()
    for key, value in zip(target_keys, target_values):
        reduce(lambda a, b: a.setdefault(b, {}), key[:-1], result)[key[-1]] = value
    return result


async def get_lat_lon(session: ClientSession) -> Tuple[float, float]:
    geojs = "https://get.geojs.io/v1/ip/geo.json"
    try:
        async with session.get(geojs) as response:
            geo = await response.json()
            return float(geo["latitude"]), float(geo["longitude"])
    except ClientConnectorError as e:
        logger.warning(f"Error connecting to {geojs}")
        return 52.51604, 13.37691
