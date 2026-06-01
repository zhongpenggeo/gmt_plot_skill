#!/usr/bin/env python3
"""
GMT figure visual comparison and review script.

Reads a generated GMT figure and the plotting plan, sends them to a vision model
for evaluation, and outputs a structured review report.

Usage:
    python compare.py <image_path> [plan.md] [output_report] [--iteration N]

Environment (.env file):
    VISION_MODEL_NAME   Vision model name (e.g. claude-sonnet-4-6, gpt-4o, gemini-2.5-flash, kimi-k2)
    VISION_API_KEY      API key (falls back to ANTHROPIC_API_KEY / OPENAI_API_KEY / GEMINI_API_KEY / MOONSHOT_API_KEY)
    VISION_API_BASE     Custom API base URL (proxy/gateway), overrides default per-provider base
    VISION_TIMEOUT      Request timeout in seconds (default: 300)
    VISION_MAX_SIZE     Max image dimension (px) before downscaling (default: 1600)

Supported providers (auto-detected from model name):
    - Anthropic: models containing "claude"
    - OpenAI:    models containing "gpt" or "openai"
    - Gemini:    models containing "gemini"
    - Kimi:      models containing "kimi" or "moonshot"
    - Others:    treated as OpenAI-compatible, must set VISION_API_BASE

Output:
    review_report_[version].md  Structured review report
"""

import os
import sys
import json
import base64
import argparse
from pathlib import Path
from datetime import datetime


# ---------------------------------------------------------------------------
# Environment
# ---------------------------------------------------------------------------

def load_env(work_dir: Path):
    """Load environment variables from .env file."""
    env_file = work_dir / ".env"
    if not env_file.exists():
        return
    with open(env_file, "r") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" in line:
                key, _, value = line.partition("=")
                key = key.strip()
                value = value.strip().strip('"').strip("'")
                if key and value and key not in os.environ:
                    os.environ[key] = value


# ---------------------------------------------------------------------------
# Image helpers
# ---------------------------------------------------------------------------

def get_image_mime_type(image_path: str) -> str:
    """Determine MIME type from file extension."""
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
    """Base64-encode an image file."""
    with open(image_path, "rb") as f:
        return base64.b64encode(f.read()).decode("utf-8")


def resize_image_if_needed(image_path: str, work_dir: Path, max_size: int = 1600) -> str:
    """Downscale image if any dimension exceeds max_size. Returns (possibly new) path."""
    try:
        from PIL import Image
    except ImportError:
        return image_path

    img = Image.open(image_path)
    w, h = img.size
    if max(w, h) <= max_size:
        return image_path

    ratio = max_size / max(w, h)
    new_size = (int(w * ratio), int(h * ratio))
    img = img.resize(new_size, Image.LANCZOS)
    resized_path = str(work_dir / "_review_resized.png")
    img.save(resized_path, optimize=True)
    old_kb = os.path.getsize(image_path) / 1024
    new_kb = os.path.getsize(resized_path) / 1024
    print(f"Image resized: {w}x{h} ({old_kb:.0f}KB) -> {new_size[0]}x{new_size[1]} ({new_kb:.0f}KB)")
    return resized_path


def resolve_timeout() -> int:
    """Resolve API request timeout from VISION_TIMEOUT env var."""
    try:
        return int(os.environ.get("VISION_TIMEOUT", "600"))
    except ValueError:
        return 300


def resolve_max_image_size() -> int:
    """Resolve max image dimension from VISION_MAX_SIZE env var."""
    try:
        return int(os.environ.get("VISION_MAX_SIZE", "1600"))
    except ValueError:
        return 1600


def convert_pdf_to_png(pdf_path: str, work_dir: Path) -> str:
    """Convert PDF to PNG using ghostscript or ImageMagick."""
    png_path = str(work_dir / "_review_temp.png")
    ret = os.system(
        f"gs -dNOPAUSE -dBATCH -sDEVICE=png16m -r150 "
        f"-sOutputFile={png_path} {pdf_path} > /dev/null 2>&1"
    )
    if ret == 0 and os.path.exists(png_path):
        return png_path
    ret = os.system(f"convert -density 150 {pdf_path} {png_path} > /dev/null 2>&1")
    if ret == 0 and os.path.exists(png_path):
        return png_path
    print("Warning: cannot convert PDF to PNG, sending PDF directly (may not be supported)")
    return pdf_path


# ---------------------------------------------------------------------------
# Prompt builder
# ---------------------------------------------------------------------------

def build_prompt(plan_content: str, iteration: int = 0) -> str:
    """Build the review prompt for the vision model."""
    return f"""You are a professional geoscience figure reviewer. Carefully examine this GMT-generated figure and evaluate it against the plotting plan requirements below.

## Plotting Plan (plan.md)
{plan_content}

## Review Requirements

Evaluate the figure across the following six dimensions:

1. **Geographic Accuracy**: Does the figure cover the required region? Are latitude/longitude labels clear and correct?
2. **Data Presentation Quality**: Is the terrain/data clearly visible? Is the color palette appropriate (intuitive tones, sufficient contrast)? Is the data resolution adequate?
3. **Annotation Completeness**: Does the title exist and is it correct? Are lat/lon labels complete? Does the color bar have units and description? Is the legend present and correct?
4. **Layout and Aesthetics**: Is the layout of all elements reasonable? Any overlapping or obscured elements? Are proportions balanced? Are borders and tick marks clear?
5. **Requirement Consistency**: Are all required elements included? Do subplot count and arrangement match the plan? Are special annotations (scale bar, north arrow, etc.) present?
6. **Technical Quality**: Are lines sharp (no aliasing or blur)? Do resolution and size meet output requirements? Are colors harmonious?

## Output Format

Output strictly in the following Markdown format:

```
## Figure Review Report

### Basic Information
- Reviewed figure: [filename]
- Review time: {datetime.now().strftime("%Y-%m-%d %H:%M")}
- Review round: {iteration + 1}

### Passed Items
- [List aspects that meet requirements, or write "All passed"]

### Items Needing Improvement
- [List aspects that could be optimized but do not break functionality]
  - Issue: [specific description]
  - Suggestion: [specific fix, note GMT parameter or module name]

### Failed Items (if any)
- [List issues that do not meet plan requirements]
  - Issue: [specific description]
  - Requirement reference: [quote relevant part of plan.md]
  - Suggestion: [specific fix, note GMT parameter or module name]
  - Fix location: [script file and approximate line/parameter to change]

### Overall Scores
- Geographic Accuracy: [1-5 stars]
- Data Presentation: [1-5 stars]
- Annotation Completeness: [1-5 stars]
- Layout & Aesthetics: [1-5 stars]
- Requirement Consistency: [1-5 stars]
- Technical Quality: [1-5 stars]

### Summary
[A concise overall assessment highlighting main strengths and key issues to fix]

### Fix Priority
[Prioritized list: data errors > missing features > annotation issues > visual quality > layout tweaks]
```

Notes:
- Evaluate strictly against plan.md requirements, not subjective preference
- Point out issues clearly with specific GMT fix suggestions (e.g. "change CPT from 'geo' to 'topo'")
- Distinguish between "must-fix" (Failed Items) and "nice-to-have" (Items Needing Improvement)
"""


# ---------------------------------------------------------------------------
# Provider routing
# ---------------------------------------------------------------------------

def detect_provider(model_name: str) -> str:
    """Detect the API provider from the model name."""
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
    """Resolve API key, checking provider-specific env vars first."""
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
    """Resolve base URL. VISION_API_BASE overrides all defaults."""
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
    """Call Anthropic (Claude) vision API."""
    import anthropic

    mime_type = get_image_mime_type(image_path)
    image_data = encode_image(image_path)

    client_kwargs = {"api_key": api_key}
    if base_url != "https://api.anthropic.com":
        client_kwargs["base_url"] = base_url

    client = anthropic.Anthropic(**client_kwargs)
    message = client.messages.create(
        model=model_name,
        # max_tokens=100000,
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
    """Call OpenAI-compatible vision API (OpenAI, Kimi, custom proxies)."""
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
    """Call Google Gemini vision API."""
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
        # "generationConfig": {"maxOutputTokens": 4096},
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
    """Route to the appropriate vision API based on detected provider."""
    if provider == "anthropic":
        return call_anthropic(image_path, prompt, model_name, api_key, base_url)
    elif provider == "gemini":
        return call_gemini(image_path, prompt, model_name, api_key, base_url, timeout=timeout)
    else:
        # openai, kimi, openai_compatible all use the same format
        return call_openai_compatible(image_path, prompt, model_name, api_key, base_url, timeout=timeout)


def main():
    parser = argparse.ArgumentParser(description="GMT figure visual comparison review")
    parser.add_argument("image", help="Path to figure to review (png/jpg/pdf)")
    parser.add_argument("plan", nargs="?", default="plan.md", help="Plotting plan file (default: plan.md)")
    parser.add_argument("output", nargs="?", default="review_report_[version].md", help="Output review report path (default: review_report_[version].md)")
    parser.add_argument("--iteration", type=int, default=0, help="Review round number (0-based, default: 0)")
    parser.add_argument("--work-dir", default=".", help="Working directory (default: current dir)")
    args = parser.parse_args()

    work_dir = Path(args.work_dir).resolve()

    # Load .env
    load_env(work_dir)

    model_name = os.environ.get("VISION_MODEL_NAME", "claude-sonnet-4-6")
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

    # Read image
    image_path = args.image
    if not os.path.exists(image_path):
        print(f"Error: image file not found: {image_path}")
        sys.exit(1)

    # Convert PDF if needed
    if image_path.lower().endswith(".pdf"):
        png_path = convert_pdf_to_png(image_path, work_dir)
        if os.path.exists(png_path):
            image_path = png_path

    # Resize large images to avoid timeouts
    max_size = resolve_max_image_size()
    image_path = resize_image_if_needed(image_path, work_dir, max_size)

    # Resolve timeout
    timeout = resolve_timeout()

    # Read plan
    plan_path = Path(args.plan)
    if not plan_path.is_absolute():
        plan_path = work_dir / args.plan
    if plan_path.exists():
        plan_content = plan_path.read_text(encoding="utf-8")
    else:
        plan_content = "(No plan file found, please review based on general figure standards)"

    # Build prompt
    prompt = build_prompt(plan_content, args.iteration)

    print(f"Provider:  {provider}")
    print(f"Model:     {model_name}")
    print(f"Base URL:  {base_url}")
    print(f"Figure:    {image_path}")
    print(f"Plan:      {plan_path}")
    print(f"Round:     {args.iteration + 1}")
    print(f"Timeout:   {timeout}s")
    print("Calling vision model ...")

    # Call model
    try:
        result = call_vision_model(image_path, prompt, model_name, api_key, base_url, provider, timeout=timeout)
    except Exception as e:
        print(f"Error: vision model call failed: {e}")
        sys.exit(1)

    # Save report
    output_path = Path(args.output)
    if not output_path.is_absolute():
        output_path = work_dir / args.output
    output_path.write_text(result, encoding="utf-8")
    print(f"Review report saved: {output_path}")

    # Print key summary lines
    print("\n--- Review Summary ---")
    for line in result.split("\n"):
        line_stripped = line.strip()
        if any(kw in line_stripped for kw in ["Scores", "Summary", "Fix Priority", "Failed Items", "Improvement"]):
            print(line_stripped)


if __name__ == "__main__":
    main()
