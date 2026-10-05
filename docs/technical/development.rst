Development
===========

This page is for people who change SERIMA's code or documentation.
For how to propose changes, see also
`CONTRIBUTING.md <https://github.com/informed-governance-project/SERIMA/blob/main/CONTRIBUTING.md>`_.


Development environment
-----------------------

Install the system packages and Poetry as described in :doc:`installation`, then:

.. code-block:: bash

    $ git clone https://github.com/informed-governance-project/SERIMA.git
    $ cd SERIMA
    $ git checkout dev
    $ git clone https://github.com/informed-governance-project/default-theme.git theme
    $ (cd theme && git checkout dev)
    $ npm ci
    $ cp governanceplatform/config_dev.py governanceplatform/config.py
    $ poetry install
    $ poetry run pre-commit install
    $ poetry run python manage.py migrate
    $ poetry run python manage.py update_group_permissions
    $ poetry run python manage.py runserver

``poetry install`` without ``--only main`` also installs the development tools (tests, linters, documentation).

Keep the theme on the branch that matches the application: ``dev`` with ``dev``, a feature branch with its
counterpart if it has one. A mismatch typically shows up as a ``TemplateDoesNotExist`` error.
The ``theme`` folder is its own Git repository: commit and push theme changes from inside it.

With ``DEBUG = True``, emails are written to the ``sent_emails`` folder instead of being sent,
and two-factor authentication is not enforced, which makes local testing easier.


Branches and pull requests
--------------------------

- Open pull requests against ``dev``. ``main`` only changes when a release is made.
- Name branches by purpose: ``feat/…``, ``fix/…``, ``test/…``, ``review/…``.
- Prefix commit messages with the area they touch: ``[GOV]`` (``governanceplatform``), ``[NI]`` (``incidents``),
  ``[SO]`` (``securityobjectives``), ``[RG]`` (``reporting``), or use ``feat:``, ``fix:``, ``docs:``…
- A pull request with user-facing changes adds an entry under ``[Unreleased]`` in ``CHANGELOG.md``.
- Theme changes need a pull request in the theme repository too, and the CI workflow pins the theme branch
  it tests against: update it when a branch depends on a theme branch.


Tests
-----

The tests run against a real PostgreSQL database, configured in ``config.py``:

.. code-block:: bash

    $ poetry run pytest                          # all tests
    $ poetry run pytest incidents/tests/         # one app

Each run recreates the test database and writes a ``.coverage`` file at the root of the project;
set ``COVERAGE_FILE`` to keep it elsewhere. In CI, ``DJANGO_CI=True`` makes the settings fall back to
``config_dev.py`` when there is no ``config.py``.


Code quality
------------

`pre-commit <https://pre-commit.com>`_ runs the checks before each commit; run them on everything with:

.. code-block:: bash

    $ poetry run pre-commit run --all-files

They include Ruff (linting, import sorting and formatting, with a line length of 140), django-upgrade,
pip-audit, and the export of ``requirements.txt`` used by the Docker image. CI runs the same checks
plus mypy and CodeQL (see :doc:`security`).


Useful commands
---------------

.. list-table::
   :header-rows: 1
   :widths: 32 68

   * - Command
     - What it does
   * - ``make run``
     - Starts the development server.
   * - ``make migration`` / ``make migrate``
     - Creates new migrations / applies them. Migrations are append-only: never edit a committed one.
   * - ``make superuser``
     - Creates a platform administrator.
   * - ``make generatepot``
     - Extracts the strings to translate; then ``python manage.py compilemessages``.
   * - ``make models``
     - Draws the model diagram.
   * - ``make screenshots-fixture`` / ``make screenshots``
     - Loads the documentation data set (wiping the database) / captures the documentation screenshots.
   * - ``make image``
     - Builds the Docker image.
   * - ``make permissions``
     - Applies the role permissions defined in ``governanceplatform/permissions.py``; run it after changing them.


Documentation
-------------

The documentation is written in reStructuredText under ``docs/`` and built with Sphinx:

.. code-block:: bash

    $ poetry install --with docs
    $ poetry run sphinx-build -b html docs docs/_build/html

The screenshots are captured from a running instance loaded with an anonymised data set;
``docs/screenshots/README.md`` explains how to load it and run the capture.


Exploring the code
------------------

The AI-generated `DeepWiki of SERIMA <https://deepwiki.com/informed-governance-project/SERIMA>`_ gives an
overview of the code base and answers questions about it. It is generated automatically and not reviewed:
when it disagrees with this guide or with the code, those are authoritative.
