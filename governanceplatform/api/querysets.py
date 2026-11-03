from __future__ import annotations

from typing import TYPE_CHECKING

from django.db.models import OuterRef, Q, Subquery

from incidents.access_control import get_observer_incidents
from incidents.models import Incident
from reporting.models import Project
from securityobjectives.helpers import get_scoped_standard_answers
from securityobjectives.models import StandardAnswer

if TYPE_CHECKING:
    from django.db.models import QuerySet

    from governanceplatform.models import User


def incidents_for_user(user: User) -> QuerySet[Incident]:
    queryset = Incident.objects.exclude(sector_regulation__isnull=True)
    if user.is_regulator():
        if not user.regulators.exists():
            return queryset.none()
        scope = Q(sector_regulation__regulator__in=user.regulators.all())
        if user.in_group("RegulatorUser"):
            scope &= Q(affected_sectors__in=user.get_sectors().all())
        queryset = queryset.filter(scope | Q(regulator=user.regulators.first()))
    elif user.is_observer():
        observer = user.observers.first()
        queryset = get_observer_incidents(observer) if observer else queryset.none()
    elif user.is_operator():
        queryset = queryset.filter(company__companyuser__user=user, company__companyuser__approved=True)
    elif user.in_group("IncidentUser"):
        queryset = queryset.filter(contact_user=user)
    else:
        queryset = queryset.none()
    return queryset.distinct().order_by("-incident_notification_date", "pk")


def declarations_for_user(user: User) -> QuerySet[StandardAnswer]:
    if user.is_regulator():
        queryset = get_scoped_standard_answers(user) if user.regulators.exists() else StandardAnswer.objects.none()
    elif user.is_operator():
        queryset = StandardAnswer.objects.filter(submitter_company__companyuser__user=user, submitter_company__companyuser__approved=True)
        latest = queryset.filter(group_id=OuterRef("group_id")).order_by("-last_update", "-pk").values("pk")[:1]
        queryset = queryset.filter(pk__in=Subquery(latest))
    else:
        queryset = StandardAnswer.objects.none()
    return queryset.select_related("standard", "group", "submitter_company").distinct().order_by("-last_update", "pk")


def projects_for_user(user: User) -> QuerySet[Project]:
    regulator = user.regulators.first()
    queryset = Project.objects.none()
    if regulator and user.in_group("RegulatorAdmin"):
        queryset = Project.objects.filter(author__regulators=regulator)
    elif regulator and user.in_group("RegulatorUser"):
        queryset = Project.objects.filter(author__regulators=regulator, sectors__in=user.get_sectors().all())
    return queryset.distinct().order_by("-updated_at", "pk")
