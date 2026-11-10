from __future__ import annotations

from functools import cached_property
from typing import TYPE_CHECKING, Any

from django.conf import settings
from django.db.models import Prefetch
from django.http import Http404
from drf_spectacular.renderers import OpenApiYamlRenderer
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView
from rest_framework.generics import RetrieveAPIView
from rest_framework.pagination import PageNumberPagination
from rest_framework.renderers import JSONRenderer
from rest_framework.throttling import UserRateThrottle
from rest_framework.viewsets import ReadOnlyModelViewSet

from incidents.models import LogReportRead
from securityobjectives.models import LogStandardAnswer

from .authentication import APIKeyAuthentication
from .permissions import ReadOnlyAPIUser
from .querysets import declarations_for_user, incidents_for_user, projects_for_user
from .serializers import (
    CurrentUserSerializer,
    DeclarationDetailSerializer,
    DeclarationSerializer,
    IncidentDetailSerializer,
    IncidentSerializer,
    ProjectSerializer,
)

if TYPE_CHECKING:
    from django.db.models import Model, QuerySet
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


API_READ_ACTION = "API READ"


class ReadOnlyViewSet(APIAccessMixin, ReadOnlyModelViewSet):
    """Logs reads the way the web does: opening a record is logged, browsing a list is not."""

    pagination_class = APIPagination

    def get_object(self) -> Model:
        obj = super().get_object()
        self.log_read(obj)
        return obj

    def log_read(self, obj: Any) -> None:
        """Reporting logs no reads on the web, so its viewset keeps this no-op."""

    @cached_property
    def actor_entity_name(self) -> str | None:
        """The reader's own organisation, or None for operators, who read on behalf of the object's company."""
        user = self.request.user
        if user.is_regulator():
            regulator = user.regulators.first()
            return regulator.name if regulator else ""
        if user.is_observer():
            observer = user.observers.first()
            return observer.name if observer else ""
        return None

    @cached_property
    def actor_role(self) -> str:
        group = self.request.user.groups.first()
        return group.name if group else ""

    def log_fields(self, company_name: str) -> dict:
        user = self.request.user
        # bulk_create bypasses the log models' save(), which is where user_full_name is normally filled.
        return {
            "user": user,
            "user_full_name": user.get_full_name(),
            "role": self.actor_role,
            "entity_name": self.actor_entity_name if self.actor_entity_name is not None else company_name,
            "action": API_READ_ACTION,
        }


class IncidentViewSet(ReadOnlyViewSet):
    module = "incidents"
    lookup_field = "incident_id"
    lookup_url_kwarg = "reference"

    def get_serializer_class(self) -> type[IncidentSerializer]:
        return IncidentDetailSerializer if self.action == "retrieve" else IncidentSerializer

    def get_queryset(self) -> QuerySet[Incident]:
        if getattr(self, "swagger_fake_view", False):
            from incidents.models import Incident

            return Incident.objects.none()
        from incidents.models import Answer, IncidentWorkflow

        reports = (
            IncidentWorkflow.objects.select_related("report_timeline").prefetch_related("workflow__translations").order_by("timestamp")
        )
        if self.action == "retrieve":
            reports = reports.prefetch_related(
                "impacts__translations",
                Prefetch(
                    "answer_set",
                    queryset=Answer.objects.select_related(
                        "question_options__question", "question_options__category_option__question_category"
                    )
                    .prefetch_related(
                        "question_options__question__translations",
                        "question_options__category_option__question_category__translations",
                        "predefined_answers__translations",
                    )
                    .order_by("question_options__category_option__position", "question_options__position"),
                ),
            )
        return incidents_for_user(self.request.user).prefetch_related(Prefetch("incidentworkflow_set", queryset=reports))

    def log_read(self, incident: Incident) -> None:
        # The response holds every report's answers, so each report is logged like the web's READ of one report.
        fields = self.log_fields(incident.company_name)
        LogReportRead.objects.bulk_create(
            LogReportRead(**fields, incident=incident, incident_report=report) for report in incident.incidentworkflow_set.all()
        )


class DeclarationViewSet(ReadOnlyViewSet):
    module = "securityobjectives"
    lookup_field = "group__group_id"
    lookup_url_kwarg = "reference"

    def get_serializer_class(self) -> type[DeclarationSerializer]:
        # Lists carry only the dashboard columns; answers and justifications need a detail request.
        return DeclarationDetailSerializer if self.action == "retrieve" else DeclarationSerializer

    def get_queryset(self) -> QuerySet[StandardAnswer]:
        if getattr(self, "swagger_fake_view", False):
            from securityobjectives.models import StandardAnswer

            return StandardAnswer.objects.none()
        queryset = declarations_for_user(self.request.user).prefetch_related("standard__translations")
        if self.action == "retrieve":
            queryset = queryset.prefetch_related("securitymeasureanswers__security_measure__translations")
        return queryset

    def log_read(self, declaration: StandardAnswer) -> None:
        company = declaration.submitter_company
        company_name = company.name if company else declaration.creator_company_name or ""
        LogStandardAnswer.objects.create(**self.log_fields(company_name), standard_answer=declaration)


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
