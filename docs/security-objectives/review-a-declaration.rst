Review a declaration
--------------------

As a regulator, you review the declarations operators submit against your frameworks. You go through the declaration
objective by objective, accept each objective or ask for its revision, comment where needed, then send the result
to the operator. Regulator administrators see all the declarations made to their regulator; regulator users see those
of the sectors assigned to them (see :doc:`/getting-started/roles-and-permissions`).

The operator's side of the cycle is described in :doc:`fill-in-a-declaration`.

Find the declarations to review
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The dashboard works as described in :doc:`dashboard`, with the differences numbered in the screenshot below.

.. figure:: /_static/images/security-objectives/review-a-declaration-01.png
   :alt: Regulator's dashboard with its differences from the operator's dashboard numbered
   :target: ../_static/images/security-objectives/review-a-declaration-01.png

1. **Import**: Replaces **New submission**. It adds a declaration from an Excel file (see `Import a declaration`_).
   An **Export** link follows it when you have the right to export (see `Export the list of declarations`_).

2. **Company**: Replaces the **Creator** column: the operator that submitted the declaration.
   The **Filter** panel also has a **Submitter** field to select an operator.

3. **Progress**: The share of the objectives you have reviewed. Once all are reviewed, a **Send** button
   replaces the bar until you send the result (see `Send the result`_).

4. **Review**: The pencil icon opens the declaration for review.

5. **Review comment**: Greyed out until every objective is reviewed. It then opens the **Review** pop-up, where you write
   your comment and send the result; once the result is sent, it shows your comment read-only.

6. **Delete**: Deletes the declaration.

   .. warning::

      Unlike operators, you can delete a declaration whatever its status, and the operator loses it too.
      Only the version listed is deleted: the previous version, if any, then appears in the list.

The dashboard lists submitted declarations only, one row per declaration with its latest submitted version.
While an operator prepares an update, you keep seeing the version they last submitted. There is no **Duplicate** icon.

Click the **Icon guide** to see the statuses as regulators see them:

.. figure:: /_static/images/security-objectives/review-a-declaration-02.png
   :alt: Legend of the regulator's dashboard with five statuses and the action icons
   :target: ../_static/images/security-objectives/review-a-declaration-02.png

.. list-table::
   :header-rows: 1
   :widths: 30 70

   * - Status
     - Meaning
   * - Under review
     - The declaration is waiting for your review, or your review is not finished: some objectives are still not reviewed.
   * - Passed
     - You have accepted every objective, and not sent the result yet.
   * - Revision required
     - You have reviewed every objective and asked for the revision of at least one, and not sent the result yet.
   * - Passed and sent
     - You have sent the operator the result **Passed**.
   * - Revision required and sent
     - You have sent the operator the result **Revision required**.

The status follows from the results you give the objectives: you never set it yourself.

Open a declaration
~~~~~~~~~~~~~~~~~~

Click the **Review** icon (pencil) of the declaration. It opens on the declaration screen described in
:ref:`declaration-screen`, where the operator's answers are read-only. The profile icon beside **Company** gives you
the name, email and phone number of the person who created the declaration. The parts specific to your review are numbered below.

.. figure:: /_static/images/security-objectives/review-a-declaration-03.png
   :alt: Declaration under review with the review comment icon, the objective result, Send, Close, the objective selector and the Icon Guide numbered
   :target: ../_static/images/security-objectives/review-a-declaration-03.png

1. **Review comment**: Opens the **Review** pop-up, to write your comment on the whole declaration (see `Comment on the declaration`_).

2. **Objective result**: Your result for the objective displayed (see `Review each objective`_).

3. **Send**: Sends the result of your review to the operator (see `Send the result`_).
   It stays disabled until every objective is reviewed.

4. **Close**: Brings you back to the dashboard.

5. **Objective selector**: One button per objective, showing your result for it. Click a button to open that objective.

6. **Icon Guide**: Shows the legend of the selector and of the maturity levels.

   .. figure:: /_static/images/security-objectives/review-a-declaration-04.png
      :alt: Legend of the objective selector with Not reviewed, Review passed and Review required, and the maturity levels
      :target: ../_static/images/security-objectives/review-a-declaration-04.png

   .. list-table::
      :header-rows: 1
      :widths: 25 25 50

      * - Button
        - Legend
        - Meaning
      * - Orange triangle
        - Not reviewed
        - You have not given the objective a result yet.
      * - Green circle
        - Review passed
        - You accepted the objective.
      * - Red square
        - Review required
        - You asked for the revision of the objective.

.. important::

   There is no **Save** button for your review: the result of an objective is saved as soon as you select it,
   and a comment on a measure as soon as you leave its field. You can click **Close** at any time and continue later.

Review each objective
~~~~~~~~~~~~~~~~~~~~~

For each objective of the declaration:

1. Read the operator's answers: the measures turned on in **Measure Implemented?**, their **Justification**,
   and the **Planned Measures**. The score is calculated as described in :doc:`fill-in-a-declaration`.

2. Where needed, write a comment on a measure in its **Review comment** field.

   .. figure:: /_static/images/security-objectives/review-a-declaration-05.png
      :alt: Objective with the operator's answers read-only and the editable Review comment column outlined
      :target: ../_static/images/security-objectives/review-a-declaration-05.png

3. Select the result of the objective in the list beside **Send**:

   - **Passed** if you accept the objective.
   - **Revision required** if the operator has to change it. Explain why in the comments.
   - **Not reviewed** to withdraw a result.

   .. figure:: /_static/images/security-objectives/review-a-declaration-06.png
      :alt: Objective result list open with Not reviewed, Passed, Revision required, All passed and All revision required
      :target: ../_static/images/security-objectives/review-a-declaration-06.png

4. Go to the next objective with the arrows or the objective selector.

.. tip::

   **All passed** and **All revision required** give every objective of the declaration that result at once.
   When most objectives are fine, select **All passed**, then change the few that need revision.

.. warning::

   The operator sees your work as you save it, before you send anything: the results of the objectives and
   your comments on measures in the declaration, and the status **Passed** or **Revision required** once every
   objective is reviewed. Only your comment on the declaration, and the email, wait until you send the result.

Comment on the declaration
~~~~~~~~~~~~~~~~~~~~~~~~~~

Click the **Review comment** icon at the top of the declaration to write your comment on the whole declaration,
for example a summary of the revisions needed. Click **Save** to keep it: it is not sent yet, and you can change it
until you send the result.

.. figure:: /_static/images/security-objectives/review-a-declaration-07.png
   :alt: Review pop-up with the review comment editor and the Save button
   :target: ../_static/images/security-objectives/review-a-declaration-07.png

Send the result
~~~~~~~~~~~~~~~

When every objective has a result, the status of the declaration becomes **Passed** if you accepted them all,
or **Revision required** if at least one needs revision, and **Send** becomes available.

1. Click **Send** in the declaration, or in the **Progress** column of the dashboard.
2. The **Review** pop-up shows the **Status** the operator will receive, which you cannot change there,
   and your **Review comment**, which is required. Write or complete the comment.
3. Click **Send**.

The platform takes you back to the dashboard with the message **The security objectives review has been sent.**
The status becomes **Passed and sent** or **Revision required and sent**, and the operator sees it as **Passed** or
**Revision required**, with your comment (see :doc:`fill-in-a-declaration`). If the framework has an email for status change
(see :doc:`/administration/regulator-admin/security-objectives`), it is sent to the users of the operator, to your
regulator's notification address, and to the regulator users of the declaration's sectors and the regulator administrators.

.. important::

   A sent result cannot be changed: the results, the comments and the review comment become read-only.
   The **Review comment** icon then shows the comment as the operator received it.


.. figure:: /_static/images/security-objectives/review-a-declaration-08.png
   :alt: Read-only Review pop-up with the status Revision required and the review comment
   :target: ../_static/images/security-objectives/review-a-declaration-08.png

.. note::

   A declaration **Passed and sent** is the one the reporting module counts as the security objectives
   of the operator for its year and sectors.

Review an updated version
~~~~~~~~~~~~~~~~~~~~~~~~~

After a **Revision required**, the operator updates the declaration and submits a new version (see :ref:`update-a-declaration`).
It appears on the dashboard as **Under review**, in place of the version you sent back.

The new version starts from your review of the previous one:

- The objectives the operator left unchanged keep your result. Those they changed are **Not reviewed** again,
  so they are the ones to review.
- Your comments on measures and on the declaration are carried over. Update or clear them as needed before sending.
- Each measure whose answer changed is outlined in orange with a **View previous version** button, as are the
  **Planned Measures** when they changed (see :ref:`compare-versions`).

.. figure:: /_static/images/security-objectives/review-a-declaration-09.png
   :alt: Objective of a new version with the changed measures and planned measures outlined in orange and a View previous version button outlined
   :target: ../_static/images/security-objectives/review-a-declaration-09.png

Review and send the new version as described above. The declaration can go back and forth until you accept it.

To follow the rounds, open **Version control** in the **More options** menu of the dashboard. It lists each submitted
version with its submission date and status. Its icons open the review comment of the version, the version itself,
and its PDF.

.. figure:: /_static/images/security-objectives/review-a-declaration-10.png
   :alt: Version control pop-up with four versions, three with the status Revision required and sent and the first Under review
   :target: ../_static/images/security-objectives/review-a-declaration-10.png

Import a declaration
~~~~~~~~~~~~~~~~~~~~

When an operator gives you its declaration as an Excel file rather than through the platform, import it:

1. Click **Import** in the top-right corner of the module.
2. In the **Import Security Objectives Statement** pop-up, select the file, then the **Company**, the **Sectors**,
   the **Evaluation Framework** and the **Year** of the declaration.
3. Click **Import**.

The declaration is created with the status **Under review** and today's submission date, in the name of an administrator
of the company, and you review it like any other. Regulator users can import only for the companies and sectors assigned to them.

.. important::

   The file must follow the layout the platform reads. On the sheet that was active when the file was saved,
   rows 4 to 120 each describe one objective: column B holds the objective code (the text before a colon),
   column G the evidence, column H the justification, and column I the maturity level reached, as a whole number.
   For each objective, the measures of the levels from 1 up to that level are turned on, and the evidence and
   justification go to the first measure of the level reached. Rows whose code is not in the framework are ignored.

Export the list of declarations
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The **Export** link appears in the top-right corner of the module once a regulator administrator has ticked
**Can export security objectives** on your account.

1. Click **Export**.
2. In the **Export security objectives** pop-up, select the **Regulation**, then the **Evaluation Framework**, **Year**,
   **Sectors** and **Status** of the declarations to export, and the **File format**: **Excel (.xlsx)** or **CSV (.csv)**.
3. Click **Export**. The file downloads when it is ready.

The file lists the declarations of your dashboard that match your choices, one row each, with the columns of the
dashboard. It does not contain the answers. A second sheet (in CSV, a second file in a ZIP archive) records who exported what, and when.

.. note::

   Each export is recorded in the log of the administration console, and your regulator's notification address,
   the regulator users of the selected sectors and the regulator administrators receive an email telling them that an export was made.
