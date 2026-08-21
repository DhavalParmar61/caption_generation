(() => {
  const PLATFORMS = {
    instagram: { label: "Instagram", tone: "Casual & Visual" },
    facebook: { label: "Facebook", tone: "Friendly" },
    linkedin: { label: "LinkedIn", tone: "Professional" },
    twitter: { label: "X / Twitter", tone: "Punchy & Conversational" },
    youtube: { label: "YouTube", tone: "Storytelling" },
  };

  const HOST_RULES = [
    "instagram.com",
    "linkedin.com",
    "facebook.com",
    "x.com",
    "twitter.com",
    "youtube.com",
  ];

  const state = {
    platform: null,
    tone: "Friendly",
    image: null,
    backendUrl: "http://127.0.0.1:8000",
  };

  function detectPlatform() {
    const host = location.hostname.toLowerCase();
    for (const h of HOST_RULES) {
      if (host === h || host.endsWith("." + h)) {
        if (h === "x.com" || h === "twitter.com") return "twitter";
        return h.split(".")[0];
      }
    }
    return null;
  }

  let fab = null;
  let panel = null;

  function buildUI() {
    if (document.getElementById("ccpro-fab")) return;

    fab = document.createElement("button");
    fab.id = "ccpro-fab";
    fab.type = "button";
    fab.textContent = "CC";
    fab.title = "CaptionGen Pro";
    fab.addEventListener("click", togglePanel);
    document.documentElement.appendChild(fab);

    panel = document.createElement("div");
    panel.id = "ccpro-panel";
    panel.innerHTML = `
      <div class="ccpro-head">
        <span class="ccpro-title">CaptionGen Pro</span>
        <button type="button" class="ccpro-close" title="Close">✕</button>
      </div>
      <div class="ccpro-detect" id="ccpro-detect"></div>
      <textarea id="ccpro-desc" placeholder="Add product/photo details (optional)…"></textarea>
      <div class="ccpro-row">
        <button type="button" class="ccpro-btn" id="ccpro-grab">🖼️ Use page image</button>
        <button type="button" class="ccpro-btn" id="ccpro-upload">⬆️ Upload</button>
      </div>
      <input type="file" class="ccpro-file" id="ccpro-file" accept="image/*">
      <button type="button" class="ccpro-btn primary" id="ccpro-gen">🚀 Generate Caption</button>
      <div id="ccpro-status"></div>
      <div id="ccpro-result">
        <div id="ccpro-meta"></div>
        <textarea id="ccpro-out"></textarea>
        <div class="ccpro-row">
          <button type="button" class="ccpro-btn primary" id="ccpro-insert">↩ Insert into composer</button>
          <button type="button" class="ccpro-btn" id="ccpro-copy">📋 Copy</button>
        </div>
      </div>
    `;
    document.documentElement.appendChild(panel);

    panel.querySelector(".ccpro-close").addEventListener("click", () => {
      panel.classList.remove("open");
      fab.style.display = "flex";
    });
    panel.querySelector("#ccpro-gen").addEventListener("click", generate);
    panel.querySelector("#ccpro-grab").addEventListener("click", grabPageImage);
    panel.querySelector("#ccpro-upload").addEventListener("click", () => {
      panel.querySelector("#ccpro-file").click();
    });
    panel.querySelector("#ccpro-file").addEventListener("change", (e) => {
      const f = e.target.files[0];
      if (f) setImage(f);
    });
    panel.querySelector("#ccpro-insert").addEventListener("click", insertResult);
    panel.querySelector("#ccpro-copy").addEventListener("click", () => {
      const out = panel.querySelector("#ccpro-out");
      navigator.clipboard.writeText(out.value).then(() => setStatus("Copied to clipboard ✓"));
    });
  }

  function togglePanel() {
    if (!panel) return;
    const open = panel.classList.toggle("open");
    fab.style.display = open ? "none" : "flex";
    if (open) updateDetect();
  }

  function updateDetect() {
    const el = panel.querySelector("#ccpro-detect");
    if (state.platform) {
      const meta = PLATFORMS[state.platform];
      el.innerHTML = `Detected: <b>${meta.label}</b> · Auto tone: <b>${meta.tone}</b>`;
    } else {
      el.innerHTML = "Open an Instagram, LinkedIn, Facebook, X or YouTube composer.";
    }
  }

  function setStatus(msg) {
    panel.querySelector("#ccpro-status").textContent = msg;
  }

  function setImage(file) {
    state.image = file;
    setStatus(`Image attached: ${file.name}`);
  }

  async function grabPageImage() {
    const imgs = Array.from(document.querySelectorAll('[role="dialog"] img, img'))
      .filter((img) => {
        const src = img.currentSrc || img.src || "";
        return (
          img.naturalWidth > 50 &&
          /^https?:|^blob:/.test(src)
        );
      })
      .sort((a, b) => (b.naturalWidth * b.naturalHeight) - (a.naturalWidth * a.naturalHeight));

    for (const img of imgs) {
      try {
        const resp = await fetch(img.src, { mode: "cors" });
        if (resp.ok) {
          const blob = await resp.blob();
          if (blob.type.startsWith("image/")) {
            setImage(new File([blob], "page-image.jpg", { type: blob.type }));
            return;
          }
        }
      } catch (e) {}
      try {
        const canvas = document.createElement("canvas");
        canvas.width = img.naturalWidth;
        canvas.height = img.naturalHeight;
        canvas.getContext("2d").drawImage(img, 0, 0);
        const blob = await new Promise((res) => canvas.toBlob(res, "image/jpeg", 0.9));
        if (blob) {
          setImage(new File([blob], "page-image.jpg", { type: "image/jpeg" }));
          return;
        }
      } catch (e) {}
    }
    setStatus("Couldn't grab an image from the page — upload one instead.");
  }

  function findComposer() {
    const all = Array.from(
      document.querySelectorAll(
        '[role="dialog"] [contenteditable="true"], ' +
          '[role="dialog"] textarea, ' +
          '[contenteditable="true"][role="textbox"], ' +
          'div[aria-label*="caption" i][contenteditable], ' +
          'textarea[aria-label*="caption" i], ' +
          '#description-textarea, ' +
          'div.ql-editor[contenteditable="true"], ' +
          '.notranslate[contenteditable="true"], ' +
          '[data-placeholder][contenteditable="true"]'
      )
    ).filter((el) => {
      const r = el.getBoundingClientRect();
      return r.width > 40 && r.height > 10 && r.top >= 0;
    });

    const inDialog = all.filter((el) => el.closest('[role="dialog"]'));
    const pool = inDialog.length ? inDialog : all;
    return pool.length ? pool[pool.length - 1] : null;
  }

  function pasteInto(el, text) {
    el.focus();
    try {
      if (document.execCommand("insertText", false, text)) {
        el.dispatchEvent(new InputEvent("input", { bubbles: true, inputType: "insertText", data: text }));
        return true;
      }
    } catch (e) {}
    try {
      el.textContent = text;
      el.dispatchEvent(new InputEvent("input", { bubbles: true, inputType: "insertText", data: text }));
      return true;
    } catch (e) {}
    return false;
  }

  function insertResult() {
    const out = panel.querySelector("#ccpro-out");
    const text = out.value;
    if (!text) return;
    const el = findComposer();
    if (el && pasteInto(el, text)) {
      setStatus("Caption inserted ✓");
    } else {
      navigator.clipboard.writeText(text).then(() => setStatus("Composer not found — caption copied instead ✓"));
    }
  }

  async function generate() {
    const btn = panel.querySelector("#ccpro-gen");
    const desc = panel.querySelector("#ccpro-desc").value.trim();
    const platforms = state.platform ? [state.platform] : ["instagram", "linkedin"];

    let description = desc;
    if (!description && state.image) {
      description = "Analyze the attached image and write a caption for it.";
    }
    if (description) description = `Tone: ${state.tone}. ${description}`;

    if (!description && !state.image) {
      setStatus("Add a description or attach an image first.");
      return;
    }

    let image = null;
    if (state.image) {
      try {
        image = await fileToData(state.image);
      } catch (e) {
        setStatus("Could not read the image file.");
        return;
      }
    }

    btn.disabled = true;
    btn.textContent = "Generating…";
    setStatus("Asking the AI…");

    chrome.runtime.sendMessage(
      {
        type: "GENERATE",
        payload: {
          backendUrl: state.backendUrl,
          description,
          keywords: [],
          platforms,
          temperature: 0.7,
          session_id: "content-" + Date.now(),
          image,
        },
      },
      (resp) => {
        btn.disabled = false;
        btn.textContent = "🚀 Generate Caption";
        if (resp && resp.status === "success") {
          const captions = resp.captions || {};
          const first = platforms.find((p) => captions[p] && captions[p].trim()) || platforms[0];
          const text = captions[first] || "";
          panel.querySelector("#ccpro-meta").textContent = `${PLATFORMS[first].label} · ${resp.provider || ""} ${resp.model || ""}`;
          panel.querySelector("#ccpro-out").value = text;
          panel.querySelector("#ccpro-result").classList.add("open");
          setStatus("Caption ready ✓");
        } else {
          setStatus("");
          panel.querySelector("#ccpro-result").classList.remove("open");
          const err = (resp && resp.detail) || "Generation failed. Is the backend running?";
          panel.querySelector("#ccpro-status").innerHTML = `<div class="ccpro-err">⚠️ ${err}</div>`;
        }
      }
    );
  }

  function fileToData(file) {
    return new Promise((resolve, reject) => {
      const reader = new FileReader();
      reader.onload = () =>
        resolve({ name: file.name, mime: file.type || "image/jpeg", data: reader.result });
      reader.onerror = reject;
      reader.readAsArrayBuffer(file);
    });
  }

  chrome.runtime.onMessage.addListener((msg, sender, sendResponse) => {
    if (msg && msg.type === "INSERT_CAPTION") {
      const el = findComposer();
      if (el && pasteInto(el, msg.text)) {
        sendResponse({ ok: true });
      } else {
        navigator.clipboard.writeText(msg.text).then(() => sendResponse({ ok: false }));
        return true;
      }
      return true;
    }
    if (msg && msg.type === "CCPRO_STATUS") {
      sendResponse({ running: true });
      return true;
    }
    return false;
  });

  chrome.storage.local.get(["backendUrl"]).then((stored) => {
    if (stored.backendUrl) state.backendUrl = stored.backendUrl;
  });

  state.platform = detectPlatform();
  buildUI();
})();