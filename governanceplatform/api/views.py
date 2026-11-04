from __future__ import annotations

from typing import TYPE_CHECKING

from django.conf import settings
from django.http import Http404
from drf_spectacular.renderers import OpenApiYamlRenderer
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView
from rest_framework.generics import RetrieveAPIView
from rest_framework.pagination import PageNumberPagination
from rest_framework.renderers import JSONRenderer
from rest_framework.throttling import UserRateThrottle
from rest_framework.viewsets import ReadOnlyModelViewSet

from .authentication import APIKeyAuthentication
from .permissions import ReadOnlyAPIUser
from .querysets import declarations_for_user, incidents_for_user, projects_for_user
from .serializers import CurrentUserSerializer, DeclarationSerializer, IncidentSerializer, ProjectSerializer

if TYPE_CHECKING:
    from django.db.models import QuerySet
    from django.http import HttpRequest, HttpResponse

    from governanceplatform.models import User
    from incidents.models import Incident
    from reporting.models import Project
    from securityobjectives.models import StandardAnswer


class APIEnabledMixin:
    def dispatch(self, request: HttpRequest, *args, **kwargs) -> HttpResponse:
        if not settings.API_ENABLED:
            raise Http404()
        response = super().dispatch(request, *args, **kwargs)
        response["Cache-Control"] = "no-store"
        return response


class APIPagination(PageNumberPagination):
    page_size = 50


class APIThrottle(UserRateThrottle):
    rate = "120/min"


class APIAccessMixin(APIEnabledMixin):
    authentication_classes = [APIKeyAuthentication]
    permission_classes = [ReadOnlyAPIUser]
    renderer_classes = [JSONRenderer]
    throttle_classes = [APIThrottle]
    http_method_names = ["get", "head", "options"]


class CurrentUserView(APIAccessMixin, RetrieveAPIView):
    serializer_class = CurrentUserSerializer

    def get_object(self) -> User:
        return self.request.user


class ReadOnlyViewSet(APIAccessMixin, ReadOnlyModelViewSet):
    pagination_class = APIPagination


class IncidentViewSet(ReadOnlyViewSet):
    serializer_class = IncidentSerializer
    lookup_field = "incident_id"
    lookup_url_kwarg = "reference"

    def get_queryset(self) -> QuerySet[Incident]:
        if getattr(self, "swagger_fake_view", False):
            from incidents.models import Incident

            return Incident.objects.none()
        return incidents_for_user(self.request.user)


class DeclarationViewSet(ReadOnlyViewSet):
    serializer_class = DeclarationSerializer
    module = "securityobjectives"
    lookup_field = "group__group_id"
    lookup_url_kwarg = "reference"

    def get_queryset(self) -> QuerySet[StandardAnswer]:
        if getattr(self, "swagger_fake_view", False):
            from securityobjectives.models import StandardAnswer

            return StandardAnswer.objects.none()
        return declarations_for_user(self.request.user).prefetch_related(
            "securitymeasureanswers__security_measure__translations", "standard__translations"
        )


class ProjectViewSet(ReadOnlyViewSet):
    serializer_class = ProjectSerializer
    module = "reporting"
    lookup_field = "api_id"
    lookup_url_kwarg = "reference"
    lookup_value_regex = "[0-9a-fA-F-]{36}"

    def get_queryset(self) -> QuerySet[Project]:
        if getattr(self, "swagger_fake_view", False):
            from reporting.models import Project

            return Project.objects.none()
        return projects_for_user(self.request.user).select_related("standard").prefetch_related("standard__translations")


class OpenAPIView(APIEnabledMixin, SpectacularAPIView):
    authentication_classes = []
    permission_classes = []
    throttle_classes = []
    renderer_classes = [OpenApiYamlRenderer]
    serve_public = True


class SwaggerView(APIEnabledMixin, SpectacularSwaggerView):
    authentication_classes = []
    permission_classes = []
    throttle_classes = []
    url_name = "api:schema"
