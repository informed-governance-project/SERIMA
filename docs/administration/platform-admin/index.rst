Platform Admin
-------------------------

If you are a **Platform Admin**, you can use the **Administration Console** as described below.

   **Please note that as a Platform Admin, you do not have access to the user interface (when you log in, you are presented with the Admin Console, and    you cannot click the Settings button on the user interface).**

There are four sections in the Administration Console: **Administration, Governance, Sites**, and **Recent Actions**.

.. figure:: /_static/images/administration/platform-admin/overview-01.png
   :alt: Login page.
   :target: ../../_static/images/administration/platform-admin/overview-01.png

**The Platform Admin has very special rights and scope of activities as follows:**

-	Creates a common database for all regulators and the users of the regulators
-	Configures the server and the regulator users
-	Sets up the admin platform
-	Creates workflows





Setting up the platform
~~~~~~~~~~~~~~~~~~~~~~~

The first platform administrator is created with the Django command:

.. code-block:: bash

    $ python manage.py createsuperuser

Despite its name, in SERIMA this command creates a platform administrator, not a Django superuser:
superusers cannot use the platform at all.

The platform administrator then:

- configures the ``Site`` section of the application;
- creates and manages the other platform administrators;
- creates the regulators and observers, and grants them access to the platform;
- creates the regulations and assigns them to the regulators;
- defines the operator categories, characteristics of the operators such as public or private,
  which the regulators can use to sort their operators;
- defines the rules that decide which incidents are forwarded to each observer.

A regulator that wants to use the platform asks the platform administrator to configure:

- the regulator, as an organisation;
- its first regulator administrator;
- the regulations it is responsible for;
- the modules to make available to it.

An observer asks the platform administrator to configure:

- the observer, as an organisation;
- its first observer administrator;
- the rules for forwarding incidents to it.

.. toctree::
   :maxdepth: 2
   :hidden:

   administration
   governance
   sites
