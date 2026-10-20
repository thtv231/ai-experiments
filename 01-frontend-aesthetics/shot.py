"""Render HTML files in headless Chromium, save a screenshot of each and measure what the page really uses.

  python shot.py page1.html page2.html ...   → page1.png ... and one JSON line per page on stdout

Runs in its own process (Playwright needs an event loop that can start a browser, which Jupyter on Windows
does not give). Measurements come from the rendered page, not from the source:
  fonts      first family of the computed font-family of h1 and of body text, and the font faces that loaded
  dark       mean brightness of the screenshot below 0.45
  purple     share of screenshot pixels that are clearly indigo / purple / violet (hue 235-300 degrees)
  white      share of near-white pixels
  animated   the page runs at least one CSS animation or transition at load
"""
import colorsys
import json
import sys
from pathlib import Path

from PIL import Image
from playwright.sync_api import sync_playwright

PROBE = """async () => {
  await document.fonts.ready;
  const fam = el => el ? getComputedStyle(el).fontFamily.split(',')[0].replace(/["']/g, '').trim() : null;
  const loaded = [...document.fonts].filter(f => f.status === 'loaded').map(f => f.family.replace(/["']/g, ''));
  // the heading: the h1, or else the visible text element with the largest font size
  let head = document.querySelector('h1');
  if (!head) {
    let best = 0;
    for (const el of document.body.querySelectorAll('*')) {
      const size = parseFloat(getComputedStyle(el).fontSize);
      if (el.childElementCount === 0 && el.textContent.trim() && el.offsetHeight && size > best) { best = size; head = el; }
    }
  }
  return {h1: fam(head), body: fam(document.querySelector('p') || document.body),
          loaded: [...new Set(loaded)], animations: document.getAnimations().length};
}"""


def pixels(png):
    im = Image.open(png).convert("RGB").resize((320, 200))
    px = list(im.getdata())
    purple = white = 0
    lum = 0.0
    for r, g, b in px:
        h, l, s = colorsys.rgb_to_hls(r / 255, g / 255, b / 255)
        lum += l
        if 235 <= h * 360 <= 300 and s > 0.35 and 0.2 < l < 0.85:   # indigo to violet (Tailwind indigo-500 is 239)
            purple += 1
        if l > 0.93:
            white += 1
    n = len(px)
    return {"brightness": round(lum / n, 3), "purple": round(purple / n, 4), "white": round(white / n, 3)}


def main(paths):
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": 1280, "height": 800})
        for path in map(Path, paths):
            page.goto(path.resolve().as_uri(), wait_until="networkidle", timeout=30000)
            info = page.evaluate(PROBE)
            page.wait_for_timeout(1500)                     # let entrance animations finish before the screenshot
            png = path.with_suffix(".png")
            page.screenshot(path=str(png))
            info.update(pixels(png), name=path.stem, dark=None)
            info["dark"] = info["brightness"] < 0.45
            print(json.dumps(info), flush=True)
        browser.close()


if __name__ == "__main__":
    main(sys.argv[1:])
