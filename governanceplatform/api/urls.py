from __future__ import annotations

from django.urls import include, path
from rest_framework.routers import SimpleRouter

from .views import CurrentUserView, DeclarationViewSet, IncidentViewSet, OpenAPIView, ProjectViewSet, SwaggerView

app_name = "api"
router = SimpleRouter()
router.register("incidents", IncidentViewSet, basename="incident")
router.register("security-objectives", DeclarationViewSet, basename="declaration")
router.register("reporting/projects", ProjectViewSet, basename="project")
urlpatterns = [
    path("v1/me/", CurrentUserView.as_view(), name="me"),
    path("v1/", include(router.urls)),
    path("openapi.yaml", OpenAPIView.as_view(), name="schema"),
    path("docs/", SwaggerView.as_view(), name="swagger"),
]
