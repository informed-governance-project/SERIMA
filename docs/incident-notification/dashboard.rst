Dashboard
----------------------------------
One of the main functions of this platform is to allow you to report incidents.
You can begin the process by either clicking the :ref:`module selector <module-selector>` and selecting
**Incident notification** or by clicking the **Go to dashboard** button of the **Incident notification** tile in the center of the screen.

.. figure:: /_static/images/incident-notification/dashboard-01.png
   :alt: Incident notification tile on the homepage
   :target: ../_static/images/incident-notification/dashboard-01.png

Either way, you will get to the Incident notification dashboard, where you can see the overview of the reported incidents.
The incident notification dashboard is a central screen where you can manage all your reported incidents.
Which incidents it lists depends on your role: operators see the incidents of their operator, regulators the incidents
notified to them, and observers the incidents forwarded to their organisation (see :doc:`/getting-started/roles-and-permissions`).

Due to the complexity of the screen, its different parts will be presented one by one, with numbered sections describing the functionality of each.

.. figure:: /_static/images/incident-notification/dashboard-02.png
   :alt: Incident notification dashboard with its parts numbered
   :target: ../_static/images/incident-notification/dashboard-02.png

1. **Overview**: By clicking the **Overview** link in the top-right corner, you can return to the landing page of the Incident notification dashboard, which displays an overview of the reported incidents.

2. **Notify an incident**: This red button opens the form for a new incident (see :doc:`report-an-incident`).

3. **Search**: The search field is the quickest way to find an incident when there are many of them.
   It looks for the text you enter in the incident reference, the contact and technical contact names, the operator, the regulator, the regulation and the sectors.

4. **Filter**: The **Filter** button opens a panel where you can narrow the list down with the following fields:

   - **Incident Reference**: Shows only the incidents whose reference contains the text you enter.
   - **Incident status**: Shows only the **Ongoing** or only the **Closed** incidents.
   - **Significant impact**: Shows only the incidents with (**Yes**) or without (**No**) a significant impact. **Unknown**, the default, shows all incidents.
   - **Sectors**: Shows only the incidents affecting the sectors you tick in the drop-down list.

   Click **Search** to apply the filter, or **Reset** to clear it.

   For example, if you select **Yes** under **Significant impact** and click **Search**,
   the list shows only the incidents marked as having a significant impact
   (indicated by a white exclamation mark on a red hexagon in the **Status** column).
   While a filter is applied, the **Filter** button shows the label **(Active)**.

   .. note::

      The search, the filter and the sort order are kept until you log out, even if you leave the dashboard.
      If the list looks incomplete, check whether the **Filter** button shows **(Active)**, and click **Reset** to see all incidents again.

5. **Icon guide**: The Icon guide is represented by a book-shaped icon labeled **AZ**.
   Clicking this icon displays the legend above the incident list.

   .. figure:: /_static/images/incident-notification/dashboard-03.png
      :alt: Legend shown by the icon guide
      :target: ../_static/images/incident-notification/dashboard-03.png

   The first part of the legend explains the icons of the **Status** column: whether the incident has a significant impact, and whether it is ongoing or closed.
   The second part explains the status of each report in the **Report** column: unsubmitted, under review, submission overdue, late submission, revision required or passed.
   You can hide the legend by clicking the Icon guide again.
   How a report moves from one status to the next is described in the :doc:`operator` and :doc:`regulator` chapters.

6. **Columns and sorting**: On the dashboard, reported incidents are displayed in a table with the following headers by default:
   **Status, Last update, Creation date, Regulator, Regulation, Sectors, Report**, and **Actions**.

   Except for the **Report** and **Actions** columns, each column has an up-and-down arrow beside its header.
   Clicking the header sorts the incidents in ascending or descending order based on that column.
   Only one column can be sorted at a time, and its arrow is shown in a darker grey.
   By default, the list is sorted by **Last update**, with the most recently updated incident at the top.
   Each column is described in the :doc:`reported-incidents` chapter.

7. **Column settings**: To hide a column or change which columns are shown, click the **Column settings** icon, which is a white gear icon on a red background.

   Clicking the icon opens the **Choice of columns** pop-up, showing all available columns. A checkmark in front of a column name indicates that the column is currently displayed. To hide a column, remove the checkmark next to its name; the column disappears from the dashboard immediately.
   Besides the default columns, you can display the **Reference**, **Detection date**, **Start date** and **Resolution date** columns.

   .. note::

      Your choice of columns is saved in your web browser, not in your account.
      On another computer or browser, or after clearing your browser data, the dashboard shows the default columns again.

   .. figure:: /_static/images/incident-notification/dashboard-04.png
      :alt: Choice of columns
      :target: ../_static/images/incident-notification/dashboard-04.png

8. **Version control**: For each submitted report, version control shows when the report was changed and the status of each version.
   Its icon is beside the report name in the **Report** column.

   Clicking the icon opens the **Version control** pop-up. At the top, you will see the name of the report and the reference of the incident.
   Below that, each version is listed with its date, its status, and action icons to read the regulator's comment, view the version, or download it as a PDF document.
   The review of a report by the regulator is described in the :doc:`regulator` chapter.

   .. figure:: /_static/images/incident-notification/dashboard-05.png
      :alt: Version control pop-up
      :target: ../_static/images/incident-notification/dashboard-05.png

9. **More options and access log**: The **More options** icon (three dots) in the **Actions** column opens a menu with further actions on the incident.
   For operators, it holds the **Access Log**, which displays all activities that occurred during the incident's lifecycle.

   Clicking **Access Log** opens the log. At the top, you can see the reference of the incident, and below it, a table with the columns **Date, User, Role, Document**, and **Action**.
   Regulators also see an **Entity** column. You can sort the table by clicking a column header; in the example below, the log is sorted by **Date**, from the oldest entry to the newest.

   .. note::

      Operators see only the actions of their own users in the log. When the regulator or an observer opens,
      reviews or downloads a report, the entry appears in the regulator's log but not in the operator's.

   .. figure:: /_static/images/incident-notification/dashboard-06.png
      :alt: Access log sorted by date
      :target: ../_static/images/incident-notification/dashboard-06.png

10. **Download PDF report**: Click the **PDF** icon in the **Actions** column to download the whole incident, with all its reports, as a PDF document.
    To download a single report instead, use the small PDF icon beside the report in the **Report** column.
