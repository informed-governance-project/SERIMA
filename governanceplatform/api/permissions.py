from __future__ import annotations

from typing import TYPE_CHECKING

from django.conf import settings
from django.utils import timezone
from rest_framework.permissions import BasePermission

from governanceplatform.globals import FUNCTIONALITY_ELIGIBLE_ROLES

if TYPE_CHECKING:
    from rest_framework.request import Request
    from rest_framework.views import APIView


class ReadOnlyAPIUser(BasePermission):
    message = "Your account cannot access this API resource."

    def has_permission(self, request: Request, view: APIView) -> bool:
        user = request.user
        if not user.is_authenticated:
            return False
        if not user.is_active or not user.email_verified or user.is_superuser or user.in_group("PlatformAdmin"):
            return False
        if not user.accepted_terms or user.accepted_terms_date is None:
            return False
        days = settings.TERMS_ACCEPTANCE_TIME_IN_DAYS
        if days and (timezone.now().date() - user.accepted_terms_date.date()).days > days:
            return False
        module = getattr(view, "module", None)
        if module in FUNCTIONALITY_ELIGIBLE_ROLES:
            return any(user.in_group(role) for role in FUNCTIONALITY_ELIGIBLE_ROLES[module]) and module in user.get_module_permissions()
        return True
