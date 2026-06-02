#!/usr/bin/env python3
"""
GMT style reference image extraction script.

Reads a user-provided style reference figure, sends it to a vision model,
and extracts GMT-compatible style parameters for use in plan generation.

Usage:
    python extract_style.py <style_image> [--output STYLE.md] [--output-dir DIR]

Environment (.env file):
    VISION_MODEL_NAME   Vision model name (e.g. claude-sonnet-4-6, gpt-4o, gemini-2.5-flash, kimi-k2)
    VISION_API_KEY      API key (falls back to ANTHROPIC_API_KEY / OPENAI_API_KEY / GEMINI_API_KEY / MOONSHOT_API_KEY)
    VISION_API_BASE     Custom API base URL (proxy/gateway), overrides default per-provider base
    VISION_TIMEOUT      Request timeout in seconds (default: 300)

Supported providers (auto-detected from model name):
    - Anthropic: models containing "claude"
    - OpenAI:    models containing "gpt" or "openai"
    - Gemini:    models containing "gemini"
    - Kimi:      models containing "kimi" or "moonshot"
    - Others:    treated as OpenAI-compatible, must set VISION_API_BASE

Output:
    STYLE.md  Structured GMT style specification
"""

import os
import sys
import json
import base64
import argparse
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv
load_dotenv()


# ---------------------------------------------------------------------------
# Image helpers
# ---------------------------------------------------------------------------

def get_image_mime_type(image_path: str) -> str:
    ext = Path(image_path).suffix.lower()
    return {
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".gif": "image/gif",
        ".webp": "image/webp",
        ".pdf": "application/pdf",
    }.get(ext, "image/png")


def encode_image(image_path: str) -> str:
    with open(image_path, "rb") as f:
        return base64.b64encode(f.read()).decode("utf-8")


def resolve_timeout() -> int:
    try:
        return int(os.environ.get("VISION_TIMEOUT", "600"))
    except ValueError:
        return 300


def convert_pdf_to_jpg(pdf_path: str, output_dir: Path) -> str:
    jpg_path = str(output_dir / "_style_temp.jpg")
    ret = os.system(
        f"gs -dNOPAUSE -dBATCH -sDEVICE=png16m -r150 "
        f"-sOutputFile={jpg_path} {pdf_path} > /dev/null 2>&1"
    )
    if ret == 0 and os.path.exists(jpg_path):
        return jpg_path
    ret = os.system(f"convert -density 50 {pdf_path} {jpg_path} > /dev/null 2>&1")
    if ret == 0 and os.path.exists(jpg_path):
        return jpg_path
    print("Warning: cannot convert PDF to jpg, sending PDF directly (may not be supported)")
    return pdf_path


# ---------------------------------------------------------------------------
# Prompt builder
# ---------------------------------------------------------------------------

def build_style_extraction_prompt() -> str:
    return """You are a GMT (Generic Mapping Tools) cartography expert. Carefully examine this reference figure and extract its visual style into a structured specification suitable for GMT plotting.

Analyze every visual element and map it to concrete GMT parameters. Be as specific as possible.

## Extraction Dimensions

### 1. Color Palette (CPT)
- Identify the dominant color scheme used for the main data layer (terrain, gravity, etc.)
- What CPT type: sequential (light→dark single hue), diverging (two hues with neutral middle), or categorical?
- Describe the key color transitions (e.g. "dark blue (#000080) at low values → cyan → yellow → dark red (#800000) at high values")
- If terrain: is it like GMT's `geo`, `topo`, `globe`, `relief`, `dem1`, `dem2`, `dem3`, `dem4`?
- If diverging: is it like `polar`, `haxby`, `roma`, `vik`?
- What is the background color (land/ocean if applicable)?
- Is there a color bar? Where is it positioned? What range and units?

### 2. Layout & Composition
- Figure aspect ratio (portrait/landscape/square, estimate ratio like 16:9, 4:3, 1:1)
- Number of subplots and their arrangement (rows × columns)
- Is there a main map with inset(s)? How are insets positioned?
- Relative sizing of map area vs. color bar vs. margins
- What map projection appears to be used? (Mercator, Robinson, Mollweide, Lambert, UTM, etc.)

### 3. Typography
- Font family style: serif (Times-like) or sans-serif (Helvetica/Arial-like)?
- Title font size relative to body (e.g. "~2× label size")
- Label font size (small/medium/large)
- Font weight: regular, bold, or mixed?
- Title placement and alignment

### 4. Map Frame & Annotations
- Frame style: plain (black/white), fancy (checkered), or other?
- Tick mark style: inside, outside, both? Tick interval/spacing?
- Latitude/longitude annotation format: degrees-minutes-seconds, decimal degrees, with ° symbol?
- Grid lines: present or absent? Solid or dashed? Spacing?
- Border/neatline style

### 5. Map Elements
- Coastline style: thin/thick, black/gray/colored? High/medium/low resolution?
- Political boundaries present? Style?
- Scale bar: present? Position? Style?
- North arrow / compass rose: present? Position?
- Legend: present? Position? Style (boxed/minimal)?
- Any special annotations or markers?

### 6. Background & Terrain
- Is there shaded relief / hillshading? If so, intensity level (subtle/strong)?
- Is the background plain white/colored, or a terrain base?
- Ocean fill color, if applicable?

### 7. Overall Aesthetic
- Describe the overall look-and-feel in 2-3 sentences
- Is it publication-quality (clean, minimal)? Field-report style? Web/presentation style?
- Target audience: scientific journal, report, presentation, poster?

## Output Format

Output strictly in the following Markdown format:

```
## Style Extraction Report

### 1. Color Palette
- CPT recommendation: [closest GMT built-in CPT name, or "custom" with description]
- CPT type: [sequential/diverging/categorical]
- Key colors: [list hex codes or color names in order from low to high]
- CPT range: [min to max if discernible]
- Color bar position: [right/bottom/top/left, or "none"]
- Background: land=[color] ocean=[color]

### 2. Layout
- Aspect ratio: [description, e.g. "landscape ~16:9"]
- Subplot arrangement: [e.g. "single panel", "2×2 grid of 4 panels"]
- Map-to-colorbar ratio: [e.g. "map ~85%, color bar ~10% of width"]
- Suggested GMT projection: [e.g. "-JM" (Mercator), "-JQ" (cylindrical equal-area)]

### 3. Typography
- Font family: [e.g. "Helvetica (sans-serif)", "Times (serif)"]
- GMT font suggestion: [e.g. "Helvetica", "Helvetica-Bold", "Times-Roman"]
- Title: size=[relative], weight=[regular/bold], position=[top-center, etc.]
- Labels: size=[relative]
- Annotation: size=[relative]

### 4. Map Frame & Annotations
- Frame style: [plain/fancy, GMT -B equivalent description]
- Tick style: [inside/outside/both, interval]
- Annotation format: [e.g. "ddd:mm (degrees and minutes)"]
- Grid lines: [present/absent, style, spacing]

### 5. Map Elements
- Coastline: resolution=[low/medium/high], pen=[thickness,color]
- Political boundaries: [present/absent, style if present]
- Scale bar: [present/absent, position, style]
- North arrow: [present/absent, position]
- Legend: [present/absent, position, style]

### 6. Background & Terrain
- Shaded relief: [present/absent, intensity]
- Terrain base: [yes/no, if yes describe]
- Ocean fill: [color if applicable]

### 7. Overall Aesthetic
- Description: [2-3 sentence overall look-and-feel]
- Style category: [publication / report / presentation / poster]
- Key distinctive features: [1-3 things that define this style]

### 8. GMT Implementation Guide
[Provide a concise, actionable summary: key GMT parameters, CPT, font settings, and frame settings that would reproduce this style. Think of this as a "style recipe" for the plan.md.]
```

Notes:
- Focus on extracting concrete, actionable GMT parameters whenever possible
- Use actual GMT parameter conventions (-B, -C, -J, etc.) in the Implementation Guide
- If uncertain about something, note your confidence level and suggest reasonable defaults
- The goal is to enable reproducing this figure's style with GMT
"""


# ---------------------------------------------------------------------------
# Provider routing (same as compare_imag.py)
# ---------------------------------------------------------------------------

def detect_provider(model_name: str) -> str:
    lower = model_name.lower()
    if "claude" in lower:
        return "anthropic"
    if "gemini" in lower:
        return "gemini"
    if "kimi" in lower or "moonshot" in lower:
        return "kimi"
    if "gpt" in lower or "openai" in lower:
        return "openai"
    return "openai_compatible"


def resolve_api_key(provider: str) -> str:
    key_map = {
        "anthropic": ["VISION_API_KEY", "ANTHROPIC_API_KEY"],
        "openai": ["VISION_API_KEY", "OPENAI_API_KEY"],
        "gemini": ["VISION_API_KEY", "GEMINI_API_KEY"],
        "kimi": ["VISION_API_KEY", "MOONSHOT_API_KEY"],
        "openai_compatible": ["VISION_API_KEY", "OPENAI_API_KEY"],
    }
    for key_name in key_map.get(provider, ["VISION_API_KEY"]):
        val = os.environ.get(key_name, "")
        if val:
            return val
    return ""


def resolve_base_url(provider: str) -> str:
    custom_base = os.environ.get("VISION_API_BASE", "")
    if custom_base:
        return custom_base.rstrip("/")
    defaults = {
        "anthropic": "https://api.anthropic.com",
        "openai": "https://api.openai.com/v1",
        "gemini": "https://generativelanguage.googleapis.com/v1beta",
        "kimi": "https://api.moonshot.cn/v1",
        "openai_compatible": "https://api.openai.com/v1",
    }
    return defaults.get(provider, "https://api.openai.com/v1")


# ---------------------------------------------------------------------------
# API call implementations
# ---------------------------------------------------------------------------

def call_anthropic(image_path: str, prompt: str, model_name: str, api_key: str, base_url: str) -> str:
    import anthropic

    mime_type = get_image_mime_type(image_path)
    image_data = encode_image(image_path)

    client_kwargs = {"api_key": api_key}
    if base_url != "https://api.anthropic.com":
        client_kwargs["base_url"] = base_url

    client = anthropic.Anthropic(**client_kwargs)
    message = client.messages.create(
        model=model_name,
        messages=[{
            "role": "user",
            "content": [
                {
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": mime_type,
                        "data": image_data,
                    },
                },
                {"type": "text", "text": prompt},
            ],
        }],
    )
    return message.content[0].text


def call_openai_compatible(image_path: str, prompt: str, model_name: str, api_key: str, base_url: str, timeout: int = 300) -> str:
    import requests

    mime_type = get_image_mime_type(image_path)
    image_data = encode_image(image_path)

    url = f"{base_url.rstrip('/')}/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": model_name,
        "messages": [{
            "role": "user",
            "content": [
                {
                    "type": "image_url",
                    "image_url": {"url": f"data:{mime_type};base64,{image_data}"},
                },
                {"type": "text", "text": prompt},
            ],
        }],
    }
    resp = requests.post(url, headers=headers, json=payload, timeout=timeout)
    resp.raise_for_status()
    return resp.json()["choices"][0]["message"]["content"]


def call_gemini(image_path: str, prompt: str, model_name: str, api_key: str, base_url: str, timeout: int = 300) -> str:
    import requests

    mime_type = get_image_mime_type(image_path)
    image_data = encode_image(image_path)

    url = f"{base_url.rstrip('/')}/models/{model_name}:generateContent?key={api_key}"
    payload = {
        "contents": [{
            "parts": [
                {"text": prompt},
                {"inline_data": {"mime_type": mime_type, "data": image_data}},
            ]
        }],
    }
    resp = requests.post(url, json=payload, timeout=timeout)
    resp.raise_for_status()
    data = resp.json()
    return data["candidates"][0]["content"]["parts"][0]["text"]


# ---------------------------------------------------------------------------
# Main orchestrator
# ---------------------------------------------------------------------------

def call_vision_model(
    image_path: str,
    prompt: str,
    model_name: str,
    api_key: str,
    base_url: str,
    provider: str,
    timeout: int = 300,
) -> str:
    if provider == "anthropic":
        return call_anthropic(image_path, prompt, model_name, api_key, base_url)
    elif provider == "gemini":
        return call_gemini(image_path, prompt, model_name, api_key, base_url, timeout=timeout)
    else:
        return call_openai_compatible(image_path, prompt, model_name, api_key, base_url, timeout=timeout)


def main():
    parser = argparse.ArgumentParser(description="GMT style reference image extraction")
    parser.add_argument("image", help="Path to style reference figure (png/jpg/pdf)")
    parser.add_argument("--output", default="STYLE.md", help="Output style report path (default: STYLE.md)")
    parser.add_argument("--output-dir", default=".", help="Output directory (default: current dir)")
    args = parser.parse_args()

    output_dir = Path(args.output_dir).resolve()

    model_name = os.environ.get("VISION_MODEL_NAME", "")
    provider = detect_provider(model_name)
    api_key = resolve_api_key(provider)
    base_url = resolve_base_url(provider)

    if not api_key:
        print(f"Error: No API key found for provider '{provider}'.")
        print("Set VISION_API_KEY in .env, or a provider-specific key:")
        print("  Anthropic: ANTHROPIC_API_KEY")
        print("  OpenAI:    OPENAI_API_KEY")
        print("  Gemini:    GEMINI_API_KEY")
        print("  Kimi:      MOONSHOT_API_KEY")
        sys.exit(1)

    image_path = args.image
    if not os.path.exists(image_path):
        print(f"Error: style image file not found: {image_path}")
        sys.exit(1)

    # Convert PDF if needed
    if image_path.lower().endswith(".pdf"):
        jpg_path = convert_pdf_to_jpg(image_path, output_dir)
        if os.path.exists(jpg_path):
            image_path = jpg_path

    timeout = resolve_timeout()
    prompt = build_style_extraction_prompt()

    print(f"Provider:  {provider}")
    print(f"Model:     {model_name}")
    print(f"Base URL:  {base_url}")
    print(f"Style ref: {image_path}")
    print(f"Timeout:   {timeout}s")
    print("Extracting style from reference image ...")

    try:
        result = call_vision_model(image_path, prompt, model_name, api_key, base_url, provider, timeout=timeout)
    except Exception as e:
        print(f"Error: vision model call failed: {e}")
        sys.exit(1)

    output_path = Path(args.output)
    if not output_path.is_absolute():
        output_path = output_dir / args.output
    output_path.write_text(result, encoding="utf-8")
    print(f"Style report saved: {output_path}")

    # Print key summary lines
    print("\n--- Style Extraction Summary ---")
    for line in result.split("\n"):
        line_stripped = line.strip()
        if any(kw in line_stripped for kw in ["CPT recommendation", "GMT font", "Description", "Style category", "GMT Implementation"]):
            print(line_stripped)


if __name__ == "__main__":
    main()
