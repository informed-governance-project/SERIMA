import re

import pytest
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured

from governanceplatform.unfold_colors import THEME_SCSS, primary_scale, scss_colour

WEIGHTS = ["50", "100", "200", "300", "400", "500", "600", "700", "800", "900", "950"]


def _lightness(colour: str) -> float:
    return float(re.match(r"oklch\(([\d.]+)%", colour).group(1))


def test_admin_primary_is_the_theme_brand_colour():
    brand = re.search(r"^\$primary:\s*(#[0-9a-fA-F]{6})\s*;", THEME_SCSS.read_text(), re.MULTILINE).group(1)

    assert settings.UNFOLD["COLORS"]["primary"]["600"] == brand


def test_scss_colour_ignores_commented_palettes(tmp_path):
    scss = tmp_path / "custom.scss"
    scss.write_text("// IBPT\n// $primary: #34a9e1;\n$primary: #e40521;\n")

    assert scss_colour("primary", scss) == "#e40521"


def test_scss_colour_rejects_a_primary_that_is_not_a_hex_colour(tmp_path):
    scss = tmp_path / "custom.scss"
    scss.write_text("$primary: $brand-red;\n")

    with pytest.raises(ImproperlyConfigured):
        scss_colour("primary", scss)


@pytest.mark.parametrize("brand", ["#e40521", "#34a9e1", "#ffd500", "#2e2f7f"])
def test_primary_scale_goes_from_light_to_dark(brand):
    scale = primary_scale(brand)
    lighter = [_lightness(scale[w]) for w in WEIGHTS[:6]]
    darker = [_lightness(scale[w]) for w in WEIGHTS[7:]]

    assert list(scale) == WEIGHTS
    assert scale["600"] == brand
    assert lighter == sorted(lighter, reverse=True)
    assert darker == sorted(darker, reverse=True)
    assert lighter[-1] > darker[0]
