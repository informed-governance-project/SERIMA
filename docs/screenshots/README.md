# Documentation screenshots

`capture.py` drives a real browser through a running SERIMA instance and writes
PNGs straight over the files in `docs/_static/` that the `.rst` sources already
reference. The docs never need editing — `git diff` shows exactly which screens
drifted.

## Setup

```bash
poetry install --with docs
poetry run playwright install chromium
```

## Running

The target instance must be running with `DEBUG = True`: that is what makes the
whole platform reachable without enrolling a TOTP device for every screenshot
account (see `RestrictViewsMiddleware`).

```bash
export SERIMA_SHOT_OPERATOR_USER=... SERIMA_SHOT_OPERATOR_PASS=...
export SERIMA_SHOT_REGULATOR_USER=... SERIMA_SHOT_REGULATOR_PASS=...
export SERIMA_SHOT_PLATFORM_USER=... SERIMA_SHOT_PLATFORM_PASS=...

make screenshots                                    # everything in shots.toml
poetry run python docs/screenshots/capture.py --list # what is defined
poetry run python docs/screenshots/capture.py --only SER_1 ui_admin_overview
poetry run python docs/screenshots/capture.py --headed   # watch it run
```

Useful flags: `--base-url` to point at another instance, `--out` to write
somewhere other than `docs/_static` (handy for eyeballing before overwriting),
`--accept-terms` when a screenshot account has not accepted the terms yet.

Set `SERIMA_SHOT_CHROMIUM` to use a system Chromium instead of Playwright's.

## Screenshot accounts

Accounts come from the environment, never from the repository. Any non-superuser
account in the right group works — `RestrictViewsMiddleware` raises 404 for
superusers, so a superuser account will fail. To set a password on an existing
dev account:

```bash
python manage.py changepassword <email>
```

Give an account a `company` in `shots.toml` when it belongs to more than one, so
the company-selection interstitial is answered the same way every run.

## Adding a shot

Each `[[shots]]` entry needs `name` (the `_static` filename, without `.png`) and
`path`. Optional keys:

| Key | Effect |
|---|---|
| `role` | which credentials to use; omit for anonymous pages |
| `steps` | `click` / `fill` / `select` / `press` / `wait_for` / `wait_ms` actions run after navigation |
| `selector` | capture just this element instead of the viewport |
| `full_page` | capture the whole scroll height |
| `hide` | extra selectors to hide, on top of the defaults |
| `settle_ms` | wait longer before the capture |
| `viewport` | `{ width, height }` just for this shot |
| `annotate` | arrows, outlines and labels drawn over the page |

## Annotating a screenshot

Callouts are drawn in the browser and anchored to real elements, so they follow
the interface when it moves instead of drifting like pixel coordinates would:

```toml
[[shots]]
name = "ui_user_login_page"
path = "/account/login"
steps = [{ action = "click", selector = "#with-account" }]
annotate = [
  { selector = "#id_auth-username", arrow = "left", label = "Your email address" },
  { selector = "button.submit_login", box = true },
  { selector = "a.text-muted", arrow = "top", label = "Forgotten it?" },
]
```

`selector` also accepts a list, in which case the callout covers all of the
elements at once — that is how the two credential fields get a single outline.

`arrow` is `left`, `right`, `top` or `bottom` — the side the arrow comes in
from, pointing at the element. `box` outlines the element, `label` prints text
at the arrow's tail, and the three can be combined on one entry. Colour comes
from `[defaults].annotation_color`.

A `selector` that matches nothing fails the run rather than quietly capturing an
un-annotated screenshot.

The block at the end of `shots.toml` lists the screenshots still taken by hand —
mostly wizard steps and crops.

## Known noise

Any page showing a captcha regenerates it on every request, so those files
always diff even when nothing changed.

Two things are hidden from every capture by `[defaults].hide` in `shots.toml`:
the django-debug-toolbar handle, and the footer version string — otherwise a
release would re-diff every screenshot over a number the docs never refer to.

Capture only what the built documentation actually uses. Several `.rst` files
sit outside every toctree, so their images are never published; `shots.toml`
notes which entries are in that position.
