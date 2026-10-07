Fill in a declaration
---------------------

A **declaration** (also called a security objectives statement) is your answer to the evaluation framework
set up by your regulator. The framework is a list of **security objectives**. Each objective comes with
**security measures** grouped by **maturity level**, from the lowest level, where nothing is in place,
to the highest. For each objective, you declare which measures are implemented, justify them,
and describe the measures you plan to take.

Each declaration goes through the same cycle:

1. You fill in the declaration and submit it.
2. The regulator reviews each objective, and either accepts the declaration (**Passed**) or asks for changes (**Revision required**).
3. If changes are needed, you update the declaration and submit the new version, which the regulator reviews again.

This chapter describes your side of that cycle. The dashboard and its statuses are described in :doc:`dashboard`,
and the regulator's review in :doc:`regulator`.

.. important::

   Each regulator sets up its own frameworks. The objectives, the maturity levels, the names of the columns,
   which columns are shown, whether the justification and the planned measures are mandatory, and whether the
   score is shown, all depend on the framework of the declaration.
   The screenshots in this chapter are examples: your declarations can look different.

Create a declaration
~~~~~~~~~~~~~~~~~~~~

Click **New submission** on the :doc:`dashboard`. In the **Create a new security objectives statement** pop-up,
select the **Evaluation Framework**, the **Year** and one or more **Sectors**, then click **Create**.
The new declaration opens straight away, with the status **Unsubmitted**.

To come back to it later, click its **Edit** icon (pencil) in the **Actions** column of the dashboard.

.. tip::

   To start from the answers of an existing declaration instead, use **Duplicate** on the dashboard.

The declaration screen
~~~~~~~~~~~~~~~~~~~~~~

The declaration shows one security objective at a time. Its parts are numbered in the screenshot below and described one by one.

.. figure:: /_static/images/security-objectives/fill-in-a-declaration-01.png
   :alt: Declaration screen with its parts numbered
   :target: ../_static/images/security-objectives/fill-in-a-declaration-01.png

1. **Submission date** and **Last update**: The submission date stays empty until the declaration is submitted.

2. **Company** and **Evaluation Framework**: The operator the declaration is for, and the framework it answers.
   The profile icon beside them opens the **Profile** pop-up, with the name, email and phone number of the person
   who created the declaration.

3. **Sectors**: The sectors the declaration covers.

4. **Review comment**: The speech bubble opens the regulator's comment on the whole declaration.
   It is greyed out until the regulator has sent the result of the review with a comment.

5. **Submit**: Sends the declaration to the regulator (see `Submit the declaration`_). It is shown only while the declaration is unsubmitted.

6. **Close**: Brings you back to the dashboard.

7. **Objective selector**: One button for each security objective of the framework, in the framework's order.
   Click a button to open that objective. The shape and colour of each button tell you how far the objective is filled in
   (see `Follow your progress`_). The selector is shown on wide screens only.

8. **Previous** and **next** arrows: Move to the previous or the next objective.

9. **Icon Guide**: Shows the legend of the selector and of the maturity levels. Click it again to hide it.

10. **Objective**: The code, name and description of the objective displayed.

11. **Score**: The score of the objective (see `Follow your progress`_).

.. important::

   There is no **Save** button: each answer is saved as soon as you change it. A switch is saved when you flip it,
   and a text field when you leave it, for example by clicking elsewhere. You can click **Close** at any time
   and continue later.

Fill in an objective
~~~~~~~~~~~~~~~~~~~~

Each objective is a table with one row per security measure, grouped by maturity level, and a **Planned Measures** field below it.

.. figure:: /_static/images/security-objectives/fill-in-a-declaration-02.png
   :alt: Security objective with its measures grouped by maturity level, two measures implemented with their justification, and the Planned Measures field
   :target: ../_static/images/security-objectives/fill-in-a-declaration-02.png

The columns are:

- **Maturity level**: The level the measures of the row belong to.
- **Security Measure**: The measure to put in place.
- **Evidence**: The evidence the regulator expects to see for that measure. You cannot edit it.
- **Measure Implemented?**: A switch to turn on for each measure that is in place.
- **Justification**: How the measure is implemented, and where the evidence can be found.
- **Review comment**: The regulator's comment on the measure. You cannot edit it. The column appears once
  the declaration has been submitted, or when the regulator has already commented on an earlier version.

To fill in an objective:

1. Turn on **Measure Implemented?** for each measure in place.

   The lowest maturity level usually describes the situation where nothing is in place. It excludes the others:
   while one of its measures is on, the measures of the other levels cannot be changed, and while a measure
   of a higher level is on, the lowest level cannot be changed. Its justification is optional.

2. Write a **Justification** for each measure you have turned on.

   When the framework makes the justification mandatory, the field of a measure turned on without one is outlined
   in red, with the placeholder **Justification required**. Do not write a justification for a measure that is off:
   the objective would stay partially filled.

3. Describe in **Planned Measures** the measures you have in place and plan to take, with a schedule of their stages.

   When the framework makes it mandatory, this field is required unless every measure above the lowest level is on.
   While it is required and empty, it is outlined in red.

Follow your progress
~~~~~~~~~~~~~~~~~~~~

The buttons of the objective selector change as you answer. Click **Icon Guide** to see their meaning
and, below it, the number and name of each maturity level of the framework.

.. figure:: /_static/images/security-objectives/fill-in-a-declaration-03.png
   :alt: Legend of the objective selector and of the maturity levels
   :target: ../_static/images/security-objectives/fill-in-a-declaration-03.png

.. list-table::
   :header-rows: 1
   :widths: 25 25 50

   * - Button
     - Legend
     - Meaning
   * - Grey outlined circle
     - Not filled
     - No measure of the objective has been answered yet.
   * - Orange triangle
     - Partially filled
     - The objective is started but not complete: a justification or the planned measures are missing,
       or a justification was written for a measure that is off.
   * - Green circle
     - Fully filled
     - Everything the framework requires for the objective is filled in. On a submitted declaration, the legend reads
       **Review passed**: the regulator accepted the objective.
   * - Red square
     - Review required
     - The regulator asked for changes to the objective (see `Update a declaration`_).

The **score** of an objective adds up, for each maturity level above the lowest, the share of that level's measures
that are turned on: a level counts 1 when all its measures are on, 0.5 when one of its two measures is on, and so on.
The number after the slash is the highest maturity level of the framework. Depending on the framework,
the score is shown with this maximum, on its own, or not at all.

The **Progress** column of the :doc:`dashboard` shows the share of the objectives that are fully filled.

.. note::

   The score is for your information: it does not decide whether you can submit the declaration.

Submit the declaration
~~~~~~~~~~~~~~~~~~~~~~

The **Submit** button becomes available once every objective is fully filled, and none is still marked for revision
(red square). Click it to send the declaration to the regulator. You can also submit a complete declaration from the
**Progress** column of the :doc:`dashboard`.

Once submitted, the declaration is listed with the status **Under review** and its submission date, with the message
**The security objectives declaration has been submitted.** If the regulator has set one up, a confirmation email is sent.

.. warning::

   A submitted declaration can no longer be changed or deleted: its fields are read-only.
   To change it, create a new version with **Update** (see `Update a declaration`_).

The review result
~~~~~~~~~~~~~~~~~

When the regulator has sent the result of the review, the status of the declaration on the dashboard becomes
**Passed** or **Revision required**. To see the result in detail, click the **Review** icon (pencil) of the declaration,
then **Review** in the pop-up: the declaration opens read-only.

.. figure:: /_static/images/security-objectives/fill-in-a-declaration-04.png
   :alt: Reviewed declaration with the review comment icon, the result of the objective, and the objectives needing revision in red
   :target: ../_static/images/security-objectives/fill-in-a-declaration-04.png

- The review result of the objective displayed, **Passed** or **Revision required**, appears beside **Close**.
- In the objective selector, the objectives accepted are green, and those needing revision are red squares.
- The **Review comment** icon, now marked with a blue dot, opens the regulator's comment on the declaration.
  The regulator can also comment on single measures, in the **Review comment** column.

.. _update-a-declaration:

Update a declaration
~~~~~~~~~~~~~~~~~~~~

To answer a **Revision required**, click the **Review** icon (pencil) of the declaration on the dashboard,
then **Update** in the **Update or review security objectives statement** pop-up.

.. figure:: /_static/images/security-objectives/fill-in-a-declaration-05.png
   :alt: Update or review security objectives statement pop-up
   :target: ../_static/images/security-objectives/fill-in-a-declaration-05.png

**Update** creates a new, unsubmitted version of the declaration, which opens straight away. It keeps your answers,
your planned measures and the regulator's comments, and the objectives needing revision are still shown as red squares.
Change the answers of those objectives: as soon as you change an answer or the planned measures of an objective,
it is no longer marked for revision. Then submit the new version, which the regulator reviews again.
The earlier versions remain unchanged, and are listed under **Version control** in the **More options** menu of the dashboard.

.. note::

   **Update** is offered on every submitted declaration, not only after a **Revision required**,
   so you can also send new information to the regulator.

Compare with the previous version
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

In a declaration that has an earlier version, each measure whose switch, justification or review comment differs from
that version is outlined in orange, with a **View previous version** button. So are the **Planned Measures** when they differ.
Click the button to see the earlier answer in the **Previous version** pop-up.

.. figure:: /_static/images/security-objectives/fill-in-a-declaration-06.png
   :alt: Previous version pop-up with the earlier answer to a security measure
   :target: ../_static/images/security-objectives/fill-in-a-declaration-06.png
