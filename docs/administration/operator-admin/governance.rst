Governance
----------

The **Governance** section of the console is where you manage your operator and its accounts.
For an operator administrator, it lists:

- **Operators**, which you can change, see `Your operator`_;
- **Users**, where you add and change the accounts of your operator, see `Users`_.

The lists and forms work as described in :doc:`/administration/platform-admin/governance`.

Your operator
~~~~~~~~~~~~~

The **Operators** list shows only the operator you are working for, with its **Acronym**, **Name**, **Address**,
**Country**, **Email address** and **Phone number**.

.. figure:: /_static/images/administration/operator-admin/governance-01.png
   :alt: Operators list with Operators selected in the sidebar and the column headers outlined
   :target: ../../_static/images/administration/operator-admin/governance-01.png

Click its acronym to open it. You can change its **Email address** and **Phone number**, then click **Save**.
Its name, address, country, acronym, entity categories and sectors are read-only: the regulator manages them
(see :ref:`regulator-user-operators`).

.. figure:: /_static/images/administration/operator-admin/governance-02.png
   :alt: Change Operator form with the editable Email address and Phone number fields outlined, the other fields read-only
   :target: ../../_static/images/administration/operator-admin/governance-02.png

.. note::

   You cannot create or delete an operator, and its form has no **Contacts for company** section:
   you manage its accounts in `Users`_.

.. _operator-admin-users:

Users
~~~~~

The **Users** list shows the accounts of your operator, your own included, and the incident user accounts suggested
as members of it. For each account, it shows the contact details, whether the email address is verified and
two-factor authentication is activated, whether the account **Is Administrator** of your operator and is
**Approved** as a member of it, when the account was created, and its **Account actions**.
To narrow the list down, search for a name or an email address.

.. figure:: /_static/images/administration/operator-admin/governance-03.png
   :alt: Users list of an operator administrator with the column headers and the Set Administrator and Reset 2FA token buttons of an operator user outlined
   :target: ../../_static/images/administration/operator-admin/governance-03.png

The **Account actions** of a row are **Set Administrator** or **Unset Administrator** and **Reset 2FA token**,
or **Approve** and **Reject** for a suggested account. Your own row has none. Each button first shows
what it will do in an **Attention** dialog: click **Confirm** to go ahead, or **Cancel**.

Create an account
"""""""""""""""""

1. Click **Add User**.
2. Enter the **First name**, **Last name**, **Email address** and **Phone number** of the account.
3. Tick **Create this user as an administrator** to make it an operator administrator; leave it unticked for an operator user.
4. Click **Save**.

.. figure:: /_static/images/administration/operator-admin/governance-04.png
   :alt: Add User form with the Create this user as an administrator box outlined
   :target: ../../_static/images/administration/operator-admin/governance-04.png

The account is linked to your operator straight away. It has no password yet: its owner chooses one with
**Password forgotten?** on the login page (see :doc:`/getting-started/login`), then sets up two-factor authentication
at the first login (see :doc:`/getting-started/enable-2fa`).

.. note::

   The email address must not belong to an existing account: the form shows
   **An account with this email address already exists.** To add an existing account to your operator,
   ask your regulator (see :ref:`regulator-user-contacts`).

Change an account
"""""""""""""""""

Click a name to open the account. You can change its **First name**, **Last name** and **Phone number**, then click **Save**.
Its **Email address** and the **Additional information** are read-only.

.. figure:: /_static/images/administration/operator-admin/governance-05.png
   :alt: Change User form of an operator user with the Reset 2FA token, Set Administrator and Delete buttons outlined
   :target: ../../_static/images/administration/operator-admin/governance-05.png

The **Reset 2FA token** and **Set Administrator** or **Unset Administrator** buttons sit beside the fields they change,
and work as in the list:

- **Set Administrator** makes the account an operator administrator, and **Unset Administrator** makes it an operator user again.
  The account is logged out either way. You cannot change your own role.
- **Reset 2FA token** removes the authentication app of the account, when its owner has lost access to it.
  At the next login, they set up two-factor authentication again (see :doc:`/getting-started/enable-2fa`).
  To reset your own, use **Account security** at the top of the console.

.. _operator-admin-approve:

Approve or reject a suggested account
"""""""""""""""""""""""""""""""""""""

An incident user is someone who created their own account to notify incidents (see :doc:`/getting-started/create-account`).
When a regulator user adds such an account to your operator (see :ref:`regulator-user-contacts`), the account is only
suggested: it joins your operator once you approve it. Unless the account already belongs to another operator,
the email address of your operator and its administrators receive an email about the suggestion.

The **Users** list then shows **There is a suggestion to link a User Account to your company. Please Approve or Reject
the suggestion.** The row of the suggested account has **Approved** unticked, and **Approve** and **Reject**
in **Account actions**.

.. figure:: /_static/images/administration/operator-admin/governance-06.png
   :alt: Users list with the suggestion message and the Approve and Reject buttons of the suggested account outlined
   :target: ../../_static/images/administration/operator-admin/governance-06.png

1. Check who the account belongs to. Click its name to see its details: the account opens read-only, with the question
   **Add this user to Company** followed by the name of your operator, and the same two buttons.

   .. figure:: /_static/images/administration/operator-admin/governance-07.png
      :alt: Suggested account opened read-only, with the Add this user to Company question and the Approve and Reject buttons outlined
      :target: ../../_static/images/administration/operator-admin/governance-07.png

2. Click **Approve** to accept the suggestion, or **Reject** to refuse it.
3. In the **Attention** pop-up, which explains what the action does, click **Confirm**, or **Cancel** to change your mind.

- **Approve**: the account becomes an operator user of your operator, and the incidents it notified move to your operator.
- **Reject**: the suggestion is removed, and the account is not linked to your operator.

.. important::

   Approve only an account you know: once approved, its owner works for your operator and sees its incidents.

Remove an account
"""""""""""""""""

Open the account, click **Delete** and confirm. The account is not deleted: it is removed from your operator
and logged out. An account left without any operator is deactivated.

.. note::

   **Delete** is not shown for an operator administrator whose account has log entries, which it has as soon as
   its owner has changed something in the console: click **Unset Administrator** first.
   For a suggested account, click **Reject** instead.
