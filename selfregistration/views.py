from django.contrib.auth.decorators import login_required
from django.http import Http404, HttpRequest, HttpResponseRedirect
from django.shortcuts import redirect

from governanceplatform.helpers import user_in_group
from governanceplatform.models import User


@login_required
def index(request: HttpRequest) -> HttpResponseRedirect:
    user = request.user
    if not isinstance(user, User) or not user_in_group(user, "RegulatorAdmin") or "selfregistration" not in user.get_module_permissions():
        raise Http404
    return redirect("admin:app_list", app_label="selfregistration")
