#!/usr/bin/env python3
"""
Social Media Caption Generator
Generates platform-specific social media captions using Gemini, OpenAI, or Claude.
"""

import os
import sys
import json
import argparse
from datetime import datetime
from dotenv import load_dotenv

# Force UTF-8 encoding on Windows terminals to support emojis and Unicode output
if sys.platform.startswith('win'):
    try:
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    except AttributeError:
        pass

# Load environment variables from .env file
load_dotenv()

# We will import rich modules. If they are not installed, we'll guide the user.
try:
    from rich.console import Console
    from rich.panel import Panel
    from rich.prompt import Prompt, Confirm
    from rich.theme import Theme
    from rich.progress import Progress, SpinnerColumn, TextColumn
    from rich.markdown import Markdown
except ImportError:
    print("Error: The 'rich' library is required to run this tool. Please run the setup script or run:")
    print("pip install rich python-dotenv google-generativeai openai anthropic")
    sys.exit(1)

# Initialize Rich Console with custom theme
custom_theme = Theme({
    "info": "cyan",
    "warning": "yellow",
    "error": "bold red",
    "success": "bold green",
    "highlight": "magenta",
    "instagram": "bold #C13584",
    "facebook": "bold #1877F2",
    "linkedin": "bold #0077B5",
    "variation": "bold #FF5722",
})
console = Console(theme=custom_theme)

DEFAULT_CONFIG_PATH = "config.json"
DEFAULT_BRAND_VOICE_PATH = "brand_voice.txt"
DEFAULT_HISTORY_PATH = "history.json"


def load_config(config_path=DEFAULT_CONFIG_PATH):
    """Load configuration from config.json."""
    default_config = {
        "provider": "gemini",
        "temperature": 0.7,
        "brand_voice_path": DEFAULT_BRAND_VOICE_PATH,
        "history_path": DEFAULT_HISTORY_PATH,
        "models": {
            "gemini": "gemini-1.5-flash",
            "openai": "gpt-4o-mini",
            "anthropic": "claude-3-5-sonnet-20240620",
            "omniroute": "deepseek-v4-flash-free"
        }
    }
    
    if not os.path.exists(config_path):
        # Return default config if file doesn't exist
        return default_config
        
    try:
        with open(config_path, "r", encoding="utf-8") as f:
            config = json.load(f)
            # Ensure all default keys exist
            for key, val in default_config.items():
                if key not in config:
                    config[key] = val
                elif isinstance(val, dict) and isinstance(config[key], dict):
                    for subkey, subval in val.items():
                        if subkey not in config[key]:
                            config[key][subkey] = subval
            return config
    except Exception as e:
        console.print(f"[warning]Warning: Could not read configuration file ({e}). Using defaults.[/warning]")
        return default_config


def get_api_key(provider):
    """Retrieve API key for the chosen provider from environment variables."""
    key_vars = {
        "gemini": "GEMINI_API_KEY",
        "openai": "OPENAI_API_KEY",
        "anthropic": "ANTHROPIC_API_KEY",
        "omniroute": "OMNIROUTE_API_KEY"
    }
    env_var = key_vars.get(provider.lower())
    if not env_var:
        return None
    return os.getenv(env_var)


def generate_with_gemini(api_key, model_name, prompt, temperature, image_bytes=None, image_mime=None):
    """Generate content using Google Gemini API, optionally with image content."""
    try:
        import google.generativeai as genai
    except ImportError:
        raise ImportError("google-generativeai library is not installed. Run 'pip install google-generativeai'")
        
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel(model_name=model_name)
    
    contents = [prompt]
    if image_bytes and image_mime:
        contents.append({
            "mime_type": image_mime,
            "data": image_bytes
        })
        
    response = model.generate_content(
        contents,
        generation_config=genai.types.GenerationConfig(temperature=temperature)
    )
    if not response.text:
        raise ValueError("Received empty response from Gemini API.")
    return response.text


def generate_with_openai(api_key, model_name, prompt, temperature, image_bytes=None, image_mime=None):
    """Generate content using OpenAI API, optionally with image content."""
    try:
        from openai import OpenAI
    except ImportError:
        raise ImportError("openai library is not installed. Run 'pip install openai'")
        
    import base64
    client = OpenAI(api_key=api_key)
    
    if image_bytes and image_mime:
        base64_image = base64.b64encode(image_bytes).decode('utf-8')
        messages = [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:{image_mime};base64,{base64_image}"
                        }
                    }
                ]
            }
        ]
    else:
        messages = [{"role": "user", "content": prompt}]
        
    response = client.chat.completions.create(
        model=model_name,
        messages=messages,
        temperature=temperature
    )
    content = response.choices[0].message.content
    if not content:
        raise ValueError("Received empty response from OpenAI API.")
    return content


def generate_with_omniroute(api_key, model_name, prompt, temperature, image_bytes=None, image_mime=None):
    """Generate content using the Omniroute OpenAI-compatible endpoint (DeepSeek), optionally with image content."""
    try:
        from openai import OpenAI
    except ImportError:
        raise ImportError("openai library is not installed. Run 'pip install openai'")

    import base64
    base_url = os.getenv("OMNIROUTE_BASE_URL", "https://api.omniroute.ai/v1")
    client = OpenAI(api_key=api_key, base_url=base_url)

    if image_bytes and image_mime:
        base64_image = base64.b64encode(image_bytes).decode('utf-8')
        messages = [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:{image_mime};base64,{base64_image}"
                        }
                    }
                ]
            }
        ]
    else:
        messages = [{"role": "user", "content": prompt}]

    response = client.chat.completions.create(
        model=model_name,
        messages=messages,
        temperature=temperature
    )
    content = response.choices[0].message.content
    if not content:
        raise ValueError("Received empty response from Omniroute API.")
    return content


def generate_with_anthropic(api_key, model_name, prompt, temperature, image_bytes=None, image_mime=None):
    """Generate content using Anthropic Claude API, optionally with image content."""
    try:
        from anthropic import Anthropic
    except ImportError:
        raise ImportError("anthropic library is not installed. Run 'pip install anthropic'")
        
    import base64
    client = Anthropic(api_key=api_key)
    
    if image_bytes and image_mime:
        base64_image = base64.b64encode(image_bytes).decode('utf-8')
        messages = [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": image_mime,
                            "data": base64_image
                        }
                    }
                ]
            }
        ]
    else:
        messages = [{"role": "user", "content": prompt}]
        
    response = client.messages.create(
        model=model_name,
        max_tokens=2000,
        temperature=temperature,
        messages=messages
    )
    content = response.content[0].text
    if not content:
        raise ValueError("Received empty response from Anthropic API.")
    return content


def get_llm_response(provider, model_name, prompt, temperature, image_bytes=None, image_mime=None):
    """Route the generation request to the correct LLM provider client."""
    api_key = get_api_key(provider)
    if not api_key:
        raise ValueError(
            f"API Key for '{provider}' is missing. Please set it in your '.env' file "
            f"using '{provider.upper()}_API_KEY'."
        )
        
    if provider.lower() == "gemini":
        return generate_with_gemini(api_key, model_name, prompt, temperature, image_bytes, image_mime)
    elif provider.lower() == "openai":
        return generate_with_openai(api_key, model_name, prompt, temperature, image_bytes, image_mime)
    elif provider.lower() == "anthropic":
        return generate_with_anthropic(api_key, model_name, prompt, temperature, image_bytes, image_mime)
    elif provider.lower() == "omniroute":
        return generate_with_omniroute(api_key, model_name, prompt, temperature, image_bytes, image_mime)
    else:
        raise ValueError(f"Unsupported provider: {provider}")



def parse_captions(response_text):
    """
    Parse the LLM response to extract the 5 generated captions.
    Uses flexible regex matches to find section boundaries.
    """
    import re
    
    # Define regex patterns for each section header
    patterns = {
        "instagram": re.compile(r'(?i)(?:---|###|\*\*|\[)\s*instagram\s*(?:---|###|\*\*|\])?|^instagram:$'),
        "facebook": re.compile(r'(?i)(?:---|###|\*\*|\[)\s*facebook\s*(?:---|###|\*\*|\])?|^facebook:$'),
        "linkedin": re.compile(r'(?i)(?:---|###|\*\*|\[)\s*linkedin\s*(?:---|###|\*\*|\])?|^linkedin:$'),
        "variation_1": re.compile(r'(?i)(?:---|###|\*\*|\[)\s*variation\s*(?:#?\s*1|one)\b|^variation\s*(?:#?\s*1|one):$'),
        "variation_2": re.compile(r'(?i)(?:---|###|\*\*|\[)\s*variation\s*(?:#?\s*2|two)\b|^variation\s*(?:#?\s*2|two):$'),
    }
    
    parsed = {}
    lines = response_text.splitlines()
    
    current_key = None
    current_content = []
    
    for line in lines:
        stripped_line = line.strip()
        matched_key = None
        
        # Check if the line matches any of the section header patterns
        for key, pattern in patterns.items():
            if pattern.search(stripped_line):
                matched_key = key
                break
                
        # If we didn't match the strict regex, do a fallback substring check on the line
        if not matched_key:
            lower_line = stripped_line.lower()
            if "instagram" in lower_line and ("---" in lower_line or "###" in lower_line or "**" in lower_line or lower_line.startswith("instagram:")):
                matched_key = "instagram"
            elif "facebook" in lower_line and ("---" in lower_line or "###" in lower_line or "**" in lower_line or lower_line.startswith("facebook:")):
                matched_key = "facebook"
            elif "linkedin" in lower_line and ("---" in lower_line or "###" in lower_line or "**" in lower_line or lower_line.startswith("linkedin:")):
                matched_key = "linkedin"
            elif "variation" in lower_line and ("1" in lower_line or "one" in lower_line) and ("---" in lower_line or "###" in lower_line or "**" in lower_line or "variation" in lower_line):
                matched_key = "variation_1"
            elif "variation" in lower_line and ("2" in lower_line or "two" in lower_line) and ("---" in lower_line or "###" in lower_line or "**" in lower_line or "variation" in lower_line):
                matched_key = "variation_2"
                
        if matched_key:
            if current_key:
                parsed[current_key] = "\n".join(current_content).strip()
            current_key = matched_key
            current_content = []
        elif current_key:
            current_content.append(line)
            
    # Save the last section
    if current_key and current_content:
        parsed[current_key] = "\n".join(current_content).strip()
        
    # Ensure all keys exist in the returned dictionary
    for key in patterns.keys():
        if key not in parsed:
            parsed[key] = ""
            
    return parsed


def save_to_history(history_path, description, keywords, provider, model_name, captions):
    """Save the generated captions and inputs to a JSON history file."""
    entry = {
        "timestamp": datetime.now().isoformat(),
        "description": description,
        "keywords": keywords,
        "provider": provider,
        "model": model_name,
        "captions": captions
    }
    
    history_data = []
    if os.path.exists(history_path):
        try:
            with open(history_path, "r", encoding="utf-8") as f:
                history_data = json.load(f)
                if not isinstance(history_data, list):
                    history_data = []
        except Exception:
            history_data = []
            
    history_data.insert(0, entry)  # Add new entry at the top
    
    try:
        with open(history_path, "w", encoding="utf-8") as f:
            json.dump(history_data, f, indent=2, ensure_ascii=False)
        return True
    except Exception as e:
        console.print(f"[warning]Warning: Could not save to history file ({e})[/warning]")
        return False


def main():
    # Setup Argument Parser
    parser = argparse.ArgumentParser(
        description="🚀 Social Media Caption Generator using LLM APIs",
        formatter_class=argparse.RawTextHelpFormatter
    )
    
    parser.add_argument("-d", "--description", help="Product or photo description")
    parser.add_argument("-k", "--keywords", help="Optional comma-separated keywords")
    parser.add_argument("-f", "--file", help="Path to a text file containing the description")
    parser.add_argument("-p", "--provider", choices=["gemini", "openai", "anthropic", "omniroute"], help="LLM Provider override")
    parser.add_argument("-m", "--model", help="LLM Model name override")
    parser.add_argument("-t", "--temperature", type=float, help="Creativity temperature override")
    parser.add_argument("--voice", help="Path to brand voice guidelines file")
    parser.add_argument("--history", help="Path to history JSON file")
    
    args = parser.parse_args()
    
    # Load configuration
    config = load_config()
    
    # Resolve parameters (arguments take precedence over config)
    provider = args.provider or config["provider"]
    model_name = args.model or config["models"].get(provider)
    temperature = args.temperature or config["temperature"]
    brand_voice_path = args.voice or config["brand_voice_path"]
    history_path = args.history or config["history_path"]
    
    # Welcome Display
    console.print()
    console.print(Panel.fit(
        "[bold success]🚀 SOCIAL MEDIA CAPTION GENERATOR[/bold success]\n"
        "[info]Produce platform-ready captions styled with your brand voice[/info]",
        border_style="cyan"
    ))
    console.print()
    
    description = ""
    keywords_list = []
    
    # Handle File Input
    if args.file:
        if not os.path.exists(args.file):
            console.print(f"[error]Error: File not found at '{args.file}'[/error]")
            sys.exit(1)
        try:
            with open(args.file, "r", encoding="utf-8") as f:
                description = f.read().strip()
            console.print(f"[info]Loaded description from file: {args.file}[/info]\n")
        except Exception as e:
            console.print(f"[error]Error reading file: {e}[/error]")
            sys.exit(1)
    elif args.description:
        description = args.description.strip()
        
    # Handle Keywords
    if args.keywords:
        keywords_list = [kw.strip() for kw in args.keywords.split(",") if kw.strip()]
        
    # If no description provided via arguments, launch the interactive prompt wizard
    is_interactive = not description
    if is_interactive:
        console.print("[highlight]Welcome to the Interactive Wizard![/highlight]")
        console.print("Please enter the product or photo details below.\n")
        
        # Description Prompt
        description = Prompt.ask("[bold]Product / Photo Description[/bold]")
        while not description.strip():
            console.print("[warning]Description cannot be empty.[/warning]")
            description = Prompt.ask("[bold]Product / Photo Description[/bold]")
            
        # Keywords Prompt
        keywords_input = Prompt.ask("[bold]Keywords[/bold] (optional, comma-separated)", default="")
        if keywords_input.strip():
            keywords_list = [kw.strip() for kw in keywords_input.split(",") if kw.strip()]
            
        # Provider Override Prompt
        change_provider = Confirm.ask(f"Use default provider [success]'{provider}'[/success] ({model_name})?", default=True)
        if not change_provider:
            provider = Prompt.ask("Select LLM Provider", choices=["gemini", "openai", "anthropic", "omniroute"], default=provider)
            model_name = config["models"].get(provider)
            console.print(f"[info]Switched to provider: {provider} ({model_name})[/info]")
            
    # Load Brand Voice Guidelines
    if not os.path.exists(brand_voice_path):
        console.print(f"[warning]Warning: Brand voice file not found at '{brand_voice_path}'. Using generic professional voice.[/warning]")
        brand_voice_guidelines = "Write engaging, professional, and friendly captions with relevant hashtags and CTAs."
    else:
        try:
            with open(brand_voice_path, "r", encoding="utf-8") as f:
                brand_voice_guidelines = f.read().strip()
        except Exception as e:
            console.print(f"[warning]Warning: Could not read brand voice file ({e}). Using generic professional voice.[/warning]")
            brand_voice_guidelines = "Write engaging, professional, and friendly captions with relevant hashtags and CTAs."
            
    # Format Keywords for prompt
    keywords_str = ", ".join(keywords_list) if keywords_list else "None provided"
    
    # Construct LLM Prompt
    prompt = f"""You are a professional social media manager and copywriter.
Your task is to generate five platform-specific captions based on the user's description and guidelines.

Input Details:
- Description: {description}
- Specific Keywords to Include: {keywords_str}

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

    console.print()
    console.print(f"[info]Generating captions using [highlight]{provider}[/highlight] (model: {model_name})...[/info]")
    
    # Run API Generation with Progress Spinner
    try:
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            transient=True
        ) as progress:
            progress.add_task(description="Thinking...", total=None)
            response_text = get_llm_response(provider, model_name, prompt, temperature)
            
        captions = parse_captions(response_text)
        
        # Display Generated Captions
        console.print("[success]✓ Captions Generated Successfully![/success]\n")
        
        # 1. Instagram Panel
        console.print(Panel(
            captions.get("instagram", "[italic red]Failed to generate Instagram caption.[/italic red]"),
            title="📸 Instagram Caption",
            title_align="left",
            border_style="instagram",
            padding=(1, 2)
        ))
        console.print()
        
        # 2. Facebook Panel
        console.print(Panel(
            captions.get("facebook", "[italic red]Failed to generate Facebook caption.[/italic red]"),
            title="👥 Facebook Caption",
            title_align="left",
            border_style="facebook",
            padding=(1, 2)
        ))
        console.print()
        
        # 3. LinkedIn Panel
        console.print(Panel(
            captions.get("linkedin", "[italic red]Failed to generate LinkedIn caption.[/italic red]"),
            title="💼 LinkedIn Caption",
            title_align="left",
            border_style="linkedin",
            padding=(1, 2)
        ))
        console.print()
        
        # 4. Variation 1 Panel
        console.print(Panel(
            captions.get("variation_1", "[italic red]Failed to generate Variation #1.[/italic red]"),
            title="✨ Variation #1 (Alternate Tone)",
            title_align="left",
            border_style="variation",
            padding=(1, 2)
        ))
        console.print()
        
        # 5. Variation 2 Panel
        console.print(Panel(
            captions.get("variation_2", "[italic red]Failed to generate Variation #2.[/italic red]"),
            title="💡 Variation #2 (Alternate CTA/Style)",
            title_align="left",
            border_style="variation",
            padding=(1, 2)
        ))
        console.print()
        
        # Save to history file
        saved = save_to_history(history_path, description, keywords_list, provider, model_name, captions)
        if saved:
            console.print(f"[success]✓ Captions saved to history: {history_path}[/success]\n")
            
    except Exception as e:
        console.print(f"\n[error]Error during generation: {e}[/error]")
        console.print("[info]Tip: Make sure you have set your API keys correctly in the .env file.[/info]")
        sys.exit(1)


if __name__ == "__main__":
    main()
