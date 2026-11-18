"""Colours of the django-unfold admin, derived from the theme's SCSS.

Unfold writes UNFOLD["COLORS"] to its --color-<name>-<weight> CSS variables. Primary is
generated from $primary in theme/static/scss/custom.scss, so the admin follows the public
site's brand colour; Unfold draws buttons, links and checkboxes from its 600. Base is
Bootstrap's gray scale, which the theme does not set either.

The SCSS is read when the admin first renders a page, not when the settings are imported:
the documentation build imports them (docs/conf.py) from a checkout without the theme repo.
"""

import functools
import math
import re
from pathlib import Path

from django.core.exceptions import ImproperlyConfigured

THEME_SCSS = Path(__file__).resolve().parent.parent / "theme" / "static" / "scss" / "custom.scss"

# Lightness (%) and chroma of Tailwind's red scale. Its steps are tuned for contrast at
# every weight, so the admin palette reuses them around the theme's own colour.
_TAILWIND_STEPS = {
    "50": (97.1, 0.013),
    "100": (93.6, 0.032),
    "200": (88.5, 0.062),
    "300": (80.8, 0.114),
    "400": (70.4, 0.191),
    "500": (63.7, 0.237),
    "600": (57.7, 0.245),
    "700": (50.5, 0.213),
    "800": (44.4, 0.177),
    "900": (39.6, 0.141),
    "950": (25.8, 0.092),
}

BASE_SCALE = {
    "50": "#f8f9fa",
    "100": "#e9ecef",
    "200": "#dee2e6",
    "300": "#ced4da",
    "400": "#adb5bd",
    "500": "#6c757d",
    "600": "#495057",
    "700": "#343a40",
    "800": "#2b3035",
    "900": "#212529",
    "950": "#16191c",
}


def _hex_to_oklch(value: str) -> tuple[float, float, float]:
    """Convert #rrggbb to OKLCH lightness (%), chroma and hue (degrees)."""

    def linear(channel: str) -> float:
        c = int(channel, 16) / 255
        return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4

    r, g, b = linear(value[1:3]), linear(value[3:5]), linear(value[5:7])
    l_ = (0.4122214708 * r + 0.5363325363 * g + 0.0514459929 * b) ** (1 / 3)
    m_ = (0.2119034982 * r + 0.6806995451 * g + 0.1073969566 * b) ** (1 / 3)
    s_ = (0.0883024619 * r + 0.2817188376 * g + 0.6299787005 * b) ** (1 / 3)
    lightness = 0.2104542553 * l_ + 0.7936177850 * m_ - 0.0040720468 * s_
    a = 1.9779984951 * l_ - 2.4285922050 * m_ + 0.4505937099 * s_
    b_ = 0.0259040371 * l_ + 0.7827717662 * m_ - 0.8086757660 * s_
    return lightness * 100, math.hypot(a, b_), math.degrees(math.atan2(b_, a)) % 360


def scss_colour(name: str, scss: Path = THEME_SCSS) -> str:
    # Only an uncommented "$name: #rrggbb;" line counts, so the commented-out
    # alternative palettes in the file are ignored.
    match = re.search(rf"^\${name}:\s*(#[0-9a-fA-F]{{6}})\s*;", scss.read_text(), re.MULTILINE)
    if match is None:
        raise ImproperlyConfigured(f"{scss} must set ${name} to a #rrggbb colour for the admin palette.")
    return match.group(1)


def primary_scale(brand: str) -> dict[str, str]:
    """Build Unfold's 11 primary weights around brand, which becomes weight 600.

    Tailwind's lightness steps are rescaled so that 600 lands on the brand's own
    lightness while 50 and 950 stay put, which keeps the weights in order however
    light or dark the brand is. Chroma keeps Tailwind's proportions to 600.
    """
    lightness, chroma, hue = _hex_to_oklch(brand)
    top, anchor, bottom = _TAILWIND_STEPS["50"][0], _TAILWIND_STEPS["600"][0], _TAILWIND_STEPS["950"][0]
    anchor_chroma = _TAILWIND_STEPS["600"][1]
    scale = {}
    for weight, (step_lightness, step_chroma) in _TAILWIND_STEPS.items():
        if step_lightness >= anchor:
            shade = lightness + (step_lightness - anchor) * (top - lightness) / (top - anchor)
        else:
            shade = bottom + (step_lightness - bottom) * (lightness - bottom) / (anchor - bottom)
        scale[weight] = f"oklch({shade:.1f}% {chroma * step_chroma / anchor_chroma:.3f} {hue:.2f})"
    scale["600"] = brand
    return scale


@functools.cache
def _theme_primary_scale() -> dict[str, str]:
    return primary_scale(scss_colour("primary"))


def theme_primary(_request=None) -> dict[str, str]:
    """Unfold calls a colour's callable for every page; it converts the values in place, so it
    gets a copy of the scale, which is only computed once."""
    return dict(_theme_primary_scale())


def unfold_colors() -> dict[str, object]:
    return {"base": BASE_SCALE, "primary": theme_primary}
