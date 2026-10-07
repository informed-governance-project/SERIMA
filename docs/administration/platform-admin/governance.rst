Governance
----------

The **Governance** section of the console is where you set up the organisations that use the platform
and their first accounts. For a platform administrator, it lists **Django Settings**, **Entity categories**,
**Functionalities**, **Observers**, **Regulations**, **Regulators** and **Users**.
This page describes them in the order of the set-up (see :doc:`index`).

Every item works the same way:

- Click its name to open the list. Click **Add** next to the name, or the **Add** button at the top right of the list,
  to create a new one; click a name in the list to open and change it.
- To delete objects, tick them in the list, choose **Delete selected** in the **Action** drop-down and click **Run**.
  A confirmation page lists everything that will be deleted along with them.
- Names, labels and descriptions can be translated: the tabs above the form (**English**, **French**, **Dutch**, **German**)
  switch between the languages of the platform.
- Beside a drop-down, the pencil icon changes the selected object, the plus icon creates a new one in a pop-up
  and the eye icon displays it.

.. _platform-regulators:

Regulators
~~~~~~~~~~

A regulator, also known as a competent authority, supervises one or more regulations.
The **Regulators** list shows the **Name**, **Full name** and **Description** of each of them.

.. figure:: /_static/images/administration/platform-admin/governance-01.png
   :alt: Regulators list with its column headers outlined
   :target: ../../_static/images/administration/platform-admin/governance-01.png

Create a regulator
""""""""""""""""""

1. Click **Add regulator** and fill in the **Name** and, optionally, the **Full name** and **Description**,
   then the **Country** and **Address**.
2. In **E-mail address for incident notification**, enter the shared address of the regulator: it receives
   a copy of the emails the platform sends about the incidents and security objectives declarations of the regulator.
3. In **Functionalities**, move the optional modules the regulator may use from **Available Functionalities**
   to **Chosen Functionalities**. Only platform administrators can change this list; regulator administrators see it read-only.

   .. figure:: /_static/images/administration/platform-admin/governance-02.png
      :alt: Change Regulator form with the contact fields and the Security Objectives and Report generation functionalities chosen
      :target: ../../_static/images/administration/platform-admin/governance-02.png

   .. note::

      A module chosen here is open to the regulator's accounts only if their role is also chosen on the functionality
      (see :ref:`functionalities`).

4. Add the first regulator administrator, as described below, and click **Save**.

Regulator administrators
""""""""""""""""""""""""

The **Regulator users** section at the bottom of the form lists the regulator administrators.
The other accounts of the regulator are created by these administrators, and are not shown to you.

.. figure:: /_static/images/administration/platform-admin/governance-03.png
   :alt: Regulator users section with the plus icon that creates an account outlined
   :target: ../../_static/images/administration/platform-admin/governance-03.png

To add an administrator, click **Add another Regulator user**, then either:

- select the account in the **User** drop-down, which lists the accounts that have no role yet;
- or click the plus icon beside it to create the account in a pop-up, with its **First name**, **Last name**,
  **Email address** and **Phone number**.

Click **Save**: the account becomes a regulator administrator of this regulator.
It has no password yet. Its owner chooses one with **Password forgotten?** on the login page
(see :doc:`/getting-started/login`), then sets up two-factor authentication at the first login
(see :doc:`/getting-started/enable-2fa`).

Two boxes on each row grant export rights:

- **Can export incidents** lets the administrator export the incidents of the regulator.
  Only a platform administrator can tick it.
- **Can export security objectives** lets the administrator export the list of security objectives declarations
  (see :doc:`/security-objectives/review-a-declaration`).

Every export is recorded in the :doc:`log entries <administration>`.

To remove an administrator from the regulator, tick **Delete?** on its row and click **Save**.
The account is not deleted, but deactivated: its owner can no longer log in.

.. warning::

   The red **Delete** button at the bottom of the form deletes the regulator itself, not the selected administrator.

Delete a regulator
""""""""""""""""""

Tick the regulator in the list and choose **Delete selected Regulators**, or click **Delete** at the bottom of its form.

.. warning::

   Deleting a regulator also deletes its incident notification workflows, security objectives frameworks and
   the rest of its configuration, and deactivates its accounts. Read the confirmation page before confirming.

.. _platform-regulations:

Regulations
~~~~~~~~~~~

The platform handles several regulations, each with its own incident notification workflows, set up by the regulators
in charge of it. The **Regulations** list shows the **Label** of each regulation and its **Regulators**.

To create a regulation, click **Add regulation**, enter its **Label**, move the regulators in charge of it from
**Available Regulators** to **Chosen Regulators**, and click **Save**.

.. figure:: /_static/images/administration/platform-admin/governance-04.png
   :alt: Change Regulation form with its label and the two regulators in charge of it
   :target: ../../_static/images/administration/platform-admin/governance-04.png

A regulator administrator can build workflows and impacts only for the regulations of their regulator.
Observers receive incidents per regulation (see `Observer regulations`_).

.. _functionalities:

Functionalities
~~~~~~~~~~~~~~~

The **Functionalities** list holds the optional modules of the platform: **Security Objective** and **Reporting**.
It shows the **Type** of each functionality, its **Name** and the **Roles** that may use it.

.. figure:: /_static/images/administration/platform-admin/governance-05.png
   :alt: Functionalities list with the security objectives and reporting functionalities and their roles
   :target: ../../_static/images/administration/platform-admin/governance-05.png

A functionality has:

- a **Type**, the module it opens. There can be only one functionality per type.
- a **Name**, the label of the module in the menu of the platform, which can be translated.
- **Roles**, the roles allowed to use the module.

.. figure:: /_static/images/administration/platform-admin/governance-06.png
   :alt: Change Functionality form with its type, name and the four roles chosen
   :target: ../../_static/images/administration/platform-admin/governance-06.png

Who can use a module
""""""""""""""""""""

Access is checked in two steps, in this order:

1. **By role.** On the functionality, move the roles that may use it from **Available Roles** to **Chosen Roles**.
   Only the roles that can work with the module are accepted:

   - Security objectives: RegulatorAdmin, RegulatorUser, OperatorAdmin, OperatorUser.
   - Reporting: RegulatorAdmin, RegulatorUser.

   Any other role is refused when you save, with the message *These roles cannot access this functionality*.

2. **By regulator.** Regulator accounts also need the functionality chosen on their regulator
   (see `Create a regulator`_). Operators have no such setting: their role is enough.

If a role is not chosen, the regulator setting is not checked: the module stays hidden from the menu
and its pages return a "not found" error. A new functionality has no role chosen, so nobody can use it
until roles are added.

Observers can use neither module. For the roles, see :doc:`/getting-started/roles-and-permissions`.

Open a module in stages
"""""""""""""""""""""""

The two steps let you open a module in stages. For example, for security objectives:

1. Choose the RegulatorAdmin and RegulatorUser roles on the functionality.
2. Choose the functionality on each regulator that will use it.
3. Let the regulators set up their frameworks (see :doc:`/administration/regulator-admin/security-objectives`).
4. Once they are ready, choose the OperatorAdmin and OperatorUser roles.

Removing a role from the functionality hides the module again for every account with that role.

.. warning::

   To close a module, remove its roles; do not delete the functionality.

.. _platform-entity-categories:

Entity categories
~~~~~~~~~~~~~~~~~

Entity categories classify the operators, for instance as public or private.
Regulators assign them to their operators, and the incident rules of the observers refer to them
(see `Observer regulations`_). The list shows the **Code** and **Label** of each category.

.. figure:: /_static/images/administration/platform-admin/governance-07.png
   :alt: Entity categories list with the Code and Label columns outlined
   :target: ../../_static/images/administration/platform-admin/governance-07.png

To create one, click **Add entity category**, enter its **Label**, which can be translated, and its **Code**, and click **Save**.

.. tip::

   Incident rules refer to entity categories by their code: changing a code afterwards stops the rules
   that use it from matching. Keep codes short and stable, such as ``PUBLIC`` or ``PRIVATE``.

.. _platform-observers:

Observers
~~~~~~~~~

An observer is an organisation that receives, read-only, the incidents it is entitled to by law.
Which incidents it receives is decided by its observer regulations.

Create an observer
""""""""""""""""""

1. Click **Add observer** and fill in the **Name** and, optionally, the **Full name** and **Description**,
   then the **Country** and **Address**.
2. In **E-mail address for incident notification**, enter the shared address of the observer:
   it receives the emails the platform sends about the incidents the observer receives, unless the observer
   administrator connects the observer to an RT ticketing system, which then receives them as tickets.
3. Add the first observer administrator in the **Observer users** section, as for a regulator
   (see `Regulator administrators`_): click **Add another Observer user**, then select the account or create it
   with the plus icon. Tick **Can export incidents** to let it export the incidents the observer receives.

   .. figure:: /_static/images/administration/platform-admin/governance-08.png
      :alt: Change Observer form with its contact fields and the Observer users section outlined
      :target: ../../_static/images/administration/platform-admin/governance-08.png

4. Add its observer regulations, as described below, and click **Save**.

The observer administrator then creates the other accounts of the observer.
Removing an administrator from the **Observer users** section deactivates the account.

Observer regulations
""""""""""""""""""""

An observer receives only the incidents covered by its observer regulations.

.. important::

   An observer without any observer regulation receives no incidents.

Click **Add another Observer regulation** for each regulation the observer is entitled to, and fill in:

- **Legal basis**: the regulation. An observer can have only one observer regulation per regulation.
- **Sectors**: the sectors covered. If none is chosen, it covers every sector of the regulation,
  including the incidents notified without a sector.
- **Incident rules**: a filter, written in JSON, on the entity categories of the operator that notified the incident.
  Enter ``{}`` to receive every incident of the regulation and sectors.

.. figure:: /_static/images/administration/platform-admin/governance-09.png
   :alt: Observer regulations section with the legal basis, sectors and incident rules of two regulations
   :target: ../../_static/images/administration/platform-admin/governance-09.png

.. tip::

   To have an observer receive every incident, add one observer regulation per regulation,
   with no sector chosen and the incident rules set to ``{}``.

The incident rules list one or more **conditions**, which refer to entity categories by their **Code**
(see `Entity categories`_). An incident is received when it matches at least one condition. To match a condition,
the operator must belong to every entity category listed in ``include``, and to none of those listed in ``exclude``.

In the example below, the observer receives the incidents of the operators categorised as ``PUBLIC`` **or** as ``CRITICAL_INFRA``:

.. code-block:: json

    {
        "conditions": [
            {"include": ["PUBLIC"]},
            {"include": ["CRITICAL_INFRA"]}
        ]
    }

In the example below, it receives the incidents of the operators categorised as ``PRIVATE``,
except those also categorised as ``CRITICAL_INFRA``:

.. code-block:: json

    {
        "conditions": [
            {"include": ["PRIVATE"], "exclude": ["CRITICAL_INFRA"]}
        ]
    }

.. _platform-users:

Users
~~~~~

The **Users** list shows the platform administrators, the regulator and observer administrators,
and the accounts that have no role yet. Next to the contact details, it shows the **Regulator** or **Observer**
of each account, its **Roles**, whether the email address is verified and two-factor authentication is activated,
and when the account was created. Narrow the list down with the search field or the **Filter** panel:
**By Regulators**, **By Observer** or **By Roles**.

.. figure:: /_static/images/administration/platform-admin/governance-10.png
   :alt: Users list with the Reset accepted terms and Reset accepted cookies buttons and the Filter panel outlined
   :target: ../../_static/images/administration/platform-admin/governance-10.png

Create a platform administrator
"""""""""""""""""""""""""""""""

Click **Add user**, fill in the **First name**, **Last name**, **Email address** and **Phone number**, and click **Save**.
As for the regulator administrators, the new administrator chooses a password with **Password forgotten?**
on the login page.

.. warning::

   **Add user** always creates a platform administrator. Create the regulator and observer administrators
   from their regulator or observer instead (see `Regulator administrators`_).

Change or deactivate an account
"""""""""""""""""""""""""""""""

Click a name to open the account. You can change its contact details and, for a platform or regulator administrator,
untick **Active** to deactivate it: its owner can no longer log in.

.. figure:: /_static/images/administration/platform-admin/governance-11.png
   :alt: Change User form of a regulator administrator with the Active box and the Reset 2FA token button
   :target: ../../_static/images/administration/platform-admin/governance-11.png

.. note::

   The **Delete** button of a platform or regulator administrator deactivates the account rather than deleting it,
   and is not offered once the account has log entries.

Reset two-factor authentication
"""""""""""""""""""""""""""""""

When someone has lost access to their authentication app, click **Reset 2FA token** on their row of the list,
or on their account. To reset several accounts at once, tick them, choose **Reset 2FA** in the **Action** drop-down
and click **Run**. At their next login, they set up two-factor authentication again (see :doc:`/getting-started/enable-2fa`).
You cannot reset your own: use **Account security** at the top of the console.

Terms of service and cookies
""""""""""""""""""""""""""""

Two buttons at the top right of the list apply to every account of the platform, after a confirmation:

- **Reset accepted terms**: every user must accept the terms of service again at their next login.
- **Reset accepted cookies**: the cookie banner is shown again to every user.

Django Settings
~~~~~~~~~~~~~~~

**Django Settings** lists the configuration of the server, read-only: the name and value of each setting.
Most secrets, such as the keys, the database settings and the email password, are left out. The settings are changed on the server
(see :ref:`configuration`).

.. figure:: /_static/images/administration/platform-admin/governance-12.png
   :alt: Variables Django Settings page listing setting names and their values
   :target: ../../_static/images/administration/platform-admin/governance-12.png
