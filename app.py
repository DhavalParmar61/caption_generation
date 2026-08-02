import os
import json
import logging
from typing import Optional, List
from fastapi import FastAPI, HTTPException, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse, HTMLResponse

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("caption_gen_web")

# Import core generation helpers from CLI file
from caption_gen import (
    load_config,
    get_llm_response,
    parse_captions,
    save_to_history,
    DEFAULT_CONFIG_PATH,
    DEFAULT_BRAND_VOICE_PATH,
    DEFAULT_HISTORY_PATH
)

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
    """Retrieve active configurations."""
    try:
        config = load_config()
        # Hide actual API keys but confirm status
        api_keys_status = {
            "gemini": bool(os.getenv("GEMINI_API_KEY")),
            "openai": bool(os.getenv("OPENAI_API_KEY")),
            "anthropic": bool(os.getenv("ANTHROPIC_API_KEY")),
            "omniroute": bool(os.getenv("OMNIROUTE_API_KEY"))
        }
        return {
            "config": config,
            "api_keys_status": api_keys_status
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
            config["provider"] = config_data["provider"]
        if "temperature" in config_data:
            config["temperature"] = float(config_data["temperature"])
        if "models" in config_data and isinstance(config_data["models"], dict):
            for k, v in config_data["models"].items():
                config["models"][k] = v
                
        with open(DEFAULT_CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=2)
            
        return {"status": "success", "config": config}
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
def get_history():
    """Retrieve generation history."""
    try:
        if os.path.exists(DEFAULT_HISTORY_PATH):
            with open(DEFAULT_HISTORY_PATH, "r", encoding="utf-8") as f:
                history_data = json.load(f)
                return history_data
        return []
    except Exception as e:
        logger.error(f"Error reading history: {e}")
        return []


@app.post("/api/generate")
async def generate_captions(
    description: Optional[str] = Form(None),
    keywords: Optional[str] = Form(None),
    provider: Optional[str] = Form(None),
    model: Optional[str] = Form(None),
    temperature: Optional[float] = Form(None),
    image: Optional[UploadFile] = File(None)
):
    """Generate platform-specific captions with text guidelines and optional image upload."""
    try:
        # Load base configuration
        config = load_config()
        
        # Override values if provided
        active_provider = provider or config["provider"]
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
        has_image = False
        
        if image:
            image_bytes = await image.read()
            image_mime = image.content_type
            has_image = True
            logger.info(f"Image uploaded: {image.filename} ({image_mime}), size={len(image_bytes)} bytes")
            
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
        
        prompt = f"""You are a professional social media manager and copywriter.
Your task is to generate five platform-specific captions based on the user's description, guidelines, and optional image.

Input Details:
{input_details}

Brand Voice Guidelines & Reference Examples:
---
{brand_voice_guidelines}
---

Please generate EXACTLY five captions, formatted with the following headers:

---INSTAGRAM---
[Your Instagram caption here, including 3-5 relevant hashtags]

---FACEBOOK---
[Your Facebook caption here, including 3-5 relevant hashtags]

---LINKEDIN---
[Your LinkedIn caption here, including 3-5 relevant hashtags]

---VARIATION 1 (Alternate Tone)---
[An alternate tone caption, e.g. witty/bold/educational, including relevant hashtags. Specify the tone name at the top of the caption in brackets, e.g. "Tone: Bold"]

---VARIATION 2 (Alternate CTA)---
[An alternate CTA/writing style caption, including relevant hashtags. Specify the variation type at the top of the caption in brackets, e.g. "Variation: Question-based CTA"]

Make sure to follow the brand voice guidelines and reference examples closely. Return ONLY these five sections separated by the markers above. Do not add intro or outro text.
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
        
        # Parse the raw response
        captions = parse_captions(response_text)
        
        # Check if all captions parsed as empty (means parsing failed or API failed)
        all_empty = all(val.strip() == "" for val in captions.values())
        if all_empty:
            # Fallback: Put the whole response into variation 1 to avoid data loss
            captions["variation_1"] = response_text
            logger.warning("Failed to parse headers. Placed entire raw text into Variation 1.")

        # Save to history
        save_to_history(
            history_path=DEFAULT_HISTORY_PATH,
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
        return JSONResponse(
            status_code=500,
            content={"status": "error", "detail": str(e)}
        )


# Setup static directories and index routing
os.makedirs("static", exist_ok=True)

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
    # When running directly, use standard port 8000
    uvicorn.run("app:app", host="127.0.0.1", port=8000, reload=True)
