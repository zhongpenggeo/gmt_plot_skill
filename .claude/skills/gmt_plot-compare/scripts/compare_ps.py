#!/usr/bin/env python3
"""
GMT PS file evaluation script using deepseek-v4-pro.

Reads a GMT-generated PostScript (PS) file and the plotting plan, sends them
to deepseek-v4-pro for structured evaluation, and outputs a review report.

Usage:
    python compare_ps.py <ps_file> [plan.md] [output_report] [--iteration N] [--work-dir DIR]

Environment:
    DEEPSEEK_API_KEY   API key for deepseek API (required)
    DEEPSEEK_API_BASE  Optional custom API base URL (default: https://api.deepseek.com)
    DEEPSEEK_TIMEOUT   Request timeout in seconds (default: 600)
    DEEPSEEK_MAX_CHARS Max PS file chars to send (default: 200000)
"""

import os
import sys
import json
import argparse
from pathlib import Path
from datetime import datetime


# ---------------------------------------------------------------------------
# PS file helpers
# ---------------------------------------------------------------------------

def read_ps_content(ps_path: str, max_chars: int = 200000) -> tuple:
    """Read PS file content. Returns (content, truncated: bool, total_size: int)."""
    total_size = os.path.getsize(ps_path)
    with open(ps_path, "r", encoding="utf-8", errors="replace") as f:
        content = f.read(max_chars)
    truncated = len(content) < total_size
    return content, truncated, total_size


def extract_ps_metadata(content: str) -> dict:
    """Extract key metadata from a GMT PS file."""
    meta = {}
    for line in content.split("\n", 500):
        line = line.strip()
        if "%%Title:" in line:
            meta["title"] = line.split(":", 1)[1].strip()
        elif "%%BoundingBox:" in line:
            parts = line.split(":", 1)[1].strip().split()
            if len(parts) == 4:
                meta["bbox"] = parts
        elif "%%Creator:" in line:
            meta["creator"] = line.split(":", 1)[1].strip()
        elif "%%CreationDate:" in line:
            meta["date"] = line.split(":", 1)[1].strip()
    return meta


# ---------------------------------------------------------------------------
# Prompt builder
# ---------------------------------------------------------------------------

def build_prompt(plan_content: str, ps_meta: dict, ps_truncated: bool,
                 ps_total_size: int, iteration: int = 0) -> str:
    """Build the evaluation prompt for deepseek-v4-pro."""
    truncation_note = ""
    if ps_truncated:
        truncation_note = (
            f"\nNote: The PS file content below has been truncated "
            f"(total size: {ps_total_size / 1024:.0f} KB). "
            f"Evaluate based on the available content.\n"
        )

    return f"""You are a professional geoscience figure reviewer. Carefully examine this GMT-generated PostScript (PS) file and evaluate it against the plotting plan requirements below.

## Plotting Plan (plan.md)
{plan_content}

## PS File Metadata
- Title: {ps_meta.get('title', 'N/A')}
- BoundingBox: {ps_meta.get('bbox', 'N/A')}
- Creator: {ps_meta.get('creator', 'N/A')}
- Date: {ps_meta.get('date', 'N/A')}
{truncation_note}

## Review Requirements

Evaluate the figure across the following six dimensions by analyzing the PS file content (look at text labels, coordinate ranges, color definitions, drawing commands, and layout structure):

1. **Geographic Accuracy**: Does the figure cover the required region? Are latitude/longitude labels clear and correct? Check coordinate ranges in the PS file against plan.md.
2. **Data Presentation Quality**: Is the color palette appropriate (check PS color definitions)? Is proper shading/rendering applied?
3. **Annotation Completeness**: Does the title exist and is it correct? Are lat/lon labels complete? Does the color bar have units and description? Search for text strings in the PS file.
4. **Layout and Aesthetics**: Is the layout reasonable? Are elements properly positioned (check PS coordinate transforms)?
5. **Requirement Consistency**: Are all required elements from plan.md present in the PS file? Do subplot count and arrangement match?
6. **Technical Quality**: Line widths, font sizes, resolution settings — check PS parameters.

## Output Format

Output strictly in the following Markdown format:

```
## Figure Review Report

### Basic Information
- Reviewed file: [ps filename]
- Review time: {datetime.now().strftime("%Y-%m-%d %H:%M")}
- Review round: {iteration + 1}
- PS file size: {ps_total_size / 1024:.0f} KB

### Passed Items
- [List aspects that meet requirements, or write "None identified as passing"]

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
- The PS file content follows below — analyze its text labels, coordinates, color commands, and drawing structure
"""


# ---------------------------------------------------------------------------
# DeepSeek API call
# ---------------------------------------------------------------------------

def call_deepseek(ps_content: str, prompt: str, api_key: str,
                  base_url: str = "https://api.deepseek.com",
                  timeout: int = 600) -> str:
    """Call deepseek-v4-pro API (OpenAI-compatible)."""
    import requests

    url = f"{base_url.rstrip('/')}/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    # Combine prompt and PS content
    full_message = (
        prompt
        + "\n\n## PS File Content (for detailed analysis)\n\n```postscript\n"
        + ps_content
        + "\n```\n\nPlease now provide your complete review report based on the above PS file content and the plotting plan."
    )

    payload = {
        "model": "deepseek-v4-pro",
        "messages": [{"role": "user", "content": full_message}],
    }

    resp = requests.post(url, headers=headers, json=payload, timeout=timeout)
    resp.raise_for_status()
    return resp.json()["choices"][0]["message"]["content"]


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="GMT PS file evaluation using deepseek-v4-pro"
    )
    parser.add_argument("ps_file", help="Path to GMT-generated PS file")
    parser.add_argument("plan", nargs="?", default="plan.md",
                        help="Plotting plan file (default: plan.md)")
    parser.add_argument("output", nargs="?", default="review_report_[version].md",
                        help="Output review report path")
    parser.add_argument("--iteration", type=int, default=0,
                        help="Review round number (0-based)")
    parser.add_argument("--work-dir", default=".",
                        help="Working directory (default: current dir)")
    args = parser.parse_args()

    work_dir = Path(args.work_dir).resolve()

    # Resolve API key
    api_key = os.environ.get("DEEPSEEK_API_KEY", "")
    if not api_key:
        print("Error: DEEPSEEK_API_KEY environment variable not set.")
        print("Set it via: export DEEPSEEK_API_KEY=your-key")
        sys.exit(1)

    base_url = os.environ.get("DEEPSEEK_API_BASE", "https://api.deepseek.com")
    try:
        timeout = int(os.environ.get("DEEPSEEK_TIMEOUT", "600"))
    except ValueError:
        timeout = 600
    try:
        max_chars = int(os.environ.get("DEEPSEEK_MAX_CHARS", "200000"))
    except ValueError:
        max_chars = 200000

    # Read PS file
    ps_path = args.ps_file
    if not os.path.exists(ps_path):
        print(f"Error: PS file not found: {ps_path}")
        sys.exit(1)
    if not ps_path.lower().endswith(".ps"):
        print(f"Warning: file does not have .ps extension: {ps_path}")

    ps_content, ps_truncated, ps_total_size = read_ps_content(ps_path, max_chars)
    ps_meta = extract_ps_metadata(ps_content)

    # Read plan
    plan_path = Path(args.plan)
    if not plan_path.is_absolute():
        plan_path = work_dir / args.plan
    if plan_path.exists():
        plan_content = plan_path.read_text(encoding="utf-8")
    else:
        plan_content = "(No plan file found, please review based on general figure standards)"

    # Build prompt
    prompt = build_prompt(plan_content, ps_meta, ps_truncated, ps_total_size,
                          args.iteration)

    print(f"PS file:   {ps_path}")
    print(f"PS size:   {ps_total_size / 1024:.0f} KB")
    print(f"Truncated: {ps_truncated}")
    print(f"Plan:      {plan_path}")
    print(f"Round:     {args.iteration + 1}")
    print(f"Base URL:  {base_url}")
    print(f"Timeout:   {timeout}s")
    print("Calling deepseek-v4-pro ...")

    # Call model
    try:
        result = call_deepseek(ps_content, prompt, api_key, base_url, timeout)
    except Exception as e:
        print(f"Error: deepseek API call failed: {e}")
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
        stripped = line.strip()
        if any(kw in stripped for kw in
               ["Scores", "Summary", "Fix Priority", "Failed Items", "Improvement"]):
            print(stripped)


if __name__ == "__main__":
    main()
