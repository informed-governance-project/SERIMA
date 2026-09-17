"""Capture SERIMA documentation screenshots with Playwright.

Reads a declarative shot list (``shots.toml``) and writes PNGs straight over the
files referenced from the ``.rst`` sources, so the docs never need editing and
``git diff`` shows exactly which screens drifted.
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import hmac
import json
import os
import struct
import sys
import time
import tomllib
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from playwright.sync_api import BrowserContext, Page, sync_playwright

HERE = Path(__file__).resolve().parent
DEFAULT_SPEC = HERE / "shots.toml"
DEFAULT_OUT = HERE.parent / "_static"

ANONYMOUS = "anonymous"


ANNOTATION_JS = """
(payload) => {
  const { items, color } = payload;
  const GAP = 10;
  const LEN = 90;
  const layer = document.createElement('div');
  layer.id = '__shot_annotations';
  layer.style.cssText = 'position:absolute;left:0;top:0;pointer-events:none;z-index:2147483647';
  document.body.appendChild(layer);

  const place = (el, left, top) => {
    el.style.position = 'absolute';
    el.style.left = `${left}px`;
    el.style.top = `${top}px`;
    layer.appendChild(el);
  };

  for (const item of items) {
    // A list of selectors is annotated as one shape covering all of them, which
    // is how adjacent form fields get a single outline.
    const selectors = Array.isArray(item.selector) ? item.selector : [item.selector];
    const rects = selectors.map((sel) => {
      const el = document.querySelector(sel);
      if (!el) throw new Error(`annotation target not found: ${sel}`);
      return el.getBoundingClientRect();
    });
    const rect = {
      left: Math.min(...rects.map((r) => r.left)),
      top: Math.min(...rects.map((r) => r.top)),
      right: Math.max(...rects.map((r) => r.right)),
      bottom: Math.max(...rects.map((r) => r.bottom)),
    };
    rect.width = rect.right - rect.left;
    rect.height = rect.bottom - rect.top;
    const box = {
      left: rect.left + window.scrollX,
      top: rect.top + window.scrollY,
      right: rect.right + window.scrollX,
      bottom: rect.bottom + window.scrollY,
    };
    box.cx = (box.left + box.right) / 2;
    box.cy = (box.top + box.bottom) / 2;

    if (item.redact) {
      // Solid block rather than `hide`, so the layout the reader sees is intact
      // while the secret underneath never reaches the published PNG.
      const patch = document.createElement('div');
      patch.style.cssText =
        `width:${rect.width}px;height:${rect.height}px;background:#9a9a9a;border:1px solid #555`;
      place(patch, box.left, box.top);
    }

    if (item.box) {
      const outline = document.createElement('div');
      outline.style.cssText =
        `width:${rect.width + 8}px;height:${rect.height + 8}px;border:3px solid ${color};` +
        // A white rule either side of the stroke keeps the callout legible on
        // whatever it lands on — brand-red buttons included, and in greyscale.
        'border-radius:6px;box-sizing:border-box;box-shadow:0 0 0 1px #fff, inset 0 0 0 1px #fff';
      place(outline, box.left - 4, box.top - 4);
    }

    if (!item.arrow) continue;

    const horizontal = item.arrow === 'left' || item.arrow === 'right';
    const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
    svg.setAttribute('width', horizontal ? LEN : 24);
    svg.setAttribute('height', horizontal ? 24 : LEN);
    // Coordinates run from the tail (0) to the tip (LEN), then the whole SVG is
    // flipped for the arrows that point back towards the element.
    const line = document.createElementNS('http://www.w3.org/2000/svg', 'line');
    const head = document.createElementNS('http://www.w3.org/2000/svg', 'polygon');
    if (horizontal) {
      line.setAttribute('x1', 2); line.setAttribute('y1', 12);
      line.setAttribute('x2', LEN - 12); line.setAttribute('y2', 12);
      head.setAttribute('points', `${LEN},12 ${LEN - 14},5 ${LEN - 14},19`);
    } else {
      line.setAttribute('x1', 12); line.setAttribute('y1', 2);
      line.setAttribute('x2', 12); line.setAttribute('y2', LEN - 12);
      head.setAttribute('points', `12,${LEN} 5,${LEN - 14} 19,${LEN - 14}`);
    }
    const halo = line.cloneNode();
    halo.setAttribute('stroke', '#fff');
    halo.setAttribute('stroke-width', 7);
    line.setAttribute('stroke', color);
    line.setAttribute('stroke-width', 3);
    head.setAttribute('fill', color);
    head.setAttribute('stroke', '#fff');
    head.setAttribute('stroke-width', 2);
    head.setAttribute('paint-order', 'stroke fill');
    svg.appendChild(halo);
    svg.appendChild(line);
    svg.appendChild(head);
    if (item.arrow === 'right') svg.style.transform = 'scaleX(-1)';
    if (item.arrow === 'bottom') svg.style.transform = 'scaleY(-1)';

    let arrowLeft, arrowTop;
    if (item.arrow === 'left') { arrowLeft = box.left - GAP - LEN; arrowTop = box.cy - 12; }
    else if (item.arrow === 'right') { arrowLeft = box.right + GAP; arrowTop = box.cy - 12; }
    else if (item.arrow === 'top') { arrowLeft = box.cx - 12; arrowTop = box.top - GAP - LEN; }
    else { arrowLeft = box.cx - 12; arrowTop = box.bottom + GAP; }
    place(svg, arrowLeft, arrowTop);

    if (!item.label) continue;
    const label = document.createElement('div');
    label.textContent = item.label;
    label.style.cssText =
      `background:${color};color:#fff;font:600 13px/1.3 system-ui,sans-serif;` +
      'padding:4px 9px;border-radius:4px;white-space:nowrap;box-shadow:0 0 0 1px #fff';
    place(label, 0, 0);
    const width = label.offsetWidth, height = label.offsetHeight;
    if (item.arrow === 'left') { label.style.left = `${arrowLeft - 8 - width}px`; label.style.top = `${box.cy - height / 2}px`; }
    else if (item.arrow === 'right') { label.style.left = `${arrowLeft + LEN + 8}px`; label.style.top = `${box.cy - height / 2}px`; }
    else if (item.arrow === 'top') { label.style.left = `${box.cx - width / 2}px`; label.style.top = `${arrowTop - 8 - height}px`; }
    else { label.style.left = `${box.cx - width / 2}px`; label.style.top = `${arrowTop + LEN + 8}px`; }
  }
}
"""


class CaptureError(RuntimeError):
    pass


def load_spec(path: Path) -> dict[str, Any]:
    with path.open("rb") as handle:
        return tomllib.load(handle)


def credentials(role: str, roles: dict[str, Any]) -> tuple[str, str]:
    config = roles.get(role)
    if config is None:
        raise CaptureError(f"role {role!r} is not declared in [roles]")

    user_var, password_var = config["username_env"], config["password_env"]
    username, password = os.environ.get(user_var), os.environ.get(password_var)
    if not username or not password:
        raise CaptureError(f"role {role!r} needs {user_var} and {password_var} in the environment")

    return username, password


def dismiss_cookie_banner(page: Page) -> None:
    """Pre-accept the banner so it never covers a screenshot.

    The theme's JS only stays quiet when the stored cookie carries the same
    version string the page was rendered with, so read it back off the DOM
    rather than hard-coding a hash that changes with the banner settings.
    """
    version = page.evaluate(
        "() => { const el = document.getElementById('cookiebanner_version'); return el ? JSON.parse(el.textContent) : 0; }"
    )
    value = json.dumps({"essential": True, "version": version})
    # Set by domain/path rather than url=: Playwright would scope the cookie to
    # the current directory, so it would stop applying once a step navigates.
    page.context.add_cookies([{"name": "cookiebanner", "value": value, "domain": urlparse(page.url).hostname, "path": "/"}])
    page.reload(wait_until="networkidle")


def log_in(context: BrowserContext, base_url: str, role: str, spec: dict[str, Any], accept_terms: bool) -> None:
    username, password = credentials(role, spec.get("roles", {}))
    page = context.new_page()
    page.goto(f"{base_url}/account/login", wait_until="domcontentloaded")
    dismiss_cookie_banner(page)

    # The theme keeps the credentials form hidden behind the landing card.
    if page.locator("#with-account").count():
        page.click("#with-account")

    page.fill("#id_auth-username", username)
    page.fill("#id_auth-password", password)
    page.click("button.submit_login")
    page.wait_for_load_state("networkidle")

    if "/account/login" in page.url:
        raise CaptureError(f"login failed for role {role!r} — check the credentials and that the account is active")

    company = spec.get("roles", {})[role].get("company")
    if company and page.locator("#id_select_company").count():
        page.select_option("#id_select_company", label=company)
        page.click("button[type=submit]")
        page.wait_for_load_state("networkidle")

    if "/accept_terms" in page.url:
        if not accept_terms:
            raise CaptureError(
                f"role {role!r} lands on the terms-acceptance page; accept them once in the UI or re-run with --accept-terms"
            )
        page.click("button[type=submit]")
        page.wait_for_load_state("networkidle")

    page.close()


def totp_code(secret: str) -> str:
    """The six digits an authenticator app would be showing right now."""
    key = base64.b32decode(secret.strip().replace(" ", "").upper() + "=" * (-len(secret.strip()) % 8))
    digest = hmac.new(key, struct.pack(">Q", int(time.time()) // 30), hashlib.sha1).digest()
    offset = digest[-1] & 0x0F
    code = struct.unpack(">I", digest[offset : offset + 4])[0] & 0x7FFFFFFF
    return f"{code % 1_000_000:06d}"


def secret_from_db(email: str) -> str:
    """The account's enrolled TOTP secret, in the base32 form TOTP expects.

    Imported lazily so the rest of the spec still runs against any instance
    without a local Django install; django-otp stores the key as hex.
    """
    import binascii
    from concurrent.futures import ThreadPoolExecutor

    import django

    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "governanceplatform.settings")
    django.setup()
    from django_otp.plugins.otp_totp.models import TOTPDevice

    # Playwright's sync API drives a greenlet event loop, and Django refuses ORM
    # calls from async context — so the query runs on a thread of its own.
    with ThreadPoolExecutor(max_workers=1) as pool:
        device = pool.submit(lambda: TOTPDevice.objects.filter(user__email=email).first()).result()

    if device is None:
        raise CaptureError(f"no TOTP device enrolled for {email}")

    return base64.b32encode(binascii.unhexlify(device.key)).decode()


def run_steps(page: Page, steps: list[dict[str, Any]]) -> None:
    for step in steps:
        action = step["action"]
        if action == "click":
            page.click(step["selector"])
        elif action == "fill":
            # ${VAR} keeps credentials in the environment rather than the spec.
            page.fill(step["selector"], os.path.expandvars(step["value"]))
        elif action == "select":
            page.select_option(step["selector"], label=step["value"])
        elif action == "press":
            page.press(step["selector"], step["key"])
        elif action == "totp":
            # At enrolment the secret is on the page; at login it is not, so it
            # has to come from the environment.
            if user_var := step.get("user_env"):
                email = os.environ.get(user_var)
                if not email:
                    raise CaptureError(f"step needs {user_var} in the environment")
                secret = secret_from_db(email)
            elif secret_var := step.get("secret_env"):
                secret = os.environ.get(secret_var)
                if not secret:
                    raise CaptureError(f"step needs {secret_var} in the environment")
            else:
                secret = page.inner_text(step["selector"])
            page.fill(step["into"], totp_code(secret))
        elif action == "wait_for":
            page.wait_for_selector(step["selector"])
        elif action == "wait_ms":
            page.wait_for_timeout(step["value"])
        else:
            raise CaptureError(f"unknown step action {action!r}")


def hide(page: Page, selectors: list[str]) -> None:
    if not selectors:
        return
    page.add_style_tag(content=f"{', '.join(selectors)} {{ display: none !important; }}")


def annotate(page: Page, items: list[dict[str, Any]], color: str) -> None:
    if not items:
        return
    page.evaluate(ANNOTATION_JS, {"items": items, "color": color})


def capture(page: Page, shot: dict[str, Any], base_url: str, out_dir: Path, defaults: dict[str, Any]) -> Path:
    if shot_viewport := shot.get("viewport"):
        page.set_viewport_size(shot_viewport)

    page.goto(f"{base_url}{shot['path']}", wait_until="networkidle")
    dismiss_cookie_banner(page)

    if steps := shot.get("steps"):
        run_steps(page, steps)

    hide(page, [*defaults.get("hide", []), *shot.get("hide", [])])
    page.wait_for_timeout(shot.get("settle_ms", defaults.get("settle_ms", 300)))

    # After the settle, so the overlays anchor to the final layout.
    annotate(page, shot.get("annotate", []), defaults.get("annotation_color", "#1a56db"))

    target = out_dir / f"{shot['name']}.png"
    target.parent.mkdir(parents=True, exist_ok=True)
    if selector := shot.get("selector"):
        page.locator(selector).screenshot(path=target)
    else:
        page.screenshot(path=target, full_page=shot.get("full_page", False))

    return target


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--spec", type=Path, default=DEFAULT_SPEC, help="shot list (default: shots.toml)")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT, help="output directory (default: docs/_static)")
    parser.add_argument("--base-url", help="override the base_url from the spec")
    parser.add_argument("--only", nargs="*", help="capture only these shot names")
    parser.add_argument("--headed", action="store_true", help="show the browser while capturing")
    parser.add_argument("--accept-terms", action="store_true", help="accept the terms of service when prompted")
    parser.add_argument("--list", action="store_true", help="list the shots in the spec and exit")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    spec = load_spec(args.spec)
    shots = spec["shots"]

    if args.only:
        shots = [shot for shot in shots if shot["name"] in args.only]
        missing = set(args.only) - {shot["name"] for shot in shots}
        if missing:
            raise CaptureError(f"no such shot(s): {', '.join(sorted(missing))}")

    if args.list:
        for shot in spec["shots"]:
            print(f"{shot['name']:<40} {shot.get('role', ANONYMOUS):<16} {shot['path']}")
        return 0

    base_url = (args.base_url or spec.get("base_url", "http://127.0.0.1:8000")).rstrip("/")
    defaults = spec.get("defaults", {})
    viewport = spec.get("viewport", {"width": 1440, "height": 900})
    args.out.mkdir(parents=True, exist_ok=True)

    with sync_playwright() as playwright:
        launch: dict[str, Any] = {"headless": not args.headed}
        if executable := os.environ.get("SERIMA_SHOT_CHROMIUM"):
            launch["executable_path"] = executable
        browser = playwright.chromium.launch(**launch)

        contexts: dict[str, BrowserContext] = {}
        try:
            for shot in shots:
                role = shot.get("role", ANONYMOUS)
                # A shot that signs in through its own steps would leave the
                # shared context authenticated for everything that follows.
                throwaway = shot.get("fresh", False)

                if throwaway:
                    context = browser.new_context(viewport=viewport, locale=spec.get("locale", "en-GB"))
                    if role != ANONYMOUS:
                        log_in(context, base_url, role, spec, args.accept_terms)
                elif role not in contexts:
                    context = browser.new_context(viewport=viewport, locale=spec.get("locale", "en-GB"))
                    if role != ANONYMOUS:
                        log_in(context, base_url, role, spec, args.accept_terms)
                    contexts[role] = context
                else:
                    context = contexts[role]

                page = context.new_page()
                try:
                    target = capture(page, shot, base_url, args.out, defaults)
                finally:
                    page.close()
                    if throwaway:
                        context.close()
                print(f"captured {target.relative_to(Path.cwd())}" if target.is_relative_to(Path.cwd()) else f"captured {target}")
        finally:
            for context in contexts.values():
                context.close()
            browser.close()

    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except CaptureError as error:
        print(f"error: {error}", file=sys.stderr)
        sys.exit(1)
