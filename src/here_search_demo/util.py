###############################################################################
#
# Copyright (c) 2023 HERE Europe B.V.
#
# SPDX-License-Identifier: MIT
# License-Filename: LICENSE
#
###############################################################################

from functools import reduce, wraps
from typing import Sequence, Tuple
from reprlib import repr as short_repr
import inspect
import logging

try:
    from IPython import get_ipython
except ImportError:
    get_ipython = None

from here_search_demo.entity.constants import berlin
from here_search_demo.http import HTTPConnectionError, HTTPSession

# isort: off
from importlib import reload

reload(logging)
from logging import basicConfig, getLogger  # noqa: E402

logger = getLogger("here_search_demo")
# isort: on


def log_signature(func):
    """
    Decorator logging:
    - function entry
    - input parameters
    - return value
    - exceptions

    Supports sync and async functions.
    Uses pre-formatted log messages to avoid literal %s output.
    """

    signature = inspect.signature(func)

    def format_parameters(args, kwargs):
        try:
            bound_args = signature.bind(*args, **kwargs)
            bound_args.apply_defaults()

            return ", ".join(f"{name}={short_repr(value)}" for name, value in bound_args.arguments.items())
        except TypeError:
            return f"args={short_repr(args)}, kwargs={short_repr(kwargs)}"

    if inspect.iscoroutinefunction(func):

        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            parameters = format_parameters(args, kwargs)
            function_name = func.__qualname__

            print(f"Entering {function_name}({parameters})")

            try:
                result = await func(*args, **kwargs)
                print(f"Returning from {function_name} -> {short_repr(result)}")
                return result
            except Exception:
                print(f"Exception in {function_name}({parameters})")
                raise

        return async_wrapper

    @wraps(func)
    def sync_wrapper(*args, **kwargs):
        parameters = format_parameters(args, kwargs)
        function_name = func.__qualname__

        print(f"Entering {function_name}({parameters})")

        try:
            result = func(*args, **kwargs)
            print(f"Returning from {function_name} -> {short_repr(result)}")
            return result
        except Exception:
            print(f"Exception in {function_name}({parameters})")
            raise

    return sync_wrapper


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


async def get_lat_lon() -> Tuple[float, float]:
    geojs = "https://get.geojs.io/v1/ip/geo.json"
    try:
        async with HTTPSession() as session:
            async with session.get(geojs) as response:
                geo = await response.json()
                return float(geo["latitude"]), float(geo["longitude"])
    except HTTPConnectionError:
        logger.warning(f"Error connecting to {geojs}")
        return berlin


is_running_in_jupyter = False if not get_ipython else get_ipython().__class__.__name__ == "ZMQInteractiveShell"
