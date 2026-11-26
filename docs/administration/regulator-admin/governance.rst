Governance
----------

The **Governance** section of the console is where you manage your regulator, its accounts, the sectors and
the operators. For a regulator administrator, it lists:

- **Regulators**, **Users**, **Sectors** and **Operators**, which you can change, as described on this page;
- **Entity categories**, **Functionalities**, **Observers** and **Regulations**, set up by the platform administrator,
  which you can only view (see `Read-only items`_).

The lists, forms, language tabs and the icons beside the drop-downs work as described in
:doc:`/administration/platform-admin/governance`.

When the platform administrator enables **Self-registration** for your role and regulator, its menu link
opens the administration section. You can create form templates and versions, and edit draft versions,
their pages and question placements. Questions and choices may be edited while no published or archived
form uses them.
Related form versions, pages, questions and choices display their translated labels.

Create reusable **Template pages** for your regulator, then open a **Template version** in draft.
In **Pages**, select a category and set its position for this version. Use the **Questions** table
under each page to add questions, set their order and choose which answers are required, eligible for
autofill, or visible to observers or the public. Save the version to keep the pages and questions together.
The same category can be selected in several versions. Each version has its own page order and question placements.
Use the inline delete controls to remove pages or question placements from a draft. Catalog definitions stay available.
The **Pages in template** and **Question orders** lists are managed from the version form.
During initial configuration, regulator administrators may delete their own templates, versions, reusable pages,
questions, and answer choices, including those used in published versions. The confirmation lists the dependent
records that will be removed. Editing the questionnaire on a published or archived version remains disabled.

.. _regulator-own:

Your regulator
~~~~~~~~~~~~~~

The **Regulators** list shows every regulator of the platform. Click your regulator to change it;
the others open read-only, with their accounts.

The form holds the **Name**, **Full name** and **Description** of your regulator, which can be translated,
its **Country** and **Address**, and its **E-mail address for incident notification**: the shared address that receives
a copy of the emails the platform sends about the incidents and security objectives declarations of your regulator.

.. figure:: /_static/images/administration/regulator-admin/governance-01.png
   :alt: Change Regulator form with the contact fields, and the read-only Functionalities field outlined
   :target: ../../_static/images/administration/regulator-admin/governance-01.png

**Functionalities** lists, read-only, the optional modules the platform administrator has opened to your regulator
(see :ref:`functionalities`). You cannot delete your regulator.

.. _regulator-accounts:

Regulator accounts
~~~~~~~~~~~~~~~~~~

The **Regulator users** section at the bottom of the form of your regulator lists all its accounts,
administrators and users, one card each. The cards are closed: each shows the name of the account, followed by
*Administrator* or by the number of sectors of a regulator user. Click the name or the arrow at the right of a card
to open it; a card you add opens by itself.

.. figure:: /_static/images/administration/regulator-admin/governance-02.png
   :alt: Regulator users section with the cards of an administrator and a regulator user opened, the regulator user's card and the Add another Regulator user link outlined
   :target: ../../_static/images/administration/regulator-admin/governance-02.png

Each card has:

- **User**: the account.
- **Is administrator**: a switch, on for a regulator administrator, off for a regulator user.
  Changing it switches the role of the account and logs it out.
- **Can export incidents**: read-only. The platform administrator grants it, and it applies to administrators only
  (see :ref:`incident-export`).
- **Can export security objectives**: lets the account export the list of security objectives declarations
  (see :doc:`/security-objectives/review-a-declaration`).
- **Sectors**: the sectors a regulator user handles. They see only the incidents and declarations of these sectors.
  Administrators see all the sectors, whatever is chosen here.

.. important::

   A regulator user with no sector chosen sees no incidents and no declarations.

Add an account
""""""""""""""

1. Click **Add another Regulator user**.
2. Select the account in the **User** drop-down, which lists the active regulator accounts not yet attached to a regulator,
   or open the menu (⋮) beside it and click **Add another User** to create the account in a pop-up, with its **First name**, **Last name**,
   **Email address** and **Phone number**.
3. Turn on **Is administrator** to make it a regulator administrator. Otherwise, choose its **Sectors**.
4. Turn on **Can export security objectives** if the account may export the declarations.
5. Click **Save**.

The new account has no password yet. Its owner chooses one with **Password forgotten?** on the login page
(see :doc:`/getting-started/login`), then sets up two-factor authentication at the first login
(see :doc:`/getting-started/enable-2fa`).

You can also create the account with **Add User** in the **Users** list: it is created as a regulator user
attached to no regulator. Attach it to your regulator as above: the **User** drop-down lists it.

Remove an account
"""""""""""""""""

Click the bin icon at the right of the card of the account: the card is covered with **This item will be deleted.**,
and **Click to cancel** keeps it. Then click **Save**. The account is not deleted, but deactivated:
its owner can no longer log in.

.. warning::

   Your own account is listed too. Turning off **Is administrator** or removing your own card
   takes away your own access.

.. _regulator-users:

Users
~~~~~

The **Users** list opens on the accounts of your regulator, and the regulator users not attached to any regulator yet.
To see the other accounts you can manage, the operator and incident user accounts, choose a role in **By Roles**
or an operator in **By Operators** under **Filters**, above the list, or search for a name.

The list shows the contact details of each account, its **Regulator**, its **Companies** (operators), its **Roles**,
whether the email address is verified and two-factor authentication is activated, and when the account was created.

.. figure:: /_static/images/administration/regulator-admin/governance-03.png
   :alt: Users list of a regulator administrator with the column headers and the Filters button outlined
   :target: ../../_static/images/administration/regulator-admin/governance-03.png

Click a name to open the account. You can change its contact details and turn off **Active** to deactivate it:
its owner can no longer log in, and it leaves the **Regulator users** section of your regulator. Whether it is
an administrator, what it may export and its sectors are set in that section (see :ref:`regulator-accounts`).
To add back an account you removed or deactivated, turn on its **Active** switch first: the **User** drop-down lists
active accounts only.

.. figure:: /_static/images/administration/regulator-admin/governance-04.png
   :alt: Change User form of a regulator user with the Active box and the Reset 2FA token button outlined
   :target: ../../_static/images/administration/regulator-admin/governance-04.png

The accounts of an operator are attached to it by a regulator user or by its operator administrators
(see :ref:`regulator-user-contacts` and :ref:`operator-admin-users`), not here.

Reset two-factor authentication
"""""""""""""""""""""""""""""""

You can reset the two-factor authentication of the accounts of your regulator, with the **Reset 2FA token** button
or the **Reset 2FA** action, as described in :ref:`platform-users`. You cannot reset it for operator accounts,
nor for your own: use **Account security** in the menu under your name, at the top right of the console.

Delete an account
"""""""""""""""""

The **Delete** button of an account behaves differently depending on the account:

- for a regulator account, it deactivates the account rather than deleting it;
- for an operator or incident user account, it deletes the account for good.

.. note::

   **Delete** is not offered for an account that has log entries: a regulator account once it has logged in,
   an operator administrator once they have made a change in the console. Turn off **Active** instead.

.. _regulator-sectors:

Sectors
~~~~~~~

The **Sectors** list shows the **Acronym**, **Name** and **Parent Sector** of each sector.

.. figure:: /_static/images/administration/regulator-admin/governance-05.png
   :alt: Sectors list with Sectors selected in the sidebar and the column headers outlined
   :target: ../../_static/images/administration/regulator-admin/governance-05.png

To create one, click **Add Sector**, enter its **Name**, which can be translated, and its **Acronym**,
of up to four characters, and click **Save**. The acronym must be unique among all sectors and sub-sectors,
as the export and import of a workflow find sectors by it: an acronym already in use is refused with
**Sector with this Acronym already exists.**

.. figure:: /_static/images/administration/regulator-admin/governance-06.png
   :alt: Add Sector form with the language tabs and the Name, Parent Sector and Acronym fields
   :target: ../../_static/images/administration/regulator-admin/governance-06.png

To make it a subsector, choose its **Parent Sector**, which lists the sectors that have no parent:
sectors have two levels at most. A sector that has subsectors only groups them: operators, regulator users
and observers are assigned its subsectors, not the sector itself.

.. warning::

   Sectors are shared by every regulator of the platform. Changing or deleting a sector changes or deletes it
   for all of them, and deleting a sector also deletes its subsectors. Read the confirmation page before confirming.

.. _regulator-operators:

Operators
~~~~~~~~~

The **Operators** list shows the **Acronym**, **Name**, **Address**, **Country**, **Email address** and **Phone number**
of each operator. Like sectors, operators are shared by every regulator of the platform.

To create one, click **Add Operator**, then fill in:

- **Contact information**: its **Name**, which must be unique, **Address**, **Country**, **Email address** and **Phone number**.
- **Configuration information**: its **Acronym**, unique, of up to ten characters.
- **Entity categories**: the categories of the operator. The incident rules of the observers refer to them
  (see :ref:`platform-observers`).
- **Sectors**: the sectors the operator is active in. They are also the sectors of all its security objectives
  declarations, which decide the regulator users who see them and the reporting projects they count in.
  A change applies at once to every declaration of the operator, including those already submitted.

Click **Save**.

.. figure:: /_static/images/administration/regulator-admin/governance-07.png
   :alt: Change Operator form with its contact information, acronym, entity categories and sectors
   :target: ../../_static/images/administration/regulator-admin/governance-07.png

The operator then needs its first operator administrator, which a regulator user adds
(see :ref:`regulator-user-contacts`).

.. note::

   An operator that still has accounts cannot be deleted: the platform keeps it and shows a warning.

Read-only items
~~~~~~~~~~~~~~~

The platform administrator sets up the following items; you can open them but not change them:

- **Regulations**: the **Label** of each regulation and its **Regulators**. You build workflows only for the regulations
  of your regulator (see :ref:`platform-regulations`).
- **Functionalities**: the optional modules and the roles that may use them (see :ref:`functionalities`).
- **Entity categories**: the **Code** and **Label** of the categories you assign to operators
  (see :ref:`platform-entity-categories`).
- **Observers**: the name and contact details of each observer, without its accounts or incident rules
  (see :ref:`platform-observers`).
- **Regulators**: the other regulators of the platform and their accounts (see :ref:`platform-regulators`).
