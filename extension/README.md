# CaptionGen Pro — Browser Extension

A Chrome (Manifest V3) companion to the **Social Media Caption Generator** app. It auto-detects the platform and tone from the URL you're on (Instagram, LinkedIn, Facebook, X/Twitter, YouTube) and generates captions — from a photo or a quick description — without leaving the page.

## What it does

- **Popup** (click the toolbar icon): detects the current site's platform & tone, lets you attach an image / paste details / pick tone & platforms, and shows copy-ready captions. Each caption has a **Copy** and a **Paste into page** button.
- **In-page button** (a "CC" bubble at the bottom-right on supported sites): opens a mini panel inside the composer page, can grab the image you already attached to your post ("Use page image"), generates a caption for that platform, and **inserts it directly into the composer's caption box**.
- Backend URL is configurable and persisted (footer of the popup, default `http://127.0.0.1:8000`).

## How it decides tone from the URL

| URL | Platform | Auto tone |
|---|---|---|
| instagram.com | Instagram | Casual & Visual |
| linkedin.com | LinkedIn | Professional |
| facebook.com | Facebook | Friendly |
| x.com / twitter.com | X / Twitter | Punchy & Conversational |
| youtube.com | YouTube | Storytelling |

The detected tone is sent to the generator (prepended as `Tone: <tone>` to the prompt). You can override it in the popup.

## Requirements

- The **backend must be running** (`python app.py` from the repo root → `http://127.0.0.1:8000`), or point the extension at any deployed instance of the app.
- A vision-capable API key in `.env` if you want image-based captioning (see the main `README.md`).

## Install (load unpacked)

1. Open `chrome://extensions`
2. Enable **Developer mode** (top-right)
3. Click **Load unpacked** and select this `extension/` folder
4. Pin the icon and open it on Instagram/LinkedIn/etc.

## Files

```
extension/
├── manifest.json        # MV3 manifest (permissions: tabs, storage)
├── background.js        # Service worker → calls /api/generate & /api/config
├── popup/               # Toolbar popup (detect, generate, copy/paste)
├── content/             # In-page "CC" button + composer insertion
└── icons/               # 16 / 48 / 128 px icons
```

## Notes & limitations

- The in-page "insert into composer" relies on each site's editable caption element (contenteditable/textarea selectors). Social networks change markup often — if insertion stops working, the extension automatically **copies the caption to your clipboard** instead.
- Image grabbing from the page is best-effort; if a site blocks it, upload the image directly.
- The extension talks to your backend over `http://127.0.0.1` — Chrome allows this because the manifest grants host permission for `http://127.0.0.1/*` and `http://localhost/*`. If you host the backend elsewhere, update the URL in the popup (and, if needed, add the domain to `host_permissions` in `manifest.json`).
