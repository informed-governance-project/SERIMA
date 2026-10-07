Dashboard
----------------------------------

The **Security Objectives** module is a self-assessment tool: you declare how your organisation meets the security objectives
of your regulator's framework, and provide evidence of the security measures in place.

Open the dashboard with the :ref:`module selector <module-selector>`, or with the **Go to dashboard** button
of the **Security Objectives** tile on the homepage.

.. figure:: /_static/images/security-objectives/dashboard-01.png
   :alt: Security Objectives tile on the homepage
   :target: ../_static/images/security-objectives/dashboard-01.png

The dashboard lists your security objectives declarations and lets you create, fill in, submit and follow them.
Its parts are numbered in the screenshot below and described one by one.

.. figure:: /_static/images/security-objectives/dashboard-02.png
   :alt: Security Objectives dashboard with its parts numbered
   :target: ../_static/images/security-objectives/dashboard-02.png

1. **Dashboard**: This link in the top-right corner brings you back to the dashboard from any page of the module.

2. **New submission**: This red button opens the **Create a new security objectives statement** pop-up.
   The new declaration is then filled in as described in :doc:`fill-in-a-declaration`.

3. **Search**: Finds declarations by the text you enter, looked up in the framework, the creator, the operator, the year and the sectors.

4. **Filter**: Opens a panel to narrow the list down by **evaluation framework**, **year**, **sectors** and **status**.
   Click **Search** to apply the filter, or **Reset** to clear it. While a filter is applied, the **Filter** button shows the label **(Active)**.

   .. note::

      The search, the filter and the sort order are kept until you log out, even if you leave the dashboard.
      If the list looks incomplete, check whether the **Filter** button shows **(Active)**.

5. **Icon guide**: The book-shaped icon labeled **AZ** displays the legend above the list.
   Its first row explains the statuses shown in the **Status** column (see the table below); its second row, the action icons.
   Click the icon again to hide the legend.

   .. figure:: /_static/images/security-objectives/dashboard-03.png
      :alt: Legend with the declaration statuses and the action icons
      :target: ../_static/images/security-objectives/dashboard-03.png

   .. list-table::
      :header-rows: 1
      :widths: 25 75

      * - Status
        - Meaning
      * - Unsubmitted
        - The declaration is being filled in, and can still be edited or deleted.
      * - Under review
        - The declaration has been submitted, and the regulator has not reviewed it yet.
      * - Passed
        - The regulator accepted the declaration.
      * - Revision required
        - The regulator needs changes: read the review comment, then submit an updated version (see point 8).

   .. note::

      Regulators see two more statuses, **Passed and sent** and **Revision required and sent**, once they have sent
      the result of their review to the operator. Operators see them as **Passed** and **Revision required**.

6. **Columns and sorting**: The declarations are listed in a table. The screenshot below numbers its columns, all displayed by default;
   the table after it describes them.

   .. figure:: /_static/images/security-objectives/dashboard-04.png
      :alt: Header of the declarations list with its ten columns numbered
      :target: ../_static/images/security-objectives/dashboard-04.png

   .. list-table::
      :header-rows: 1
      :widths: 5 20 75

      * - #
        - Column
        - Description
      * - 1
        - Status
        - The status of the declaration (see point 5).
      * - 2
        - Last update
        - The date and time of the last change to the declaration.
      * - 3
        - Submission date
        - The date and time at which the declaration was submitted; empty until then.
      * - 4
        - Identifier
        - The reference the platform gives the declaration, starting with ``SO_``.
      * - 5
        - Evaluation Framework
        - The framework of security objectives the declaration answers.
      * - 6
        - Creator
        - Operators only: the person who created the declaration. Regulators see the **Company** instead.
      * - 7
        - Sectors
        - The sectors the declaration covers.
      * - 8
        - Year
        - The year the declaration is for.
      * - 9
        - Progress
        - How much of the declaration has been filled in. At 100 %, an unsubmitted declaration shows a **Submit** button here instead.
      * - 10
        - Actions
        - The actions on the declaration, described in points 8 to 13.

   Except for **Actions**, each column has an up-and-down arrow beside its header: click the header to sort the list
   in ascending or descending order. By default, the list is sorted by **Last update**, the most recent at the top.

   .. important::

      Once a declaration is complete, a **Submit** button replaces its progress bar: click it to submit the declaration.
      The declaration screen has its own **Submit** button (see :doc:`fill-in-a-declaration`).

7. **Column settings**: The white gear icon on a red background opens the **Choice of columns** pop-up.
   A checkmark in front of a column name means the column is displayed; remove it to hide the column.

   .. figure:: /_static/images/security-objectives/dashboard-05.png
      :alt: Choice of columns pop-up
      :target: ../_static/images/security-objectives/dashboard-05.png

   .. note::

      Your choice of columns is saved in your web browser, not in your account.
      On another computer or browser, or after clearing your browser data, the dashboard shows all columns again.

Points 8 to 13 are the actions of each declaration, in the order they appear in the **Actions** column.

8. **Edit / Review**: The pencil icon. Its tooltip tells you what it does:

   - **Edit** on an unsubmitted declaration: opens it so that you can fill it in.
   - **Review** on a submitted declaration: opens the **Update or review security objectives statement** pop-up.
     **Review** opens the declaration read-only; **Update** creates a new, unsubmitted version of it, with your answers,
     which you can change and submit again. Use it after a **Revision required**.

9. **Review comment**: The speech bubble opens the regulator's comment on the declaration.
   It is greyed out until the regulator has sent the result of the review with a comment.

10. **Duplicate**: Copies the declaration, with all its answers, to another year and sector, which saves filling in a similar declaration from scratch.
    In the **Duplicate the selected security objectives statement to** pop-up, select the **year** and the **sectors**, then click **Duplicate**.

    .. figure:: /_static/images/security-objectives/dashboard-06.png
       :alt: Duplicate the selected security objectives statement pop-up
       :target: ../_static/images/security-objectives/dashboard-06.png

    The copy appears at the top of the list as an unsubmitted declaration, with the message
    **The security objectives declaration has been duplicated.**

    .. figure:: /_static/images/security-objectives/dashboard-07.png
       :alt: Dashboard with the duplicated declaration outlined
       :target: ../_static/images/security-objectives/dashboard-07.png

    .. note::

       The **Duplicate** icon is disabled when the evaluation framework of the declaration is no longer active.

11. **Download**: Downloads the declaration as a PDF document.

12. **Delete**: Deletes the declaration. Only unsubmitted declarations can be deleted; for the others, the icon is greyed out.

13. **More options**: The three-dot icon opens a menu with the **Access Log** and, once the declaration has several versions, **Version control**.

    .. figure:: /_static/images/security-objectives/dashboard-08.png
       :alt: More options menu with the Access Log outlined
       :target: ../_static/images/security-objectives/dashboard-08.png

    The **Access Log** lists everything that happened to the declaration, with the columns **Date, Entity, User, Role**, and **Action**.

    .. figure:: /_static/images/security-objectives/dashboard-09.png
       :alt: Access log sorted by date, oldest first
       :target: ../_static/images/security-objectives/dashboard-09.png

    .. note::

       Operators see only the actions of operator users in the log. The regulator's readings and reviews
       appear in the regulator's log only.
