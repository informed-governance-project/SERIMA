Permissions and roles
=====================

Summary
----------

The available roles are:

- PlatformAdmin (Django super admin)
- RegulatorAdmin
- RegulatorUser
- ObserverAdmin
- ObserverUser
- OperatorAdmin
- OperatorUser



Permissions
--------------------

PlatformAdmin (Django super admin)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The first platform administrator must be created with the Django command:

.. code-block:: bash

    $ python manage.py createsuperuser


The platform administrator is able to configure the ``Site`` section of the Django application.
The platform administrator is able to create and manage other platform administrators.
The platform administrator grants access to the governance platform to regulators and observers.
A regulator, also known as competent authority, is a public organisation responsible as per the law for the supervision of a or multiple regulations.
An observer is an organisation having a role defined by the law. He gets information to conduct his missions on a read only modus. The platform administrator defines the rules used by the automatic information forward to the observers.
The platform administrator creates the regulations on the platform and assign them to the regulators.
The platform administrator defines the operator categories. These are characteristics of the operators e.g. public/private. These categories are made available to the regulators, who can use them to sort the operators.

Each regulator, who wants to use the incident notification module, should ask the platform administrator to configure:
- the regulator (as organization)
- the first regulator administrator
- the regulations he is responsible for.
- the modules from the platform to be made available.

Each observer, who wants to use the incident notification module, should ask the platform administrator to configure:
- the observer (as organization)
- the first observer administrator
- the logic for the automatic information forward.


RegulatorAdmin
~~~~~~~~~~~~~~~~
The regulator administrator can create other regulator administrator but also regulator users for his organization.
The regulator administrator has the responsibility to configure the regulations he is responsible for. A regulation is configured using a workflow containing various reports. Each report is a collection of questions structured using the question categories.
The regulator administrator has access to any item of his organization. (Unlimited view).


RegulatorUser
~~~~~~~~~~~~~~~~
The regulator administrator, when creating a regulator user, can limit his field of responsibilities to a or various sectors. (Limited view)
The regulator user can create company and create an operator administrator who is the administrator of the company (operator).
The regulator user is responsible to review the deliverables sent by the operators of his sectors.


ObserverAdmin
~~~~~~~~~~~~~~~~
The observer administrator can create other observer administrators but also observer users for his entity.
The observer administrator has a read only access to the items sent to his organization.


ObserverUser
~~~~~~~~~~~~~~~~
The observer user has a read only access to the items sent to his organization.


OperatorAdmin
~~~~~~~~~~~~~~~~
When creating a company, the regulator has to associate it to an operator administrator.
An operator administrator can create other operator administrators but also operator users for his organization.


OperatorUser
~~~~~~~~~~~~~~~~
An operator user is responsible to deliver the required documents and information to the regulators, who are supervising him.
