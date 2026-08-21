const PLATFORMS = {
  instagram: { label: "Instagram", icon: "📸", tone: "Casual & Visual" },
  facebook: { label: "Facebook", icon: "👥", tone: "Friendly" },
  linkedin: { label: "LinkedIn", icon: "💼", tone: "Professional" },
  twitter: { label: "X / Twitter", icon: "🐦", tone: "Punchy & Conversational" },
  youtube: { label: "YouTube", icon: "▶️", tone: "Storytelling" },
};

const HOST_RULES = [
  { host: "instagram.com", platform: "instagram" },
  { host: "linkedin.com", platform: "linkedin" },
  { host: "facebook.com", platform: "facebook" },
  { host: "x.com", platform: "twitter" },
  { host: "twitter.com", platform: "twitter" },
  { host: "youtube.com", platform: "youtube" },
];

const TONE_OPTIONS = [
  "Professional",
  "Friendly",
  "Casual & Visual",
  "Bold & Punchy",
  "Humorous",
  "Minimalist",
];

const state = {
  backendUrl: "http://127.0.0.1:8000",
  platform: null,
  tone: "Friendly",
  selected: [],
  image: null,
  results: null,
};

const $ = (id) => document.getElementById(id);

function detectFromUrl(url) {
  try {
    const host = new URL(url).hostname.toLowerCase();
    for (const rule of HOST_RULES) {
      if (host === rule.host || host.endsWith("." + rule.host)) {
        return rule.platform;
      }
    }
  } catch (e) {}
  return null;
}

function initPlatformChips() {
  const wrap = $("platform-chips");
  wrap.innerHTML = "";
  for (const [id, meta] of Object.entries(PLATFORMS)) {
    const chip = document.createElement("span");
    chip.className = "chip" + (state.selected.includes(id) ? " active" : "");
    chip.textContent = meta.icon + " " + meta.label;
    chip.dataset.platform = id;
    chip.addEventListener("click", () => {
      const i = state.selected.indexOf(id);
      if (i >= 0) {
        state.selected.splice(i, 1);
        chip.classList.remove("active");
      } else {
        state.selected.push(id);
        chip.classList.add("active");
      }
    });
    wrap.appendChild(chip);
  }
}

function initToneSelect() {
  const sel = $("tone-select");
  sel.innerHTML = "";
  const auto = document.createElement("option");
  auto.value = "__auto__";
  auto.textContent = `Auto (${state.tone})`;
  sel.appendChild(auto);
  for (const t of TONE_OPTIONS) {
    const opt = document.createElement("option");
    opt.value = t;
    opt.textContent = t;
    sel.appendChild(opt);
  }
}

function setDetected(platform) {
  const platEl = $("detect-platform");
  const toneEl = $("detect-tone");
  if (platform) {
    const meta = PLATFORMS[platform];
    state.platform = platform;
    state.tone = meta.tone;
    platEl.textContent = "Detected: " + meta.label;
    toneEl.textContent = "Auto tone: " + meta.tone;
    state.selected = [platform];
  } else {
    state.platform = null;
    state.tone = "Friendly";
    platEl.textContent = "General site";
    toneEl.textContent = "Auto tone: Friendly";
    state.selected = ["instagram", "linkedin"];
  }
  initPlatformChips();
  initToneSelect();
}

function countHashtags(text) {
  const m = text.match(/#[A-Za-z0-9_]+/g);
  return m ? m.length : 0;
}

function renderResults(data) {
  const wrap = $("result-list");
  wrap.innerHTML = "";
  if (!data || !data.captions) return;
  let any = false;
  for (const [plat, text] of Object.entries(data.captions)) {
    if (!text || !text.trim()) continue;
    any = true;
    const meta = PLATFORMS[plat] || { label: plat, icon: "•" };
    const card = document.createElement("div");
    card.className = "caption-card";

    const head = document.createElement("div");
    head.className = "card-head";
    head.innerHTML = `<span class="card-title">${meta.icon} ${meta.label}</span>`;
    const mtag = document.createElement("span");
    mtag.className = "card-meta";
    mtag.textContent = `${text.length} chars · ${countHashtags(text)} tags`;
    head.appendChild(mtag);

    const ta = document.createElement("textarea");
    ta.className = "caption-text";
    ta.value = text;

    const actions = document.createElement("div");
    actions.className = "card-actions";
    const copyBtn = document.createElement("button");
    copyBtn.className = "btn-mini copy";
    copyBtn.textContent = "📋 Copy";
    copyBtn.addEventListener("click", () => {
      navigator.clipboard.writeText(ta.value).then(() => {
        copyBtn.textContent = "✅ Copied";
        setTimeout(() => (copyBtn.textContent = "📋 Copy"), 1200);
      });
    });
    const insertBtn = document.createElement("button");
    insertBtn.className = "btn-mini";
    insertBtn.textContent = "↩ Paste into page";
    insertBtn.addEventListener("click", () => {
      chrome.tabs.sendMessage(
        null,
        { type: "INSERT_CAPTION", text: ta.value },
        (resp) => {
          if (chrome.runtime.lastError) {
            copyBtn.textContent = "Open composer first";
            setTimeout(() => (copyBtn.textContent = "📋 Copy"), 1200);
            return;
          }
          insertBtn.textContent = resp && resp.ok ? "✅ Inserted" : "Copied to clipboard";
        }
      );
    });
    actions.appendChild(copyBtn);
    actions.appendChild(insertBtn);

    card.appendChild(head);
    card.appendChild(ta);
    card.appendChild(actions);
    wrap.appendChild(card);
  }

  if (any) {
    $("provider-tag").textContent = `${data.provider || ""} · ${data.model || ""}`.trim();
    $("results").classList.remove("hidden");
  } else {
    showError("The AI returned empty captions. Try again.");
  }
}

function showError(msg) {
  $("result-list").innerHTML = `<div class="error-box">⚠️ ${msg}</div>`;
  $("results").classList.remove("hidden");
}

function checkBackend() {
  chrome.runtime.sendMessage(
    { type: "CHECK_BACKEND", payload: { url: state.backendUrl } },
    (resp) => {
      const dot = $("status-dot");
      const txt = $("status-text");
      if (resp && resp.ok) {
        dot.classList.add("ok");
        txt.textContent = "backend online";
      } else {
        dot.classList.remove("ok");
        txt.textContent = "backend offline";
      }
    }
  );
}

function getTabUrl() {
  return new Promise((resolve) => {
    chrome.tabs.query({ active: true, currentWindow: true }, (tabs) => {
      resolve(tabs && tabs[0] ? tabs[0].url || "" : "");
    });
  });
}

function fileToData(file) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () =>
      resolve({
        name: file.name,
        mime: file.type || "image/jpeg",
        data: reader.result,
      });
    reader.onerror = reject;
    reader.readAsArrayBuffer(file);
  });
}

async function init() {
  const stored = await chrome.storage.local.get(["backendUrl"]);
  if (stored.backendUrl) state.backendUrl = stored.backendUrl;
  $("backend-input").value = state.backendUrl;

  const url = await getTabUrl();
  setDetected(detectFromUrl(url));
  checkBackend();

  $("backend-save").addEventListener("click", () => {
    state.backendUrl = $("backend-input").value.trim() || "http://127.0.0.1:8000";
    chrome.storage.local.set({ backendUrl: state.backendUrl });
    checkBackend();
  });

  $("img-input").addEventListener("change", (e) => {
    const f = e.target.files[0];
    if (!f) return;
    if (f.size > 5 * 1024 * 1024) {
      showError("Image is too large (max 5 MB).");
      return;
    }
    state.image = f;
    $("img-preview-img").src = URL.createObjectURL(f);
    $("img-preview").classList.remove("hidden");
    $("dz-text").textContent = f.name;
  });

  $("img-remove").addEventListener("click", (e) => {
    e.preventDefault();
    state.image = null;
    $("img-input").value = "";
    $("img-preview").classList.add("hidden");
    $("dz-text").textContent = "Click to attach (JPG/PNG/WEBP, max 5MB)";
  });

  $("gen-form").addEventListener("submit", async (e) => {
    e.preventDefault();
    const btn = $("btn-generate");
    const spinner = $("btn-spinner");
    btn.disabled = true;
    spinner.classList.remove("hidden");

    const desc = $("desc-input").value.trim();
    const keywords = $("kw-input").value
      .split(",")
      .map((k) => k.trim())
      .filter(Boolean);
    const tone = $("tone-select").value === "__auto__" ? state.tone : $("tone-select").value;
    const temperature = parseFloat($("temp-input").value);
    const platforms = state.selected.length ? state.selected : Object.keys(PLATFORMS);

    let description = desc;
    if (!description && state.image) description = "Analyze the attached image and write a caption for it.";
    if (description) description = `Tone: ${tone}. ${description}`;

    let image = null;
    if (state.image) {
      try {
        image = await fileToData(state.image);
      } catch (err) {
        showError("Could not read the image file.");
        btn.disabled = false;
        spinner.classList.add("hidden");
        return;
      }
    }

    chrome.runtime.sendMessage(
      {
        type: "GENERATE",
        payload: {
          backendUrl: state.backendUrl,
          description,
          keywords,
          platforms,
          temperature,
          session_id: "ext-" + Date.now(),
          image,
        },
      },
      (resp) => {
        btn.disabled = false;
        spinner.classList.add("hidden");
        if (resp && resp.status === "success") {
          state.results = resp;
          renderResults(resp);
        } else {
          showError((resp && resp.detail) || "Generation failed. Check that the backend is running.");
        }
      }
    );
  });
}

init();