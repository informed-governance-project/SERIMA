from __future__ import annotations

from datetime import timedelta
from typing import TYPE_CHECKING

from django import forms
from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.http import Http404
from django.shortcuts import get_object_or_404, render
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from django.views.decorators.cache import never_cache
from django.views.decorators.debug import sensitive_post_parameters, sensitive_variables
from django.views.decorators.http import require_GET, require_http_methods, require_POST
from django_otp.decorators import otp_required

from .models import APIKey

if TYPE_CHECKING:
    from typing import Any
    from uuid import UUID

    from django.http import HttpRequest, HttpResponse

    from .models import Company, User


class APIKeyForm(forms.Form):
    name = forms.CharField(max_length=100, label=_("Name"))
    expires_in_days = forms.IntegerField(min_value=1, max_value=365, initial=90, label=_("Expires in (days)"))
    password = forms.CharField(widget=forms.PasswordInput, label=_("Confirm your password"))

    def __init__(self, *args, user, company, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = user
        self.company = company

    def clean_password(self) -> str:
        password = self.cleaned_data["password"]
        if not self.user.check_password(password):
            raise forms.ValidationError(_("Incorrect password."))
        return password

    def clean(self) -> dict[str, Any]:
        if self.user.is_operator() and self.company is None:
            raise forms.ValidationError(_("Select one of your approved companies before creating a key."))
        return super().clean()


def key_company(request: HttpRequest) -> Company | None:
    """An operator key is bound to the company in use, and only while the user's membership in it is approved."""
    if not request.user.is_operator():
        return None
    membership = (
        request.user.companyuser_set.filter(company_id=request.session.get("company_in_use"), approved=True)
        .select_related("company")
        .first()
    )
    return membership.company if membership else None


def key_table_context(user: User) -> dict[str, Any]:
    api_keys = list(user.api_keys.select_related("company").order_by("-created_at"))
    return {"api_keys": api_keys, "show_company": any(key.company_id for key in api_keys)}


def check_key_management_access(request: HttpRequest) -> None:
    if not settings.API_ENABLED:
        raise Http404()
    if not request.user.get_api_modules():
        raise PermissionDenied()


@login_required
@otp_required
@never_cache
@require_GET
def manage_api_keys(request: HttpRequest) -> HttpResponse:
    check_key_management_access(request)
    return render(request, "account/api_keys.html", key_table_context(request.user))


@login_required
@otp_required
@never_cache
@sensitive_post_parameters("password")
@sensitive_variables("token")
@require_http_methods(["GET", "POST"])
def create_api_key(request: HttpRequest) -> HttpResponse:
    check_key_management_access(request)
    token = None
    company = key_company(request)
    form = APIKeyForm(request.POST if request.method == "POST" else None, user=request.user, company=company)
    if request.method == "POST" and form.is_valid():
        token = APIKey.issue(
            user=request.user,
            name=form.cleaned_data["name"],
            expires_at=timezone.now() + timedelta(days=form.cleaned_data["expires_in_days"]),
            company=company,
        )[1]
    return render(
        request,
        "modals/create_api_key.html",
        {"form": form, "token": token, "company": company, **key_table_context(request.user)},
    )


@login_required
@otp_required
@never_cache
@require_POST
def revoke_api_key(request: HttpRequest, key_id: UUID) -> HttpResponse:
    if not settings.API_ENABLED:
        raise Http404()
    key = get_object_or_404(APIKey, pk=key_id, user=request.user)
    APIKey.objects.filter(pk=key.pk, revoked_at__isnull=True).update(revoked_at=timezone.now())
    return render(request, "parts/api_keys_table.html", key_table_context(request.user))
