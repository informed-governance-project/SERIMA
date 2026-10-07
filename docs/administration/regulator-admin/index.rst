Regulator Admin
---------------

The regulator administrator sets up the platform for their regulator: the accounts of the regulator,
the sectors and operators, the incident notification workflows and, when the modules are open to the regulator,
the security objectives frameworks and the report configuration. The regulators, regulations and modules themselves
are created by the platform administrator (see :doc:`/administration/platform-admin/index`).

Besides the administration console, a regulator administrator uses the modules of the platform like a regulator user,
and sees everything of their regulator whatever the sectors (see :doc:`/getting-started/roles-and-permissions`).

.. toctree::
   :maxdepth: 2
   :hidden:

   administration
   governance
   incident-notification
   security-objectives

The administration console
~~~~~~~~~~~~~~~~~~~~~~~~~~

Click **Settings** in the header of the platform to open the console on its home page, **Site administration**.
Click **Return to user interface** at the top right to go back to the platform. The other links at the top right
manage your **Account security** (two-factor authentication) and your password, log you out and choose the language
of the console.

.. figure:: /_static/images/administration/regulator-admin/index-01.png
   :alt: Site administration page of a regulator administrator with its five sections, the Recent actions panel and the Return to user interface link outlined
   :target: ../../_static/images/administration/regulator-admin/index-01.png

The console has five sections and a panel:

- **Administration**: the **Log entries** and **Script execution logs**, see :doc:`administration`.
- **Governance**: your regulator and its accounts, the sectors and operators, and, read-only, the regulations,
  regulators, observers, functionalities and entity categories, see :doc:`governance`.
- **Incident notification**: the workflows, reports, questions, impacts and emails of the incident notification
  module, see :doc:`incident-notification`.
- **Reporting**: the configuration of the generated reports. Its guide will be published once the module is stable.
- **Security objectives**: the frameworks operators declare against, see :doc:`security-objectives`.
- **Recent actions**: your own latest actions, logins included. Each one, except deletions,
  links to the object concerned.

Each item of a section shows **View** when you can only read it, and **Add** and **Change** when you can edit it.
The lists and forms work as described in :doc:`/administration/platform-admin/governance`.

.. note::

   The **Reporting** and **Security objectives** sections appear only once the platform administrator has opened
   the module to the RegulatorAdmin role and to your regulator (see :ref:`functionalities`).

Set up your regulator
~~~~~~~~~~~~~~~~~~~~~

Once the platform administrator has created your regulator and its regulations, set it up in this order,
since each step uses what the previous ones created:

1. Check the contact details of your regulator and add its accounts (see :ref:`regulator-own` and :ref:`regulator-accounts`).
2. Create the sectors the regulations cover, if they are missing (see :ref:`regulator-sectors`).
3. Create the operators you supervise (see :ref:`regulator-operators`).
4. Build the incident notification workflows of your regulations (see :doc:`incident-notification`).
5. If the module is open to your regulator, set up the security objectives frameworks (see :doc:`security-objectives`).
