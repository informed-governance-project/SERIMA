Governance
----------

The **Governance** section of the console is where you manage your observer and its accounts.
For an observer administrator, it lists:

- **Observers**, where you change your observer, its RT connection and who administers it,
  see `Your observer`_, `RT ticketing system`_ and `Observer accounts`_;
- **Users**, where you add and change the accounts of your observer, see `Users`_.

The lists and forms work as described in :doc:`/administration/platform-admin/governance`.

.. _observer-admin-observer:

Your observer
~~~~~~~~~~~~~

The **Observers** list shows only your observer, with its **Name**, **Full name** and **Description**.

.. figure:: /_static/images/administration/observer-admin/governance-01.png
   :alt: Observers list with Observers selected in the sidebar and the column headers outlined
   :target: ../../_static/images/administration/observer-admin/governance-01.png

Click its name to open it. You can change:

- its **Name**, **Full name** and **Description**, in each language of the platform: click a language tab,
  fill in the fields and save before switching to another tab;
- its **Country** and **Address**;
- its **E-mail address for incident notification**, the shared address that receives the emails the platform sends
  about the incidents your observer receives, unless an RT ticketing system receives them instead
  (see `RT ticketing system`_).

Then click **Save**.

.. figure:: /_static/images/administration/observer-admin/governance-02.png
   :alt: Change Observer form with the language tabs and the E-mail address for incident notification field outlined
   :target: ../../_static/images/administration/observer-admin/governance-02.png

.. note::

   When no RT ticketing system is connected, the emails about an incident also go to every account of your observer,
   administrators and users alike.

.. _observer-admin-rt:

RT ticketing system
~~~~~~~~~~~~~~~~~~~

Instead of emails, your observer can receive the incidents as tickets in a queue of a Request Tracker (RT) instance.
Click **RT Configuration** in the form of your observer to unfold it, then:

1. Enter the **URL** of the RT instance, such as ``https://rt.example.com``, the **Token** of an RT account
   allowed to create tickets, and the **Queue** that receives them.
2. Click **Save and continue editing**.
3. Click **Test RT Connection**. The result is shown beside the button: **RT connection successful.**,
   or **RT connection failed. Check URL, queue and token.**

.. figure:: /_static/images/administration/observer-admin/governance-03.png
   :alt: RT Configuration section unfolded, with its URL, Token and Queue fields and the Test RT Connection button outlined
   :target: ../../_static/images/administration/observer-admin/governance-03.png

A successful test creates a test ticket in the queue, which you can delete. From then on, the first email about
an incident opens a ticket in the queue, and the following ones are added to that ticket as replies.
Your observer's address and accounts no longer receive these emails.

.. note::

   The URL must use HTTPS and point to a public address. Once saved, the token is masked:
   to replace it, enter the new one; to remove it, clear the field and save.

.. important::

   The emails go back to your observer's address and accounts whenever the RT instance cannot be reached
   with the URL, token and queue saved. Test the connection again after changing any of them.

.. _observer-admin-accounts:

Observer accounts
~~~~~~~~~~~~~~~~~

The **Observer users** section at the bottom of the form of your observer lists its accounts, one row each.

.. figure:: /_static/images/administration/observer-admin/governance-04.png
   :alt: Observer users section with the Is administrator and Can export incidents columns and the Add another Observer user link outlined
   :target: ../../_static/images/administration/observer-admin/governance-04.png

Each row has:

- **User**: the account. The drop-down lists the accounts of your observer and the observer administrator accounts
  linked to no observer.
- **Is administrator**: keep it ticked: every member of an observer's staff is an observer administrator.
  Changing it switches the role of the account and logs it out.
- **Can export incidents**: whether the account can export the incidents your observer receives, read-only:
  the platform administrator sets it.
- **Delete?**: removes the account from your observer. The account is logged out, and can no longer use the platform;
  an observer administrator left without any observer to administer is also deactivated.

To make an existing account of your observer an observer administrator, tick **Is administrator** on its row
and click **Save**. To add a row, click **Add another Observer user** and choose the account.

.. warning::

   Your own row is in the list too. Unticking **Is administrator** or ticking **Delete?** on it removes your access
   to the console as soon as you save.

.. _observer-admin-users:

Users
~~~~~

The **Users** list shows the accounts of your observer, your own included. For each account, it shows
the contact details, its **Observer** and **Roles**, whether the email address is verified and two-factor authentication
is activated, when the account was created, and its **Account actions**. To narrow the list down, search for a name
or an email address, or use **By Roles** in the **Filter** panel.

.. figure:: /_static/images/administration/observer-admin/governance-05.png
   :alt: Users list of an observer administrator with the column headers and the Filter panel outlined
   :target: ../../_static/images/administration/observer-admin/governance-05.png

Create an account
"""""""""""""""""

1. Click **Add User**.
2. Enter the **First name**, **Last name**, **Email address** and **Phone number** of the account.
3. Click **Save**.

.. figure:: /_static/images/administration/observer-admin/governance-06.png
   :alt: Add User form with its contact information fields outlined
   :target: ../../_static/images/administration/observer-admin/governance-06.png

The account is linked to your observer straight away, but without the administrator role.

.. important::

   Every member of an observer's staff is an observer administrator: after creating the account, tick
   **Is administrator** on its row in `Observer accounts`_ and click **Save**.

The account has no password yet: its owner chooses one with **Password forgotten?** on the login page
(see :doc:`/getting-started/login`), then sets up two-factor authentication at the first login
(see :doc:`/getting-started/enable-2fa`).

.. note::

   The email address must not belong to an existing account: the form shows
   **An account with this email address already exists.**

Change an account
"""""""""""""""""

Click a name to open the account. You can change its **First name**, **Last name**, **Email address**
and **Phone number**, then click **Save**. The **Additional information** is read-only: the **Observer** and **Roles**
of the account, when it joined, and whether its email address is verified and two-factor authentication activated.

.. figure:: /_static/images/administration/observer-admin/governance-07.png
   :alt: Change User form of an observer administrator with the Contact information and Additional information sections outlined
   :target: ../../_static/images/administration/observer-admin/governance-07.png

Reset two-factor authentication
"""""""""""""""""""""""""""""""

When someone has lost access to their authentication app, click **Reset 2FA token** on their row of the list,
or beside **2FA Activated** on their account, then **Confirm** in the **Attention** dialog. To reset several accounts
at once, tick them, choose **Reset 2FA** in the **Action** drop-down and click **Run**. At their next login,
they set up two-factor authentication again (see :doc:`/getting-started/enable-2fa`).
You cannot reset your own: use **Account security** at the top of the console.

Remove an account
"""""""""""""""""

To withdraw someone's access, remove their account from your observer in `Observer accounts`_.

.. warning::

   The **Delete** button of an account deletes it for good, rather than removing it from your observer.
   It is refused for an account with log entries, which it has as soon as it has changed something in the console
   or exported incidents.
