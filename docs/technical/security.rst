Security model
==============

Security policy
---------------

Supported versions
``````````````````

The last stable version of this software always provides security updates.
There will be no security patches for other releases (tagged or not).

Reporting a vulnerability
`````````````````````````

If you think you have found a potential security issue, do not open a public GitHub issue.
Email us instead, at opensource@nc3.lu.

You can also specify how you would like to be credited for your finding
(commit message or release notes for the new release). We respect your privacy
and will only publicize your involvement if you grant us permission.

Public security issues are listed
`here <https://github.com/informed-governance-project/SERIMA/issues?q=is%3Aissue+label%3Asecurity+>`_.


Source code
-----------

Every push and pull request is checked on GitHub:

- **CodeQL** analyses the Python and JavaScript code for vulnerabilities;
- **pip-audit** checks the Python dependencies for known vulnerabilities, and GitHub's dependency review
  checks the dependencies a pull request adds;
- Django's deployment checks (``manage.py check --deploy``) catch insecure settings;
- **Ruff** (linting and formatting) and **mypy** (type checking) verify code quality.

The same checks run locally before each commit thanks to `pre-commit <https://pre-commit.com>`_,
which also detects private keys committed by mistake.


Authentication and sessions
---------------------------

- **Two-factor authentication** is mandatory for every account: a user who has not enabled it
  can reach nothing but the two-factor set-up pages.
- **Passwords** must be at least 12 characters long, not too similar to the user's details, not common,
  not entirely numeric, and different from the current password and the last 24.
- **Sensitive pages** — account details, password, backup tokens and disabling two-factor authentication —
  require logging in again first.
- **Sessions** expire after a period of inactivity set by ``SESSION_COOKIE_AGE``.
- **Superusers** cannot use the platform at all; administrators work through roles
  (see :doc:`/getting-started/roles-and-permissions`).
- Users who belong to several operators choose the one they act for at each login,
  and every action is limited to that operator.


Data
----

- **Retention**: incidents, security objectives declarations, logs and unused incident user accounts
  are deleted automatically after the periods set in the configuration (see :doc:`installation`).
- **Secrets**: the RT tokens of observers are stored encrypted with ``RT_SECRET_KEY``.
- **Access**: every user only sees the data of their own organisation, and regulator users
  only the sectors assigned to them.
