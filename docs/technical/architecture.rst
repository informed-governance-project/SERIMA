Architecture
============


High-level architecture
-----------------------

.. figure:: /_static/images/technical/global-architecture.png
   :alt: High-level architecture
   :target: ../_static/images/technical/global-architecture.png

   High-level architecture of a Django application.

A SERIMA instance is made of the following components:

- **Web application**: the Django project (``governanceplatform``), served by Gunicorn or Apache ``mod_wsgi``.
  Static files are served by the application itself, with WhiteNoise.
- **Theme**: the templates, styles and translations of the interface, in a separate Git repository
  checked out in the ``theme`` folder (see :doc:`installation`).
- **PostgreSQL**: all persistent data.
- **Redis**: the message broker between the web application and the background workers.
- **Celery worker**: runs the slow tasks outside the web requests — report generation (DOCX, PDF and the charts
  rendered with Kaleido), security objectives exports and imports.
- **Celery beat**: triggers the scheduled tasks, such as reminders and data retention (see :doc:`installation`).
- **File storage**: generated reports and import/export files, written to ``PATH_FOR_REPORTING_PDF``.
- **Email server**: notifications, reminders and password resets.


Models
------

.. figure:: /_static/images/technical/app-models.png
   :alt: Application models
   :target: ../_static/images/technical/app-models.png

   Business-related models for the *incidents* and *governance* modules.

The diagram is generated with ``make models``.
