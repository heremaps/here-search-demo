from aiohttp import ClientSession

from typing import Tuple
import asyncio


async def get_lat_lon(session: ClientSession) -> Tuple[float, float]:
    async with session.get('https://get.geojs.io/v1/ip/geo.json') as response:
        geo = await response.json()
        return float(geo["latitude"]), float(geo["longitude"])


class Timer:
    def __init__(self, milliseconds, callback):
        self._timeout = milliseconds
        self._callback = callback

    async def _job(self):
        await asyncio.sleep(self._timeout/1000.0)
        self._callback()

    def start(self):
        self._task = asyncio.ensure_future(self._job())

    def cancel(self):
        self._task.cancel()


def debounce(milliseconds):
    def decorator(fn):
        timer = None
        def debounced(*args, **kwargs):
            nonlocal timer
            def call_it():
                fn(*args, **kwargs)
            if timer is not None:
                timer.cancel()
            timer = Timer(milliseconds, call_it)
            timer.start()
        return debounced
    return decorator