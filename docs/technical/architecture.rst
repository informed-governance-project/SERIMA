Architecture
============


High-level architecture
-----------------------

.. figure:: /_static/images/technical/global-architecture.png
   :alt: High-level architecture of a Django application
   :target: ../_static/images/technical/global-architecture.png

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

The overview shows the models of the four applications and their relations, without fields.
The diagrams below show each application in detail; models from other applications appear as plain boxes.
The django-parler translation models (``*Translation``) are left out: a translatable model is marked
``<TranslatableModel>`` in its header.

.. figure:: /_static/images/technical/app-models.png
   :alt: Overview of the models of the governance, incidents, security objectives and reporting applications
   :target: ../_static/images/technical/app-models.png

Governance
~~~~~~~~~~

.. figure:: /_static/images/technical/models-governanceplatform.png
   :alt: Models of the governance application: users, companies, regulators, sectors and regulations
   :target: ../_static/images/technical/models-governanceplatform.png

Incident notification
~~~~~~~~~~~~~~~~~~~~~

.. figure:: /_static/images/technical/models-incidents.png
   :alt: Models of the incidents application: incidents, workflows, questions and impacts
   :target: ../_static/images/technical/models-incidents.png

Security objectives
~~~~~~~~~~~~~~~~~~~

.. figure:: /_static/images/technical/models-securityobjectives.png
   :alt: Models of the security objectives application: standards, domains, objectives, measures and answers
   :target: ../_static/images/technical/models-securityobjectives.png

Reporting
~~~~~~~~~

.. figure:: /_static/images/technical/models-reporting.png
   :alt: Models of the reporting application: projects, risk data, observations, templates and generated reports
   :target: ../_static/images/technical/models-reporting.png

The diagrams are generated with ``make models``.
