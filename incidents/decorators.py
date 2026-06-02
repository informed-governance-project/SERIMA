import functools

from django.contrib import messages
from django.contrib.auth import logout
from django.shortcuts import redirect
from django.utils.translation import gettext_lazy as _

from governanceplatform.helpers import (
    is_observer_user,
    is_user_operator,
    is_user_regulator,
    user_in_group,
)


def check_user_is_correct(view_func):
    """
    This decorator ensures that a logged in user
    has a entity (regulator, observer or company) linked.
    """

    @functools.wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        user = request.user
        if user_in_group(user, "PlatformAdmin") or user_in_group(user, "IncidentUser"):
            return view_func(request, *args, **kwargs)

        if is_user_regulator(user) and user.regulators.exists():
            return view_func(request, *args, **kwargs)

        if is_observer_user(user) and user.observers.exists():
            return view_func(request, *args, **kwargs)

        if is_user_operator(user) and user.companies.exists():
            return view_func(request, *args, **kwargs)

        messages.error(
            request,
            _("The user account has currently no associated entities. Please contact the administrator."),
        )

        logout(request)
        return redirect("login")

    return _wrapped_view


def regulator_role_required(view_func, redirect_url="/"):
    """
    This decorator ensures that a logged in user has a regulator role.
    """

    @functools.wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if is_user_regulator(request.user):
            return view_func(request, *args, **kwargs)

        messages.info(request, "User must be have a regulator role to access the page.")
        return redirect(redirect_url)

    return wrapper
