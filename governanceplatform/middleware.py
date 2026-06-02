from django.conf import settings
from django.contrib import messages
from django.contrib.auth import logout
from django.http import Http404, JsonResponse
from django.shortcuts import redirect
from django.urls import resolve, reverse
from django.utils.timezone import now
from django.utils.translation import gettext_lazy as _

from governanceplatform.helpers import (
    is_observer_user,
    is_user_operator,
    is_user_regulator,
    user_in_group,
)
from governanceplatform.models import Functionality
from governanceplatform.settings import TERMS_ACCEPTANCE_TIME_IN_DAYS
from governanceplatform.views import select_company


def is_user_verified(user):
    """Return True if the user has passed OTP verification.

    In DEBUG mode, verification is bypassed so developers without an OTP
    device can still access the application. In production, delegates to
    django-otp's is_verified() which is added to the user object by
    OTPMiddleware.
    """
    if settings.DEBUG:
        return True
    return user.is_verified()


class SessionExpiryMiddleware:
    """Middleware to check if the session has expired."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        user = request.user

        if not user.is_authenticated:
            if request.method == "POST" and "csrftoken" not in request.COOKIES:
                messages.warning(
                    request,
                    _("CSRF token expired. Please try again."),
                )
                return redirect("login")

            return self.get_response(request)

        session_expiry_time = request.session.get("_session_expiry")
        current_timestamp = now().timestamp()

        if session_expiry_time and current_timestamp > session_expiry_time:
            messages.warning(
                request,
                _("Session expired. Please log in again to continue."),
            )

            logout(request)
            request.session.flush()

            if request.headers.get("X-Requested-With") == "XMLHttpRequest":
                return JsonResponse(
                    {"error": "session_expired", "login_url": reverse("login")},
                    status=401,
                )

            return redirect("login")

        request.session["_session_expiry"] = current_timestamp + settings.SESSION_COOKIE_AGE
        request.session.modified = True

        if not request.session.get("company_in_use") and user.companies.exists():
            if user.companies.distinct().count() > 1:
                return select_company(request)

            request.session["company_in_use"] = user.companies.first().id

        return self.get_response(request)


class RestrictViewsMiddleware:
    """
    Middleware that blocks URLs depending the user group.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        user = request.user
        if user.is_authenticated:
            # Superusers are not allowed to access the platform
            if user.is_superuser:
                raise Http404()

            if settings.DEBUG:
                user.is_verified = lambda: True

            if (
                not is_user_verified(user)
                and not request.path == reverse("two_factor:profile")
                and not request.path == reverse("two_factor:setup")
                and not request.path == reverse("two_factor:qr")
                and not request.path == reverse("logout")
            ):
                return redirect("two_factor:profile")

            if user_in_group(user, "PlatformAdmin"):
                if request.path == reverse("index") or request.path.startswith("/incidents/"):
                    return redirect("admin:index")

            if user_in_group(user, "IncidentUser"):
                if (
                    request.path.startswith("/incidents/incident/")
                    or request.path == reverse("regulator_incidents")
                    or request.path == reverse("export_incidents")
                ):
                    raise Http404()

            if is_user_regulator(user) and not request.session.get("is_regulator_incidents", False):
                if (
                    request.path == reverse("declaration")
                    or request.path.startswith("/incidents/delete/")
                    or request.path == reverse("create_workflow")
                ):
                    raise Http404()

            if is_observer_user(user):
                if (
                    request.path == reverse("declaration")
                    or request.path == reverse("regulator_incidents")
                    or request.path.startswith("/incidents/delete/")
                    or request.path.startswith("/incidents/incident/")
                    or request.path == reverse("create_workflow")
                    or request.path == reverse("edit_workflow")
                ):
                    raise Http404()

            if is_user_operator(user):
                if (
                    request.path.startswith("/incidents/incident/")
                    or request.path == reverse("regulator_incidents")
                    or request.path == reverse("export_incidents")
                ):
                    raise Http404()

        return self.get_response(request)


# check if the terms have been accepted
class TermsAcceptanceMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Only check for authenticated users
        user = request.user
        if user.is_authenticated and is_user_verified(user):
            # let the user logout and read terms
            if request.path == reverse("logout") or request.path == reverse("terms"):
                return self.get_response(request)
            if not request.user.accepted_terms and not request.path == reverse("accept_terms"):
                return redirect("accept_terms")
            # we want also to check the last checked
            if TERMS_ACCEPTANCE_TIME_IN_DAYS != 0:
                if request.user.accepted_terms_date is None and not request.path == reverse("accept_terms"):
                    return redirect("accept_terms")
                if request.user.accepted_terms_date is not None and not request.path == reverse("accept_terms"):
                    dt = now().date() - request.user.accepted_terms_date.date()
                    if dt.days > TERMS_ACCEPTANCE_TIME_IN_DAYS:
                        return redirect("accept_terms")
        return self.get_response(request)


# check if the regulator has access to functionality
class CheckFunctionalityAccessMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        user = request.user
        if user.is_authenticated:
            functionalities_types = Functionality.objects.filter(regulator__isnull=False).values_list("type", flat=True)

            functionality_path = resolve(request.path).route.split("/")[0]
            if not Functionality.objects.filter(type=functionality_path).exists():
                return self.get_response(request)

            if functionality_path not in functionalities_types:
                raise Http404()

            # regulator case
            if request.user.regulators.first() is not None:
                regulator = request.user.regulators.first()
                regulator_functionalities = regulator.functionalities.values_list("type", flat=True)
                if functionality_path not in regulator_functionalities:
                    raise Http404()

        return self.get_response(request)


# Force login for sensitive views
class ForceReloginMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        user = request.user
        force_relogin_paths = [
            "/account/edit/",
            "/account/password_change/",
            "/account/two_factor/backup/tokens/",
            "/account/two_factor/disable/",
        ]

        if request.path in force_relogin_paths:
            relogin_flag = request.session.get("force_relogin_done")
            if relogin_flag:
                request.session.pop("force_relogin_done", None)
                return self.get_response(request)

            if user.is_authenticated and not relogin_flag:
                if request.method == "POST":
                    return self.get_response(request)

                no_backup_tokens = request.user.staticdevice_set.filter(token_set__isnull=True).exists()
                if no_backup_tokens:
                    return self.get_response(request)

                messages.warning(
                    request,
                    _("For security reasons, you will need to log in again to access it."),
                )
                logout(request)
                request.session["force_relogin_done"] = True

                return redirect(f"{reverse('login')}?next={request.path}")

        return self.get_response(request)
