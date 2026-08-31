Incident Notification
~~~~~~~~~~~~~~~~~~~~~~~

Use this section to create your incident notification workflow.

Emails
^^^^^^^^^^^^^^^^^^^^^

By clicking the **Emails** link in the **Incident Notification** section, you can view the email templates that have been set up in your **SERIMA** instance. These email templates are available on the **Select Email to Change** screen and are used during the incident notification workflow.

The email templates are shown as a list in a table with the columns Name, **Subject**, and **Content**.

.. figure:: ../_static/regulator_admin_images/Reg_Admin_23.png
   :alt: Select Email to Change
   :target: /_static/regulator_admin_images/Reg_Admin_23.png

Click the name of the template to see its content. The screenshot below shows an example of the **New Incident Notification** template. 

You can see the **Name**, the **Subject**, and the **Content** of the email:

.. figure:: ../_static/regulator_admin_images/Reg_Admin_24.png
   :alt: New Incident Notification
   :target: /_static/regulator_admin_images/Reg_Admin_24.png

Beneath the Content area, you can see the usable placeholders you can use to replace the relevant information in your template.

.. figure:: ../_static/regulator_admin_images/Reg_Admin_64.png
   :alt: New Incident Notification
   :target: /_static/regulator_admin_images/Reg_Admin_64.png

These placeholders are automatically populated and replace the relevant information whenever the email is sent. You can set up your template emails in four languages: English, French, Dutch, and German. 

   **English is the platform’s default language, so email templates are typically created in English and translated into other languages when needed.**

You can switch between these four languages on the platform using the **language selector dropdown** in the top-right corner of the application. The default language is English. 

   **If you switch to another language, but the email template has not been translated into that language, the platform will fall back to English and display the English version of the email.**

.. figure:: ../_static/regulator_admin_images/Reg_Admin_25.png
   :alt: language selector dropdown
   :target: /_static/regulator_admin_images/Reg_Admin_25.png

Impact
^^^^^^^^^^^^^^^^^^^^^

Click the **Impact** link to go to the **Select Impacts to change** screen. On this screen, you can check which impacts are defined in your system. On the Select Impacts to change screen, you can see the impacts list in a table format with the columns **Regulations, Sector, Sub-sector**, and **Title**.

.. figure:: ../_static/regulator_admin_images/Reg_Admin_26.png
   :alt: Select Impacts to change
   :target: /_static/regulator_admin_images/Reg_Admin_26.png

Depending on your needs (such as the regulations you are subject to or the sectors you operate in), you can set up different impacts. As shown in the screenshot above, you can configure impacts for the same regulation, sector, and sub-sector, with variations based on the number of users.

You can set up an impact named **DNS 1h** for a one-hour DNS service outage and add the following description (as can be seen in the screenshot below): *Moderate impact on DNS service for at least 1 hour (e.g., between 2 and 5 percent of domains unresolved or a decrease of 5 to 10 percent in DNS traffic or unavailability of 2 name servers)*.

.. figure:: ../_static/regulator_admin_images/Reg_Admin_63.png
   :alt: Change Impacts
   :target: /_static/regulator_admin_images/Reg_Admin_63.png

If you have many impacts, you can use the **Search** and **Filter** features to find specific ones. In the Filter section on the right side of the screen, you can narrow down your impacts by sector or legal basis.

   **How to export selected impacts?**

Select the impact or impacts you want to export by checking the box next to each relevant impact. If you want to select all impacts at once, use the first checkbox on the left of the Regulations column header.

Then, open the **Action** dropdown menu, choose **Export Selected Impact**, and click **Go**. The selected impacts will be exported to a CSV file.

.. figure:: ../_static/regulator_admin_images/Reg_Admin_27.png
   :alt: Export Selected Impact
   :target: /_static/regulator_admin_images/Reg_Admin_27.png
.

   **How to delete selected impacts?**

Select the impact or impacts you want to delete by checking the box next to each relevant impact. Then, open the **Action** dropdown menu, choose **Delete Selected Impact**, and click **Go**. The selected impacts will be deleted.

.. figure:: ../_static/regulator_admin_images/Reg_Admin_28.png
   :alt: Delete Selected Impact
   :target: /_static/regulator_admin_images/Reg_Admin_28.png


Incident notification workflow
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

The incident notification workflow is the most important part of the application. It allows you to set up the **environment** (entities, observers, operators, regulators, and more) and define the building blocks of a **workflow** (emails, impacts, reports, questions, and more) to create a mechanism for managing reported incidents and maintaining communication among all system stakeholders. This mechanism is the heart of the process and is called the **incident notification workflow**.

Based on the above, you can create a workflow only after the required components (essentially the entire system) have been set up, including regulators, operators, and email templates.

Click the **Incident notification workflows** link to go to the **Select Incident notification workflow to change** screen. On this screen, you can check what kind of incident notification workflows are defined in your system.

.. figure:: ../_static/regulator_admin_images/Reg_Admin_30.png
   :alt: Select Incident notification workflow to change
   :target: /_static/regulator_admin_images/Reg_Admin_30.png

Click the name of the workflow you want to open. The **Change Incident Notification Workflow** screen is complex and contains several sections.

At the top is the **General** section, which displays the workflow name. Below it is the **Supervision** section, showing the **Legal basis** (regulation) and the **Regulator** (in this case, ILR). The third section (**Sectors**) lists the sectors selected for this workflow.

.. figure:: ../_static/regulator_admin_images/Reg_Admin_31.png
   :alt: NIS Workflow
   :target: /_static/regulator_admin_images/Reg_Admin_31.png

When you set up a new workflow, you can select a different regulation (Legal basis) or regulator using the dropdown menus, provided these options have already been configured in your **SERIMA** instance.

The fourth section is **Notification Email**. This section contains the email templates you set up on the **Select Email to Change** screen (Incident Notification -> Emails). In a typical workflow, there are at least three email templates you should use: an opening email, a status update email, and a closing email.

.. figure:: ../_static/regulator_admin_images/Reg_Admin_32.png
   :alt: Notification Email
   :target: /_static/regulator_admin_images/Reg_Admin_32.png

When an operator reports an incident, they will receive an opening email confirming that the incident has been successfully reported. An example template for an **Opening email** can be seen below:

.. figure:: ../_static/regulator_admin_images/Reg_Admin_22.png
   :alt: Change Email screen
   :target: /_static/regulator_admin_images/Reg_Admin_22.png

When the status of the incident changes, the **Status update email** is sent out. When the incident is closed, the **Closing email** is used. When you set up a new workflow (or change an existing one), use the dropdown menus next to the email templates and choose a different email template –if needed:

.. figure:: ../_static/regulator_admin_images/Reg_Admin_33.png
   :alt: Available email templates
   :target: /_static/regulator_admin_images/Reg_Admin_33.png

Next to the dropdown menus, you can see the following icons:

.. figure:: ../_static/regulator_admin_images/Reg_Admin_65.png
   :alt: Notification email icons
   :target: /_static/regulator_admin_images/Reg_Admin_65.png

The fifth section is called **Incident Reports**. Here you can view the incident reports set up in the system. 

   **Please note that you must set up incident reports first (using Incident Notification -> Incident Reports) before selecting       the ones you want to use in the workflows.**

The screenshot below shows an example of a workflow: the NIS workflow uses two reports (the **Preliminary Incident Report** and the **Final Incident Report**).

.. figure:: ../_static/regulator_admin_images/Reg_Admin_34.png
   :alt: Preliminary Incident Report
   :target: /_static/regulator_admin_images/Reg_Admin_34.png

In the **Position** field, a smaller number indicates that the step occurs before a larger number. This feature is especially useful when you have multiple reports, as it allows you to define the order in which reports should be used.

The **Deadline in Hours** field specifies, in hours, the latest time by which the report should be sent after the Event Triggering Deadline. This is the timeframe within which the Operator User must fill out the preliminary notification.

The **Event Triggering Deadline** can have different values: None, Notification Date, Detection Date, or Previous Workflow. It defines the reference point from which the workflow element should be triggered. 

For example, as shown in the screenshot above, the **Preliminary Incident Report** should be activated no later than 24 hours after the **Detection Date**. As also shown in the screenshot above, once the **Preliminary Incident Report** has been created, the **Final Incident Report** must be completed no later than 360 hours afterward.

Incident reports
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Click the **Incident reports** link to go to the **Select Incident report to change** screen. On this screen, you can check what kind of incident reports are defined in your system. The reports are in a table format with the following columns: **Name, Label, Description, Impacts Disclosure Required, Submission Email**, and **Creator**.

.. figure:: ../_static/regulator_admin_images/Reg_Admin_29.png
   :alt: Select an incident report to change
   :target: /_static/regulator_admin_images/Reg_Admin_29.png

   **Reports are the building blocks of a workflow; they are the steps you create to assemble a process called a workflow.**

You can configure different workflows to best suit your needs. You can create new reports either by clicking the **Add** link in the Incident Notification section on the left, or by clicking the **Add Notification Report** button in the top-right corner.

**How to delete a selected incident report?**

Select the incident report or reports you want to delete by checking the box next to each relevant report. Then, open the **Action** dropdown menu, choose **Delete Selected Incident Reports**, and click **Go**. The selected reports will be deleted.

.. figure:: ../_static/regulator_admin_images/Reg_Admin_28.png
   :alt: Delete selected Incident reports
   :target: /_static/regulator_admin_images/Reg_Admin_28.png

**How to check the details of a report?**

Click the name of a report to view its details. You will then be directed to the **Change Incident Report** screen. At the top of this screen is the **General** section, which displays the name, label, and description of the report. The second section is the **Notification email**, where you can set which email template you want to use for the selected report. 

.. figure:: ../_static/regulator_admin_images/Reg_Admin_35.png
   :alt: Change Incident reports
   :target: /_static/regulator_admin_images/Reg_Admin_35.png

The third section is the **Questionnaire**, which displays all the questions you have set up for the report. In the first column of the table (**Question**), you can see the questions themselves. The second column (**Mandatory**) contains a checkbox; if selected, the question is marked as mandatory, meaning the person completing the questionnaire must answer it.

The **Position** column determines the order of the questions. When you hover your mouse over this field, up and down arrows appear, making it straightforward to change the position value.

The **Category Option** column can have different values, such as Regulation, General Notification Information, Nature of the Incident, and Handling of the Incident. You can select the appropriate category from the dropdown menu.

Next to the Category Option column, you will find the Edit, Add, Delete, and View icons, which allow you to modify the selected question directly if needed.

Finally, the **Delete** column includes a checkbox. If you select this checkbox and click Save at the bottom of the screen, the chosen question will be removed from the list.

The screenshot below shows the columns described above. Please note that this screenshot is only an example and is truncated; in practice, you will typically create many more than four questions in your reports.

.. figure:: ../_static/regulator_admin_images/Reg_Admin_36.png
   :alt: Questionnaire
   :target: /_static/regulator_admin_images/Reg_Admin_36.png

In front of each question title, you can see a number in square brackets. This number represents the reference of the selected question in the database. The next chapter explains the questions in more detail.

First, you need to create your questions under **Incident Notification -> Questions**. You can then select the questions you need to build the questionnaire for your report. 

In this example, the first question in the questionnaire is **Affected telecommunication services** with the reference number [**23**], but you can select a different question by using the dropdown menu.

.. figure:: ../_static/regulator_admin_images/Reg_Admin_37.png
   :alt: Affected telecommunication services
   :target: /_static/regulator_admin_images/Reg_Admin_37.png

Once you have made your changes, click the Save button at the bottom of the screen to save them.

Questions
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Click the **Questions** link to go to the **Select Question to change** screen. On this screen, you can check what kind of questions are defined in your system. The questions you create here can be used in **Incident Reports**. When creating reports, you can link these questions to build a questionnaire within the report.

The questions are in a table format with the following columns: **Reference, Label, Question Type, Predefined answers**, and **Creator**.

.. figure:: ../_static/regulator_admin_images/Reg_Admin_38.png
   :alt: Select Question to change
   :target: /_static/regulator_admin_images/Reg_Admin_38.png

Click either the **Reference** number or the **Label** of the question to view it. Once you click, you will be directed to the **Select Questions to change** screen. At the top, you can see the **Question Type**, the **Reference**, and the **Label**. 

If you click the **Question Type** dropdown menu, you will see several options, such as **Freetext, Multiple Choice**, and **Single Option Choice**.

.. figure:: ../_static/regulator_admin_images/Reg_Admin_39.png
   :alt: Select Question type
   :target: /_static/regulator_admin_images/Reg_Admin_39.png

Beneath that, you can find the **Predefined Answers** section. Here, you can also use the **Position** and the **Delete** options to manage the order of the answers or delete selected answers.

Reminder emails
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Click the **Reminder emails** link to go to the **Select Reminder email to change** screen. On this screen, you can check what kind of reminder emails are defined in your system. You can add reminder emails either by clicking the **Add** link in the **Incident Notification** section on the left, or by using the **Add reminder email** button in the top right-hand corner.

The emails are shown in a table with the following columns: **Regulation, Report, Email subject, Trigger event**, and **Delays in hours**.

.. figure:: ../_static/regulator_admin_images/Reg_Admin_40.png
   :alt: Select Reminder email to change
   :target: /_static/regulator_admin_images/Reg_Admin_40.png

You can link the selected reminder email to a specific report by choosing the appropriate option from the **Report** dropdown.

.. figure:: ../_static/regulator_admin_images/Reg_Admin_42.png
   :alt: Change Reminder email
   :target: /_static/regulator_admin_images/Reg_Admin_42.png

You can also use the **Email** dropdown to choose the appropriate email template and the **Trigger event** dropdown to choose the trigger event you want to use.
