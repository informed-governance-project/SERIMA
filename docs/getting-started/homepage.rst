The homepage
------------

Parts of the homepage
~~~~~~~~~~~~~~~~~~~~~

On the homepage, you will find the following main functionalities (as numbered in the screenshot below):

.. figure:: /_static/images/getting-started/homepage-01.png
   :alt: Homepage with its parts numbered from 1 to 7
   :target: ../_static/images/getting-started/homepage-01.png

1. **SERIMA Home button**: Use this button in the top-left corner to come back to the homepage at any time.
2. **Settings**: This option takes you to the settings page. The content of the Settings page may vary depending on the type of user
   account you are logged in with. See :doc:`/administration/index`.
3. **Account type**: Use the downward-pointing arrow next to the user type to open the drop-down menu.
   What each account type can do is described in :doc:`roles-and-permissions`.

   .. figure:: /_static/images/getting-started/homepage-02.png
      :alt: Account menu open, with the Account, Security, Password and Log out entries
      :target: ../_static/images/getting-started/homepage-02.png

   - **Account**: By selecting the **Account** option, you can manage your account.
     You may change your first name, last name, and phone number.
     To proceed, you will need to log in again and provide a token to access the **Account Management** screen.

     .. figure:: /_static/images/getting-started/homepage-03.png
        :alt: Account management form with the first name, last name and phone number
        :target: ../_static/images/getting-started/homepage-03.png

   - **Security**: The Security menu takes you to the Account Security screen,
     where you can generate backup tokens for account access and enable or disable
     (This is strongly not recommended) two-factor authentication (see :doc:`enable-2fa`).

   - **Password**: If you select the **Password** menu, you will need to log in again and provide your token to access the **Change Password** screen.
     There, you can update your password. You must enter your current password and then type your new password twice
     (Please make sure to follow the :ref:`password requirements <password-requirements>`).

     .. figure:: /_static/images/getting-started/homepage-04.png
        :alt: Change password form
        :target: ../_static/images/getting-started/homepage-04.png

   - **Log out**: Use this link to log out of the application. In case you are not active, the system will log you out for security reasons.

4. **Contact**: Click the envelope icon to open the Contact form, through which you can send a message to the platform's support team.

     .. figure:: /_static/images/getting-started/homepage-05.png
        :alt: Contact form
        :target: ../_static/images/getting-started/homepage-05.png

5. **Language selector**: In the top right-hand corner, you can switch between English (**EN**), French (**FR**), Dutch (**NL**), and German (**DE**).
6. **Incident notification**: Use this module to report cybersecurity incidents to the competent authority (see :doc:`/incident-notification/index`).
7. **Security objectives**: A self-assessment module to fulfill security objectives evaluation and provide evidence for security measures in place
   (see :doc:`/security-objectives/index`).

The modules shown depend on your role and on what your regulator has enabled.

Module selector
~~~~~~~~~~~~~~~

Once you are away from the homepage, the cards are replaced by a **module selector** next to the SERIMA Home button.
Click it to open a dropdown menu listing the modules available to you, and switch to another one without going back to the homepage.

.. figure:: /_static/images/getting-started/homepage-06.png
   :alt: Module selector open on the incident notification module
   :target: ../_static/images/getting-started/homepage-06.png

Staying logged in
~~~~~~~~~~~~~~~~~

- **Pages that ask you to log in again**: opening **Account**, **Password**, or the backup tokens and two-factor settings
  under **Security** logs you out and asks you to log in again first, so that nobody can change them on an unattended session.
- **Inactivity**: after a period without activity, set by your platform, you are logged out and asked to log in again.
- **Terms of service**: the platform asks you to accept its terms of service at your first login,
  and again once your last acceptance is older than the period set by your platform (usually a year).
