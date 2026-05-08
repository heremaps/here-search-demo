###############################################################################
#
# Copyright (c) 2026 HERE Europe B.V.
#
# SPDX-License-Identifier: MIT
# License-Filename: LICENSE
#
###############################################################################

import asyncio
import base64
import hashlib
import hmac
import http.client
import json
import os
import sys
import time
import urllib.parse
import uuid
from configparser import ConfigParser
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any


class Credentials:
    default_auth_url = "https://account.api.here.com/oauth2/token"

    def __init__(self):
        self._api_key = None
        self._token = None
        self._expires = None
        self._access_key_id = None
        self._access_key_secret = None
        self._url = None
        self._scope = None
        self._refresh_handle = None
        self._refresh_timer = None
        self._config()

    @property
    async def atoken(self) -> dict:
        if not self._access_key_secret:
            return None
        now = datetime.now(timezone.utc)
        if self._expires is None or self._expires < now + timedelta(seconds=1800):
            token_dict = await self._aretrieve_token()
            self._token = token_dict.get("accessToken") or token_dict.get("access_token")
            expires_in = token_dict.get("expiresIn") or token_dict.get("expires_in")
            seconds = int(expires_in)
            self._expires = now + timedelta(seconds=seconds)
            self._schedule_refresh(seconds, use_async=True)
        return self._token

    @property
    def token(self) -> str | None:
        if not self._access_key_secret:
            return None
        now = datetime.now(timezone.utc)
        if self._expires is None or self._expires < now + timedelta(seconds=1800):
            token_dict = self._retrieve_token()
            self._token = token_dict.get("accessToken") or token_dict.get("access_token")
            expires_in = token_dict.get("expiresIn") or token_dict.get("expires_in")
            seconds = int(expires_in)
            self._expires = now + timedelta(seconds=seconds)
            self._schedule_refresh(seconds, use_async=False)
        return self._token

    @property
    def api_key(self) -> str | None:
        return self._api_key

    def _config(self) -> dict:
        """
        Load configuration from environment variables or credentials file.

        Credentials files are searched across several directories
        (JupyterLite ``/drive``, current working directory, user home,
        ``~/.here/``) and under several conventional names.

        Supported variables are:
        - HERE_TOKEN_ENDPOINT_URL
        - HERE_ACCESS_KEY_ID
        - HERE_ACCESS_KEY_SECRET
        - HERE_TOKEN_SCOPE (optional)
        """
        # 1) Try to load a credentials file if present
        config = ConfigParser()
        filenames = ["credentials.properties", "credentials.properties.txt", ".credentials.properties"]
        search_dirs = [
            Path("/drive"),  # JupyterLite default root directory for artifacts
            Path.cwd(),  # Current working directory
            Path(""),  # Explicit "." (covers edge cases)
            Path.home(),  # User home directory
            Path(os.environ.get("HOME", "")) / ".here",  # ~/.here/
        ]
        if Path.cwd().parts[-1] == "notebooks":
            search_dirs.append(Path.cwd().parents[0])
        paths = [d / fname for d in search_dirs for fname in filenames]
        file_config = None
        for path in paths:
            if path.exists():
                with path.open() as f:
                    config.read_string("[DEFAULT]\n" + f.read())
                file_config = dict(config["DEFAULT"])
                break

        # 2) Resolve values with priority: env > file, and for URL: env > file > default
        url = (
            os.getenv("HERE_TOKEN_ENDPOINT_URL")
            or (file_config.get("here.token.endpoint.url") if file_config else None)
            or self.default_auth_url
        )
        access_key_id = os.getenv("HERE_ACCESS_KEY_ID") or (
            file_config.get("here.access.key.id") if file_config else None
        )
        access_key_secret = os.getenv("HERE_ACCESS_KEY_SECRET") or (
            file_config.get("here.access.key.secret") if file_config else None
        )
        scope = os.getenv("HERE_TOKEN_SCOPE") or (file_config.get("here.token.scope") if file_config else None)

        self._api_key = (
            os.getenv("API_KEY")
            or os.getenv("HERE_API_KEY")
            or ((file_config.get("apikey") or file_config.get("here.api.key")) if file_config else None)
        )

        # 3) set the necessary variable if we have all of the mandatory ones
        if url and access_key_id and access_key_secret:
            self._url = url
            self._access_key_id = access_key_id
            self._access_key_secret = access_key_secret
            self._scope = scope

    def _signature(self, url: str):
        oauth_nonce = uuid.uuid4().hex
        oauth_timestamp = str(int(time.time()))
        oauth_signature_method = "HMAC-SHA256"
        oauth_version = "1.0"
        params = {
            "oauth_consumer_key": self._access_key_id,
            "oauth_nonce": oauth_nonce,
            "oauth_signature_method": oauth_signature_method,
            "oauth_timestamp": oauth_timestamp,
            "oauth_version": oauth_version,
        }
        sorted_items = sorted(params.items())
        encoded_params = "&".join(
            f"{urllib.parse.quote(str(k), safe='')}={urllib.parse.quote(str(v), safe='')}" for k, v in sorted_items
        )
        base_string = "&".join(["POST", urllib.parse.quote(url, safe=""), urllib.parse.quote(encoded_params, safe="")])
        signing_key = f"{self._access_key_secret}&"
        digest = hmac.new(signing_key.encode(), base_string.encode(), hashlib.sha256).digest()
        signature = base64.b64encode(digest).decode()
        params["oauth_signature"] = signature
        return params

    def _build_auth_and_body(self):
        params = self._signature(self._url)
        auth_header = "OAuth " + ", ".join(f'{k}="{urllib.parse.quote(str(v))}"' for k, v in params.items())
        body = {
            "grantType": "client_credentials",
            "clientId": self._access_key_id,
            "clientSecret": self._access_key_secret,
        }
        if self._scope:
            body["scope"] = self._scope
        return auth_header, body

    def _cancel_refresh(self):
        """Cancel any previously scheduled token refresh."""
        if self._refresh_handle is not None:
            self._refresh_handle.cancel()
            self._refresh_handle = None
        if self._refresh_timer is not None:
            self._refresh_timer.cancel()
            self._refresh_timer = None

    def _schedule_refresh(self, expires_in: int, use_async: bool = False):
        """Schedule a token refresh ``expires_in - 1800`` seconds from now.

        Works in asyncio-based environments (JupyterLab, xeus-python,
        JupyterLite / Pyodide) as well as plain synchronous contexts
        (falls back to :class:`threading.Timer`).
        """
        delay = max(expires_in - 1800, 0)
        if delay <= 0:
            return
        self._cancel_refresh()

        try:
            loop = asyncio.get_running_loop()
            if use_async:
                self._refresh_handle = loop.call_later(delay, lambda: asyncio.ensure_future(self.atoken()))
            else:
                self._refresh_handle = loop.call_later(
                    delay,
                    lambda: asyncio.ensure_future(loop.run_in_executor(None, self.token)),
                )
        except RuntimeError:
            # No running event loop – fall back to a daemon thread.
            import threading

            self._refresh_timer = threading.Timer(delay, self.token)
            self._refresh_timer.daemon = True
            self._refresh_timer.start()

    async def _aretrieve_token(self) -> Any:
        if sys.platform != "emscripten":
            raise RuntimeError("Async token only supported in Pyodide/emscripten.")

        from js import fetch
        from pyodide.ffi import to_js

        auth_header, body = self._build_auth_and_body()

        # from js import JSON
        # body_json = JSON.stringify(to_js(body))
        body_json = json.dumps(body)

        options = {
            "method": "POST",
            "headers": {"Content-Type": "application/json", "Authorization": auth_header},
            "body": body_json,
        }
        resp = await fetch(self._url, to_js(options))
        if not resp.ok:
            text = await resp.text()
            raise RuntimeError(f"Token request failed {resp.status}: {text}")

        resp_json = await resp.json()
        resp_dict = resp_json.to_py() if hasattr(resp_json, "to_py") else resp_json
        return resp_dict

    def _retrieve_token(self) -> dict:
        auth_header, body = self._build_auth_and_body()
        body_json = json.dumps(body)
        parsed_url = urllib.parse.urlparse(self._url)
        conn = http.client.HTTPSConnection(parsed_url.netloc)
        headers = {"Content-Type": "application/json", "Authorization": auth_header}
        conn.request("POST", parsed_url.path, body=body_json, headers=headers)
        resp = conn.getresponse()
        resp_text = resp.read().decode()
        if resp.status != 200:
            raise RuntimeError(f"Token request failed {resp.status}: {resp_text}")
        token_dict = json.loads(resp_text)
        return token_dict
