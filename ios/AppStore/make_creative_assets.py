#!/usr/bin/env python3
"""Generate App Store creative assets (header / search results / universal).

Brand colors sampled from the iOS app icon: sky gradient, white smile mark.
Apple specs (App Store Connect > creative assets specifications):
  universal 5244x2950 PNG, art safe area 1402x962 at (1921, 660)
  header    3840x1646,      art safe area 1646x661  at (1097, 493)
  search    3840x2560,      art safe area 2168x1030 at (836, 765)
No alpha channel is allowed, so every canvas is painted edge to edge.

Running it rewrites the .svg sources *and* re-renders the .png files that are
actually uploaded, so a layout change here can never leave stale PNGs behind.

Prerequisite: a Chrome-family browser, used headless as the SVG renderer — it
is the only one that ships on a stock macOS dev machine and it rasterises SVG
filters (the blurs and drop shadows this art leans on) correctly. Checked, in
order: $CHROME_BIN, Google Chrome, Chromium and Edge in /Applications, then
google-chrome / chromium / chromium-browser on $PATH. Install Chrome, or point
$CHROME_BIN at a binary, if none is found.

    python3 make_creative_assets.py

Each render is verified before the script exits: exact pixel dimensions, and a
PNG colour type with no alpha channel, both of which App Store Connect rejects
on a mismatch.
"""
import math
import os
import shutil
import struct
import subprocess
import sys
import tempfile

OUT = os.path.dirname(os.path.abspath(__file__))

# PNG colour types that carry an alpha channel; App Store Connect rejects both.
PNG_ALPHA_COLOR_TYPES = {4, 6}


def smiley(cx, cy, d, opacity=1.0, stroke="#ffffff", shadow=False, weight=1.0):
    """Smile mark, proportioned from the app icon (icon circle diameter 710)."""
    s = d / 710.0
    filt = ' filter="url(#soft)"' if shadow else ""
    return f'''<g transform="translate({cx:.1f},{cy:.1f})" opacity="{opacity}"{filt}>
  <circle r="{355*s:.2f}" fill="none" stroke="{stroke}" stroke-width="{19*s*weight:.2f}"/>
  <ellipse cx="{-122*s:.2f}" cy="{-105*s:.2f}" rx="{48*s:.2f}" ry="{80*s:.2f}" fill="{stroke}"/>
  <ellipse cx="{122*s:.2f}" cy="{-105*s:.2f}" rx="{48*s:.2f}" ry="{80*s:.2f}" fill="{stroke}"/>
  <path d="M {-157*s:.2f} {90*s:.2f} Q 0 {205*s:.2f} {157*s:.2f} {90*s:.2f}"
        fill="none" stroke="{stroke}" stroke-width="{23*s*weight:.2f}" stroke-linecap="round"/>
</g>'''


def bubble(cx, cy, r, op=0.14, ring=0.0, face=0.0, blur=None, gloss=True):
    """Glassy floating bubble, optionally ringed and carrying a faint smile."""
    g = [f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="{r:.1f}" fill="url(#glass)" opacity="{op+0.5:.2f}"/>',
         f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="{r:.1f}" fill="#ffffff" opacity="{op:.2f}"/>']
    if ring:
        g.append(f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="{r:.1f}" fill="none" stroke="#ffffff" '
                 f'stroke-width="{max(2.0, r*0.030):.1f}" opacity="{ring:.2f}"/>')
    if gloss:
        g.append(f'<ellipse cx="{cx-r*0.36:.1f}" cy="{cy-r*0.44:.1f}" rx="{r*0.30:.1f}" '
                 f'ry="{r*0.17:.1f}" fill="#ffffff" opacity="{min(0.42, op+0.16):.2f}" '
                 f'transform="rotate(-32 {cx-r*0.36:.1f} {cy-r*0.44:.1f})"/>')
    if face:
        g.append(smiley(cx, cy, r * 1.12, opacity=face))
    attr = f' filter="url(#{blur})"' if blur else ""
    return f'<g{attr}>' + "\n".join(g) + '</g>'


def cloud(cx, cy, w, h, op=0.22):
    """Soft cloud bank built from overlapping blurred ellipses."""
    parts = []
    for fx, fy, fr in ((-0.34, 0.10, 0.52), (0.0, -0.08, 0.74), (0.33, 0.12, 0.56),
                       (0.62, 0.22, 0.34), (-0.62, 0.24, 0.32)):
        parts.append(f'<ellipse cx="{cx+w*fx:.0f}" cy="{cy+h*fy:.0f}" '
                     f'rx="{w*fr*0.55:.0f}" ry="{h*fr*0.52:.0f}" fill="#ffffff"/>')
    return (f'<g opacity="{op}" filter="url(#cloudblur)">' + "".join(parts) + '</g>')


def rays(cx, cy, r, n=11, op=0.10):
    """Faint light rays fanning from the sun."""
    out = []
    for i in range(n):
        a0 = (i / n) * 2 * math.pi
        wid = 0.030 * 2 * math.pi
        x1, y1 = cx + r * math.cos(a0 - wid), cy + r * math.sin(a0 - wid)
        x2, y2 = cx + r * math.cos(a0 + wid), cy + r * math.sin(a0 + wid)
        out.append(f'<path d="M {cx:.0f} {cy:.0f} L {x1:.0f} {y1:.0f} L {x2:.0f} {y2:.0f} Z" '
                   f'fill="#FFF8E4"/>')
    return (f'<g opacity="{op}" filter="url(#cloudblur)">' + "".join(out) + '</g>')


def defs(w, h):
    return f'''<defs>
  <linearGradient id="sky" x1="0.08" y1="0" x2="0" y2="1">
    <stop offset="0%" stop-color="#DCF1FB"/>
    <stop offset="26%" stop-color="#AFDAF0"/>
    <stop offset="58%" stop-color="#7CBBE0"/>
    <stop offset="84%" stop-color="#5099CB"/>
    <stop offset="100%" stop-color="#3A86BB"/>
  </linearGradient>
  <radialGradient id="glass" cx="34%" cy="28%" r="78%">
    <stop offset="0%" stop-color="#ffffff" stop-opacity="0.26"/>
    <stop offset="62%" stop-color="#ffffff" stop-opacity="0.05"/>
    <stop offset="100%" stop-color="#2F7FB2" stop-opacity="0.10"/>
  </radialGradient>
  <radialGradient id="halo" cx="50%" cy="50%" r="50%">
    <stop offset="0%" stop-color="#ffffff" stop-opacity="0.42"/>
    <stop offset="48%" stop-color="#ffffff" stop-opacity="0.16"/>
    <stop offset="100%" stop-color="#ffffff" stop-opacity="0"/>
  </radialGradient>
  <radialGradient id="warm" cx="50%" cy="50%" r="50%">
    <stop offset="0%" stop-color="#FFFBEC" stop-opacity="0.92"/>
    <stop offset="34%" stop-color="#FFF4D4" stop-opacity="0.40"/>
    <stop offset="100%" stop-color="#FFF1CE" stop-opacity="0"/>
  </radialGradient>
  <linearGradient id="floor" x1="0" y1="0" x2="0" y2="1">
    <stop offset="0%" stop-color="#2A74A6" stop-opacity="0"/>
    <stop offset="100%" stop-color="#2A74A6" stop-opacity="0.34"/>
  </linearGradient>
  <radialGradient id="vig" cx="50%" cy="46%" r="72%">
    <stop offset="60%" stop-color="#1F6694" stop-opacity="0"/>
    <stop offset="100%" stop-color="#1F6694" stop-opacity="0.30"/>
  </radialGradient>
  <filter id="soft" x="-40%" y="-40%" width="180%" height="180%">
    <feDropShadow dx="0" dy="{h*0.008:.1f}" stdDeviation="{h*0.014:.1f}"
                  flood-color="#14577E" flood-opacity="0.30"/>
  </filter>
  <filter id="far" x="-40%" y="-40%" width="180%" height="180%">
    <feGaussianBlur stdDeviation="{h*0.006:.1f}"/>
  </filter>
  <filter id="near" x="-40%" y="-40%" width="180%" height="180%">
    <feGaussianBlur stdDeviation="{h*0.016:.1f}"/>
  </filter>
  <filter id="cloudblur" x="-40%" y="-40%" width="180%" height="180%">
    <feGaussianBlur stdDeviation="{h*0.045:.1f}"/>
  </filter>
</defs>'''


def compose(w, h, safe, layout, hero_frac=0.96):
    sx, sy, sw, sh = safe
    cx, cy = sx + sw / 2.0, sy + sh / 2.0
    d = min(sh * hero_frac, sw * 0.70)
    sun = layout["sun"]
    p = [defs(w, h), f'<rect width="{w}" height="{h}" fill="url(#sky)"/>']
    p.append(rays(sun[0] * w, sun[1] * h, max(w, h) * 0.62, op=0.09))
    p.append(f'<ellipse cx="{sun[0]*w:.0f}" cy="{sun[1]*h:.0f}" rx="{w*0.30:.0f}" '
             f'ry="{h*0.50:.0f}" fill="url(#warm)"/>')
    for c in layout["clouds"]:
        p.append(cloud(c[0] * w, c[1] * h, w * c[2], h * c[3], c[4]))
    for b in layout["far"]:
        p.append(bubble(b[0] * w, b[1] * h, h * b[2], op=b[3], blur="near", gloss=False))
    p.append(f'<ellipse cx="{cx:.0f}" cy="{cy:.0f}" rx="{d*1.35:.0f}" ry="{d*1.35:.0f}" '
             f'fill="url(#halo)"/>')
    for b in layout["mid"]:
        p.append(bubble(b[0] * w, b[1] * h, h * b[2], op=b[3], ring=b[4], face=b[5],
                        blur="far" if b[6] else None))
    p.append(smiley(cx, cy, d, shadow=True, weight=1.12))
    for b in layout["near"]:
        p.append(bubble(b[0] * w, b[1] * h, h * b[2], op=b[3], blur="near", gloss=False))
    p.append(f'<rect y="{h*0.62:.0f}" width="{w}" height="{h*0.38:.0f}" fill="url(#floor)"/>')
    p.append(f'<rect width="{w}" height="{h}" fill="url(#vig)"/>')
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" '
            f'viewBox="0 0 {w} {h}">\n' + "\n".join(p) + "\n</svg>")


def find_chrome():
    """Locate a headless-capable Chrome-family binary, or explain the failure."""
    candidates = [
        os.environ.get("CHROME_BIN"),
        "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
        "/Applications/Chromium.app/Contents/MacOS/Chromium",
        "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
        shutil.which("google-chrome"),
        shutil.which("chromium"),
        shutil.which("chromium-browser"),
    ]
    for path in candidates:
        if path and os.path.exists(path) and os.access(path, os.X_OK):
            return path
    raise SystemExit(
        "No Chrome-family browser found to render the PNGs. Install Google "
        "Chrome, or set CHROME_BIN to a Chrome/Chromium/Edge binary."
    )


def png_dimensions_and_color_type(path):
    """Read width, height and colour type straight out of the PNG's IHDR."""
    with open(path, "rb") as handle:
        header = handle.read(33)
    if header[:8] != b"\x89PNG\r\n\x1a\n" or header[12:16] != b"IHDR":
        raise SystemExit(f"{os.path.basename(path)} is not a PNG")
    width, height = struct.unpack(">II", header[16:24])
    return width, height, header[25]


def render(chrome, name, svg, w, h):
    """Rasterise one asset to <name>.png at exactly w x h, and verify it."""
    svg_path = os.path.join(OUT, name + ".svg")
    png_path = os.path.join(OUT, name + ".png")
    with open(svg_path, "w") as handle:
        handle.write(svg)

    # The SVG goes through a minimal HTML host so the page has no margin and no
    # scrollbars; it is scratch, so it lives in a temp dir rather than beside
    # the committed sources.
    html = (f'<!doctype html><meta charset="utf-8">'
            f'<style>html,body{{margin:0;padding:0;background:#3A86BB;}}'
            f'svg{{display:block;width:{w}px;height:{h}px;}}</style>{svg}')
    with tempfile.TemporaryDirectory() as tmp:
        html_path = os.path.join(tmp, name + ".html")
        with open(html_path, "w") as handle:
            handle.write(html)
        # --force-device-scale-factor=1 keeps CSS pixels and output pixels equal,
        # so --window-size is the exact asset size. No --default-background-color
        # override: the page paints its own opaque background and we want the
        # screenshot opaque (Apple rejects alpha).
        result = subprocess.run(
            [chrome, "--headless", "--disable-gpu", "--hide-scrollbars",
             "--force-device-scale-factor=1", f"--window-size={w},{h}",
             f"--screenshot={png_path}", f"file://{html_path}"],
            capture_output=True, text=True,
        )
    if not os.path.exists(png_path):
        raise SystemExit(
            f"Chrome produced no PNG for {name}:\n{result.stderr.strip()}")

    actual_w, actual_h, color_type = png_dimensions_and_color_type(png_path)
    if (actual_w, actual_h) != (w, h):
        raise SystemExit(
            f"{name}.png came out {actual_w}x{actual_h}, expected {w}x{h}")
    if color_type in PNG_ALPHA_COLOR_TYPES:
        raise SystemExit(
            f"{name}.png has an alpha channel (colour type {color_type}); "
            "App Store Connect rejects transparency")
    return png_path, actual_w, actual_h


CHROME = find_chrome()
RENDERED = []


def write(name, svg, w, h):
    RENDERED.append(render(CHROME, name, svg, w, h))


# bubbles: (x, y, r, opacity, ring, face, blurred)
# ---------------------------------------------------------------- universal
# Safe area sits high, so the lower third stays atmospheric (UI overlays it).
write("universal_5244x2950", compose(5244, 2950, (1921, 660, 1402, 962), {
    "sun": (0.80, 0.04),
    "clouds": [(0.20, 0.80, 0.52, 0.30, 0.20), (0.78, 0.86, 0.46, 0.26, 0.16),
               (0.50, 0.97, 0.70, 0.24, 0.14)],
    "far": [(0.42, 0.16, 0.016, 0.12), (0.60, 0.21, 0.012, 0.11),
            (0.30, 0.62, 0.020, 0.10), (0.70, 0.70, 0.015, 0.09)],
    "mid": [(0.155, 0.30, 0.108, 0.15, 0.32, 0.36, False),
            (0.265, 0.56, 0.062, 0.13, 0.26, 0.00, False),
            (0.075, 0.57, 0.040, 0.11, 0.20, 0.00, True),
            (0.345, 0.22, 0.034, 0.12, 0.22, 0.00, True),
            (0.845, 0.30, 0.100, 0.15, 0.30, 0.32, False),
            (0.745, 0.57, 0.058, 0.13, 0.24, 0.00, False),
            (0.925, 0.56, 0.038, 0.11, 0.20, 0.00, True),
            (0.655, 0.21, 0.030, 0.12, 0.22, 0.00, True)],
    "near": [(0.06, 0.94, 0.075, 0.09), (0.93, 0.92, 0.065, 0.08),
             (0.47, 0.88, 0.050, 0.07)],
}), 5244, 2950)

# ------------------------------------------------------------------- header
write("header_3840x1646", compose(3840, 1646, (1097, 493, 1646, 661), {
    "sun": (0.82, 0.02),
    "clouds": [(0.18, 0.88, 0.50, 0.34, 0.20), (0.80, 0.92, 0.44, 0.30, 0.16)],
    "far": [(0.40, 0.14, 0.022, 0.12), (0.62, 0.18, 0.018, 0.11),
            (0.33, 0.78, 0.026, 0.10)],
    "mid": [(0.140, 0.34, 0.150, 0.15, 0.32, 0.36, False),
            (0.255, 0.74, 0.088, 0.13, 0.26, 0.00, False),
            (0.055, 0.70, 0.056, 0.11, 0.20, 0.00, True),
            (0.310, 0.16, 0.046, 0.12, 0.22, 0.00, True),
            (0.860, 0.34, 0.142, 0.15, 0.30, 0.32, False),
            (0.750, 0.75, 0.082, 0.13, 0.24, 0.00, False),
            (0.950, 0.66, 0.050, 0.11, 0.20, 0.00, True),
            (0.690, 0.15, 0.040, 0.12, 0.22, 0.00, True)],
    "near": [(0.05, 0.96, 0.105, 0.09), (0.95, 0.95, 0.090, 0.08)],
}), 3840, 1646)

# ----------------------------------------------------------- search results
write("search_3840x2560", compose(3840, 2560, (836, 765, 2168, 1030), {
    "sun": (0.82, 0.04),
    "clouds": [(0.16, 0.86, 0.54, 0.30, 0.22), (0.82, 0.90, 0.48, 0.26, 0.17),
               (0.50, 0.99, 0.72, 0.24, 0.13)],
    "far": [(0.38, 0.10, 0.020, 0.12), (0.63, 0.12, 0.016, 0.11),
            (0.50, 0.70, 0.024, 0.09)],
    "mid": [(0.105, 0.22, 0.110, 0.15, 0.32, 0.36, False),
            (0.175, 0.74, 0.082, 0.13, 0.26, 0.00, False),
            (0.045, 0.48, 0.048, 0.11, 0.20, 0.00, True),
            (0.255, 0.08, 0.040, 0.12, 0.22, 0.00, True),
            (0.895, 0.23, 0.104, 0.15, 0.30, 0.32, False),
            (0.825, 0.75, 0.076, 0.13, 0.24, 0.00, False),
            (0.955, 0.50, 0.044, 0.11, 0.20, 0.00, True),
            (0.735, 0.08, 0.034, 0.12, 0.22, 0.00, True)],
    "near": [(0.07, 0.95, 0.080, 0.09), (0.92, 0.94, 0.070, 0.08),
             (0.50, 0.92, 0.055, 0.07)],
}), 3840, 2560)

for path, width, height in RENDERED:
    size_mb = os.path.getsize(path) / 1_000_000
    print(f"{os.path.basename(path):<28} {width}x{height}  {size_mb:.1f} MB  no alpha")
print(f"rendered {len(RENDERED)} assets with {os.path.basename(CHROME)}",
      file=sys.stderr)
