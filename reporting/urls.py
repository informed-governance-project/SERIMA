from django.urls import path

from .views import (
    access_log,
    add_report_recommendations,
    bulk_update_company_project,
    cancel_report_generation,
    copy_report_project,
    copy_report_recommendations,
    create_report_project,
    dashboard_report_project,
    delete_report_project,
    delete_report_recommendation,
    download_report,
    download_template,
    edit_report_project,
    generate_report_project,
    import_risk_analysis,
    import_risk_analysis_status,
    report_generation_status,
    report_recommendations,
    reporting,
    review_comment_report,
    update_company_project,
    update_report_recommendation,
)

urlpatterns = [
    # Report generation
    path("", reporting, name="reporting"),
    # Report project
    path("project/create", create_report_project, name="create_report_project"),
    path(
        "project/<int:report_project_id>/copy",
        copy_report_project,
        name="copy_report_project",
    ),
    path(
        "project/<int:report_project_id>/edit",
        edit_report_project,
        name="edit_report_project",
    ),
    path(
        "project/<int:report_project_id>/delete",
        delete_report_project,
        name="delete_report_project",
    ),
    path(
        "project/<int:report_project_id>/dashboard",
        dashboard_report_project,
        name="dashboard_report_project",
    ),
    path(
        "company_project/<int:company_project_id>/update",
        update_company_project,
        name="update_company_project",
    ),
    path(
        "project/<int:report_project_id>/company_project/bulk_update",
        bulk_update_company_project,
        name="bulk_update_company_project",
    ),
    # Generate Reports
    path(
        "project/<int:report_project_id>/report/generate",
        generate_report_project,
        name="generate_report_project",
    ),
    # Download Reports
    path(
        "project/<int:report_project_id>/report/download/<uuid:file_uuid>",
        download_report,
        name="download_report",
    ),
    # Report generation status
    path(
        "project/<int:report_project_id>/report/status",
        report_generation_status,
        name="report_generation_status",
    ),
    # Cancel Report generation
    path(
        "project/<int:report_project_id>/report/cancel",
        cancel_report_generation,
        name="cancel_report_generation",
    ),
    path(
        "recommendations/<int:company_id>/<int:sector_id>/<int:year>/",
        report_recommendations,
        name="report_recommendations",
    ),
    path(
        "review_comment_report/<int:company_id>/<int:sector_id>/<int:year>/",
        review_comment_report,
        name="review_comment_report",
    ),
    path(
        "recommendations/add/<int:company_id>/<int:sector_id>/<int:year>/",
        add_report_recommendations,
        name="add_report_recommendations",
    ),
    path(
        "recommendations/delete/<int:company_id>/<int:sector_id>/<int:year>/<int:report_rec_id>",
        delete_report_recommendation,
        name="delete_report_recommendations",
    ),
    path(
        "recommendations/copy/<int:company_id>/<int:sector_id>/<int:year>/",
        copy_report_recommendations,
        name="copy_report_recommendations",
    ),
    path(
        "recommendations/update/<int:report_rec_id>",
        update_report_recommendation,
        name="update_report_recommendation",
    ),
    path(
        "access_log/<int:project_id>",
        access_log,
        name="reporting_access_log",
    ),
    # Import risk analysis
    path("import_risk_analysis", import_risk_analysis, name="import_risk_analysis"),
    path("import_risk_analysis_status/<str:group_id>", import_risk_analysis_status, name="import_risk_analysis_status"),
    # Current template download
    path(
        "admin/reporting/template/<int:pk>/download/",
        download_template,
        name="reporting_template_download",
    ),
]
