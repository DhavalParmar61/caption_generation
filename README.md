# 🚀 Social Media Caption Generator

A CLI + web tool that generates platform-specific social media captions from a product or photo description using Omniroute (DeepSeek), Gemini, OpenAI, or Anthropic (Claude) LLM APIs.

It produces ready-to-use captions (Instagram, Facebook, LinkedIn, plus two alternate tone/CTA variations) for whichever platforms you select, customized using a brand voice guide and relevant hashtags. The CLI output is styled with rich terminal panels for visual clarity.

---

## ✨ Features

- **Flexible Inputs**: Pass descriptions and keywords via command-line arguments, read from a text file, or use the guided interactive wizard.
- **Multi-Provider Support**: Out-of-the-box support for **Google Gemini**, **OpenAI**, and **Anthropic (Claude)**.
- **Brand Voice Consistency**: Uses a custom `brand_voice.txt` rules file and reference examples to maintain consistent tone, structure, and formatting.
- **Rich Terminal Output**: Renders beautifully styled panels using color coding for each platform.
- **Persisted History**: Saves all generated captions and request inputs with timestamps for easy retrieval.
- **Platform Selection**: Pick exactly which platforms to generate — via the `--platforms` flag in the CLI or checkboxes in the web UI.
- **Session-Scoped Web App**: Run the built-in FastAPI web UI with image upload, per-session history, delete/clear history, and a "New Generation" button.
- **Easy Setup**: Includes double-click automation scripts (`setup.bat` for Windows and `setup.sh` for macOS/Linux).

---

## 📁 Repository Structure

```
caption_generator/
│
├── .env.example          # Template for API keys
├── requirements.txt      # Python package dependencies
├── config.json           # Active provider, default models, and configuration settings
├── brand_voice.txt       # Brand guidelines and caption examples
├── caption_gen.py        # Core tool executable script
├── setup.bat             # Automatic setup script for Windows
├── setup.sh              # Automatic setup script for macOS/Linux
└── README.md             # Documentation
```

---

## 🛠️ Installation & Setup

### Prerequisites
Make sure you have **Python 3.8 or newer** installed.

### Windows (Quick Setup)
1. Double-click the `setup.bat` file.
2. This creates a virtual environment (`.venv`), upgrades pip, installs dependencies, and creates a `.env` file from the template.
3. Open the newly created `.env` file in a text editor and paste your API key (e.g. `GEMINI_API_KEY`, `OPENAI_API_KEY`, or `ANTHROPIC_API_KEY`).

### macOS / Linux (Quick Setup)
1. Open a terminal in the project directory.
2. Make the setup script executable and run it:
   ```bash
   chmod +x setup.sh
   ./setup.sh
   ```
3. Open the newly created `.env` file and configure your API keys.

---

## ⚙️ Configuration

### API Keys (`.env`)
Uncomment and fill in the key for your preferred provider inside the `.env` file:
```env
GEMINI_API_KEY=AIzaSy...
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...
```

### Global Settings (`config.json`)
You can tweak active models, creativity temperature, or target files:
```json
{
  "provider": "gemini",
  "temperature": 0.7,
  "brand_voice_path": "brand_voice.txt",
  "history_path": "history.json",
  "models": {
    "gemini": "gemini-1.5-flash",
    "openai": "gpt-4o-mini",
    "anthropic": "claude-3-5-sonnet-20240620"
  }
}
```

### Customizing Your Brand Voice (`brand_voice.txt`)
Modify `brand_voice.txt` to align the generator with your brand:
- **Tone & Style**: Set rules for hook, emojis, tone wordings, and CTAs.
- **Reference Examples**: Provide 1-2 examples of high-performing captions. The LLM will perform few-shot learning to mimic these structures.

---

## 🚀 How to Run the Tool

Make sure your virtual environment is activated before running:
- **Windows**: `call .venv\Scripts\activate`
- **macOS/Linux**: `source .venv/bin/activate`

### 1. Interactive Prompt Wizard
Run the script without arguments. It will guide you through entering a description and keywords step-by-step:
```bash
python caption_gen.py
```

### 2. Command Line Arguments
Provide inputs directly as flags:
```bash
python caption_gen.py -d "Wireless noise-cancelling headphones with 40h battery" -k "headphones, tech, travel"
```

### 3. Reading from a Text File
If you have long description drafts, place them in a text file (e.g., `input.txt`) and run:
```bash
python caption_gen.py -f input.txt -k "marketing, business, tools"
```

### 4. Overriding Defaults
You can temporarily override the default provider or temperature via arguments:
```bash
# Generate using GPT-4o-mini with higher creativity
python caption_gen.py -d "Organic lavender soap bar" -p openai -m gpt-4o-mini -t 0.9
```

### 5. Choosing Platforms
By default all five caption types are generated. To limit them, pass `--platforms` (comma-separated: `instagram`, `facebook`, `linkedin`, `variation_1`, `variation_2`) — the interactive wizard also asks which platforms you want:
```bash
# Only LinkedIn and the alternate-tone variation
python caption_gen.py -d "Organic lavender soap bar" --platforms linkedin,variation_1
```

---

## 📜 Generation History

History in the **web app** is kept **only for the current browser session** — it is tied to a per-session id (stored in the tab's `sessionStorage`), not to an email or account. Each session sees its own history, and entries live in memory on the server, so they are lost when the tab is closed or the server restarts. You can delete single entries or clear all of it via the history drawer.

(The CLI tool `caption_gen.py` still optionally writes to the plain `history.json` file, ignored by git.)

Each entry logs:
- Exact inputs (description, keywords)
- Model & provider metadata
- ISO Timestamp
- Parsed text for each selected platform/caption

---

## 🌐 Running the Web App

Launch the browser UI (recommended for sharing with others):

```bash
python app.py
```

Then open `http://127.0.0.1:8000`. To bind to a different host/port:

```bash
# Reachable from your local network (others on the same Wi-Fi)
set HOST=0.0.0.0
python app.py
```

### Image uploads need a vision-capable API key
Text-only generation works with any configured provider. **Image upload requires a vision model**, so if your active provider only has text models (e.g. a DeepSeek-only Omniroute key), add a key for a vision-capable provider in `.env` — `GEMINI_API_KEY`, `OPENAI_API_KEY`, or `ANTHROPIC_API_KEY`. When you upload an image, the app automatically uses the first configured vision-capable provider instead of falling back to one that can't see the image.

## 🔗 Sharing with Others via a Public URL

Others must be able to reach your machine, so a tunnel gives them a real URL. The app runs on your PC and the tunnel forwards requests to it.

### Option A: Cloudflare Quick Tunnel (recommended, free, no account needed for ephemeral URL)
1. Download `cloudflared`: https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/downloads/
2. Start the app: `python app.py`
3. In a second terminal: `cloudflared tunnel --url http://localhost:8000`
4. Cloudflare prints a URL like `https://random-words.trycloudflare.com` — share that. Each restart gets a new URL; with a free Cloudflare account and `cloudflared tunnel login` you can get a stable named tunnel.

### Option B: ngrok
1. Install ngrok and run `ngrok config add-authtoken <your-token>` once.
2. `python app.py`, then `ngrok http 8000`.
3. Share the `https://...ngrok.io` URL.

> Note: anyone with the URL can use the app and pay for your API keys, so only share with people you trust or add your own access rules.
