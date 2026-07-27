<!-- markdownlint-configure-file { "MD024": { "siblings_only": true } } -->

# Changelog

All notable changes to SERIMA are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- "View previous version" button on questions whose answer changed since the previous report; opens a modal showing the previous answer
- "View previous version" button on security-measure rows whose implementation, justification or review comment changed from the previous declaration version; opens a modal showing the previous values

### Fixed

- Password reset email now actually sent after registration; the reset form no longer tries to re-validate the already-consumed registration captcha

## [0.5.16] - 2026-07-06

### Added

- Conditional question options in incident notification forms: questions can now trigger/hide other question options based on the selected answer, with full history tracking via `ConditionalQuestionOptionsHistory` (#802)
- RT connection test button and view for ObserverAdmin, mirroring the existing operator/regulator RT check (#783)
- Temporary storage for regulator's comments in `WorkflowWizardView` until form submission (#812)
- Autosave functionality for regulator's comment date in `WorkflowWizardView` (#820)

### Fixed

- RT URL encoding in `check_rt_config` to correctly handle special characters (#783)
- Permission check added to `test_rt_connection_view` to return 404 if the user lacks change permission
- `ReportLog` text now set in the application's default language, independent of the acting user's language (#803)
- User session population migration now handles non-existing user IDs gracefully
- Email addresses now base64-encoded to fix delivery with some webmail providers (#818)
- Labels and conditions updated for `IncidentStatusForm` fields, including `is_significative_impact` (#819)

### Changed

- `django-parler` dependency switched from a Git-based reference to the published `>=2.4,<3` release constraint
- Redis Docker image upgraded from `7-alpine` to `8-alpine`
- `UserAdmin` form handling refactored to support the `change` parameter and adjusted fieldsets for `OperatorAdmin` (#798)
- GitHub Actions workflows, docs, and scripts updated to reference `main` instead of `master`
- Routine dependency updates (`poetry.lock`, `package-lock.json`, `docs/requirements-app.txt`)

---

## [0.5.15] - 2026-06-08

### Fixed

- `force_logout_user` O(N) session-table scan replaced by a single indexed query via a custom `UserSession` model with a `user` FK column (#758)
- Operator logs now only show operator activity, excluding regulator and observer actions (#791)
- Operator user is now directly approved when created by operator admin (#785)
- Workflow "Save as New" content is now pre-configured correctly (#778)
- 500 error when creating a new user (#771)

### Added

- `pytest-cov` dev dependency; coverage collection enabled for `governanceplatform` and `incidents` apps
- CI coverage XML report artifact upload in `pytest.yml`
- `detect-private-key` pre-commit hook to block accidental credential commits
- Possibility to format frontend text in incident notification (#638)
- Function to prevent the use of old regulations (#767)
- Option to make a new user an admin when created by an operator admin (#786)
- Sector assignment for observer users (#689)
- Accessibility declaration updated from 22/05/2026 (#795)

### Changed

- `pytest.ini`: `addopts` now includes `--cov` flags for automatic coverage reporting on every test run
- `pytest.yml` CI: enforces 50% coverage floor (`--cov-fail-under=50`) and uploads `coverage.xml` artifact
- `pythonapp.yml` CI: bumped `actions/checkout@v1` → `@v4` to match other workflows
- `.gitignore`: added `.claude/`, `.env*`, `*.pem`, `*.key`, `credentials.json`, `secrets.toml`
- An operator no longer sees all companies in which a user is configured (#792)
- Repository renamed to `SERIMA`; references updated in Docker Compose, local Git configuration, and website links (#779)
- Code review with Claude AI (#761)

---

## [0.5.14] - 2026-05-08

### Added

- Chrome runtime shared libraries in Docker image required by kaleido v1 for static image export (#679)
- Django 6 upgrade with custom django-parler fork
- Enhanced sectors filter in incident notifications (#670)
- Impacts choices in incident export (#677)
- Permission centralisation in `permission.py` (#646)
- `get_sectors_grouped` helper
- `django.contrib.postgres` added to INSTALLED_APPS (#635)
- Sectors readonly field for OperatorAdmin in CompanyAdmin
- User deactivation via signals and improved user validation decorator (#646)
- Bootstrap version update in governance settings

### Fixed

- Code review (#745)
- `plotly_get_chrome` now runs non-interactively during Docker build to avoid `EOFError` (#679)
- Email formatting: markdown and sanitization steps now correctly scoped inside the per-language conditional block in `render_to_string_multi_languages` (#668)

### Changed

- `cryptography` updated from 46.x to 47.x (#679)
- `kaleido` updated from 0.2.1 to 1.2.0; Chrome must now be installed explicitly (#679)
- `pyproject.toml` migrated to Poetry 2.0 / PEP 621: metadata moved to `[project]` table, dependencies converted to PEP 508 syntax, `poetry-core>=2.0.0` pinned in `[build-system]`
- `gunicorn` moved from a standalone Dockerfile `pip install` step into `pyproject.toml` dependencies, tracked in `poetry.lock` (#686)
- `COPYING` renamed to `LICENSE`; `[project.license]` updated to SPDX expression format with `license-files` reference
- Superuser access restricted in `RestrictViewsMiddleware` (#646)
- Removed 'delete' permission for 'company' in RegulatorUser group (#646)
- Permissions cleanup: consolidated controls into `permission.py` (#646)
- `log_action` function fixed for Django 6 compatibility (#635)

---

## [0.5.13] - 2026-03-26

### Added

- Dokploy docker-compose deployment support
- `img` tag support with `alt`, `src`, and `width` attributes in admin rich text (#604)
- Sectors field on company for reporting (#639)

### Changed

- Excluded sectors without children from choice list for operators
- Dependency updates

---

## [0.5.12] - 2026-02-25

### Added

- Honeypot captcha on password reset form (#617)
- Full IP-based validator with migration (#617)
- Captcha field in password reset and signup forms (#617)
- Optional SMTP authentication settings
- Role tag display in incident logs (#600)
- Simplified incident log creation logic (#600)

### Fixed

- Translation placeholders in validator admin (#621)
- OTP debug mode: bypass OTP setup for new users, preserve for existing ones (#664, #665)

### Changed

- Docker base image upgraded to Python 3.12
- 2FA reset rules updated for RegulatorUser (#577)
- HOME environment variable set for `www-data` in Docker

---

## [0.5.11] - 2026-01-26

### Added

- Filter by regulator on incident list for RegulatorUser (#603)

### Fixed

- HTTP error response status codes in access log and export views (#603)
- Escaped and handled `None` values in incident workflow comments
- Modal error response format (#603)

### Changed

- Removed function to assign sector to operators (#593)
- `gettext_lazy` used throughout admin display decorators for translations (#586)

---

## [0.5.10] - 2025-12-09

### Added

- Multilingual email content support (#533)
- Configuration variables view (#543)
- `onchange` classes on review status form (#557)

### Fixed

- RegulatorAdmin 2FA reset rules (#550)
- Prevent RegulatorUser from seeing ObserverUser and resetting 2FA (#550)
- Celery task running (#542)

### Changed

- Script to delete incident users and remove debug traces (#542)

---

## [0.5.9] - 2025-11-12

### Added

- Incident export with file format selection (CSV, XLSX) (#441)
- XLSX export format support via openpyxl (#441)
- Email notification for PlatformAdmin on mass incident export (#441)
- `sectorregulation` field in incident export (#441)

### Fixed

- Question duplication in admin: appends `(copy)` to unique fields (#522)
- `Functionality` choices use a callable to fix dynamic choices in migrations

### Changed

- Removed `sectors` field from `CompanyUser` model; factorised operator permission helpers (#487)

---

## [0.5.8] - 2025-10-14

### Added

- Search field for Governance module (#448)
- Sort on all model fields in Governance module (#448)
- Status log entry created when report status changes (#449)

### Fixed

- `maxDate` format in Dominus date widget (#468)
- PlatformAdmin redirection to admin page on login
- PDF filename timestamp format (#500)
- Report status limited to valid choices with default (#499)
- Redirect to first report when only one unique sector regulation (#501)

---

## [0.5.7] - 2025-09-15

### Added

- Cookies policy and sitemap views (#454)
- Sitemap includes home, account, and notification URLs (#454)
- Custom authentication form with enhanced login validation and inactive user handling (#461)

### Fixed

- Incident user validation in `CompanyUser` model (#459)
- Email address normalised (lowercased) on registration (#460)
- Incident attached to first approved company when user linked to several (#469)
- Only approved companies proposed in company selector (#469)

### Changed

- Incident delta calculated from detection date on incident only

---

## [0.5.6] - 2025-08-28

### Added

- `min_date` support in `TempusDominusV6Widget` (#183)
- Timeline form pre-filled with data from previous report (#183)

### Fixed

- Incident date handling in PDF report generation (#183)
- Date validation in `IncidenteDateForm` (#183)
- Resolution date conversion for report timeline (#183)

---

## [0.5.5] - 2025-06-24

### Added

- Celery async task queue with Redis broker
- Docker volumes for `shared_dir` and theme for Celery workers
- `update_group_permissions` command run at Docker startup
- Debug toolbar conditionally loaded via environment variable
- `poetry-plugin-export` added to pre-commit configuration

### Fixed

- Incident report limit check logic and datetime field warnings

### Changed

- Update script uses `APP_TAG` and `THEME_TAG` variables for clearer deployment
- Cronjob and `update_all_group_permissions` script replaced by Docker startup command

---

## [0.5.4] - 2025-04-24

### Added

- `FROM` field in configuration for contact form sender address

---

## [0.5.3] - 2025-04-23

### Fixed

- Form attributes for `QuestionForm` with multiple-choice questions (#326)
- Reply-to header added to contact form emails

---

## [0.5.2] - 2025-04-16

### Added

- Method to retrieve sectors that have no children

### Fixed

- `EMAIL_FOR_CONTACT` now reads `contact_email` from `REGULATOR_CONTACT` config
- `PUBLIC_URL` and `SITE_NAME` read from environment variables in dev config

---

## [0.3.9] - 2025-01-08

### Fixed

- Admin queryset limitation removed for new question categories (#260)

---

## [0.3.8] - 2025-01-06

### Fixed

- Set correct permission when PlatformAdmin creates a user (#259)

---

## [0.3.7] - 2025-01-03

### Changed

- Theme update

---

## [0.3.6] - 2025-01-02

### Added

- Docker deployment with `docker-compose` and Gunicorn production setup
- Docker cron script for scheduled tasks
- GitHub Actions Docker build and push workflow
- `APP_VERSION` injected at Docker build time
- Bind address configurable via environment variable

---

## [0.3.5] - 2024-12-19

### Added

- Tag selection in the `update.sh` deployment script

---

## [0.3.4] - 2024-12-18

### Fixed

- Incident table filter now persists sector choices in session (#250)
- Initial values correctly selected in dropdown checkboxes (#249)
- `CompanyUser` existence checked before saving to avoid errors (#246)

---

## [0.3.3] - 2024-12-17

### Changed

- Translation updates (BE, FR, NL)

---

## [0.3.2] - 2024-12-05

### Added

- Debug toolbar documentation
- Documentation updates and fixes

---

## [0.3.1] - 2024-11-27

### Added

- Timeline section for reports in PDF output

### Fixed

- Password minimum length enforced to 12 characters (#231)
- CSRF cookie age configured
- PDF and incident list renamed for clarity (#230)

---

## [0.3.0] - 2024-11-22

### Added

- Message reminder mixin for unsaved changes (#229)

### Fixed

- Multiple UI and logic issues (#225–#228)
- `entity_categories` field set to readonly for non-RegulatorUser roles
- Incidents queryset ordered consistently

---

## [0.2.9] - 2024-11-13

### Added

- Security objectives app (`securityobjectives`)
- Log entry created when an operator reads a comment in security objectives

---

## [0.2.8] - 2024-10-29

### Fixed

- Category and question option ordering in admin
- New report no longer shows all categories (only applicable ones)
- `QuestionCategoryOptions` model: removed unnecessary `report` foreign key

---

## [0.2.7] - 2024-10-10

### Added

- Check preventing deletion of a workflow that is in use (#211)

### Fixed

- Answer rendering for RL questions in PDF
- Various queryset and form ID fixes

---

## [0.2.6] - 2024-09-19

### Added

- Impact ordering in reports (#190)

### Fixed

- Operators and regulators now share the same incident history view (#184)

---

## [0.2.5] - 2024-09-04

### Fixed

- Language translation issues (#172)
- Observer inline queryset in admin

### Changed

- Import/export disabled for certain models (#171)
- Removed `receive_all_incident` field from regulator

---

## [0.2.4] - 2024-08-13

### Added

- `pytz` timezone library dependency

### Fixed

- Database migration errors on clean database

---

## [0.2.3] - 2024-08-05

### Fixed

- Base URL path for WeasyPrint PDF report generation

---

## [0.2.2] - 2024-05-30

### Fixed

- Security vulnerability (#154)
- CodeQL-reported security issue (CVE-2023-32681 / GHSA-j8r2-6x86-q33q in `requests`)

---

## [0.2.1] - 2024-05-30

### Added

- Incident list view for RegulatorUser
- Import/export for questions, predefined answers, and question categories
- Documentation for question import/export and user interface

### Fixed

- Email template import issue
- Sector choice list in impacts

---

## [0.2.0] - 2024-04-10

### Added

- Improved incident list layout with clear visual separation

### Fixed

- Translation issues in `globals.py` (#140)
- User rights retained when companies are still linked (#119)

---

## [0.1.12] - 2024-04-03

### Changed

- Light theme is now the default

### Fixed

- Significant impact flag not properly set to `false`

---

## [0.1.11] - 2024-04-03

### Added

- Default timezone set to `Europe/Paris`

### Fixed

- RegulatorUser unable to access PDF and incident history
- RegulatorUser unable to modify status, significant impact, and incident ID

---

## [0.1.10] - 2024-04-03

### Fixed

- RegulatorUser unable to access an incident
- Model choices field accepts only valid two-item iterables

---

## [0.1.9] - 2024-04-03

### Changed

- Release bump

---

## [0.1.7] - 2024-04-03

### Fixed

- Issue when a user is linked to multiple sectors within a company

---

## [0.1.6] - 2024-03-27

### Added

- PlatformAdmin can now create PlatformAdmin, CertUser, and RegulatorUser accounts (#52)
- Documentation: Django Sites configuration, email notifications, admin panel screenshots

### Fixed

- Sector query limited to sectors covered by `SectorRegulations`
- Notification date typo
- Incident starting date handling when null
- Workflow save when detection date is missing from form

---

## [0.1.5] - 2024-03-20

### Changed

- Release bump

---

## [0.1.4] - 2024-02-26

### Added

- Incident list view for CERT users (#105)
- Security enforcement on workflow editing
- Access check before `create_workflow`

### Fixed

- OperatorAdmin view and queryset (#118)
- CERT and RegulatorUser role separation (#105)

---

## [0.1.3] - 2024-02-09

### Added

- Timeline section in each report
- Incident history column in operator incident list (#100)
- Regulation filter for impacts
- Impact ordering in incident reports (#93)

### Fixed

- Various sector and company selection issues

---

## [0.1.2] - 2024-02-01

### Added

- Pagination on operator incident list
- Impacts displayed grouped by sector (#99)

### Fixed

- CL/RL question handling
- Pagination on regulator incident list (#90)

---

## [0.1.1] - 2024-01-26

### Added

- First draft for incident history in regulator view
- Operator incident list with filters and sort (#88)

### Fixed

- Company deletion prevented when users are attached (#73)
- Sector creation and edit issues
- Sector fetching with multilingual support (#88)

---

## [0.1.0] - 2023-09-14

### Added

- Initial release of the SERIMA governance platform
- User management with PlatformAdmin, RegulatorAdmin, RegulatorUser, OperatorAdmin, OperatorUser, and ObserverUser roles
- Incident notification workflow with multi-step reports
- Two-factor authentication (TOTP via `django-otp`)
- Multilingual support (EN, FR, NL, DE) via `django-parler`
- REST API (feature-flagged) via Django REST Framework
- PDF report generation via WeasyPrint
- Admin site with import/export capabilities
- Email notifications for incident events
- Bootstrap 5 frontend

[0.5.16]: https://github.com/informed-governance-project/SERIMA/compare/v0.5.15...v0.5.16
[0.5.15]: https://github.com/informed-governance-project/SERIMA/compare/v0.5.14...v0.5.15
[0.5.14]: https://github.com/informed-governance-project/SERIMA/compare/v0.5.13...v0.5.14
[0.5.13]: https://github.com/informed-governance-project/SERIMA/compare/v0.5.12...v0.5.13
[0.5.12]: https://github.com/informed-governance-project/SERIMA/compare/v0.5.11...v0.5.12
[0.5.11]: https://github.com/informed-governance-project/SERIMA/compare/v0.5.10...v0.5.11
[0.5.10]: https://github.com/informed-governance-project/SERIMA/compare/v0.5.9...v0.5.10
[0.5.9]: https://github.com/informed-governance-project/SERIMA/compare/v0.5.8...v0.5.9
[0.5.8]: https://github.com/informed-governance-project/SERIMA/compare/v0.5.7...v0.5.8
[0.5.7]: https://github.com/informed-governance-project/SERIMA/compare/v0.5.6...v0.5.7
[0.5.6]: https://github.com/informed-governance-project/SERIMA/compare/v0.5.5...v0.5.6
[0.5.5]: https://github.com/informed-governance-project/SERIMA/compare/v0.5.4...v0.5.5
[0.5.4]: https://github.com/informed-governance-project/SERIMA/compare/v0.5.3...v0.5.4
[0.5.3]: https://github.com/informed-governance-project/SERIMA/compare/v0.5.2...v0.5.3
[0.5.2]: https://github.com/informed-governance-project/SERIMA/compare/v0.3.9...v0.5.2
[0.3.9]: https://github.com/informed-governance-project/SERIMA/compare/v0.3.8...v0.3.9
[0.3.8]: https://github.com/informed-governance-project/SERIMA/compare/v0.3.7...v0.3.8
[0.3.7]: https://github.com/informed-governance-project/SERIMA/compare/v0.3.6...v0.3.7
[0.3.6]: https://github.com/informed-governance-project/SERIMA/compare/v0.3.5...v0.3.6
[0.3.5]: https://github.com/informed-governance-project/SERIMA/compare/v0.3.4...v0.3.5
[0.3.4]: https://github.com/informed-governance-project/SERIMA/compare/v0.3.3...v0.3.4
[0.3.3]: https://github.com/informed-governance-project/SERIMA/compare/v0.3.2...v0.3.3
[0.3.2]: https://github.com/informed-governance-project/SERIMA/compare/v0.3.1...v0.3.2
[0.3.1]: https://github.com/informed-governance-project/SERIMA/compare/v0.3.0...v0.3.1
[0.3.0]: https://github.com/informed-governance-project/SERIMA/compare/v0.2.9...v0.3.0
[0.2.9]: https://github.com/informed-governance-project/SERIMA/compare/v0.2.8...v0.2.9
[0.2.8]: https://github.com/informed-governance-project/SERIMA/compare/v0.2.7...v0.2.8
[0.2.7]: https://github.com/informed-governance-project/SERIMA/compare/v0.2.6...v0.2.7
[0.2.6]: https://github.com/informed-governance-project/SERIMA/compare/v0.2.5...v0.2.6
[0.2.5]: https://github.com/informed-governance-project/SERIMA/compare/v0.2.4...v0.2.5
[0.2.4]: https://github.com/informed-governance-project/SERIMA/compare/v0.2.3...v0.2.4
[0.2.3]: https://github.com/informed-governance-project/SERIMA/compare/v0.2.2...v0.2.3
[0.2.2]: https://github.com/informed-governance-project/SERIMA/compare/v0.2.1...v0.2.2
[0.2.1]: https://github.com/informed-governance-project/SERIMA/compare/v0.2.0...v0.2.1
[0.2.0]: https://github.com/informed-governance-project/SERIMA/compare/v0.1.12...v0.2.0
[0.1.12]: https://github.com/informed-governance-project/SERIMA/compare/v0.1.11...v0.1.12
[0.1.11]: https://github.com/informed-governance-project/SERIMA/compare/v0.1.10...v0.1.11
[0.1.10]: https://github.com/informed-governance-project/SERIMA/compare/v0.1.9...v0.1.10
[0.1.9]: https://github.com/informed-governance-project/SERIMA/compare/v0.1.7...v0.1.9
[0.1.7]: https://github.com/informed-governance-project/SERIMA/compare/v0.1.6...v0.1.7
[0.1.6]: https://github.com/informed-governance-project/SERIMA/compare/v0.1.5...v0.1.6
[0.1.5]: https://github.com/informed-governance-project/SERIMA/compare/v0.1.4...v0.1.5
[0.1.4]: https://github.com/informed-governance-project/SERIMA/compare/v0.1.3...v0.1.4
[0.1.3]: https://github.com/informed-governance-project/SERIMA/compare/v0.1.2...v0.1.3
[0.1.2]: https://github.com/informed-governance-project/SERIMA/compare/v0.1.1...v0.1.2
[0.1.1]: https://github.com/informed-governance-project/SERIMA/compare/v0.1.0...v0.1.1
[0.1.0]: https://github.com/informed-governance-project/SERIMA/releases/tag/v0.1.0
