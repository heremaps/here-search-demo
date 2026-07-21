/******************************************************************************
 *
 * Copyright (c) 2026 HERE Europe B.V.
 *
 * SPDX-License-Identifier: MIT
 * License-Filename: LICENSE
 *
 *****************************************************************************/

const DB_NAME = "here-search-demo-db";
const STORE_NAME = "files-store";
const CRED_KEY = "credentials.properties";
const REQUIRED_KEYS = [
  "here.token.endpoint.url",
  "here.access.key.id",
  "here.access.key.secret",
  "here.api.key",
];

function openDB(name) {
  return new Promise((resolve, reject) => {
    const request = indexedDB.open(name, 1);
    request.onupgradeneeded = () => request.result.createObjectStore(STORE_NAME);
    request.onsuccess = () => resolve(request.result);
    request.onerror = () => reject(request.error);
  });
}

function getDB() {
  return openDB(DB_NAME);
}

function idbGetFromDB(db, key) {
  return new Promise((resolve) => {
    const tx = db.transaction(STORE_NAME, "readonly");
    const req = tx.objectStore(STORE_NAME).get(key);
    req.onsuccess = () => resolve(req.result);
  });
}

async function idbGet(key) {
  const db = await getDB();
  return idbGetFromDB(db, key);
}

async function idbSet(key, value) {
  const db = await getDB();
  return new Promise((resolve) => {
    const tx = db.transaction(STORE_NAME, "readwrite");
    tx.objectStore(STORE_NAME).put(value, key);
    tx.oncomplete = () => resolve();
  });
}

function parseProps(text) {
  const props = {};
  for (const line of String(text).split("\n")) {
    const trimmed = line.trim();
    if (!trimmed || trimmed.startsWith("#")) continue;
    const idx = trimmed.indexOf("=");
    if (idx === -1) continue;
    props[trimmed.slice(0, idx).trim().toLowerCase()] = trimmed.slice(idx + 1).trim();
  }
  return props;
}

function normalizeCredentials(properties) {
  return {
    "here.token.endpoint.url": properties["here.token.endpoint.url"] ?? "",
    "here.access.key.id": properties["here.access.key.id"] ?? "",
    "here.access.key.secret": properties["here.access.key.secret"] ?? "",
    "here.api.key": properties["here.api.key"] || properties["apikey"] || "",
  };
}

function isValidCredentials(text) {
  const normalized = normalizeCredentials(parseProps(text));
  const requiredValues = REQUIRED_KEYS.map((key) => normalized[key]);
  return requiredValues.every((value) => value && value !== "...");
}

function hasValidActiveConfig(model) {
  const activeConfig = model.get("active_config") || {};
  return REQUIRED_KEYS.every((key) => {
    const value = activeConfig[key];
    return value && value !== "...";
  });
}

function render({ model, el }) {
  const container = document.createElement("div");
  container.className = "cred-container";

  const uploadZone = document.createElement("div");
  uploadZone.className = "cred-upload-zone";

  const fileInput = document.createElement("input");
  fileInput.type = "file";
  fileInput.style.display = "none";

  const label = document.createElement("div");

  uploadZone.appendChild(fileInput);
  uploadZone.appendChild(label);
  container.appendChild(uploadZone);
  el.appendChild(container);

  function setStatus(loaded) {
    if (loaded) {
      label.innerHTML = "✅";
      uploadZone.style.borderColor = "#10b981";
      uploadZone.style.background = "#f0fdf4";
    } else {
      label.innerHTML = "🔑";
      uploadZone.style.borderColor = "#9c27b0";
      uploadZone.style.background = "#fdfaff";
    }
  }

  function flashError() {
    uploadZone.style.borderColor = "#ef4444";
    uploadZone.style.background = "#fee2e2";
    setTimeout(() => setStatus(hasValidActiveConfig(model) || !!model.get("_raw_text_sync")), 600);
  }

  async function ingestFile(file) {
    const text = await file.text();
    if (!isValidCredentials(text)) {
      flashError();
      return;
    }
    const blob = new Blob([text], { type: "text/plain" });
    await idbSet(CRED_KEY, blob);
    model.set("_raw_text_sync", text);
    model.save_changes();
    setStatus(true);
  }

  model.on("change:_flash_error", flashError);
  model.on("change:active_config", () => setStatus(hasValidActiveConfig(model) || !!model.get("_raw_text_sync")));
  model.on("change:_raw_text_sync", () => setStatus(hasValidActiveConfig(model) || !!model.get("_raw_text_sync")));

  uploadZone.addEventListener("click", () => fileInput.click());
  fileInput.addEventListener("change", (e) => {
    if (e.target.files[0]) ingestFile(e.target.files[0]);
  });
  uploadZone.addEventListener("dragover", (e) => {
    e.preventDefault();
    uploadZone.style.background = "#e8f5e9";
  });
  uploadZone.addEventListener("dragleave", () => setStatus(hasValidActiveConfig(model) || !!model.get("_raw_text_sync")));
  uploadZone.addEventListener("drop", (e) => {
    e.preventDefault();
    if (e.dataTransfer.files[0]) ingestFile(e.dataTransfer.files[0]);
  });

  (async () => {
    setStatus(hasValidActiveConfig(model) || !!model.get("_raw_text_sync"));
    const blob = await idbGet(CRED_KEY);
    if (blob) {
      const text = await blob.text();
      if (isValidCredentials(text)) {
        model.set("_raw_text_sync", text);
        model.save_changes();
        setStatus(true);
      }
    }
  })();
}

export default { render };
