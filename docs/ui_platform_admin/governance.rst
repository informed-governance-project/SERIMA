Governance
~~~~~~~~~~~~~~~~~~~~~~~

The next section in the left panel is called **Governance**. It includes several functionalities, which are briefly explained in this chapter.

Django Settings
^^^^^^^^^^^^^^^^^^^^^

You can use the **Django Settings** to check the configuration of your **SERIMA** server instance. The variables you can see here are read-only.

.. figure:: ../_static/platform_admin_images/PLAT_ADM_04.png
   :alt: Django Settings
   :target: ../_static/platform_admin_images/PLAT_ADM_04.png

Entity categories
^^^^^^^^^^^^^^^^^^^^^

The Platform Admin creates the categories for the Operators. Entity categories are used for the classification of operators (depending on the terminology used in different regulations, operators, companies, and entities may be used to refer to the same thing). 

Click the **Entity categories** link in the **Governance** section to go to the **Select entity category to change** screen. Here, you can see a list of categories (if any have been set up). You can create new categories by clicking the **Add Entity Category** button in the top right corner.

To delete a category, first select it by checking the box next to the category. Then, open the Action drop-down menu and choose the **Delete selected entity categories** option, and click **Go**.

.. figure:: ../_static/platform_admin_images/PLAT_ADM_05.png
   :alt: Select entity category to change
   :target: ../_static/platform_admin_images/PLAT_ADM_05.png

There are two columns on the **Change Entity category** screen. The **Code** column on the left displays the code you assigned to the entity when you set it up. The **Label** column indicates the type of classification you want to create for different entities in the **SERIMA** system. This is also defined when you create a new entity category or modify an existing one.

.. figure:: ../_static/platform_admin_images/PLAT_ADM_10.png
   :alt: Change entity category
   :target: ../_static/platform_admin_images/PLAT_ADM_10.png

Functionalities 
^^^^^^^^^^^^^^^^^^^^^

The **Functionalities** section shows which modules are enabled in the platform. As per the screenshot below, there are two modules set up in the system: **Reporting** and **Security Objective**.

You can create new Functionalities by clicking the **Add Functionality** button in the top right corner. To delete a Functionality, first select it by checking the box next to the functionality. Then, open the **Action** drop-down menu and choose the **Delete selected Functionalities** option, and click **Go**.

.. figure:: ../_static/platform_admin_images/PLAT_ADM_06.png
   :alt: Select Functionality to change
   :target: ../_static/platform_admin_images/PLAT_ADM_06.png

Observers 
^^^^^^^^^^^^^^^^^^^^^

An observer is a type of regulator with limited permissions. Observers cannot edit incidents on the platform; they have read-only access and can only view incidents. 

As a Platform Admin, you can create an Observer either by clicking the **Add Observer** button in the top-right corner or by selecting the **Add** link in the **Governance** section. The **Change Observer** screen appears, where you can set up a new Observer.

When creating a new Observer, provide its name, description, country, and address. Then configure its functionalities by selecting and adding them to the **Chosen Functionalities list**:

.. figure:: ../_static/platform_admin_images/PLAT_ADM_11.png
   :alt: Chosen Functionalities list
   :target: ../_static/platform_admin_images/PLAT_ADM_11.png

53










