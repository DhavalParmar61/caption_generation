const DEFAULT_BACKEND = "http://127.0.0.1:8000";

chrome.runtime.onMessage.addListener((msg, sender, sendResponse) => {
  if (msg && msg.type === "GENERATE") {
    generate(msg.payload)
      .then((data) => sendResponse(data))
      .catch((err) =>
        sendResponse({
          status: "error",
          detail: err && err.message ? err.message : String(err),
        })
      );
    return true;
  }
  if (msg && msg.type === "CHECK_BACKEND") {
    checkBackend(msg.payload && msg.payload.url)
      .then((ok) => sendResponse({ status: "success", ok }))
      .catch(() => sendResponse({ status: "success", ok: false }));
    return true;
  }
  return false;
});

async function checkBackend(url) {
  const base = (url || DEFAULT_BACKEND).replace(/\/+$/, "");
  const res = await fetch(`${base}/api/config`, { signal: AbortSignal.timeout(4000) });
  return res.ok;
}

async function generate(payload) {
  const base = (payload.backendUrl || DEFAULT_BACKEND).replace(/\/+$/, "");
  if (!payload.description && !(payload.image && payload.image.data)) {
    throw new Error("Please add a description or an image.");
  }
  const fd = new FormData();
  fd.append("description", payload.description || "");
  fd.append("keywords", (payload.keywords || []).join(","));
  fd.append("temperature", String(payload.temperature != null ? payload.temperature : 0.7));
  fd.append("platforms", (payload.platforms || []).join(","));
  fd.append("session_id", payload.session_id || "");
  if (payload.image && payload.image.data) {
    const blob = new Blob([payload.image.data], {
      type: payload.image.mime || "image/jpeg",
    });
    fd.append("image", blob, payload.image.name || "image.jpg");
  }
  const res = await fetch(`${base}/api/generate`, { method: "POST", body: fd });
  const data = await res.json().catch(() => ({}));
  if (!res.ok || data.status === "error") {
    throw new Error(data.detail || "Generation failed. Please try again.");
  }
  return data;
}