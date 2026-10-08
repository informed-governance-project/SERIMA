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
make screenshots-fixture                            # wipe the database, load the fixture, set passwords
make screenshots                                    # everything in shots.toml
poetry run python docs/screenshots/capture.py --list # what is defined
poetry run python docs/screenshots/capture.py --only images/getting-started/enable-2fa-01 images/getting-started/login-01
poetry run python docs/screenshots/capture.py --only 'images/getting-started/*'   # wildcards: quote them
poetry run python docs/screenshots/capture.py --headed   # watch it run
```

Useful flags: `--spec` to use another shot list, `--base-url` to point at another instance, `--out` to write
somewhere other than `docs/_static` (handy for eyeballing before overwriting),
`--accept-terms` when a screenshot account has not accepted the terms yet.

Set `SERIMA_SHOT_CHROMIUM` to use a system Chromium instead of Playwright's.

## Screenshot data

`fixture.json` holds everything the screens show: the incident, security
objectives and reporting configuration, sample incidents and declarations in
every status, two report projects, and the accounts below.

| Entity | Who |
| --- | --- |
| Regulator A | `regulator-admin@example.org`, `regulator-user@example.org` |
| Regulator B | `regulator-b-admin@example.org`, `regulator-b-user@example.org` |
| Operator A | `operator-admin@example.org` (also administrator of Operator B) |
| Operator B | `operator-user@example.org` |
| — | `incident-user@example.org`: an incident user suggested to Operator A, awaiting its approval |
| Observer A | `observer-admin@example.org` |
| — | `platform-admin@example.org` |

All text is in English only. Risk-analysis data (risks, assets, threats,
vulnerabilities, recommendations, service statistics) is not part of it; import
a MONARC file through the reporting module when a shot needs it. Nor are the
companies and years of a report project: loading rebuilds them, all unselected,
so tick them in the project before shooting its screens.

### Loading it

`make screenshots-fixture` replaces the whole content of the configured
database. It asks first — the prompt is red — and stops on any answer but
`yes`. Then it flushes the database, runs the migrations, creates the groups
(`update_group_permissions`; the fixture refers to them by name), loads the
fixture and runs `screenshot_fixture --create`. Back up the database first if it
holds anything you want to keep.

## Screenshot accounts

The accounts come from the fixture with no usable password.
`screenshot_fixture --create` gives one to each role in `shots.toml`, accepts
the terms for it, and removes its TOTP device:

| Role | Account | Environment override |
| --- | --- | --- |
| `operator_admin` | `operator-admin@example.org` | `SERIMA_SHOT_OPERATOR_ADMIN_USER` / `_PASS` |
| `operator_user` | `operator-user@example.org` | `SERIMA_SHOT_OPERATOR_USER` / `_PASS` |
| `regulator_admin` | `regulator-admin@example.org` | `SERIMA_SHOT_REGULATOR_ADMIN_USER` / `_PASS` |
| `regulator_user` | `regulator-user@example.org` | `SERIMA_SHOT_REGULATOR_USER` / `_PASS` |
| `observer_admin` | `observer-admin@example.org` | `SERIMA_SHOT_OBSERVER_ADMIN_USER` / `_PASS` |
| `platform_admin` | `platform-admin@example.org` | `SERIMA_SHOT_PLATFORM_USER` / `_PASS` |

The command writes every login to `docs/screenshots/.fixture-credentials.json`,
keyed by role. The file is gitignored and readable only by its owner.

```bash
python manage.py screenshot_fixture --create               # generated passwords
python manage.py screenshot_fixture --create --password …  # one password for all
python manage.py screenshot_fixture --delete               # no more logins
```

Each account's password comes from `--password`, then the role's `_PASS`
variable, and is otherwise generated. `--delete` makes the passwords unusable
again, removes the TOTP devices and the credentials file, and keeps the
accounts, because the fixture's incidents, declarations and logs point at them.
The command refuses to run when `DEBUG` is off, or before the fixture is loaded.

### Using real accounts instead

Environment variables take precedence over the credentials file, so a real
account can stand in for any role. Any non-superuser account in the right group
works — `RestrictViewsMiddleware` raises 404 for superusers, so a superuser
account will fail. To set a password on an existing dev account:

```bash
python manage.py changepassword <email>
```

Give an account a `company` in `shots.toml` when it belongs to more than one, so
the company-selection interstitial is answered the same way every run.

## Adding a shot

Each `[[shots]]` entry needs `name` (the `_static` filename, without `.png`) and
`path`. Optional keys:

| Key | Effect |
| --- | --- |
| `role` | which credentials to log in with beforehand; omit for anonymous pages |
| `credentials_from` | a role whose credentials `fill` steps can type as `${username}` / `${password}` |
| `fresh` | use a new browser context for this shot alone, and close it afterwards |
| `steps` | `click` / `fill` / `select` / `hover` / `press` / `totp` / `delete_totp` / `captcha` / `wait_for` / `wait_ms` actions run after navigation |
| `email` | `true` to capture the last email the instance sent instead of a page; `path` is then not needed |
| `selector` | capture just this element instead of the viewport |
| `full_page` | capture the whole scroll height |
| `hide` | extra selectors to hide, on top of the defaults |
| `settle_ms` | wait longer before the capture |
| `viewport` | `{ width, height }` just for this shot |
| `annotate` | arrows, outlines, labels and redactions drawn over the page |

Shots with the same `role` share one logged-in browser context. A shot that
signs in through its own steps must set `fresh = true`, or it would leave that
session behind for every shot that follows. A `fill` value can also expand any
other `${VAR}` from the environment. The run stops on any placeholder that is
still unresolved, so it never types a literal `${...}` into a form.

## Captcha and email shots

A `captcha` step fills `into` with the answer to the captcha on the page. It
reads the challenge key from the hidden `#id_captcha_0` input (override with
`key`) and looks the answer up in the database, so — like a `totp` step that
reads an enrolled device — it needs a checkout configured against the same
database as the target instance.

A shot with `email = true` opens no page. It renders the last message the
instance wrote to `EMAIL_FILE_PATH` — the file-based backend Django uses when
`DEBUG` is on — with its From, To and Subject lines above the body. It shows
whatever the shot before it made the platform send, so keep the two together:
`create-account-03` captures the set-password email `create-account-02` triggers
by signing up.

That sign-up creates `new-account@example.org`. `screenshot_fixture --create`
deletes it again, so run it before shooting the sign-up shots a second time.

## Two-factor steps

A `totp` step computes the current six-digit code and fills it into `into`. The
secret comes from the first of these that applies:

| Step keys | Secret read from |
| --- | --- |
| `selector` | the page itself — the `otpauth:` link on the enrolment wizard |
| `user_env` | the enrolled device of the account whose email is in that variable |
| `secret_env` | a base32 secret held in that variable |
| none, with `credentials_from` | the enrolled device of that role's account |

Reading an enrolled device queries the database through Django, so those forms
only work from a checkout configured against the same database as the target
instance.

The enrolment shots are stateful. The wizard exists only while the account has
no TOTP device, and `images/getting-started/enable-2fa-04` creates one by completing it.
The last enrolment shot ends with a `delete_totp` step, which removes the
device again — so every shot after it logs in without a token prompt, and the
wizard is back for the next run. `delete_totp` removes the TOTP devices of the
shot's `credentials_from` account. The order within the enrolment shots still
matters, because the login token prompt only appears once a device exists.

## Annotating a screenshot

Callouts are drawn in the browser and anchored to real elements, so they follow
the interface when it moves instead of drifting like pixel coordinates would:

```toml
[[shots]]
name = "images/getting-started/login-02"
path = "/account/login"
steps = [{ action = "click", selector = "#with-account" }]
annotate = [
  { selector = "#id_auth-username", arrow = "left", label = "Your email address" },
  { selector = "button.submit_login", box = true },
  { selector = "a.text-muted", arrow = "top", label = "Forgotten it?" },
]
```

`redact = true` covers the element with a solid block instead of marking it —
use it for anything that must not reach a published PNG, such as the TOTP
secret and QR code on the enrolment wizard. It keeps the layout intact, which
`hide` would not.

`selector` also accepts a list, in which case the callout covers all of the
elements at once — that is how the two credential fields get a single outline.

`arrow` is `left`, `right`, `top` or `bottom` — the side the arrow comes in
from, pointing at the element. `box` outlines the element, `label` prints text
at the arrow's tail, and the three can be combined on one entry. `length`
changes the arrow from its default 90px; `length = 0` drops the arrow and sets
the label right beside the element, for controls packed too close together for
arrows to clear one another. Colour comes
from `[defaults].annotation_color`.

A `selector` that matches nothing fails the run rather than quietly capturing an
un-annotated screenshot.

The block at the end of `shots.toml` lists the screenshots still taken by hand —
mostly wizard steps and crops.

## Known noise

Any page showing a captcha regenerates it on every request, and the
set-password email carries a fresh token every run, so those files always diff
even when nothing changed.

The footer version string is hidden from every capture by `[defaults].hide` in
`shots.toml` — otherwise a release would re-diff every screenshot over a number
the docs never refer to.

Capture only what the built documentation actually uses.
