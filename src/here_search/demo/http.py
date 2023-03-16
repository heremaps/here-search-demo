###############################################################################
#
# Copyright (c) 2023 HERE Europe B.V.
#
# SPDX-License-Identifier: MIT
# License-Filename: LICENSE
#
###############################################################################

try:
    from .lite import HTTPSession, HTTPConnectionError
except ImportError:
    from aiohttp import ClientSession as HTTPSession, ClientConnectorError as HTTPConnectionError
