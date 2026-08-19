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
    copy_declaration,
    create_so_declaration,
    declaration,
    delete_declaration,
    download_declaration_pdf,
    get_security_objectives,
    import_so_declaration,
    review_comment_declaration,
    submit_declaration,
)

urlpatterns = [
    # Root
    path("", get_security_objectives, name="securityobjectives"),
    # Select SO standard
    path("create", create_so_declaration, name="create_so_declaration"),
    # SO declaration
    path("declaration", declaration, name="so_declaration"),
    # Copy SO declaration
    path(
        "copy/<int:group_id>",
        copy_declaration,
        name="copy_so_declaration",
    ),
    # Submit SO declaration
    path(
        "submit/<int:standard_answer_id>",
        submit_declaration,
        name="submit_so_declaration",
    ),
    # Delete SO declaration
    path(
        "delete/<int:standard_answer_id>",
        delete_declaration,
        name="delete_so_declaration",
    ),
    # Add review comment SO declaration
    path(
        "review_comment/<int:standard_answer_id>",
        review_comment_declaration,
        name="review_comment_so_declaration",
    ),
    # Download PDF SO declaration pdf
    path(
        "download/<int:standard_answer_id>",
        download_declaration_pdf,
        name="download_so_declaration_pdf",
    ),
    # Import SO declaction
    path("import", import_so_declaration, name="import_so_declaration"),
    # Logs SO declaction
    path(
        "access_log/<int:standard_answer_id>",
        access_log,
        name="so_access_log",
    ),
]
