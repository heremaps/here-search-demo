###############################################################################
#
# Copyright (c) 2023 HERE Europe B.V.
#
# SPDX-License-Identifier: MIT
# License-Filename: LICENSE
#
###############################################################################

"""HTTP session abstraction.

At runtime we choose between:
- the browser/pyodide implementation in ``lite.HTTPSession`` when a JS runtime
  is actually available (Pyodide / JupyterLite),
- the standard aiohttp ``ClientSession`` everywhere else (classic CPython,
  JupyterLab, notebooks, etc.).

This prevents importing the browser transport in regular notebooks where the
``js`` module is not available and where ``lite`` would otherwise raise
HTTPConnectionError("js module unavailable; lite.py requires a browser runtime").
"""

_IS_BROWSER_RUNTIME = False
try:  # pragma: no cover
    import js  # type: ignore[attr-defined]
except ImportError:  # pragma: no cover
    js = None  # type: ignore[assignment]
else:  # pragma: no cover
    _IS_BROWSER_RUNTIME = True

if _IS_BROWSER_RUNTIME:
    from .lite import HTTPConnectionError, HTTPResponseError, HTTPSession
else:
    from aiohttp import (
        ClientConnectorError as HTTPConnectionError,
        ClientResponseError as HTTPResponseError,
        ClientSession as HTTPSession,
    )

__all__ = ["HTTPSession", "HTTPConnectionError", "HTTPResponseError"]
