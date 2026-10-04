"""
LabUI appearance themes — palettes and font sets, compiled to static/themes.css.

    python3 submission_strategy/jfr/web/themes.py        # rewrite static/themes.css

Every colour in the app resolves to a CSS variable, in two layers:

  * Semantic tokens used by base.html's components and the page stylesheets:
    --ground, --surface, --raised, --sunken, --ink, --ink-muted, --line,
    --signal (the accent), --data (secondary), --live, … — one set for light
    mode and one for dark.
  * Tailwind ramps (`bg-brand-600`, `text-ink-400`, `dark:bg-ink-900`…) read
    --c-<name>-<step> as "R G B" channels, so utilities follow the palette and
    keep alpha modifiers (`bg-brand-500/20`). Ramps do not change with dark
    mode; templates pick a different step under `dark:` as Tailwind intends.

A palette is chosen with `<html data-palette="…">` and a font set with
`<html data-font="…">`; base.html sets both before first paint from
localStorage. "bench" is the default and keeps its hand-tuned values exactly;
the other palettes are generated in OKLCH so their ramps are perceptually even.

Stdlib only.
"""
from __future__ import annotations

import math
from pathlib import Path

OUT = Path(__file__).parent / "static" / "themes.css"
STEPS = [50, 100, 200, 300, 400, 500, 600, 700, 800, 900, 950]


# ── Colour math (sRGB ↔ OKLab/OKLCH) ──────────────────────────────────────────

def _srgb_to_lin(c: float) -> float:
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def _lin_to_srgb(c: float) -> float:
    return 12.92 * c if c <= 0.0031308 else 1.055 * c ** (1 / 2.4) - 0.055


def hex_to_oklch(h: str) -> tuple[float, float, float]:
    h = h.lstrip("#")
    r, g, b = (_srgb_to_lin(int(h[i:i + 2], 16) / 255) for i in (0, 2, 4))
    l_ = (0.4122214708 * r + 0.5363325363 * g + 0.0514459929 * b) ** (1 / 3)
    m_ = (0.2119034982 * r + 0.6806995451 * g + 0.1073969566 * b) ** (1 / 3)
    s_ = (0.0883024619 * r + 0.2817188376 * g + 0.6299787005 * b) ** (1 / 3)
    L = 0.2104542553 * l_ + 0.7936177850 * m_ - 0.0040720468 * s_
    a = 1.9779984951 * l_ - 2.4285922050 * m_ + 0.4505937099 * s_
    bb = 0.0259040371 * l_ + 0.7827717662 * m_ - 0.8086757660 * s_
    return L, math.hypot(a, bb), math.degrees(math.atan2(bb, a)) % 360


def _oklch_to_rgb(L: float, C: float, H: float) -> tuple[float, float, float]:
    a, b = C * math.cos(math.radians(H)), C * math.sin(math.radians(H))
    l_ = (L + 0.3963377774 * a + 0.2158037573 * b) ** 3
    m_ = (L - 0.1055613458 * a - 0.0638541728 * b) ** 3
    s_ = (L - 0.0894841775 * a - 1.2914855480 * b) ** 3
    r = 4.0767416621 * l_ - 3.3077115913 * m_ + 0.2309699292 * s_
    g = -1.2684380046 * l_ + 2.6097574011 * m_ - 0.3413193965 * s_
    bl = -0.0041960863 * l_ - 0.7034186147 * m_ + 1.7076147010 * s_
    return r, g, bl


def oklch(L: float, C: float, H: float) -> str:
    """OKLCH → #rrggbb, reducing chroma until the colour fits in sRGB."""
    L = min(max(L, 0.0), 1.0)
    for _ in range(40):
        r, g, b = _oklch_to_rgb(L, C, H)
        if all(-1e-4 <= v <= 1 + 1e-4 for v in (r, g, b)):
            break
        C *= 0.92
    r, g, b = (min(max(_lin_to_srgb(min(max(v, 0), 1)), 0), 1) for v in _oklch_to_rgb(L, C, H))
    return "#{:02x}{:02x}{:02x}".format(*(round(v * 255) for v in (r, g, b)))


def channels(hexc: str) -> str:
    h = hexc.lstrip("#")
    return " ".join(str(int(h[i:i + 2], 16)) for i in (0, 2, 4))


def rgba(hexc: str, alpha: float) -> str:
    return f"rgba({channels(hexc).replace(' ', ',')},{alpha})"


# Lightness per ramp step, light → dark; chroma tapers at both ends.
_RAMP_L = {50: .975, 100: .945, 200: .89, 300: .815, 400: .725, 500: .64,
           600: .555, 700: .475, 800: .395, 900: .325, 950: .235}
_RAMP_C = {50: .22, 100: .38, 200: .62, 300: .85, 400: 1.0, 500: 1.0,
           600: .95, 700: .85, 800: .72, 900: .58, 950: .45}


def ramp(base_hex: str, chroma: float | None = None) -> dict[int, str]:
    _, C, H = hex_to_oklch(base_hex)
    C = C if chroma is None else chroma
    return {s: oklch(_RAMP_L[s], C * _RAMP_C[s], H) for s in STEPS}


def neutral_ramp(hue: float, chroma: float) -> dict[int, str]:
    Ls = {50: .982, 100: .955, 200: .905, 300: .82, 400: .68, 500: .54,
          600: .43, 700: .35, 800: .265, 900: .205, 950: .155}
    return {s: oklch(Ls[s], chroma * (1.6 if 300 <= s <= 700 else 1.0), hue) for s in STEPS}


# ── Palettes ──────────────────────────────────────────────────────────────────
# signal = the accent (buttons, active nav, links); data = the secondary colour
# (measurements, your-own-text, positive states); neutral = (hue, chroma) of
# the paper-and-ink greys.

PALETTES: dict[str, dict] = {
    "bench":    {"label": "Bench",    "blurb": "Vermillion on warm paper",
                 "signal": "#de4b2c", "data": "#0e7c6e", "live": "#8fa31e", "neutral": (75, .012)},
    "sage":     {"label": "Sage",     "blurb": "Moss green on soft linen",
                 "signal": "#3f7f52", "data": "#2a6f9e", "live": "#9a8f1e", "neutral": (135, .010)},
    "harbor":   {"label": "Harbor",   "blurb": "Ink blue on cool grey",
                 "signal": "#2c64c9", "data": "#0e8174", "live": "#7f9c1c", "neutral": (250, .012)},
    "plum":     {"label": "Plum",     "blurb": "Violet on pale lilac-grey",
                 "signal": "#7b4bd0", "data": "#16827a", "live": "#8fa31e", "neutral": (300, .010)},
    "ochre":    {"label": "Ochre",    "blurb": "Amber on cream",
                 "signal": "#b8650f", "data": "#2a7064", "live": "#7f9c1c", "neutral": (85, .020)},
    "graphite": {"label": "Graphite", "blurb": "Monochrome, pencil on paper",
                 "signal": "#33373d", "data": "#3f6c8c", "live": "#6f8a2a", "neutral": (260, .004)},
}
DEFAULT_PALETTE = "bench"

# Bench keeps the hand-tuned values it shipped with.
_BENCH_RAMPS = {
    "ink":   ["#faf7f1", "#f1ebe1", "#e3dacb", "#c8bca8", "#9a9184", "#6e675d",
              "#4e4941", "#3a352e", "#262320", "#1a1815", "#100f0d"],
    "brand": ["#fdf0ec", "#fbddd4", "#f7bcab", "#f1937a", "#e96a48", "#de4b2c",
              "#c33a1e", "#9e2d17", "#7a2413", "#5c1c10", "#35100a"],
    "data":  ["#e6f5f2", "#c3e8e2", "#8fd4c9", "#55bcae", "#26a094", "#0e7c6e",
              "#0a6459", "#095047", "#0a3f39", "#08322e", "#041e1b"],
    "live":  ["#f7fae4", "#edf3c3", "#dde78d", "#c8d84f", "#b0c42c", "#8fa31e",
              "#6f8017", "#556214", "#434d15", "#394115", "#1d2306"],
}
_BENCH_LIGHT = {
    "ground": "#efeae1", "surface": "#fbf8f3", "raised": "#ffffff", "sunken": "#f4efe6",
    "stock": "#f4e7cd", "stock-line": "#ddcaa4", "ink": "#171512", "ink-muted": "#6e675d",
    "ink-faint": "#9a9184", "line": "#e6dece", "line-firm": "#d3c8b6", "signal": "#de4b2c",
    "signal-ink": "#9e2d17", "signal-wash": "#fdf0ec", "data": "#0e7c6e", "data-wash": "#e6f5f2",
    "live": "#8fa31e", "live-wash": "#f7fae4", "warn": "#b8791b", "danger": "#c0392b",
    "grid": "rgba(23,21,18,0.055)",
}
_BENCH_DARK = {
    "ground": "#0c0b0a", "surface": "#141210", "raised": "#1c1a16", "sunken": "#171512",
    "stock": "#241f17", "stock-line": "#453b28", "ink": "#f2ece2", "ink-muted": "#a79e90",
    "ink-faint": "#7a7266", "line": "#2b2721", "line-firm": "#3c362d", "signal": "#ff6a45",
    "signal-ink": "#ff8f73", "signal-wash": "#2a1611", "data": "#2fbfac", "data-wash": "#0c2723",
    "live": "#c6db3a", "live-wash": "#232709", "warn": "#e3a53d", "danger": "#e8695c",
    "grid": "rgba(242,236,226,0.05)",
}


def _palette_tokens(p: dict) -> tuple[dict, dict, dict]:
    """→ (ramps, light semantic tokens, dark semantic tokens)."""
    nh, nc = p["neutral"]
    sL, sC, sH = hex_to_oklch(p["signal"])
    dL, dC, dH = hex_to_oklch(p["data"])
    lL, lC, lH = hex_to_oklch(p["live"])
    n = lambda L, c=nc: oklch(L, c, nh)                       # noqa: E731
    ramps = {
        "ink": neutral_ramp(nh, nc),
        "brand": ramp(p["signal"]),
        "data": ramp(p["data"]),
        "live": ramp(p["live"]),
    }
    ink_l = n(.2, nc * 1.5)
    light = {
        "ground": n(.935), "surface": n(.982), "raised": n(.997, nc * .4), "sunken": n(.955),
        "stock": oklch(.955, min(sC, .1) * .3, sH), "stock-line": oklch(.86, min(sC, .1) * .5, sH),
        "ink": ink_l, "ink-muted": n(.49, nc * 1.6), "ink-faint": n(.65, nc * 1.4),
        "line": n(.905), "line-firm": n(.845),
        "signal": p["signal"], "signal-ink": oklch(max(sL - .14, .25), sC, sH),
        "signal-wash": oklch(.965, sC * .22, sH),
        "data": p["data"], "data-wash": oklch(.965, dC * .25, dH),
        "live": p["live"], "live-wash": oklch(.97, lC * .25, lH),
        "warn": "#b8791b", "danger": "#c0392b",
        "grid": rgba(ink_l, 0.055),
    }
    ink_d = n(.94, nc * .8)
    # A near-black accent (graphite) cannot simply be lightened into a usable
    # dark-mode accent; give it a light grey instead.
    dark_sig = oklch(.80, sC, sH) if sL < .35 and sC < .03 else oklch(max(sL, .70), sC, sH)
    dark = {
        "ground": n(.135), "surface": n(.17), "raised": n(.205), "sunken": n(.185),
        "stock": oklch(.235, min(sC, .1) * .35, sH), "stock-line": oklch(.34, min(sC, .1) * .5, sH),
        "ink": ink_d, "ink-muted": n(.74, nc * 1.4), "ink-faint": n(.58, nc * 1.3),
        "line": n(.27), "line-firm": n(.33),
        "signal": dark_sig, "signal-ink": oklch(.82, sC * .8, sH),
        "signal-wash": oklch(.24, sC * .35, sH),
        "data": oklch(max(dL, .72), dC, dH), "data-wash": oklch(.23, dC * .35, dH),
        "live": oklch(.84, lC, lH), "live-wash": oklch(.24, lC * .3, lH),
        "warn": "#e3a53d", "danger": "#e8695c",
        "grid": rgba(ink_d, 0.05),
    }
    return ramps, light, dark


# ── Font sets ─────────────────────────────────────────────────────────────────
# `href` is a Google Fonts stylesheet (None = system fonts, nothing to load).

FONTS: dict[str, dict] = {
    "editorial": {
        "label": "Editorial", "blurb": "Fraunces · Public Sans · JetBrains Mono",
        "sans": "'Public Sans', system-ui, sans-serif",
        "display": "'Fraunces', Georgia, serif",
        "mono": "'JetBrains Mono', ui-monospace, monospace",
        "href": "https://fonts.googleapis.com/css2?family=Fraunces:opsz,wght@9..144,400;9..144,600;9..144,700"
                "&family=Public+Sans:ital,wght@0,400;0,500;0,600;0,700;1,400"
                "&family=JetBrains+Mono:wght@400;500;700&display=swap",
    },
    "system": {
        "label": "System", "blurb": "Your Mac's own fonts — SF Pro, New York, SF Mono",
        "sans": "-apple-system, BlinkMacSystemFont, 'SF Pro Text', 'Helvetica Neue', system-ui, sans-serif",
        "display": "ui-serif, 'New York', 'Iowan Old Style', Georgia, serif",
        "mono": "ui-monospace, 'SF Mono', Menlo, monospace",
        "href": None,
    },
    "classic": {
        "label": "Classic", "blurb": "Source Serif · Inter · IBM Plex Mono",
        "sans": "'Inter', system-ui, sans-serif",
        "display": "'Source Serif 4', Georgia, serif",
        "mono": "'IBM Plex Mono', ui-monospace, monospace",
        "href": "https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700"
                "&family=Source+Serif+4:opsz,wght@8..60,400;8..60,600;8..60,700"
                "&family=IBM+Plex+Mono:wght@400;500&display=swap",
    },
    "plex": {
        "label": "Plex", "blurb": "IBM Plex Serif · Sans · Mono — one engineered family",
        "sans": "'IBM Plex Sans', system-ui, sans-serif",
        "display": "'IBM Plex Serif', Georgia, serif",
        "mono": "'IBM Plex Mono', ui-monospace, monospace",
        "href": "https://fonts.googleapis.com/css2?family=IBM+Plex+Sans:ital,wght@0,400;0,500;0,600;0,700;1,400"
                "&family=IBM+Plex+Serif:wght@400;600;700&family=IBM+Plex+Mono:wght@400;500&display=swap",
    },
    "readable": {
        "label": "Readable", "blurb": "Literata · Atkinson Hyperlegible — built for legibility",
        "sans": "'Atkinson Hyperlegible', system-ui, sans-serif",
        "display": "'Literata', Georgia, serif",
        "mono": "'IBM Plex Mono', ui-monospace, monospace",
        "href": "https://fonts.googleapis.com/css2?family=Atkinson+Hyperlegible:ital,wght@0,400;0,700;1,400"
                "&family=Literata:opsz,wght@7..72,400;7..72,600;7..72,700"
                "&family=IBM+Plex+Mono:wght@400;500&display=swap",
    },
    "modern": {
        "label": "Modern", "blurb": "Space Grotesk · DM Sans · DM Mono",
        "sans": "'DM Sans', system-ui, sans-serif",
        "display": "'Space Grotesk', system-ui, sans-serif",
        "mono": "'DM Mono', ui-monospace, monospace",
        "href": "https://fonts.googleapis.com/css2?family=DM+Sans:opsz,wght@9..40,400;9..40,500;9..40,600;9..40,700"
                "&family=Space+Grotesk:wght@500;600;700&family=DM+Mono:wght@400;500&display=swap",
    },
}
DEFAULT_FONT = "editorial"


# ── CSS emission ──────────────────────────────────────────────────────────────

def _decls(ramps: dict, sem: dict | None) -> str:
    out = []
    for name, r in ramps.items():
        vals = r if isinstance(r, list) else [r[s] for s in STEPS]
        out += [f"--c-{name}-{s}:{channels(v)}" for s, v in zip(STEPS, vals)]
    if sem:
        out += [f"--{k}:{v}" for k, v in sem.items()]
    return ";".join(out)


def build_css() -> str:
    parts = [
        "/* Generated by submission_strategy/jfr/web/themes.py — do not edit by hand. */",
        # Bench is the default: plain :root / html.dark, lowest specificity.
        f":root{{{_decls(_BENCH_RAMPS, _BENCH_LIGHT)}}}",
        f"html.dark{{{_decls({}, _BENCH_DARK)}}}",
    ]
    for key, p in PALETTES.items():
        if key == DEFAULT_PALETTE:
            continue
        ramps, light, dark = _palette_tokens(p)
        # html[data-palette] (0,1,1) beats html.dark (0,1,1) by source order;
        # html.dark[data-palette] (0,2,1) beats both.
        parts.append(f'html[data-palette="{key}"]{{{_decls(ramps, light)}}}')
        parts.append(f'html.dark[data-palette="{key}"]{{{_decls({}, dark)}}}')
    # Font sets.
    d = FONTS[DEFAULT_FONT]
    parts.append(f":root{{--font-sans:{d['sans']};--font-display:{d['display']};--font-mono:{d['mono']}}}")
    for key, f in FONTS.items():
        if key == DEFAULT_FONT:
            continue
        parts.append(f'html[data-font="{key}"]{{--font-sans:{f["sans"]};'
                     f'--font-display:{f["display"]};--font-mono:{f["mono"]}}}')
    return "\n".join(parts) + "\n"


def manifest() -> dict:
    """What the appearance picker needs: names, blurbs, swatches, font hrefs."""
    pals = {}
    for key, p in PALETTES.items():
        if key == DEFAULT_PALETTE:
            light, dark = _BENCH_LIGHT, _BENCH_DARK
        else:
            _, light, dark = _palette_tokens(p)
        pals[key] = {"label": p["label"], "blurb": p["blurb"],
                     "swatch": [light["surface"], light["signal"], light["data"], dark["surface"]]}
    fonts = {k: {"label": f["label"], "blurb": f["blurb"], "href": f["href"],
                 "sans": f["sans"], "display": f["display"]} for k, f in FONTS.items()}
    return {"palettes": pals, "fonts": fonts,
            "defaults": {"palette": DEFAULT_PALETTE, "font": DEFAULT_FONT}}


if __name__ == "__main__":
    css = build_css()
    OUT.write_text(css, encoding="utf-8")
    print(f"{OUT} — {len(PALETTES)} palettes, {len(FONTS)} font sets, {len(css):,} bytes")
