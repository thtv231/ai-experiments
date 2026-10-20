"""Prompting for frontend aesthetics: a measured experiment.

3 models x 3 pages x 4 system prompts = 36 generated web pages. Each page is rendered in headless
Chromium (shot.py), screenshotted and measured: heading/body font, dark or light, share of indigo/purple
pixels, CSS animations at load.

  python experiment.py                 # generate missing pages, then measure all of them
  python experiment.py --measure-only  # only re-measure the pages already in results/pages
  python experiment.py --models gpt-oss-120b --tasks saas   # a smaller run

Keys come from a .env file next to this script (or the environment):
  GROQ_API_KEY=...     free key at console.groq.com (gpt-oss-120b, qwen3.6-27b)
  OPENAI_API_KEY=...   only needed for gpt-4o-mini
Every reply is cached in results/cache/, so re-running costs nothing. Delete a cache file to regenerate.

Idea: Anthropic Claude Cookbooks (MIT), coding/prompting_for_frontend_aesthetics.ipynb.
"""
import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
PAGES = HERE / "results" / "pages"
CACHE = HERE / "results" / "cache"

BASE = """You are an expert frontend engineer. Build exactly what the user asks for as ONE self-contained
HTML file: CSS in a <style> tag, no JavaScript frameworks, fonts only from Google Fonts, no external images.
Reply with the HTML file only, in a single ```html code block."""

AESTHETICS = """<frontend_aesthetics>
Left alone, you drift toward the same safe design every time. Make the choices a good human designer would defend.
- Typography: pick distinctive Google Fonts that suit the subject. Pair a characterful display face with a
  readable body face, and use strong contrasts of size and weight.
- Colour and theme: commit to one clear palette, written as CSS variables: a dominant colour and one or two
  sharp accents. Borrow from real sources: magazines, film posters, editor themes, a place or an era.
- Motion: one well-planned entrance with staggered delays, in CSS only, beats many small effects.
- Backgrounds: create depth with layered gradients, patterns or texture instead of one flat colour.
- Avoid: Inter, Roboto, Arial and system fonts; purple gradients on white; the same centred hero with three
  cards every time.
Make every design different: light or dark, different fonts, different layout.
</frontend_aesthetics>"""

TYPOGRAPHY = """<typography>
Typography makes or breaks a page. Never use Inter, Roboto, Arial, Open Sans or system fonts. Choose
distinctive Google Fonts that fit the subject: for example an editorial serif, a geometric display face or a
characterful monospace. Pair one display face with one body face, and use big jumps in size and weight.
</typography>"""

THEME = """<theme>
Always design in a vintage letterpress style: cream paper background, ink-black text, one vermilion red
accent, serif headlines, thin rules between sections, no gradients and no rounded cards.
</theme>"""

VARIANTS = {"base": BASE, "full": BASE + "\n\n" + AESTHETICS, "type": BASE + "\n\n" + TYPOGRAPHY,
            "theme": BASE + "\n\n" + THEME}

TASKS = {
    "saas": "A landing page for Huddle, an app that schedules team meetings.",
    "blog": "The home page of a travel writer's personal blog, showing three recent posts.",
    "bakery": "A sales dashboard for a small neighbourhood bakery: today's revenue, best sellers, "
              "and a weekly revenue chart drawn with CSS.",
}

# name: (base_url, key variable, model id, extra request fields)
MODELS = {
    "gpt-oss-120b": ("https://api.groq.com/openai/v1", "GROQ_API_KEY", "openai/gpt-oss-120b", {}),
    "qwen3.6-27b": ("https://api.groq.com/openai/v1", "GROQ_API_KEY", "qwen/qwen3.6-27b",
                    {"extra_body": {"reasoning_format": "hidden"}}),
    "gpt-4o-mini": (None, "OPENAI_API_KEY", "gpt-4o-mini", {}),
}

GENERIC = {"inter", "roboto", "arial", "helvetica", "helvetica neue", "open sans", "segoe ui", "system-ui",
           "-apple-system", "sans-serif", "ui-sans-serif"}


def is_generic(font):
    return font is None or font.strip().lower() in GENERIC


def extract_html(reply):
    """The HTML inside the first ```html block (or the whole reply if there is no fence)."""
    reply = re.sub(r"<think>.*?</think>", "", reply, flags=re.S)
    m = re.search(r"```(?:html)?\s*\n(.*?)```", reply, re.S)
    return (m.group(1) if m else reply).strip()


def generate(model, variant, task):
    """One request → pages/<model>_<variant>_<task>.html. Replies are cached by request content."""
    from openai import OpenAI
    base_url, key_env, mid, extra = MODELS[model]
    request = {"model": mid, "temperature": 1.0, "max_tokens": 12000, "seed": 0,
               "messages": [{"role": "system", "content": VARIANTS[variant]}, {"role": "user", "content": TASKS[task]}]}
    CACHE.mkdir(parents=True, exist_ok=True)
    cache = CACHE / (hashlib.sha256(json.dumps(request, sort_keys=True).encode()).hexdigest()[:24] + ".json")
    if cache.exists():
        reply = json.loads(cache.read_text(encoding="utf-8"))["reply"]
    else:
        client = OpenAI(api_key=os.environ[key_env], base_url=base_url) if base_url else OpenAI(api_key=os.environ[key_env])
        reply = client.chat.completions.create(**request, **extra).choices[0].message.content or ""
        cache.write_text(json.dumps({"request": request, "reply": reply}, ensure_ascii=False), encoding="utf-8")
    path = PAGES / f"{model}_{variant}_{task}.html"
    path.write_text(extract_html(reply), encoding="utf-8")
    return path


def measure(paths):
    out = subprocess.run([sys.executable, str(HERE / "shot.py"), *map(str, paths)], capture_output=True,
                         text=True, encoding="utf-8", check=True).stdout
    return {m["name"]: m for m in map(json.loads, out.splitlines())}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--measure-only", action="store_true")
    ap.add_argument("--models", nargs="*", default=list(MODELS))
    ap.add_argument("--tasks", nargs="*", default=list(TASKS))
    ap.add_argument("--variants", nargs="*", default=list(VARIANTS))
    a = ap.parse_args()
    try:
        from dotenv import load_dotenv
        load_dotenv(HERE / ".env")
    except ImportError:
        pass
    PAGES.mkdir(parents=True, exist_ok=True)
    combos = [(m, v, t) for m in a.models for v in a.variants for t in a.tasks]
    if not a.measure_only:
        for m, v, t in combos:
            if not (PAGES / f"{m}_{v}_{t}.html").exists():
                print("generate", m, v, t, flush=True)
                generate(m, v, t)
    paths = [PAGES / f"{m}_{v}_{t}.html" for m, v, t in combos if (PAGES / f"{m}_{v}_{t}.html").exists()]
    rows = []
    for name, mm in measure(paths).items():
        model, variant, task = name.split("_")
        rows.append({"model": model, "variant": variant, "task": task, "h1": mm["h1"], "body": mm["body"],
                     "generic": is_generic(mm["h1"]), "generic_body": is_generic(mm["body"]),
                     "purple": mm["purple"] > 0.02, "dark": mm["dark"], "animated": mm["animations"] > 0})
    print(f"\n{'prompt':7} {'pages':>5} {'generic body':>13} {'indigo>2%':>10} {'dark':>5} {'animated':>9} {'heading fonts':>14}")
    for v in a.variants:
        r = [x for x in rows if x["variant"] == v]
        if r:
            print(f"{v:7} {len(r):5} {sum(x['generic_body'] for x in r):13} {sum(x['purple'] for x in r):10} "
                  f"{sum(x['dark'] for x in r):5} {sum(x['animated'] for x in r):9} {len({x['h1'] for x in r}):14}")
    (HERE / "results" / "measured.json").write_text(json.dumps(rows, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
