/* ==============================================================================
   CaptionGen Pro - Frontend Logic
   Auto-detects the active LLM provider from .env keys and handles generation,
   image upload, tabs, copy/download, brand voice and history.
   ============================================================================== */

(function () {
  "use strict";

  const $ = (sel) => document.querySelector(sel);
  const $$ = (sel, scope) => Array.from((scope || document).querySelectorAll(sel));

  const PLATFORMS = ["instagram", "facebook", "linkedin", "variation_1", "variation_2"];

  // Platforms currently generated / visible (a subset of PLATFORMS).
  let activePlatforms = PLATFORMS.slice();

  // Holds the latest generated model (for the output metadata).
  let currentModel = null;
  let uploadedFile = null;

  // Session-scoped identity & generation tracking
  function getSessionId() {
    let sid = sessionStorage.getItem("cg-session-id");
    if (!sid) {
      sid =
        (window.crypto && crypto.randomUUID && crypto.randomUUID()) ||
        "s-" + Date.now().toString(36) + "-" + Math.random().toString(36).slice(2);
      sessionStorage.setItem("cg-session-id", sid);
    }
    return sid;
  }
  const sessionId = getSessionId();
  let captionsDirty = false;
  let currentGen = null; // { description, keywords, provider, model } of current output

  /* ---------------------------------------------------------------------
     Toast notifications
     --------------------------------------------------------------------- */
  let toastTimer = null;
  function showToast(message, type = "success") {
    const toast = $("#toast-notification");
    const msg = $("#toast-message");
    const icon = toast.querySelector(".toast-icon");
    msg.textContent = message;
    icon.className = "bx toast-icon";
    icon.classList.add(type === "error" ? "bx-x-circle" : "bx-check-circle");
    toast.classList.remove("hidden");
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => toast.classList.add("hidden"), 3200);
  }

  /* ---------------------------------------------------------------------
     Theme toggle
     --------------------------------------------------------------------- */
  function initTheme() {
    const saved = localStorage.getItem("cg-theme");
    const btn = $("#theme-toggle-btn");
    if (saved === "light" || saved === "dark") {
      document.documentElement.setAttribute("data-theme", saved);
    }
    btn.addEventListener("click", () => {
      const root = document.documentElement;
      const next = root.getAttribute("data-theme") === "dark" ? "light" : "dark";
      root.setAttribute("data-theme", next);
      localStorage.setItem("cg-theme", next);
    });
  }

  /* ---------------------------------------------------------------------
     Config / key availability check
     --------------------------------------------------------------------- */
  async function loadConfig() {
    try {
      const res = await fetch("/api/config");
      if (!res.ok) throw new Error("Could not load config");
      const data = await res.json();

      // Warning when nothing is configured
      const anyConfigured = (data.providers || []).some((p) => p.configured);
      if (!anyConfigured) {
        showToast("No API key found in .env — add one to use the generator.", "error");
      }
    } catch (err) {
      console.error(err);
      showToast("Could not contact the backend.", "error");
    }
  }

  /* ---------------------------------------------------------------------
     Creativity slider
     --------------------------------------------------------------------- */
  function initTemperature() {
    const slider = $("#temp-slider");
    slider.addEventListener("input", () => {
      $("#temp-val").textContent = slider.value;
    });
    $("#temp-val").textContent = slider.value;
  }

  /* ---------------------------------------------------------------------
     Keyword tags
     --------------------------------------------------------------------- */
  const keywordSet = new Set();

  function addTag(text) {
    const clean = text.trim().replace(/^#/, "");
    if (!clean || keywordSet.has(clean)) return;
    keywordSet.add(clean);

    const badge = document.createElement("span");
    badge.className = "tag-badge";
    badge.textContent = "#" + clean;
    const close = document.createElement("i");
    close.className = "bx bx-x";
    close.addEventListener("click", () => {
      keywordSet.delete(clean);
      badge.remove();
    });
    badge.appendChild(close);
    $("#tags-badge-list").appendChild(badge);
  }

  function initTags() {
    const input = $("#keyword-input");
    input.addEventListener("keydown", (e) => {
      if (e.key === "Enter" || e.key === ",") {
        e.preventDefault();
        addTag(input.value);
        input.value = "";
      }
    });
    input.addEventListener("blur", () => {
      if (input.value.trim()) {
        addTag(input.value);
        input.value = "";
      }
    });
  }

  /* ---------------------------------------------------------------------
     Image upload (drag & drop + browse + preview)
     --------------------------------------------------------------------- */
  function initImageUpload() {
    const zone = $("#image-drop-zone");
    const fileInput = $("#image-upload-file");
    const preview = $("#image-preview-container");
    const previewImg = $("#image-preview-img");

    function acceptFile(file) {
      if (!file) return;
      if (!file.type.startsWith("image/")) {
        showToast("Please choose an image file (JPG, PNG, WEBP).", "error");
        return;
      }
      if (file.size > 5 * 1024 * 1024) {
        showToast("Image is too large (max 5 MB).", "error");
        return;
      }
      uploadedFile = file;
      previewImg.src = URL.createObjectURL(file);
      preview.classList.remove("hidden");
      zone.querySelector(".drop-zone-prompt").style.display = "none";
    }

    function clearPreview() {
      uploadedFile = null;
      fileInput.value = "";
      preview.classList.add("hidden");
      previewImg.src = "";
      zone.querySelector(".drop-zone-prompt").style.display = "";
    }

    // Browse via hidden input (click on the zone opens the file picker)
    zone.addEventListener("click", () => fileInput.click());
    fileInput.addEventListener("change", () => acceptFile(fileInput.files[0]));

    // Drag & drop
    ["dragenter", "dragover"].forEach((ev) =>
      zone.addEventListener(ev, (e) => {
        e.preventDefault();
        zone.classList.add("drag-over");
      })
    );
    ["dragleave", "drop"].forEach((ev) =>
      zone.addEventListener(ev, (e) => {
        e.preventDefault();
        zone.classList.remove("drag-over");
      })
    );
    zone.addEventListener("drop", (e) => acceptFile(e.dataTransfer.files && e.dataTransfer.files[0]));

    // Remove image
    $("#btn-remove-preview").addEventListener("click", (e) => {
      e.stopPropagation();
      clearPreview();
    });
  }

  /* ---------------------------------------------------------------------
     Loader / output visibility
     --------------------------------------------------------------------- */
  function setLoading(on, text) {
    if (on) {
      $("#output-placeholder").classList.add("hidden");
      $("#captions-results-container").classList.add("hidden");
      const loader = $("#generation-loader");
      loader.classList.remove("hidden");
      if (text) $("#loader-status-text").textContent = text;
    } else {
      $("#generation-loader").classList.add("hidden");
    }
  }

  /* ---------------------------------------------------------------------
     Generation
     --------------------------------------------------------------------- */
  function getSelectedPlatforms() {
    return $$(".platform-check").filter((cb) => cb.checked).map((cb) => cb.value);
  }

  function setActivePlatforms(platforms) {
    activePlatforms = (platforms || []).filter((p) => PLATFORMS.includes(p));
    if (!activePlatforms.length) activePlatforms = PLATFORMS.slice();

    $$(".tab-btn").forEach((btn) => {
      btn.classList.toggle("hidden", !activePlatforms.includes(btn.dataset.platform));
    });
    $$(".tab-pane").forEach((pane) => {
      pane.classList.toggle("hidden", !activePlatforms.includes(pane.id.replace("pane-", "")));
    });

    // If the currently active tab was hidden, switch to the first visible one
    const activeBtn = $(".tab-btn.active");
    if (activeBtn && !activePlatforms.includes(activeBtn.dataset.platform)) {
      const first = $$(".tab-btn").find((b) => activePlatforms.includes(b.dataset.platform));
      if (first) {
        $$(".tab-btn").forEach((b) => b.classList.remove("active"));
        $$(".tab-pane").forEach((p) => p.classList.remove("active"));
        first.classList.add("active");
        const pane = $("#pane-" + first.dataset.platform);
        if (pane) pane.classList.add("active");
      }
    }
  }

  async function handleGenerate(e) {
    e.preventDefault();

    const description = $("#prompt-desc").value.trim();
    const keywords = Array.from(keywordSet).join(", ");
    const temperature = $("#temp-slider").value;
    const selectedPlatforms = getSelectedPlatforms();

    if (!description && !uploadedFile) {
      showToast("Please add a description or upload an image.", "error");
      return;
    }
    if (!selectedPlatforms.length) {
      showToast("Please select at least one platform.", "error");
      return;
    }

    const fd = new FormData();
    fd.append("description", description);
    fd.append("keywords", keywords);
    fd.append("temperature", temperature);
    fd.append("platforms", selectedPlatforms.join(","));
    fd.append("session_id", sessionId);
    if (uploadedFile) fd.append("image", uploadedFile);

    setLoading(true, uploadedFile ? "AI is analyzing your image…" : "AI is reading guidelines…");

    const btn = $("#btn-submit-generate");
    const spinner = $("#btn-spinner");
    btn.disabled = true;
    spinner.classList.remove("hidden");

    try {
      const res = await fetch("/api/generate", { method: "POST", body: fd });
      const data = await res.json().catch(() => ({}));

      if (!res.ok || data.status === "error") {
        throw new Error(data.detail || "Generation failed. Please try again.");
      }

      currentModel = data.model || data.provider || "";
      currentGen = {
        description,
        keywords: keywords ? keywords.split(",").map((k) => k.trim()).filter(Boolean) : [],
        provider: data.provider || "",
        model: data.model || "",
      };
      captionsDirty = false;
      renderCaptions(data.captions || {});
      showToast("Your captions are ready!");
    } catch (err) {
      showToast(err.message || "Generation failed.", "error");
      // Restore placeholder for a clean retry
      setLoading(false);
      $("#output-placeholder").classList.remove("hidden");
    } finally {
      btn.disabled = false;
      spinner.classList.add("hidden");
    }
  }

  /* ---------------------------------------------------------------------
     Rendering captions
     --------------------------------------------------------------------- */
  function countHashtags(text) {
    const m = text.match(/(?:^|\s)#[\wÀ-ÿ]+/g);
    return m ? m.length : 0;
  }

  function renderCaptions(captions) {
    const platforms = Object.keys(captions || {}).filter((p) => PLATFORMS.includes(p));
    setActivePlatforms(platforms.length ? platforms : activePlatforms);
    activePlatforms.forEach((p) => {
      const text = captions[p] || "";
      const ta = $("#text-" + p);
      if (ta) {
        ta.value = text;
        ta.setAttribute("readonly", "readonly");
        ta.classList.remove("editable");
      }
      const cc = $("#char-count-" + p);
      if (cc) cc.textContent = `Characters: ${text.length}`;
      const hc = $("#hashtag-count-" + p);
      if (hc) hc.textContent = `Hashtags: ${countHashtags(text)}`;
    });
    $("#captions-results-container").classList.remove("hidden");
    updateCountBadges();
  }

  function updateCountBadges() {
    activePlatforms.forEach((p) => {
      const ta = $("#text-" + p);
      if (!ta) return;
      const text = ta.value || "";
      $("#char-count-" + p).textContent = `Characters: ${text.length}`;
      $("#hashtag-count-" + p).textContent = `Hashtags: ${countHashtags(text)}`;
    });
  }

  /* ---------------------------------------------------------------------
     Tabs
     --------------------------------------------------------------------- */
  function initTabs() {
    const tabs = $$(".tab-btn");
    const content = $("#captions-tabs-content");
    tabs.forEach((btn) => {
      btn.addEventListener("click", () => {
        tabs.forEach((b) => b.classList.remove("active"));
        $$(".tab-pane", content).forEach((p) => p.classList.remove("active"));
        btn.classList.add("active");
        const pane = $("#pane-" + btn.dataset.platform);
        if (pane) pane.classList.add("active");
      });
    });
  }

  /* ---------------------------------------------------------------------
     Edit toggle for caption textareas
     --------------------------------------------------------------------- */
  let editActive = false;
  function initEditToggles() {
    $$(".btn-edit-toggle").forEach((btn) => {
      btn.addEventListener("click", () => {
        const ta = $("#text-" + btn.dataset.platform);
        if (!ta) return;
        if (editActive) {
          ta.setAttribute("readonly", "readonly");
          ta.classList.remove("editable");
          editActive = false;
          btn.querySelector("i").className = "bx bx-edit";
          if (btn.lastChild) btn.lastChild.textContent = " Edit";
        } else {
          ta.removeAttribute("readonly");
          ta.classList.add("editable");
          editActive = true;
          btn.querySelector("i").className = "bx bx-check";
          if (btn.lastChild) btn.lastChild.textContent = " Done";
        }
      });
    });
  }

  /* ---------------------------------------------------------------------
     New Generation (save current captions, then start fresh)
     --------------------------------------------------------------------- */
  function initCaptionDirtyTracking() {
    PLATFORMS.forEach((p) => {
      const ta = $("#text-" + p);
      if (ta) ta.addEventListener("input", () => { captionsDirty = true; });
    });
  }

  function currentCaptions() {
    const out = {};
    activePlatforms.forEach((p) => {
      const ta = $("#text-" + p);
      if (ta) out[p] = ta.value || "";
    });
    return out;
  }

  function hasCaptions() {
    return activePlatforms.some((p) => {
      const ta = $("#text-" + p);
      return ta && ta.value.trim();
    });
  }

  async function handleNewGeneration() {
    if (hasCaptions() && captionsDirty) {
      try {
        const res = await fetch("/api/history/save", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            session_id: sessionId,
            description: (currentGen && currentGen.description) || "Edited captions",
            keywords: (currentGen && currentGen.keywords) || [],
            provider: (currentGen && currentGen.provider) || currentModel || "",
            model: (currentGen && currentGen.model) || currentModel || "",
            captions: currentCaptions(),
          }),
        });
        if (res.ok) showToast("Current captions saved to history.");
      } catch {
        showToast("Could not save current captions.", "error");
      }
    }

    resetWorkspace();
  }

  function resetWorkspace() {
    // Clear inputs
    $("#prompt-desc").value = "";
    keywordSet.clear();
    $("#tags-badge-list").innerHTML = "";
    $("#keyword-input").value = "";
    // Clear image preview
    if (uploadedFile) {
      const preview = $("#image-preview-container");
      const zone = $("#image-drop-zone");
      uploadedFile = null;
      $("#image-upload-file").value = "";
      preview.classList.add("hidden");
      $("#image-preview-img").src = "";
      zone.querySelector(".drop-zone-prompt").style.display = "";
    }
    // Reset platform selection & restore all tabs
    $$(".platform-check").forEach((cb) => { cb.checked = true; });
    setActivePlatforms(PLATFORMS);
    // Clear output
    PLATFORMS.forEach((p) => {
      const ta = $("#text-" + p);
      if (ta) ta.value = "";
    });
    currentModel = null;
    currentGen = null;
    captionsDirty = false;
    $("#output-placeholder").classList.remove("hidden");
    $("#generation-loader").classList.add("hidden");
    $("#captions-results-container").classList.add("hidden");
    updateCountBadges();
    $("#prompt-desc").focus();
  }

  /* ---------------------------------------------------------------------
     Copy & download
     --------------------------------------------------------------------- */
  function copyToClipboard(text) {
    if (navigator.clipboard && navigator.clipboard.writeText) {
      return navigator.clipboard.writeText(text);
    }
    return new Promise((resolve, reject) => {
      const tmp = document.createElement("textarea");
      tmp.value = text;
      document.body.appendChild(tmp);
      tmp.select();
      try {
        document.execCommand("copy");
        resolve();
      } catch (err) {
        reject(err);
      } finally {
        document.body.removeChild(tmp);
      }
    });
  }

  function initCopy() {
    // Per-platform copy
    $$(".copy-single-btn").forEach((btn) => {
      btn.addEventListener("click", async () => {
        const text = $("#text-" + btn.dataset.platform).value;
        if (!text) return showToast("Nothing to copy yet.", "error");
        try {
          await copyToClipboard(text);
          showToast("Caption copied to clipboard!");
        } catch {
          showToast("Could not copy.", "error");
        }
      });
    });

    // Copy all
    $("#copy-all-btn").addEventListener("click", async () => {
      const text = activePlatforms.map((p) => $("#text-" + p).value).filter(Boolean).join("\n\n-----\n\n");
      if (!text) return showToast("Nothing to copy yet.", "error");
      try {
        await copyToClipboard(text);
        showToast("All captions copied!");
      } catch {
        showToast("Could not copy.", "error");
      }
    });

    // Download .txt
    $("#download-txt-btn").addEventListener("click", () => {
      const parts = [];
      const titles = {
        instagram: "Instagram",
        facebook: "Facebook",
        linkedin: "LinkedIn",
        variation_1: "Variation 1 (Alternate Tone)",
        variation_2: "Variation 2 (Alternate CTA)",
      };
      activePlatforms.forEach((p) => {
        const text = $("#text-" + p).value;
        if (!text) return;
        parts.push(`===== ${titles[p]} =====\n\n${text}`);
      });
      if (!parts.length) return showToast("Nothing to download yet.", "error");
      const blob = new Blob([parts.join("\n\n\n")], { type: "text/plain;charset=utf-8" });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = "captions.txt";
      a.click();
      URL.revokeObjectURL(url);
      showToast("Downloaded captions.txt");
    });
  }

  /* ---------------------------------------------------------------------
     Brand voice editor
     --------------------------------------------------------------------- */
  async function loadBrandVoice() {
    try {
      const res = await fetch("/api/brand-voice");
      const data = await res.json();
      $("#brand-voice-editor").value = data.brand_voice || "";
    } catch {
      $("#brand-voice-editor").value = "";
    }
  }

  function initBrandVoice() {
    $("#save-voice-btn").addEventListener("click", async () => {
      const brandVoice = $("#brand-voice-editor").value;
      try {
        const res = await fetch("/api/brand-voice", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ brand_voice: brandVoice }),
        });
        if (!res.ok) throw new Error();
        const status = $("#voice-save-status");
        status.textContent = "Saved ✓";
        status.className = "save-status-text success";
        setTimeout(() => {
          status.textContent = "";
          status.className = "save-status-text";
        }, 2000);
      } catch {
        $("#voice-save-status").textContent = "Could not save.";
        $("#voice-save-status").className = "save-status-text error";
      }
    });
  }

  /* ---------------------------------------------------------------------
     History drawer
     --------------------------------------------------------------------- */
  const HISTORY_LABELS = {
    instagram: "Instagram",
    facebook: "Facebook",
    linkedin: "LinkedIn",
    variation_1: "Variation 1",
    variation_2: "Variation 2",
  };

  function initHistory() {
    $("#history-toggle-btn").addEventListener("click", openHistory);
    $("#history-close-btn").addEventListener("click", closeHistory);
    $("#history-overlay").addEventListener("click", closeHistory);
    $("#history-clear-btn").addEventListener("click", handleClearHistory);
    document.addEventListener("keydown", (e) => {
      if (e.key === "Escape") closeHistory();
    });
  }

  function openHistory() {
    $("#history-overlay").classList.add("active");
    $("#history-drawer").classList.add("active");
    loadHistory();
  }

  function closeHistory() {
    $("#history-overlay").classList.remove("active");
    $("#history-drawer").classList.remove("active");
  }

  async function loadHistory() {
    const container = $("#history-list-container");
    container.innerHTML = `<p class="history-empty">Loading history…</p>`;
    try {
      const res = await fetch("/api/history?session_id=" + encodeURIComponent(sessionId));
      const data = await res.json();
      renderHistory(Array.isArray(data) ? data : []);
    } catch {
      container.innerHTML = `<p class="history-empty">Could not load history.</p>`;
    }
  }

  async function deleteHistoryEntry(id) {
    try {
      const res = await fetch("/api/history/delete", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ session_id: sessionId, id }),
      });
      if (!res.ok) throw new Error();
      showToast("History entry deleted.");
      loadHistory();
    } catch {
      showToast("Could not delete entry.", "error");
    }
  }

  async function handleClearHistory() {
    if (!confirm("Delete ALL of your history? This cannot be undone.")) return;
    try {
      const res = await fetch("/api/history/clear", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ session_id: sessionId }),
      });
      if (!res.ok) throw new Error();
      showToast("All history cleared.");
      loadHistory();
    } catch {
      showToast("Could not clear history.", "error");
    }
  }

  function renderHistory(entries) {
    const container = $("#history-list-container");
    if (!entries.length) {
      container.innerHTML = `<p class="history-empty">No generations yet. Create one to see it here.</p>`;
      return;
    }
    container.innerHTML = "";
    entries.forEach((entry, idx) => {
      const card = document.createElement("div");
      card.className = "history-card";
      const when = new Date(entry.timestamp).toLocaleString();
      card.innerHTML = `
        <div class="history-meta">
          <span class="history-provider-badge">${escapeHtml(entry.provider)}</span>
          <span class="history-time">${escapeHtml(when)}</span>
        </div>
        <div class="history-desc">${escapeHtml(entry.description || "(Image-based generation)")}</div>
        ${keywordsHtml(entry)}
        <div class="history-actions">
          <button class="btn btn-icon-small btn-load-history" data-idx="${idx}"><i class="bx bx-show"></i> View</button>
          <button class="btn btn-icon-small btn-danger btn-delete-history" data-id="${escapeHtml(entry.id)}"><i class="bx bx-trash"></i> Delete</button>
        </div>
      `;
      container.appendChild(card);
    });

    $$(".btn-load-history", container).forEach((btn) => {
      btn.addEventListener("click", () => {
        const entry = entries[Number(btn.dataset.idx)];
        if (entry && entry.captions) {
          currentGen = {
            description: entry.description || "",
            keywords: entry.keywords || [],
            provider: entry.provider || "",
            model: entry.model || "",
          };
          captionsDirty = false;
          currentModel = entry.model || "";
          renderCaptions(entry.captions);
          closeHistory();
          showToast("Loaded from history.");
        }
      });
    });

    $$(".btn-delete-history", container).forEach((btn) => {
      btn.addEventListener("click", (e) => {
        e.stopPropagation();
        deleteHistoryEntry(btn.dataset.id);
      });
    });
  }

  function keywordsHtml(entry) {
    if (!entry.keywords || !entry.keywords.length) return "";
    const tags = entry.keywords
      .map((k) => `<span class="history-tag-badge">#${escapeHtml(k)}</span>`)
      .join("");
    return `<div class="history-tags">${tags}</div>`;
  }

  function escapeHtml(str) {
    const d = document.createElement("div");
    d.textContent = str == null ? "" : String(str);
    return d.innerHTML;
  }

  /* ---------------------------------------------------------------------
     Bootstrap
     --------------------------------------------------------------------- */
  document.addEventListener("DOMContentLoaded", () => {
    initTheme();
    initTemperature();
    initTags();
    initImageUpload();
    initTabs();
    initCopy();
    initEditToggles();
    initCaptionDirtyTracking();
    initBrandVoice();
    initHistory();
    loadBrandVoice();
    loadConfig();

    $("#generator-form").addEventListener("submit", handleGenerate);
    $("#new-gen-btn").addEventListener("click", handleNewGeneration);
  });
})();