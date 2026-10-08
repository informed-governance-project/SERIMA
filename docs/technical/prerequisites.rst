Prerequisites
=============

Software
--------

- A GNU/Linux distribution. Tested on Ubuntu 26.04 LTS, which is also the base image of the official Docker image.
- Python 3.14 or later.
- PostgreSQL, for persistent storage. Tested with PostgreSQL 18.
- Redis, as the message broker of the background workers (Celery).
- Node.js 24 and npm 11, to install the front-end assets.
- An outgoing email server (Postfix or equivalent), for notifications, reminders and password resets.
- A web server: Gunicorn, or Apache with ``mod_wsgi``, behind Apache or Nginx as a reverse proxy.

Ubuntu 26.04 LTS provides Python 3.14 as its default interpreter. On distributions that ship an older one
— Debian Bookworm (3.11) or Ubuntu 22.04 LTS (3.10), for instance — install Python 3.14 separately,
either from the deadsnakes PPA or with ``pyenv install 3.14``.

The reporting module needs two more pieces of software, both listed in :doc:`installation`:

- LibreOffice, to update the table of contents of the generated DOCX reports and convert them to PDF;
- Chrome, which Kaleido drives to render the report charts, with the system libraries it depends on.

The official Docker image includes both.

Instead of installing all of this by hand, you can run the official Docker images: see :doc:`docker`.


Hardware
--------

A server with the following resources runs the platform comfortably,
with the database on the same machine:

- 4 vCPU;
- 4 GB of RAM;
- 20 GB of disk.

Report generation is the most demanding task: each chart render starts a Chromium process.
Allow more memory if many reports are generated at once,
and cap the renders per worker with ``KALEIDO_CONCURRENCY_PER_WORKER`` (see :doc:`installation`).


Network
-------

Installing and updating the platform requires access to GitHub, PyPI and npm,
from which the application, the theme and their dependencies are retrieved.
