###############################################################################
#
# Copyright (c) 2026 HERE Europe B.V.
#
# SPDX-License-Identifier: MIT
# License-Filename: LICENSE
#
###############################################################################

import configparser
import pathlib

import anywidget
import traitlets


class CredentialsLoader(anywidget.AnyWidget):
    _raw_text_sync = traitlets.Unicode("").tag(sync=True)
    _flash_error = traitlets.Int(0).tag(sync=True)
    active_config = traitlets.Dict({}).tag(sync=True)

    CREDENTIAL_KEYS = ("here.token.endpoint.url", "here.access.key.id", "here.access.key.secret", "here.api.key")

    _esm = pathlib.Path(__file__).parent / "js" / "credentials_loader.mjs"

    _css = """
    .cred-container {
        display: inline-block;
    }
    .cred-upload-zone {
        border: 2px dashed #9c27b0;
        border-radius: 8px;
        padding: 4px 6px;
        background: #fdfaff;
        text-align: center;
        cursor: pointer;
        display: inline-block;
        line-height: 1;
        transition: all 0.2s ease;
    }
    .cred-upload-zone:hover {
        background: #f7f0fc;
        border-color: #7b1fa2;
    }
    """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.observe(self._on_raw_text, names="_raw_text_sync")

    def _on_raw_text(self, change):
        raw = change["new"]
        if not raw:
            return
        try:
            config = configparser.ConfigParser()
            config.read_string("[DEFAULT]\n" + raw)
            section = config["DEFAULT"]
            result = {k: section.get(k, "") for k in self.CREDENTIAL_KEYS}
            if not result["here.api.key"]:
                result["here.api.key"] = section.get("apikey", "")
            if any(v in ("", "...") for v in result.values()):
                self._flash_error += 1
                return
            self.active_config = result
        except Exception:
            self._flash_error += 1
