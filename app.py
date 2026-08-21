import os
import json
import time
import uuid
import logging
from datetime import datetime
from typing import Optional, List
from fastapi import FastAPI, HTTPException, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse, HTMLResponse

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("caption_gen_web")

# ---------------------------------------------------------------------------
# Provider registry & auto-detection
# Ordered by display/priority. The app automatically uses whatever provider
# has an API key configured in .env (no manual selection on the UI).
# ---------------------------------------------------------------------------
PROVIDER_INFO = {
    "omniroute": {"label": "Omniroute · DeepSeek", "env": "OMNIROUTE_API_KEY", "icon": "bx-chip"},
    "openai": {"label": "OpenAI", "env": "OPENAI_API_KEY", "icon": "bx-bot"},
    "anthropic": {"label": "Anthropic · Claude", "env": "ANTHROPIC_API_KEY", "icon": "bx-brain"},
    "gemini": {"label": "Google Gemini", "env": "GEMINI_API_KEY", "icon": "bx-planet"},
}
# Auto-selection preference order
PROVIDER_PRIORITY = ["omniroute", "openai", "anthropic", "gemini"]

MAX_IMAGE_SIZE = 5 * 1024 * 1024  # 5 MB


def get_provider_key(provider: str) -> Optional[str]:
    """Return the env var name for a provider, or None."""
    info = PROVIDER_INFO.get(provider)
    return info["env"] if info else None


def provider_has_key(provider: str) -> bool:
    env = get_provider_key(provider)
    return bool(env and os.getenv(env))


def available_providers() -> dict:
    """Return provider -> bool isConfigured based on .env keys."""
    return {p: provider_has_key(p) for p in PROVIDER_INFO}


def get_active_provider(config: dict) -> str:
    """Pick the provider to use: the configured preference if its key exists,
    otherwise the first provider (by priority) that has a key configured."""
    preferred = config.get("provider")
    if provider_has_key(preferred):
        return preferred
    for provider in PROVIDER_PRIORITY:
        if provider_has_key(provider):
            return provider
    return preferred  # if nothing at all, fall back to preference for a clear error


# ---------------------------------------------------------------------------
# Vision model resolution
# Some models (e.g. DeepSeek) cannot "see" images. When an image is uploaded
# we transparently fall back to a vision-capable model on the same endpoint.
# ---------------------------------------------------------------------------
import time
import httpx

_MODEL_LIST_TTL = 300
_model_list_cache = {"ts": 0, "data": {}}


def omniroute_model_list() -> dict:
    """Return {model_id: has_vision} fetched from the Omniroute endpoint (cached)."""
    now = time.time()
    if _model_list_cache["data"] and now - _model_list_cache["ts"] < _MODEL_LIST_TTL:
        return _model_list_cache["data"]
    base = os.getenv("OMNIROUTE_BASE_URL", "http://localhost:20128/v1").rstrip("/")
    try:
        with httpx.Client(timeout=10.0) as client:
            resp = client.get(f"{base}/models")
            resp.raise_for_status()
        data = {
            m["id"]: bool(m.get("capabilities", {}).get("vision"))
            for m in resp.json().get("data", [])
        }
        _model_list_cache["data"] = data
        _model_list_cache["ts"] = now
        return data
    except Exception as e:
        logger.warning(f"Could not fetch model list: {e}")
        return _model_list_cache["data"]


def resolve_image_provider_and_model(provider: str, model_name: str, config: dict, has_image: bool):
    """When an image is sent but the active provider/model can't see images, prefer a
    vision-capable provider/model. Returns (provider, model, used_fallback)."""
    if not has_image:
        return provider, model_name, False

    # Non-omniroute providers already use vision-capable models with their own key.
    if provider != "omniroute":
        return provider, model_name, False

    # Prefer another configured provider that officially supports vision.
    for candidate in ("gemini", "openai", "anthropic"):
        if provider_has_key(candidate):
            return candidate, config["models"].get(candidate, ""), True

    # Otherwise fall back to a vision-capable model on the Omniroute endpoint.
    models = omniroute_model_list()
    if models and not models.get(model_name):
        vision_models = [mid for mid, vis in models.items() if vis and "deepseek" not in mid]
        if vision_models:
            for pref in ("claude-sonnet", "claude-opus", "gpt", "gemini"):
                for mid in vision_models:
                    if pref in mid.lower():
                        return provider, mid, True
            return provider, vision_models[0], True
    return provider, model_name, False

# Import core generation helpers from CLI file
from caption_gen import (
    load_config,
    get_llm_response,
    parse_captions,
    resolve_platforms,
    build_platform_sections,
    filter_captions,
    DEFAULT_CONFIG_PATH,
    DEFAULT_BRAND_VOICE_PATH
)

# ---------------------------------------------------------------------------
# Session-scoped history storage (in-memory)
# History is tied to the current browser session, not to an email/user id,
# and is lost when the server restarts or the session ends.
# ---------------------------------------------------------------------------
SESSION_HISTORY = {}
MAX_ENTRIES_PER_SESSION = 200


def load_session_history(session_id: str) -> list:
    """Load history entries for a single session."""
    session_id = (session_id or "default").strip()
    return SESSION_HISTORY.get(session_id, [])


def set_session_history(session_id: str, entries: list) -> None:
    SESSION_HISTORY[(session_id or "default").strip()] = entries


def save_to_session_history(session_id: str, description, keywords, provider, model_name, captions) -> bool:
    """Insert a new entry at the top of the session's history."""
    session_id = (session_id or "default").strip()
    entry = {
        "id": str(uuid.uuid4()),
        "timestamp": datetime.now().isoformat(),
        "description": description,
        "keywords": keywords,
        "provider": provider,
        "model": model_name,
        "captions": captions,
    }
    history = SESSION_HISTORY.setdefault(session_id, [])
    history.insert(0, entry)
    del history[MAX_ENTRIES_PER_SESSION:]
    return True


app = FastAPI(
    title="Social Media Caption Generator API",
    description="Backend API for generating platform-specific captions with image and text inputs."
)

# Allow CORS for development flexibility
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Ensure data directories or templates exist
if not os.path.exists(DEFAULT_BRAND_VOICE_PATH):
    default_voice = (
        "Tone: Friendly, professional, and engaging.\n"
        "Formatting: Clear paragraphs, use relevant emojis, and end with a strong Call-to-Action (CTA).\n"
        "Reference Examples:\n"
        "1. 🚀 Ready to level up your workflow? Discover our new dashboard designed to save you hours every week. Link in bio! #productivity #saas #tools\n"
    )
    try:
        with open(DEFAULT_BRAND_VOICE_PATH, "w", encoding="utf-8") as f:
            f.write(default_voice)
    except Exception as e:
        logger.error(f"Error creating default brand voice file: {e}")


@app.get("/api/config")
def get_config():
    """Retrieve active configurations and auto-detected provider status."""
    try:
        config = load_config()
        active_provider = get_active_provider(config)
        return {
            "config": config,
            "active_provider": active_provider,
            "provider_label": PROVIDER_INFO[active_provider]["label"],
            "provider_model": config["models"].get(active_provider, ""),
            "providers": [
                {
                    "id": provider,
                    "label": PROVIDER_INFO[provider]["label"],
                    "configured": available,
                    "active": provider == active_provider,
                }
                for provider, available in available_providers().items()
            ],
        }
    except Exception as e:
        logger.error(f"Error loading config: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/config")
def update_config(config_data: dict):
    """Save configuration updates."""
    try:
        config = load_config()
        # Update config fields
        if "provider" in config_data:
            if config_data["provider"] not in PROVIDER_INFO:
                raise HTTPException(status_code=400, detail=f"Unknown provider '{config_data['provider']}'.")
            config["provider"] = config_data["provider"]
        if "temperature" in config_data:
            config["temperature"] = float(config_data["temperature"])
        if "models" in config_data and isinstance(config_data["models"], dict):
            for k, v in config_data["models"].items():
                if k in PROVIDER_INFO:
                    config["models"][k] = v
                
        with open(DEFAULT_CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=2)
            
        return {"status": "success", "config": config}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating config: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/brand-voice")
def get_brand_voice():
    """Retrieve brand voice guidelines."""
    try:
        if os.path.exists(DEFAULT_BRAND_VOICE_PATH):
            with open(DEFAULT_BRAND_VOICE_PATH, "r", encoding="utf-8") as f:
                return {"brand_voice": f.read()}
        return {"brand_voice": ""}
    except Exception as e:
        logger.error(f"Error loading brand voice: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/brand-voice")
def update_brand_voice(payload: dict):
    """Save brand voice guidelines."""
    try:
        brand_voice = payload.get("brand_voice", "")
        with open(DEFAULT_BRAND_VOICE_PATH, "w", encoding="utf-8") as f:
            f.write(brand_voice)
        return {"status": "success"}
    except Exception as e:
        logger.error(f"Error saving brand voice: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/history")
def get_history(session_id: str = ""):
    """Retrieve generation history for the current session."""
    return load_session_history(session_id)


@app.post("/api/history/delete")
def delete_history_entry(payload: dict):
    """Delete a single history entry for the session by its id."""
    session_id = payload.get("session_id", "")
    entry_id = payload.get("id", "")
    if not entry_id:
        raise HTTPException(status_code=400, detail="Missing entry id.")
    history = load_session_history(session_id)
    remaining = [h for h in history if h.get("id") != entry_id]
    if len(remaining) == len(history):
        raise HTTPException(status_code=404, detail="Entry not found.")
    set_session_history(session_id, remaining)
    return {"status": "success"}


@app.post("/api/history/clear")
def clear_history(payload: dict):
    """Delete all history entries for the session."""
    session_id = (payload.get("session_id", "") or "default").strip()
    SESSION_HISTORY.pop(session_id, None)
    return {"status": "success"}


@app.post("/api/history/save")
def save_history_entry(payload: dict):
    """Save an arbitrary set of captions (e.g. edited ones) to the session's history."""
    captions = payload.get("captions") or {}
    if not isinstance(captions, dict):
        captions = {}
    description = payload.get("description") or "(Image-based Generation)"
    keywords = payload.get("keywords") or []
    provider = payload.get("provider") or ""
    model_name = payload.get("model") or ""
    save_to_session_history(payload.get("session_id", ""), description, keywords, provider, model_name, captions)
    return {"status": "success"}


@app.post("/api/generate")
async def generate_captions(
    description: Optional[str] = Form(None),
    keywords: Optional[str] = Form(None),
    provider: Optional[str] = Form(None),
    model: Optional[str] = Form(None),
    temperature: Optional[float] = Form(None),
    image: Optional[UploadFile] = File(None),
    platforms: Optional[str] = Form(None),
    session_id: Optional[str] = Form(None)
):
    """Generate platform-specific captions with text guidelines and optional image upload."""
    has_image = False
    try:
        # Load base configuration
        config = load_config()

        # Auto-detect the provider when none is explicitly given
        active_provider = (provider or get_active_provider(config)).lower()
        if active_provider not in PROVIDER_INFO:
            return JSONResponse(
                status_code=400,
                content={"status": "error", "detail": f"Unknown provider '{active_provider}'."}
            )

        # Friendly error if the auto-selected provider has no key configured
        if not provider_has_key(active_provider):
            label = PROVIDER_INFO[active_provider]["label"]
            return JSONResponse(
                status_code=400,
                content={
                    "status": "error",
                    "detail": (
                        f"No API key is configured for {label}. "
                        f"Add {PROVIDER_INFO[active_provider]['env']} to your '.env' file, "
                        "or configure a key for another provider."
                    )
                }
            )

        active_model = model or config["models"].get(active_provider)
        active_temp = temperature if temperature is not None else config["temperature"]
        
        # Build keywords list
        keywords_list = []
        if keywords:
            keywords_list = [kw.strip() for kw in keywords.split(",") if kw.strip()]
        keywords_str = ", ".join(keywords_list) if keywords_list else "None provided"
        
        # Load brand voice
        brand_voice_guidelines = "Write engaging, professional, and friendly captions with relevant hashtags and CTAs."
        if os.path.exists(DEFAULT_BRAND_VOICE_PATH):
            try:
                with open(DEFAULT_BRAND_VOICE_PATH, "r", encoding="utf-8") as f:
                    brand_voice_guidelines = f.read().strip()
            except Exception as e:
                logger.warning(f"Error reading brand voice file: {e}")

        # Image processing
        image_bytes = None
        image_mime = None
        
        if image:
            image_bytes = await image.read()
            image_mime = (image.content_type or "").lower()
            has_image = True
            logger.info(f"Image uploaded: {image.filename} ({image_mime}), size={len(image_bytes)} bytes")

            if len(image_bytes) > MAX_IMAGE_SIZE:
                return JSONResponse(
                    status_code=400,
                    content={"status": "error", "detail": "Image is too large (max 5 MB). Please upload a smaller image."}
                )
            if image_mime and not image_mime.startswith("image/"):
                return JSONResponse(
                    status_code=400,
                    content={"status": "error", "detail": "Unsupported file type. Please upload an image (JPG, PNG, WEBP)."}
                )

            # If the active provider/model can't see images, auto-fall back to a vision-capable one
            resolved_provider, resolved_model, used_fallback = resolve_image_provider_and_model(
                active_provider, active_model, config, True
            )
            if used_fallback:
                logger.info(
                    f"Active provider can't see images; using '{resolved_model}' on '{resolved_provider}'."
                )
            active_provider = resolved_provider
            active_model = resolved_model
            
        # Build prompt
        details = []
        if description and description.strip():
            details.append(f"- Description: {description.strip()}")
        else:
            details.append("- Description: (Analyze the attached image and generate matching descriptions/captions)")
            
        if keywords_str != "None provided":
            details.append(f"- Specific Keywords to Include: {keywords_str}")
            
        if has_image:
            details.append(
                "- Image content: An image has been uploaded as part of this request. "
                "Analyze its content, subject, setting, and mood, and align the captions to represent "
                "what is shown in the image."
            )
            
        input_details = "\n".join(details)

        # Determine which platforms the user wants captions for
        selected_platforms = resolve_platforms(platforms)

        platform_count = len(selected_platforms)
        platform_sections = build_platform_sections(selected_platforms)
        count_label = "caption" if platform_count == 1 else "captions"

        prompt = f"""You are a professional social media manager and copywriter.
Your task is to generate {platform_count} platform-specific {count_label} based on the user's description, guidelines, and optional image.

Input Details:
{input_details}

Brand Voice Guidelines & Reference Examples:
---
{brand_voice_guidelines}
---

Please generate EXACTLY {platform_count} {count_label}, formatted with the following headers:

{platform_sections}

Make sure to follow the brand voice guidelines and reference examples closely. Return ONLY the sections listed above, separated by the markers. Do not add intro or outro text.
"""
        
        logger.info(f"Sending request to {active_provider} with model {active_model}...")
        
        # Get LLM response
        response_text = get_llm_response(
            provider=active_provider,
            model_name=active_model,
            prompt=prompt,
            temperature=active_temp,
            image_bytes=image_bytes,
            image_mime=image_mime
        )
        
        # Parse the raw response and keep only the platforms the user asked for
        captions = filter_captions(parse_captions(response_text), selected_platforms)

        # Check if all captions parsed as empty (means parsing failed or API failed)
        all_empty = all(val.strip() == "" for val in captions.values())
        if all_empty:
            # Fallback: Put the whole response into the first requested platform to avoid data loss
            first_platform = selected_platforms[0]
            captions[first_platform] = response_text
            logger.warning("Failed to parse headers. Placed entire raw text into %s.", first_platform)

        # Save to session history
        save_to_session_history(
            session_id=session_id,
            description=description or "(Image-based Generation)",
            keywords=keywords_list,
            provider=active_provider,
            model_name=active_model,
            captions=captions
        )
        
        return {
            "status": "success",
            "provider": active_provider,
            "model": active_model,
            "captions": captions
        }
        
    except Exception as e:
        logger.error(f"Error in generate endpoint: {e}", exc_info=True)
        detail = str(e)
        if "rate_limit" in detail.lower() or "429" in detail:
            return JSONResponse(
                status_code=429,
                content={
                    "status": "error",
                    "detail": (
                        "The AI provider is currently rate-limited (too many requests in a short time). "
                        "Please wait a few seconds and try again."
                    )
                }
            )
        if has_image and ("401" in detail or "Missing API key" in detail or "invalid_api_key" in detail):
            detail = (
                "Image generation failed: your current API key only has access to DeepSeek models, "
                "which can't see images. Add GEMINI_API_KEY, OPENAI_API_KEY, or ANTHROPIC_API_KEY "
                "to your '.env' file so the app can use a vision-capable model, then restart the server."
            )
        return JSONResponse(
            status_code=500,
            content={"status": "error", "detail": detail}
        )


# Setup static directories and index routing
os.makedirs("static", exist_ok=True)

@app.get("/favicon.ico")
async def get_favicon():
    """Serve favicon (avoids a 404 for browsers that request /favicon.ico directly)."""
    return FileResponse("static/favicon.svg", media_type="image/svg+xml")


@app.get("/")
async def get_index():
    """Serve UI homepage."""
    index_path = "static/index.html"
    if os.path.exists(index_path):
        return FileResponse(index_path)
    return HTMLResponse("<h1>Web UI static files are not built yet. Create static/index.html to view page.</h1>")


# Serve general static assets from /static
app.mount("/static", StaticFiles(directory="static"), name="static")


if __name__ == "__main__":
    import uvicorn
    host = os.getenv("HOST", "127.0.0.1")
    port = int(os.getenv("PORT", "8000"))
    # When running directly, use standard port 8000 (override via HOST/PORT env vars)
    uvicorn.run("app:app", host=host, port=port, reload=True)
