"""
URL configuration for SERIMA project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/4.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""

from django.urls import path

from .views import (
    access_log,
    create_workflow,
    delete_incident,
    download_incident_pdf,
    download_incident_report_pdf,
    edit_incident,
    edit_workflow,
    export_incidents,
    get_form_list,
    get_incidents,
    review_workflow,
)

urlpatterns = [
    # Root
    path("", get_incidents, name="incidents"),
    # incidents reported by the regulator
    path("regulator_incidents", get_incidents, name="regulator_incidents"),
    # incident declaration
    path("declaration", get_form_list, name="declaration"),
    path("create_workflow", create_workflow, name="create_workflow"),
    path("edit_workflow", edit_workflow, name="edit_workflow"),
    path("review_workflow", review_workflow, name="review_workflow"),
    path(
        "incident/<int:incident_id>",
        edit_incident,
        name="regulator_incident_edit",
    ),
    path(
        "access_log/<int:incident_id>",
        access_log,
        name="access_log",
    ),
    path(
        "download-pdf/<int:incident_id>",
        download_incident_pdf,
        name="download_incident_pdf",
    ),
    path(
        "download-incident-report-pdf/<int:incident_workflow_id>",
        download_incident_report_pdf,
        name="download_incident_report_pdf",
    ),
    path(
        "delete/<int:incident_id>",
        delete_incident,
        name="delete_incident",
    ),
    path(
        "export_incidents",
        export_incidents,
        name="export_incidents",
    ),
]
