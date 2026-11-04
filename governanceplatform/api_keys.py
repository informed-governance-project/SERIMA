from __future__ import annotations

from datetime import timedelta
from typing import TYPE_CHECKING

from django import forms
from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from django.views.decorators.cache import never_cache
from django.views.decorators.debug import sensitive_post_parameters, sensitive_variables
from django.views.decorators.http import require_http_methods, require_POST
from django_otp.decorators import otp_required

from .models import APIKey

if TYPE_CHECKING:
    from uuid import UUID

    from django.http import HttpRequest, HttpResponse


class APIKeyForm(forms.Form):
    name = forms.CharField(max_length=100, label=_("Name"))
    expires_in_days = forms.IntegerField(min_value=1, max_value=365, initial=90, label=_("Expires in (days)"))
    password = forms.CharField(widget=forms.PasswordInput, label=_("Confirm your password"))

    def __init__(self, *args, user, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = user

    def clean_password(self) -> str:
        password = self.cleaned_data["password"]
        if not self.user.check_password(password):
            raise forms.ValidationError(_("Incorrect password."))
        return password


@login_required
@otp_required
@never_cache
@sensitive_post_parameters("password")
@sensitive_variables("token")
@require_http_methods(["GET", "POST"])
def manage_api_keys(request: HttpRequest) -> HttpResponse:
    if not settings.API_ENABLED:
        raise Http404()
    token = None
    form = APIKeyForm(request.POST if request.method == "POST" else None, user=request.user)
    if request.method == "POST" and form.is_valid():
        _, token = APIKey.issue(
            user=request.user,
            name=form.cleaned_data["name"],
            expires_at=timezone.now() + timedelta(days=form.cleaned_data["expires_in_days"]),
        )
        form = APIKeyForm(user=request.user)
    return render(
        request, "account/api_keys.html", {"form": form, "token": token, "api_keys": request.user.api_keys.order_by("-created_at")}
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
    messages.success(request, _("API key revoked."))
    return redirect("api_keys")
