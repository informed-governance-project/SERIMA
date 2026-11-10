Read-only API
=============

Enabling the API
----------------

The API, its documentation and API key management are disabled by default.
Set ``API_ENABLED = True`` in ``governanceplatform/config.py`` and restart the
application to enable them. Missing configuration defaults to ``False``.
Apply the database migrations with ``poetry run python manage.py migrate``.
No additional Python dependencies are needed.

``API_ENABLED`` is the master switch: when it is ``False`` nothing below applies.
Once it is ``True``, nobody can use the API until a platform administrator grants
access per module, as described in `API access per module`_.

API access per module
---------------------

In the administration, **API access** lists the three modules the API exposes:
incident notification, security objectives and reporting. For each one, the
platform administrator picks the roles allowed to read it through the API. A new
installation grants no role, so the API serves nobody until access is granted.

Only roles that can use a module on the web are offered for it. Incident
notification is open to regulator, operator, incident and observer roles;
security objectives and reporting to the roles listed for their functionality.

API access never widens web access. A user reads a module through the API only
when their role is granted it here *and* they can use it on the web: for
security objectives and reporting, the functionality must also be enabled for
their role and, for regulator users, on their regulator. ``/api/v1/me/`` needs at
least one module.

Users with no module granted see no **API keys** menu entry and cannot open the
**API keys** page. Their existing keys are refused on every endpoint while no
module is granted, and work again if a module is granted back before they expire.

API keys
--------

Sign in, complete two-factor authentication when required, and open **API keys**
in the account menu. Click **New API key**, give the key a name, choose an
expiry between 1 and 365 days (90 by default), and confirm your password. Copy
the key immediately, with the **Copy** button if you like: the full value is
displayed only in the creation window and cannot be retrieved once that window
is closed. Operators create a key for the company they have selected; to read
another company's data, switch company and create a key there. The table of keys
shows only each key's creation date, name, company (for operators), identifying
prefix, expiry and status. Use the bin icon to revoke a key: after
confirmation it is invalidated immediately. Changing the account password, or
disabling or resetting its two-factor authentication, revokes all the user's
keys. Users can manage only their own keys; creation and revocation require a
browser session and CSRF protection.
API keys cannot create or revoke other keys through the API.

Keys contain 256 random bits. Only their SHA-256 digest is stored; the database
never stores a recoverable key. Use HTTPS, keep keys out of URLs and logs, and
store them in your client's secret storage. Revocation and expiry are checked
on every request. Disabling the API makes existing keys unusable without deleting
them; keys that are still valid work again if the API is re-enabled.

Access logging
--------------

API reads are written to the module's **Access Log** with the action
``API READ``, following the same rules as the web pages:

- Opening an incident (``/api/v1/incidents/{reference}/``) logs one entry per
  report, as opening a report on the web does. An incident with no report logs
  nothing.
- Opening a declaration (``/api/v1/security-objectives/{reference}/``) logs one
  entry.
- Lists are not logged, as browsing a dashboard is not.
- Reporting projects are not logged, as opening a project on the web is not.

Records outside the user's scope return ``404`` and are not logged.

Each entry records the key owner, their role and their organisation, as the web
log does: the regulator or observer, the key's company for operators, and none
for incident users. The key used is not recorded. The entries follow the
visibility rules of the web log.

Requests
--------

Send the key in the ``Authorization`` header:

.. code-block:: bash

    curl --header "Authorization: Bearer ${SERIMA_API_KEY}" \
        https://serima.example.org/api/v1/me/

Data endpoints return JSON and accept only ``GET``, ``HEAD`` and ``OPTIONS``.
They do not accept browser-session or Basic authentication. Write methods return
``405`` for authorized users. Missing, invalid, expired or revoked keys return
``401``. An account or module without access returns ``403``; a record outside
the user's scope returns ``404``. Responses are marked ``Cache-Control: no-store``.

Lists use pages of 50 records, selected with ``?page=2``, and return ``count``,
``next``, ``previous`` and ``results``. Authenticated requests are limited to
120 per minute per user, shared across their keys, using the configured Django
cache; excess requests return ``429``. Configure a shared cache for consistent
limits across application workers.

Resources
---------

.. list-table::
   :header-rows: 1
   :widths: 45 55

   * - Endpoint
     - Returned data
   * - ``/api/v1/me/``
     - The key owner's email, first name and last name.
   * - ``/api/v1/incidents/``
     - Incident references, company name, notification/detection/update dates,
       incident status, significant-impact flag and internal/complaint references.
   * - ``/api/v1/incidents/{reference}/``
     - One incident, using its incident reference.
   * - ``/api/v1/security-objectives/``
     - Latest visible declarations, with the dashboard data only: reference,
       standard, company, submission year, dates and status.
   * - ``/api/v1/security-objectives/{reference}/``
     - Latest visible declaration for the declaration group reference, adding its
       measure answers (measure, justification and implementation flag).
   * - ``/api/v1/reporting/projects/``
     - Reporting project reference, name, standard, dates, years, reference year
       and generation status.
   * - ``/api/v1/reporting/projects/{reference}/``
     - One project, using its opaque UUID reference.

The API does not provide file generation/downloads, administrative settings,
review comments, user directories or historical declaration versions.

Access follows the owner
------------------------

The key owner must remain active and have accepted the
current terms within the configured acceptance period. Superusers and platform
administrators cannot use these data endpoints. Keys do not grant extra roles.
Changes to roles, memberships, module switches and sector assignments take effect
on the next request.

Incident users see only their own incidents. An operator's key is bound to the
company selected when the key was created, and reads only that company's
incidents and security-objective declarations, as the web shows only the company
in use. Switching company in the browser afterwards does not change the key. The
key acts with the user's role in that company (administrator or user), and is
refused once that membership is no longer approved. Operator keys created before
company binding are refused. Regulator users retain
their regulator and sector scope; regulator administrators retain their regulator
scope. Observers retain their incident regulation rules. Detached accounts have
no organization data.

Every module requires the user's role to be granted in `API access per module`_.
Security objectives and reporting additionally require the existing role and
regulator functionality switches. Reporting remains restricted to regulator
roles, and observers cannot read security-objective declarations or reporting
projects. Regulators cannot read unsubmitted declarations. Operators see an
in-progress review as ``DELIV`` until the review has been sent; draft verdicts and
review comments are never included in their responses.

OpenAPI and Swagger
-------------------

When enabled, ``/api/openapi.yaml`` serves the OpenAPI YAML schema and
``/api/docs/`` serves Swagger UI using locally installed sidecar assets. These
two documentation endpoints are public, contain no application records, and
vanish when the API is disabled. In Swagger, use **Authorize** to enter the full
key. Authorization is not persisted across page reloads.

Generate the same schema offline with:

.. code-block:: bash

    poetry run python manage.py spectacular --file /tmp/openapi.yaml --validate
