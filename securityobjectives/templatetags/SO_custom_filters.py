import json

from django import template
from django.conf import settings
from django.core.serializers.json import DjangoJSONEncoder
from django.utils.translation import gettext_lazy as _

from securityobjectives.globals import STANDARD_ANSWER_REVIEW_STATUS
from securityobjectives.models import StandardAnswer

register = template.Library()


# replace a field in the URL, used for filter + pagination
@register.simple_tag
def url_replace(request, field, value):
    d = request.GET.copy()
    d[field] = value
    return d.urlencode()


# get settings value
@register.simple_tag
def settings_value(name):
    return getattr(settings, name, "")


@register.simple_tag(takes_context=True)
def get_all_versions(context, standard):
    is_regulator = context.get("is_regulator", False)

    queryset = (
        StandardAnswer.objects.filter(submit_date__isnull=False, group=standard.group)
        .only("id", "submit_date", "status", "review_comment")
        .order_by("-last_update")
    )

    if is_regulator:
        queryset = queryset.exclude(status="UNDE")

    data = list(queryset.values("id", "submit_date", "status", "review_comment"))

    if not data:
        return None

    for item in data:
        item["status_class"] = status_class(context, item["status"])
        item["status_icon"] = status_icon(context, item["status"])
        item["status_tooltip"] = status_tooltip(context, item["status"])
        item["status_color"] = status_color(item["status"])

    return json.dumps(data, cls=DjangoJSONEncoder)


@register.simple_tag(takes_context=True)
def status_class(context, value):
    if value == "PASS":
        if context["is_regulator"]:
            return "border border-passed border-2"
        return "bg-passed"
    if value == "PASSM":
        return "bg-passed"
    if value == "FAIL":
        if context["is_regulator"]:
            return "border border-failed border-2"
        return "bg-failed "
    if value == "FAILM":
        return "bg-failed "
    if value == "DELIV":
        return "bg-under-review"
    return "bg-unsubmitted"


@register.simple_tag()
def status_color(value):
    if value == "PASS" or value == "PASSM":
        return "text-passed"
    if value == "FAIL" or value == "FAILM":
        return "text-failed "
    if value == "DELIV":
        return "text-under-review"
    return "text-unsubmitted"


@register.simple_tag(takes_context=True)
def status_icon(context, value):
    if value == "PASS":
        if context["is_regulator"]:
            return "custom-icon-passed"
        return "custom-icon-passed-white"
    if value == "PASSM":
        if context["is_regulator"]:
            return "custom-icon-passed-sent"
        return "custom-icon-passed-white"
    if value == "FAIL":
        if context["is_regulator"]:
            return "custom-icon-failed"
        return "custom-icon-failed-white"
    if value == "FAILM":
        if context["is_regulator"]:
            return "custom-icon-failed-sent"
        return "custom-icon-failed-white"
    if value == "DELIV":
        return "custom-icon-under-review-white"
    return "custom-icon-unsubmitted-white"


@register.simple_tag(takes_context=True)
def status_tooltip(context, value):
    STANDARD_ANSWER_REVIEW_STATUS_DICT = dict(STANDARD_ANSWER_REVIEW_STATUS)
    if value == "PASSM" and not context["is_regulator"]:
        value = "PASS"
    if value == "FAILM" and not context["is_regulator"]:
        value = "FAIL"
    return STANDARD_ANSWER_REVIEW_STATUS_DICT.get(value)


@register.filter
def split(value, delimiter=","):
    """Splits the string by delimiter."""
    return value.split(delimiter)


@register.simple_tag(takes_context=True)
def display_role(context, log):
    is_regulator = context.get("is_regulator", False)
    is_observer = context.get("is_observer", False)
    if is_regulator or is_observer:
        return log.role

    if "User" in log.role:
        return _("User")
    return _("Administrator")
