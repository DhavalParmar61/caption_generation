# 🚀 Social Media Caption Generator

A CLI tool that generates platform-specific social media captions from a product or photo description using Gemini, OpenAI, or Anthropic (Claude) LLM APIs.

It produces **five ready-to-use captions** (Instagram, Facebook, LinkedIn, plus two alternate tone/CTA variations) that are customized using a brand voice guide and relevant hashtags. The output is styled with rich terminal panels for visual clarity.

---

## ✨ Features

- **Flexible Inputs**: Pass descriptions and keywords via command-line arguments, read from a text file, or use the guided interactive wizard.
- **Multi-Provider Support**: Out-of-the-box support for **Google Gemini**, **OpenAI**, and **Anthropic (Claude)**.
- **Brand Voice Consistency**: Uses a custom `brand_voice.txt` rules file and reference examples to maintain consistent tone, structure, and formatting.
- **Rich Terminal Output**: Renders beautifully styled panels using color coding for each platform.
- **Persisted History**: Saves all generated captions and request inputs with timestamps to `history.json` for easy retrieval.
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

---

## 📜 Generation History

Every successful generation is appended to `history.json` under the project root. This file logs:
- Exact inputs (description, keywords)
- Model & provider metadata
- ISO Timestamp
- Parsed text for all 5 generated variations
