try:
    from .lite import HTTPSession, HTTPConnectionError
except ImportError:
    from aiohttp import ClientSession as HTTPSession, ClientConnectorError as HTTPConnectionError
