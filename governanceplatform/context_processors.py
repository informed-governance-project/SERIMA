from django.utils.translation import get_language
from django.utils.translation import gettext_lazy as _

from governanceplatform import __version__

from .helpers import is_observer_user, is_user_regulator, user_in_group
from .models import ApplicationConfig, Functionality
from .settings import COOKIEBANNER, REGULATOR_CONTACT, SITE_NAME


def extra_content_for_all_templates(request):
    user = request.user
    extra_data = {
        "site_name": SITE_NAME,
        "is_staff": user.is_staff,
        "is_only_admin": False,
        "regulator_name": REGULATOR_CONTACT["name"],
    }
    extra_data["is_regulator"] = is_user_regulator(user)
    extra_data["is_observer"] = is_observer_user(user)

    if user_in_group(user, "PlatformAdmin"):
        extra_data["is_only_admin"] = True
        extra_data["template_header"] = "admin/base_site.html"
        extra_data["site_header"] = SITE_NAME + " " + _("Settings")
        extra_data["site_title"] = SITE_NAME

    return extra_data


def get_version(request):
    """
    Context proprocessor used to render the version of the sowftware
    in the HTML template.
    """
    return __version__


def instance_configurations(request):
    return {
        "regulator": REGULATOR_CONTACT,
        "cookiebanner": COOKIEBANNER,
    }


def user_modules(request):
    path = request.path
    user_modules = [
        {"type": "incidents", "name": _("Incident notification")},
    ]
    module_labels = {
        "/incidents": _("Incident notification"),
    }

    if request.user.is_authenticated:
        user_module_permissions = []
        # TODO: Uncomment next lines when merging with reporting branch
        # user = request.user

        # if is_user_regulator(user) or is_observer_user(user):
        #     user_module_permissions = user.get_module_permissions()
        # if is_user_operator(user):
        #     user_module_permissions = ["securityobjectives"]

        app_module_availables = Functionality.objects.filter(regulator__isnull=False).distinct().order_by("id")
        for module in app_module_availables:
            if module.type in user_module_permissions:
                module_name = None
                if hasattr(module, "safe_translation_getter"):
                    module_name = module.safe_translation_getter("name", language_code=get_language())
                else:
                    module_name = getattr(module, "name", None)

                user_modules.append({"type": module.type, "name": module_name})
                module_labels[f"/{module.type}"] = module_name

    name = next(
        (label for prefix, label in module_labels.items() if path.startswith(prefix)),
        _("Modules"),
    )

    return {
        "user_modules": user_modules,
        "current_module": name,
    }


def cookiebanner_version(request):
    try:
        cfg = ApplicationConfig.objects.get(key="cookiebanner")
        version = cfg.value
    except ApplicationConfig.DoesNotExist:
        version = 0
    return {"cookiebanner_version": version}
