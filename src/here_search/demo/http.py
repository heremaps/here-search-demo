###############################################################################
#
# Copyright (c) 2023 HERE Europe B.V.
#
# SPDX-License-Identifier: MIT
# License-Filename: LICENSE
#
###############################################################################

try:
    from .lite import HTTPConnectionError, HTTPResponseError, HTTPSession
except ImportError:
    from aiohttp import ClientConnectorError as HTTPConnectionError
    from aiohttp import ClientResponseError as HTTPResponseError
    from aiohttp import ClientSession as HTTPSession

__all__ = [HTTPSession, HTTPConnectionError, HTTPResponseError]
