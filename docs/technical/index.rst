Overview
========

For the people who install, update and maintain a SERIMA instance, and for those who work on its code.

A SERIMA instance is more than a web application. Alongside the Django application it needs a PostgreSQL database,
a Redis server, two background processes (a Celery worker and Celery beat), an outgoing email server,
and the theme, which lives in its own Git repository.

.. rubric:: Which page do I need?

- **Installing a new instance:** check the :doc:`prerequisites`, then follow either :doc:`docker`
  (recommended) or the manual :doc:`installation`.
- **Upgrading an instance:** :doc:`update`.
- **Understanding how SERIMA is built:** :doc:`architecture` and :doc:`modules`.
- **Reviewing its security:** :doc:`security`.
- **Working on the code:** :doc:`development`.

.. toctree::
   :maxdepth: 2

   prerequisites
   installation
   docker
   update
   architecture
   modules
   security
   development
