Back-end Reporting Configuration
---------------------------------

Each regulation requires a single configuration that is linked to the corresponding regulator.

  **As a Regulator Admin, you can set up the configuration of the reports in the administration interface (back-end) of the SERIMA platform.**

Log in as a Regulator Admin, go to the administration interface, and select Configurations in the Reporting section.

.. figure:: /_static/reporting_module_images/Rep_48.png
   :alt: Back-end Reporting Configuration
   :target: ../_static/reporting_module_images/Rep_48.png

In SERIMA, a Security Objective statement must be created for each operator.

 **Reporting is linked to Security Objectives and the Risk Analysis from MONARC. To generate a report document, you must first create the report   elements.**

Add configuration
~~~~~~~~~~~~~~~~~~~~~~~~~

You can create a new configuration either by clicking the **Add** link next to Configurations, or from the **Select Configuration to change** screen, selecting the **Add Configuration** button.

 **Configure reporting settings for each Security Standard. First, choose the standard you want to use. Next, upload a DOCX template to the platform, and finally add colors to the reporting configuration.**

When generating the report, you can also define the order of the colors used.

.. figure:: /_static/reporting_module_images/Rep_49.png
   :alt: Add Configuration
   :target: ../_static/reporting_module_images/Rep_49.png

**Standard**
^^^^^^^^^^^^^^^^^^^^^

From the **Standard** dropdown menu, select a standard. Once you have selected a standard, you can use the **Action icons** to the right of the dropdown menu to manage it:

.. figure:: /_static/reporting_module_images/Rep_50.png
   :alt: Action icons
   :target: ../_static/reporting_module_images/Rep_50.png

•	**Change the selected standard** 	– Click the pencil icon to choose a different standard.
•	**Add another standard** – Click the green plus (+) icon to add an additional standard.
•	**View the selected standard** 	– Click the eye icon to open the selected standard.

You will be redirected to the **View Standard** page for that standard.

**Templates docx**
^^^^^^^^^^^^^^^^^^^^^

Templates are DOCX files. The application supports four languages, allowing you to create templates in **English (EN), French (FR), Dutch (NL)**, and **German (DE)**.

 **A DOCX Template must be provided for each supported language.** See `Writing a DOCX template`_ for the placeholders a template can use.

In the **Templates (DOCX)** section, you can manage your DOCX templates. Select the language for your template, click **Choose File**, and upload your DOCX template.

You can add multiple templates to your configuration, for example by uploading templates in different languages.

.. figure:: /_static/reporting_module_images/Rep_51.png
   :alt: Templates docx
   :target: ../_static/reporting_module_images/Rep_51.png

**Colors**
^^^^^^^^^^^^^^^^^^^^^

Finally, you can configure the colors used in your report to represent different maturity levels.

Each maturity level has a **Color** field, in hexadecimal format, which defaults to white (``#FFFFFF``). Although this field is not used in the **Security Objectives** module, the **Reporting** module uses it, so set a distinct color for each level, for example ``#ed2939``, ``#ffc000``, ``#dde96d`` and ``#00b050``. On the **Select Maturity Level to change** screen, you can view the color and the label for the color used in the **Reporting** module.

Define a **color palette** used in chart series. The colors you define are used first, in their order. They are followed by the Plotly qualitative palettes **Set1** and **Set2**, which are used on their own when no color is defined, and fill in when a chart has more series than defined colors:

.. figure:: /_static/reporting_module_images/Rep_60.png
   :alt: color palette
   :target: ../_static/reporting_module_images/Rep_60.png

First, select the color position you want to edit. Then, use the color picker: drag the slider to adjust the color range and click within the palette to select your desired color.

.. figure:: /_static/reporting_module_images/Rep_58.png
   :alt: color palette
   :target: ../_static/reporting_module_images/Rep_58.png

Below the color picker, you can see the selected color and its hexadecimal color code. If you already know the hexadecimal code of the color you want to use, you can enter it directly into the field. A preview of the selected color is displayed next to the hexadecimal code.

.. figure:: /_static/reporting_module_images/Rep_52.png
   :alt: color picker
   :target: ../_static/reporting_module_images/Rep_52.png

These colors are important because they are used when creating and downloading a report; they define how information is displayed in the report.

Once everything is configured, click **Save**. The newly created configuration will then appear in the **Select Configuration to Change** screen.

.. figure:: /_static/reporting_module_images/Rep_53.png
   :alt: Select Configuration to Change
   :target: ../_static/reporting_module_images/Rep_53.png

How to download a template?
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Once you have set up and saved a report configuration, you can download the templates by clicking the appropriate **Download** link.

.. figure:: /_static/reporting_module_images/Rep_54.png
   :alt: Download a template
   :target: ../_static/reporting_module_images/Rep_54.png

How to delete a template?
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Once you have set up and saved a report configuration, you can delete a template by selecting the checkbox in the **Delete** column for the relevant **template**.

.. figure:: /_static/reporting_module_images/Rep_55.png
   :alt: Delete a template
   :target: ../_static/reporting_module_images/Rep_55.png

How to delete colors?
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Once you have set up and saved a report configuration, you can delete a color by selecting the checkbox in the **Delete** column for the relevant **color**.

.. figure:: /_static/reporting_module_images/Rep_56.png
   :alt: Delete a color
   :target: ../_static/reporting_module_images/Rep_56.png

To delete a Color, check the relevant checkbox and click **Save**

.. figure:: /_static/reporting_module_images/Rep_57.png
   :alt: Delete a color
   :target: ../_static/reporting_module_images/Rep_57.png

The message **"The configuration <configuration name> was changed successfully."** appears at the top of the **Select Configuration to Change** screen. If you open the same configuration again, the deleted color is no longer displayed.

These colors are important because they are used when creating and downloading a report; they define how information is displayed in the report. Since the yellow color has been deleted, only the green and red colors are displayed in the example below (the screenshot is an example from a printout report):

.. figure:: /_static/reporting_module_images/Rep_59.png
   :alt: printed report
   :target: ../_static/reporting_module_images/Rep_59.png

Writing a DOCX template
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

A DOCX template is a Word document containing placeholders, which are replaced with the operator's data when a report is generated. To start from a working example, download the sample template and the report generated from it:

- :download:`Sample DOCX template </_static/docx_test_template.docx>`
- :download:`Report generated from the sample template </_static/docx_test_template_rendered.docx>`

**Text placeholders**

These placeholders are replaced with text, and can be used anywhere in a paragraph:

- ``{{ operator_name }}``: the name of the operator
- ``{{ sector }}``: the sector of the operator
- ``{{ year }}``: the reference year of the report
- ``{{ publication_date }}``: the date the report is generated
- ``{{ threshold_for_high_risk }}``: the threshold above which a risk is considered high, as set in the report project
- ``{{ top_ranking }}``: the number of entries shown in the rankings, as set in the report project
- ``{{ report_observations }}``: the observations written for the operator

The recommendations selected for the operator are inserted as a bulleted list with ``{{p report_recommendations }}``. Note the ``p`` after the opening braces, and place this placeholder alone in its paragraph.

**Chart placeholders**

These placeholders are replaced with a chart image:

- ``{{ chart_security_objectives_by_level }}``
- ``{{ chart_evolution_security_objectives_by_domain }}``
- ``{{ chart_evolution_security_objectives_by_domain_with_sector_avg }}``
- ``{{ chart_evolution_security_objectives }}``
- ``{{ chart_average_risk_level }}``
- ``{{ chart_high_risk_rate }}``
- ``{{ chart_average_high_risk_level }}``
- ``{{ chart_evolution_highest_risks }}``

**Table placeholders**

These placeholders are replaced with a table. **Each one must be alone in its own paragraph, in the body of the document**: the whole paragraph is replaced by the table, and a placeholder sharing its paragraph with other text, or placed inside a table, a header or a footer, is left as it is.

- ``{{ table_of_evolution_security_objectives }}``
- ``{{ table_of_evolution_security_objectives_by_domain }}``
- ``{{ table_of_highest_security_objectives_in_the_sector }}``
- ``{{ table_of_lowest_security_objectives_in_the_sector }}``
- ``{{ table_of_evolution_of_the_weakest_security_objectives }}``
- ``{{ table_of_security_objectives_by_maturity_level }}``
- ``{{ maturity_level_legend }}``
- ``{{ table_of_evolution_of_the_highest_risks }}``
- ``{{ table_of_treatment_of_the_highest_risks }}``
- ``{{ table_of_risk_summary }}``
- ``{{ table_of_top_threats_by_occurrence }}``
- ``{{ table_of_top_vulnerabilities_by_occurrence }}``
- ``{{ table_of_recommendations }}``

Recommendations for observation
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Click the **Recommendations for Observation** link to go to the **Select Recommendation for Observation to change** screen. On this screen, you can check what kind of recommendations have been set up.

You can add new recommendations either by clicking the **Add** link in the **Reporting** section on the left, or by using the **Add recommendation for observation** button in the top right-hand corner.

.. figure:: /_static/regulator_admin_images/Reg_Admin_43.png
   :alt: Add recommendation for observation
   :target: ../_static/regulator_admin_images/Reg_Admin_43.png

The recommendations are displayed in a table with the following columns: **Recommendation, Description**, and **Sectors**. When opening an existing recommendation or creating a new one, these are the fields that must be populated.

On the **Change Recommendation for observation** screen, provide a **Recommendation name**, then an optional **Description**, and finally select one or more **Sectors** to which the recommendation applies.

.. figure:: /_static/regulator_admin_images/Reg_Admin_44.png
   :alt: Change Recommendation for observation
   :target: ../_static/regulator_admin_images/Reg_Admin_44.png

Once the fields are set, click **Save** to store your changes. If you want to create more than one recommendation at a time, click the **Save and add another** button at the bottom of the screen.

You can also **delete a recommendation** by clicking the **Delete** button at the bottom of the **Change Recommendation for observation** screen.
