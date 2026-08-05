Prerequisites
=============

Software
--------

Generally speaking, requirements are the following:

- A GNU/Linux distribution. Tested on Debian Bookworm and Ubuntu 22.04.3 LTS;
- Python version >= 3.14. Tested with Python 3.14;
- A PostgreSQL server for persistent storage. Tested with PostgreSQL 15.3 and 15.5;
- An email server — outgoing email;
- A cron daemon — scheduled tasks.

Postfix, or an equivalent software, is required for the email notifications.

For the Web server you can use Gunicorn, uWSGI, Apache or Nginx.


Hardware
--------

The Django application is designed to operate efficiently, and it can run
seamlessly on a Raspberry Pi when paired with Gunicorn and either Nginx or
Apache to handle request proxying. It is advisable to allocate ample memory
and disk space, particularly for the database, especially when it shares the
same server. This proactive approach ensures smoother performance and
mitigates potential resource constraints.

A decent configuration for a server would be:

- number of vCPU: 4;
- RAM (GB): 4;
- HDD (GB): 20.

The application will function seamlessly with these settings.
Moreover, these values are relatively low when considering the capacity of
modern servers.


Network
-------

The deployment on the different servers requires an Internet connection since
the updates are retrieved from the GitHub repository.
