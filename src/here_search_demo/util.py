###############################################################################
#
# Copyright (c) 2023 HERE Europe B.V.
#
# SPDX-License-Identifier: MIT
# License-Filename: LICENSE
#
###############################################################################
import sys
import time
from collections import defaultdict

from functools import reduce
from typing import Sequence, Tuple

try:
    from IPython import get_ipython
except ImportError:
    get_ipython = None

from here_search_demo.entity.constants import berlin
from here_search_demo.http import HTTPConnectionError, HTTPSession

# isort: off
from importlib import reload
import logging

reload(logging)
from logging import basicConfig, getLogger  # noqa: E402

logger = getLogger("here_search")
# isort: on


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


class AsyncCPUProfiler:
    TOOL_ID = 1

    def __init__(self):
        self.total_time = defaultdict(float)
        self.self_time = defaultdict(float)
        self.call_count = defaultdict(int)
        self.min_time = {}
        self.max_time = {}
        self.stack = []
        # stack entry layout (all mutable → list):
        #   [0] code object
        #   [1] start time of current running segment
        #   [2] accumulated children CPU duration
        #   [3] accumulated suspended duration (time between PY_YIELD and PY_RESUME)
        #   [4] timestamp of last PY_YIELD, or None when running

    def _now(self):
        return time.perf_counter()

    def on_call(self, code, instruction_offset):
        self.stack.append([code, self._now(), 0.0, 0.0, None])

    def on_yield(self, code, instruction_offset, retval):
        # Coroutine/generator suspending: pause the clock for its stack entry.
        now = self._now()
        for i in range(len(self.stack) - 1, -1, -1):
            entry = self.stack[i]
            if entry[0] is code and entry[4] is None:
                entry[4] = now  # record yield timestamp
                break

    def on_resume(self, code, instruction_offset):
        # Coroutine/generator resuming: restart the clock.
        now = self._now()
        for i in range(len(self.stack) - 1, -1, -1):
            entry = self.stack[i]
            if entry[0] is code and entry[4] is not None:
                entry[3] += now - entry[4]  # accumulate suspended time
                entry[4] = None  # mark as running again
                break

    def on_return(self, code, instruction_offset, retval):
        if not self.stack:
            return

        entry = self.stack.pop()
        code_obj, start, children_duration, suspended_duration, _ = entry
        wall_duration = self._now() - start
        cpu_duration = wall_duration - suspended_duration  # actual CPU time

        # Propagate CPU duration to parent's children counter
        if self.stack:
            self.stack[-1][2] += cpu_duration

        if "here_search_demo" not in code_obj.co_filename:
            return

        filename = code_obj.co_filename
        pkg_path = (
            filename.split("here_search_demo/")[-1] if "here_search_demo/" in filename else filename.split("/")[-1]
        )
        key = f"{code_obj.co_name} ({pkg_path}:{code_obj.co_firstlineno})"
        self.total_time[key] += cpu_duration
        self.self_time[key] += cpu_duration - children_duration
        self.call_count[key] += 1
        if key not in self.min_time or cpu_duration < self.min_time[key]:
            self.min_time[key] = cpu_duration
        if key not in self.max_time or cpu_duration > self.max_time[key]:
            self.max_time[key] = cpu_duration

    def start(self):
        sys.monitoring.use_tool_id(self.TOOL_ID, "AsyncCPUProfiler")
        sys.monitoring.register_callback(self.TOOL_ID, sys.monitoring.events.PY_START, self.on_call)
        sys.monitoring.register_callback(self.TOOL_ID, sys.monitoring.events.PY_RESUME, self.on_resume)
        sys.monitoring.register_callback(self.TOOL_ID, sys.monitoring.events.PY_YIELD, self.on_yield)
        sys.monitoring.register_callback(self.TOOL_ID, sys.monitoring.events.PY_RETURN, self.on_return)
        sys.monitoring.set_events(
            self.TOOL_ID,
            sys.monitoring.events.PY_START
            | sys.monitoring.events.PY_RESUME
            | sys.monitoring.events.PY_YIELD
            | sys.monitoring.events.PY_RETURN,
        )

    def stop(self):
        sys.monitoring.set_events(self.TOOL_ID, 0)
        sys.monitoring.free_tool_id(self.TOOL_ID)

    def report(self, limit=30):
        print(f"\n{'function':<55} {'calls':>6} {'total':>10} {'self':>10} {'mean':>10} {'spread':>10}")
        print("-" * 105)
        rows = sorted(self.total_time.items(), key=lambda x: -x[1])[:limit]
        for key, total in rows:
            n = self.call_count[key]
            mean = total / n
            spread = self.max_time[key] - self.min_time[key]
            self_t = self.self_time[key]
            print(f"{key:<55} {n:>6} {total:>10.4f}s {self_t:>9.4f}s {mean:>9.4f}s {spread:>9.4f}s")
