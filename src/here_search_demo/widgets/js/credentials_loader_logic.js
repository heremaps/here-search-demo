/******************************************************************************
 *
 * Copyright (c) 2026 HERE Europe B.V.
 *
 * SPDX-License-Identifier: MIT
 * License-Filename: LICENSE
 *
 *****************************************************************************/

(function (root) {
  var REQUIRED_KEYS = [
    "here.token.endpoint.url",
    "here.access.key.id",
    "here.access.key.secret",
  ];

  function parseProps(text) {
    var props = {};
    var lines = String(text).split("\n");
    for (var i = 0; i < lines.length; i += 1) {
      var trimmed = lines[i].trim();
      if (!trimmed || trimmed.indexOf("#") === 0) continue;
      var idx = trimmed.indexOf("=");
      if (idx === -1) continue;
      var key = trimmed.slice(0, idx).trim().toLowerCase();
      var value = trimmed.slice(idx + 1).trim();
      props[key] = value;
    }
    return props;
  }

  function normalizeCredentials(properties) {
    var p = properties || {};
    return {
      "here.token.endpoint.url": p["here.token.endpoint.url"] || "",
      "here.access.key.id": p["here.access.key.id"] || "",
      "here.access.key.secret": p["here.access.key.secret"] || "",
      "here.api.key": p["here.api.key"] || p.apikey || "",
    };
  }

  function isValidCredentials(text) {
    var normalized = normalizeCredentials(parseProps(text));
    var values = [
      normalized[REQUIRED_KEYS[0]],
      normalized[REQUIRED_KEYS[1]],
      normalized[REQUIRED_KEYS[2]],
      normalized["here.api.key"],
    ];
    for (var i = 0; i < values.length; i += 1) {
      if (!values[i] || values[i] === "...") return false;
    }
    return true;
  }

  function hasValidActiveConfig(activeConfig) {
    var config = activeConfig || {};
    var values = [
      config["here.token.endpoint.url"],
      config["here.access.key.id"],
      config["here.access.key.secret"],
      config["here.api.key"],
    ];
    for (var i = 0; i < values.length; i += 1) {
      if (!values[i] || values[i] === "...") return false;
    }
    return true;
  }

  var api = {
    parseProps: parseProps,
    normalizeCredentials: normalizeCredentials,
    isValidCredentials: isValidCredentials,
    hasValidActiveConfig: hasValidActiveConfig,
  };

  root.CredentialsLoaderLogic = api;
  if (typeof module !== "undefined" && module.exports) {
    module.exports = api;
  }
})(typeof globalThis !== "undefined" ? globalThis : this);
