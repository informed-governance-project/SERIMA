Security Objectives
-------------------

The **Security Objectives** section of the console holds the evaluation frameworks that operators answer
in their declarations (see :doc:`/security-objectives/fill-in-a-declaration`) and that your regulator reviews
(see :doc:`/security-objectives/review-a-declaration`). It lists **Domains**, **Email templates**,
**Maturity levels**, **Security Measures**, **Security Objectives** and **Standards**.

.. note::

   The section is shown only once the platform administrator has opened the module to regulator administrators
   and to your regulator (see :ref:`functionalities` and :ref:`platform-regulators`).

How the pieces fit together
~~~~~~~~~~~~~~~~~~~~~~~~~~~

- A **standard** is a framework, called **Evaluation Framework** in the declarations. It belongs to your regulator
  and to one regulation, and it sets how the declaration table looks and which fields are mandatory.
- A standard has **maturity levels**, from the lowest, where nothing is in place, to the highest.
- Its **security objectives** are grouped into **domains**. The standard sets the order of its objectives.
- Each objective has **security measures**. Each measure belongs to a maturity level and states
  the **evidence** you expect to see for it.
- **Email templates** are the emails sent when a declaration is submitted and when you send the result of a review.

Since each item refers to the previous ones, set them up in this order:

1. `Email templates`_
2. `Standards`_, with **Active** unticked
3. `Maturity levels`_
4. `Domains`_
5. :ref:`Security objectives <regadmin-security-objectives>`
6. The objectives of the standard (see `Objectives of the standard`_)
7. `Security measures`_
8. Tick **Active** on the standard, so that operators can declare against it.

Alternatively, create the standard and import the rest from a file (see `Import and export a framework`_).

Every item works the same way:

- Click its name to open the list. Click **Add** next to the name, or the **Add** button at the top right of the list,
  to create a new one; click a line of the list to open and change it.
- To delete objects, tick them in the list, choose the **Delete selected** action in the **Action** drop-down
  and click **Run**.
- Texts can be translated: the tabs above the form (**English**, **French**, **Dutch**, **German**) switch
  between the languages of the platform. Save your changes before you leave the tab of a language.

.. important::

   You can change or delete only the objects your regulator created. Once a declaration has answered
   a security measure, the measure, its security objective and the domain of the objective become read-only:
   their page opens as **View** instead of **Change**, with the message **Modification and deletion actions are not allowed**.
   Maturity levels and email templates stay editable. A standard stays partly editable (see `A standard in use`_).

Email templates
~~~~~~~~~~~~~~~

The **Email templates** list shows the **Name**, **Subject** and **Content** of each template.
A template has:

- a **Name**, which identifies it in the drop-downs of the standards. Operators never see it.
- a **Subject** and a **Content**, which can be translated. The content is written in Markdown:
  the **HTML preview** below it shows how it is formatted, once saved.

.. figure:: /_static/images/administration/regulator-admin/security-objectives-01.png
   :alt: Change Email template form with its name, subject, content, available placeholder and HTML preview
   :target: ../../_static/images/administration/regulator-admin/security-objectives-01.png

The only placeholder is ``#SO_REFERENCE#``, replaced by the identifier of the declaration, in the subject or the content.
As for incident emails, one email is sent in all languages: the content in the default language of the platform comes first,
followed by each translation that differs from it.

The emails are sent to the users of the operator, to your regulator's address for incident notification,
to your regulator administrators, and to the regulator users in charge of the sectors of the declaration.

Standards
~~~~~~~~~

The **Standards** list shows whether each standard is **Active**, its **Label**, **Description** and **Regulator**.
The **Import** and **Export** buttons at the top right are described in `Import and export a framework`_.

.. figure:: /_static/images/administration/regulator-admin/security-objectives-02.png
   :alt: Standards list with the Standards entry of the sidebar, the Import and Export buttons and the column headers outlined
   :target: ../../_static/images/administration/regulator-admin/security-objectives-02.png

Create a standard
"""""""""""""""""

1. Click **Add standard** and fill in the **General** section:

   - **Active**: operators can create a declaration, with **New submission** on the :doc:`/security-objectives/dashboard`,
     only on an active standard that contains objectives, and duplicate one only if its standard is active. Untick it until the framework is complete.
   - **Regulation**: the regulation the framework belongs to. Only the regulations of your regulator are listed
     (see :ref:`platform-regulations`).
   - **Label** and **Description**: the name of the framework, shown to operators as the **Evaluation Framework**.

2. In **Notification Email**, select the emails of the standard (see `Email templates`_):

   - **Submission e-mail**: sent when an operator submits a declaration.
   - **Email for status change**: sent when you send the result of a review.
   - **Email for closure**: not sent by the platform at the moment.

   .. figure:: /_static/images/administration/regulator-admin/security-objectives-03.png
      :alt: Add Standard form with its General and Notification Email sections
      :target: ../../_static/images/administration/regulator-admin/security-objectives-03.png

3. Set up the declaration table, as described below, and click **Save and continue editing**.
   The **Security objectives in standards** section appears once the standard is saved.

Columns and score
"""""""""""""""""

The **Columns display settings** set how the table of each objective looks in the declarations
(see :ref:`declaration-screen`):

- Each column has a **label**. Leave it empty to use the default name shown below the field, translated in every
  language; a label you enter applies only to the language tab it is entered in.
- **Show** hides or shows the **Maturity level**, **Evidence**, **Justification** and **Review comment** columns,
  and the **Planned Measures** field below the table. The **Security Measure** and **Measure Implemented?**
  columns are always shown.
- **Mandatory**, for **Justification** and **Planned Measures**, requires the operator to fill them in before
  the objective counts as fully filled. A hidden field cannot be mandatory: the form refuses to save it.

In **Score display settings**, **Score** chooses how the score of each objective is shown in the declaration
and its PDF: **Score and maximum**, **Score only** or **Hidden**.

.. figure:: /_static/images/administration/regulator-admin/security-objectives-04.png
   :alt: Columns display settings and Score display settings of a standard
   :target: ../../_static/images/administration/regulator-admin/security-objectives-04.png

Objectives of the standard
""""""""""""""""""""""""""

Once the domains and security objectives exist, open the standard again. In **Security objectives in standards**,
click **Add another Security objectives in standard** for each objective, and fill in its row:

- **Security objective**: the objective. Only your objectives whose domain belongs to this standard, and that are
  not already in another standard, are listed.
- **Position**: the order of the objective in the declaration.
- **Priority**: a rank used by the report generation module to order objectives that have the same score.

.. figure:: /_static/images/administration/regulator-admin/security-objectives-05.png
   :alt: Security objectives in standards section with the column headers outlined
   :target: ../../_static/images/administration/regulator-admin/security-objectives-05.png

A standard in use
"""""""""""""""""

Once a declaration has been created with a standard, a warning at the top of its page says it is in use.
Its **Active** box, label, description, column labels, the **Show** boxes of the **Maturity level**, **Evidence**
and **Review comment** columns, and the score display stay editable. The regulation, the notification emails,
the **Justification** and **Planned Measures** settings and the list of security objectives become read-only.

.. note::

   The column settings are read each time a declaration is displayed, so changing them changes the existing
   declarations too.

.. warning::

   Deleting a standard also deletes its security objectives, domains, maturity levels and security measures.
   A standard in use cannot be deleted: untick **Active** instead to stop new declarations.

Maturity levels
~~~~~~~~~~~~~~~

The **Maturity levels** list shows the **Standard**, **Level**, **Color** and **Label** of each level.

.. figure:: /_static/images/administration/regulator-admin/security-objectives-06.png
   :alt: Maturity levels list with the Maturity levels entry of the sidebar and the column headers outlined
   :target: ../../_static/images/administration/regulator-admin/security-objectives-06.png

A maturity level has:

- a **Standard**. Each standard has its own levels.
- a **Label**, such as "Basic", shown in the declarations and in the legend of the **Icon Guide**.
- a **Level**, its number. Each number can be used only once per standard.
- a **Color**, used in the reports of the reporting module.

The standard and the level number cannot be changed once the level is saved.

.. important::

   Number the levels from 0. The lowest level describes the situation where nothing is in place:
   in a declaration, it excludes the other levels, and the score counts only the levels above 0
   (see :doc:`/security-objectives/fill-in-a-declaration`).

Domains
~~~~~~~

Domains group the security objectives of a standard, such as governance or incident management.
The **Domains** list shows the **Standard**, **Position** and **Label** of each domain.

.. figure:: /_static/images/administration/regulator-admin/security-objectives-07.png
   :alt: Domains list with the Domains entry of the sidebar and the column headers outlined
   :target: ../../_static/images/administration/regulator-admin/security-objectives-07.png

A domain has a **Standard**, a **Label** and a **Position**, its order in the standard.

.. note::

   Moving a domain to another standard removes its objectives from the standard they were in.

.. _regadmin-security-objectives:

Security objectives
~~~~~~~~~~~~~~~~~~~

The **Security Objectives** list shows the **Standard**, **Unique code**, **Objective**, **Description** and **Domain**
of each objective. Use the filters on the right, for instance **By Standard**, to find one.

.. figure:: /_static/images/administration/regulator-admin/security-objectives-08.png
   :alt: Security Objectives list with the Security Objectives entry of the sidebar and the column headers outlined
   :target: ../../_static/images/administration/regulator-admin/security-objectives-08.png

A security objective has:

- a **Domain**, which ties it to a standard. Only your domains are listed.
- a **Unique code**, shown before its name in the declarations. Your regulator cannot use the same code twice.
- an **Objective**, its name, and a **Description**, both shown to operators at the top of the objective.

.. figure:: /_static/images/administration/regulator-admin/security-objectives-09.png
   :alt: Add Security Objective form with its domain, unique code, objective and description
   :target: ../../_static/images/administration/regulator-admin/security-objectives-09.png

An objective appears in declarations only once it is added to its standard (see `Objectives of the standard`_).
Moving it to a domain of another standard removes it from its standard.

Security measures
~~~~~~~~~~~~~~~~~

The **Security Measures** list shows the **Standard**, **Security Objective**, **Level**, **Position** and **Description**
of each measure. Use the **By standard** and **By Security Objective** filters to find one.

.. figure:: /_static/images/administration/regulator-admin/security-objectives-10.png
   :alt: Security Measures list, sidebar collapsed, with the column headers outlined
   :target: ../../_static/images/administration/regulator-admin/security-objectives-10.png

A security measure is one row of the table of an objective. It has:

- a **Security Objective**. Only the objectives already added to a standard are listed. It cannot be changed
  once the measure is saved.
- a **Level**: the maturity level of the measure. It must belong to the standard of the objective, or the form
  refuses to save the measure.
- a **Position**: the order of the measure in the table of the objective. The rows are sorted by position only,
  so number the measures level by level, starting with the lowest level.
- a **Description**: the measure the operator implements, in the **Security Measure** column.
- an **Evidence**: what you expect to see to accept the measure, in the **Evidence** column.

.. figure:: /_static/images/administration/regulator-admin/security-objectives-11.png
   :alt: Add Security Measure form with its security objective, level, position, description and evidence
   :target: ../../_static/images/administration/regulator-admin/security-objectives-11.png

Import and export a framework
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The **Import** and **Export** buttons of the **Standards** list move the content of a framework in and out
of the platform as a file, one line per security measure. The texts are read and written in the language
the console is displayed in.

Export
""""""

Click **Export**, tick the columns to export, choose the **Format** (for instance csv or xlsx) and click **Submit**.
The file is prepared in the background; click **Download export data** when it is ready.

.. figure:: /_static/images/administration/regulator-admin/security-objectives-12.png
   :alt: Export page with the list of columns to export and the format drop-down
   :target: ../../_static/images/administration/regulator-admin/security-objectives-12.png

.. tip::

   Export an existing framework to get a file with the expected columns, then edit it to import another one.

Import
""""""

1. Create the standard first: the import fills in an existing standard, and does not create it.
2. Click **Import**. The page lists the columns the file can contain: ``label`` and ``regulation`` identify
   the standard and its regulation by their names, the other columns describe the domain, the security objective,
   the maturity level and the security measure of each line.
3. Select the **File to import** and its **Format**, and click **Submit**.

   .. figure:: /_static/images/administration/regulator-admin/security-objectives-13.png
      :alt: Import page with the list of accepted columns, the file and format fields
      :target: ../../_static/images/administration/regulator-admin/security-objectives-13.png

4. The platform first shows the changes the file would make. Check them, then confirm the import.

The import creates or updates, for your regulator, the domains by position, the security objectives by unique code
and domain, the maturity levels by level number, and the security measures by objective, level and position.
It also adds the objectives to the standard, with their position and priority.
