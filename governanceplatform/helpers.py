import secrets
from collections import defaultdict
from typing import Any

import bleach
from bleach.css_sanitizer import CSSSanitizer
from django.conf import settings
from django.contrib import messages
from django.db import connection
from django.db.models import F, Max, Q, Value
from django.db.models.fields import TextField
from django.db.models.functions import Coalesce, Lower, NullIf
from django.http import HttpRequest
from django.template.loader import render_to_string
from django.utils import translation
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _
from markdown import markdown

from incidents.models import (
    Answer,
    Incident,
    PredefinedAnswer,
    Question,
    QuestionCategoryOptions,
    QuestionOptionsHistory,
    SectorRegulation,
    Workflow,
)

from .models import Company, User


def table_exists(table_name: str) -> bool:
    """Checks if a table exists."""
    all_tables = connection.introspection.table_names()
    return table_name in all_tables


def generate_token():
    """Generates a random token-safe text string."""
    return secrets.token_urlsafe(32)[:32]


def user_in_group(user, group_name) -> bool:
    """Check user group"""
    if not user.is_authenticated:
        return False
    return any(user_group.name == group_name for user_group in user.groups.all())


def instance_user_in_group(user_instance, group_name) -> bool:
    return any(user_group.name == group_name for user_group in user_instance.groups.all())


def is_user_regulator(user: User) -> bool:
    return user_in_group(user, "RegulatorAdmin") or user_in_group(user, "RegulatorUser")


def is_user_operator(user: User) -> bool:
    return user_in_group(user, "OperatorAdmin") or user_in_group(user, "OperatorUser")


def is_observer_user(user: User) -> bool:
    return user_in_group(user, "ObserverAdmin") or user_in_group(user, "ObserverUser")


def is_observer_user_viewing_all_incident(user: User) -> bool:
    if not is_observer_user(user):
        return False
    observer = user.observers.first()
    return observer is not None and observer.is_receiving_all_incident


def get_active_company_from_session(request) -> Company | None:
    company_in_use = request.session.get("company_in_use")
    return request.user.companies.filter(id=company_in_use).first() if company_in_use else None


def can_access_incident(user: User, incident: Incident, company_id=-1) -> bool:
    # if it's regulator incident
    if (
        is_user_regulator(user)
        and Incident.objects.filter(
            pk=incident.id,
            regulator=user.regulators.first(),
        ).exists()
    ):
        return True

    # RegulatorUser can access only incidents from accessible sectors.
    if (
        user_in_group(user, "RegulatorUser")
        and Incident.objects.filter(pk=incident.id, sector_regulation__regulator=user.regulators.first()).exists()
    ):
        return incident.affected_sectors.filter(id__in=user.get_sectors().all()).exists()

    # RegulatorAdmin can access only incidents from accessible regulators.
    if (
        user_in_group(user, "RegulatorAdmin")
        and Incident.objects.filter(pk=incident.id, sector_regulation__regulator=user.regulators.first()).exists()
    ):
        return True
    # OperatorAdmin/User can access only incidents related to selected company.
    if (
        is_user_operator(user)
        and user.companyuser_set.filter(company__id=company_id, approved=True).exists()
        and Incident.objects.filter(pk=incident.id, company__id=company_id).exists()
    ):
        return True
    # IncidentUser can access their reports.
    if user_in_group(user, "IncidentUser") and Incident.objects.filter(pk=incident.id, contact_user=user).exists():
        return True
    # ObserverUser access all incident if he is in a observer who can access all incident.
    if is_observer_user_viewing_all_incident(user):
        return True
    if is_observer_user(user):
        incident_lists = user.observers.first().get_incidents()
        if incident in incident_lists:
            return True

    return False


# check if the user is allowed to create an incident_workflow
def can_create_incident_report(user: User, incident: Incident, company_id=-1) -> bool:
    # if it's incident user
    if user_in_group(user, "IncidentUser") and Incident.objects.filter(pk=incident.id, contact_user=user).exists():
        return True

    # if it's the incident of the user he can create
    if company_id and incident.contact_user == user and user.companyuser_set.filter(company__id=company_id, approved=True).exists():
        return True

    # if it's regulator incident
    if (
        is_user_regulator(user)
        and Incident.objects.filter(
            pk=incident.id,
            regulator=user.regulators.first(),
        ).exists()
    ):
        return True

    # OperatorAdmin/User can create only incidents related to selected company.
    if (
        company_id
        and is_user_operator(user)
        and user.companyuser_set.filter(company__id=company_id, approved=True).exists()
        and Incident.objects.filter(pk=incident.id, company__id=company_id).exists()
    ):
        return True

    return False


# check if the user is allowed to edit an incident_workflow
# for regulators to add message
def can_edit_incident_report(user: User, incident: Incident, company_id=-1) -> bool:
    # if it's incident user
    if user_in_group(user, "IncidentUser") and Incident.objects.filter(pk=incident.id, contact_user=user).exists():
        return True

    # if it's the incident of the user he can create
    if company_id and incident.contact_user == user and user.companyuser_set.filter(company__id=company_id, approved=True).exists():
        return True

    # if it's regulator incident
    if (
        is_user_regulator(user)
        and Incident.objects.filter(
            pk=incident.id,
            regulator=user.regulators.first(),
        ).exists()
    ):
        return True

    # OperatorAdmin/User can edit only incidents related to selected company.
    if (
        company_id
        and is_user_operator(user)
        and user.companyuser_set.filter(company__id=company_id, approved=True).exists()
        and Incident.objects.filter(pk=incident.id, company__id=company_id).exists()
    ):
        return True

    # if he is the regulator admin of the incident need to be link to his regulator
    if user_in_group(user, "RegulatorAdmin") and incident.sector_regulation.regulator == user.regulators.first():
        return True
    # if he is the regulator user of the incident, he need to have the sectors
    if user_in_group(user, "RegulatorUser") and incident.sector_regulation.regulator == user.regulators.first():
        return incident.affected_sectors.filter(id__in=user.get_sectors().all()).exists()

    return False


def set_creator(request: HttpRequest, obj: Any, change: bool) -> Any:
    regulator = request.user.regulators.first()
    if regulator is None:
        return obj
    if not change:
        obj.creator_name = regulator
        obj.creator_id = regulator.id

    if not obj.creator_name or not obj.creator_id:
        obj.creator_name = str(regulator)
        obj.creator_id = regulator.id
    return obj


def can_change_or_delete_obj(request: HttpRequest, obj: Any, message="") -> bool:
    # Cache per (type, pk) so multiple objects in one request are each evaluated once.
    cache = getattr(request, "_can_change_or_delete_obj", {})
    cache_key = (type(obj).__name__, getattr(obj, "pk", None))
    if cache_key in cache:
        return cache[cache_key]
    request._can_change_or_delete_obj = cache

    if not obj.pk:
        cache[cache_key] = True
        return True

    creator = getattr(obj, "creator", getattr(obj, "regulator", None))

    if not creator:
        cache[cache_key] = True
        return True

    in_use = True
    # [Predefined Answer] Check if obj is already in use
    if isinstance(obj, PredefinedAnswer):
        in_use = Answer.objects.filter(predefined_answers=obj).exists()

    # [Question Category] Check if obj is already in use
    if isinstance(obj, QuestionCategoryOptions):
        in_use = (
            Answer.objects.filter(question_options__category_option=obj).exists()
            or QuestionOptionsHistory.objects.filter(category_option=obj).exists()
        )

    # [Question] Check if obj is already in use
    if isinstance(obj, Question):
        in_use = (
            Answer.objects.filter(question_options__question=obj).exists() or QuestionOptionsHistory.objects.filter(question=obj).exists()
        )

    # [Workflow] in_use flag is set to False
    if isinstance(obj, Workflow):
        in_use = False

    # [Sector Regulation] Check if obj is already in use
    if isinstance(obj, SectorRegulation):
        in_use = Incident.objects.filter(sector_regulation=obj).exists()

    regulator = request.user.regulators.first()
    if creator == regulator and not in_use:
        cache[cache_key] = True
        return True

    if not message:
        message = _(
            "<strong>Modification and deletion actions are not allowed.</strong><br>"
            "- This {object_name} is either in use.<br>"
            "- You are not its creator ({creator_name})"
        )

    object_name = obj._meta.verbose_name.lower()
    creator_name = creator

    messages.warning(
        request,
        format_html(
            message,
            object_name=object_name,
            creator_name=creator_name,
        ),
    )
    cache[cache_key] = False
    return False


# Remove languages are not translated
def filter_languages_not_translated(form):
    tabs = form.context_data.get("language_tabs")
    if not tabs:
        return form

    tabs.allow_deletion = False
    tabs[:] = [lang for lang in tabs if lang[3] != "empty"]
    return form


def get_sectors_grouped(sectors):
    sectors = sectors.prefetch_related("children")
    categs = defaultdict(list)
    for sector in sectors:
        sector_name = sector.get_safe_translation()

        if sector.parent:
            parent_name = sector.parent.get_safe_translation()
            categs[parent_name].append([sector.id, sector_name])

        if not sector.children.exists() and not sector.parent:
            categs[sector_name].append([sector.id, sector_name])

    sectors_grouped = ((sector, sorted(options, key=lambda item: item[1])) for sector, options in categs.items())

    return sorted(sectors_grouped, key=lambda item: item[0])


# From a queryset with translated fields, build a queryset that selects:
#  1. the value in the requested language,
#  2. falling back to the default language if the translation is missing.
#
# If orderable = True, the function also creates normalized sort fields for
# each entry in translated_fields. For example, with translated_fields = ["label", "tooltip"],
# it will generate _label_sort and _tooltip_sort.
#
# These *_sort fields are case-insensitive (they ignore uppercase/lowercase when sorting).
# If it is important to sort with case sensitivity, set orderable = False
# and order directly by the translated field, e.g. .order_by("_label").
def translated_queryset(qs, language, default_language, translated_fields=None, orderable=False):
    default_lang = default_language
    lang = language
    annotations = {}
    if translated_fields is None:
        translated_fields = []

    for f in translated_fields:
        # Annotate value with the requested lang and default one
        annotations[f"_{f}_lang"] = Max(f"translations__{f}", filter=Q(translations__language_code=lang))
        annotations[f"_{f}_default"] = Max(f"translations__{f}", filter=Q(translations__language_code=default_lang))

    qs = qs.annotate(**annotations)

    # Apply Coalesce for fallback (_field = _field_lang or _field_default or "")
    final_annotations = {}
    for f in translated_fields:
        final_annotations[f"_{f}"] = Coalesce(
            f"_{f}_lang",
            f"_{f}_default",
            Value(""),
            output_field=TextField(),
        )
    qs = qs.annotate(**final_annotations)

    if orderable:
        sort_annotations = {}

        for f in translated_fields:
            sort_annotations[f"_{f}_sort"] = Lower(F(f"_{f}"))
        qs = qs.annotate(**sort_annotations)

    return qs


def annotate_translated_field_from_related_models(
    qs,
    *,
    full_path,
    annotated_name,
):
    default_lang = settings.PARLER_DEFAULT_LANGUAGE_CODE
    lang = translation.get_language()
    relation_path, translated_field = full_path.rsplit("__translations__", 1)

    lang_key = f"_{translated_field}_lang"
    default_key = f"_{translated_field}_default"

    return qs.annotate(
        **{
            lang_key: Max(
                f"{relation_path}__translations__{translated_field}",
                filter=Q(**{f"{relation_path}__translations__language_code": lang}),
            ),
            default_key: Max(
                f"{relation_path}__translations__{translated_field}",
                filter=Q(**{f"{relation_path}__translations__language_code": default_lang}),
            ),
        }
    ).annotate(
        **{
            annotated_name: Coalesce(
                NullIf(lang_key, Value("")),
                NullIf(default_key, Value("")),
                output_field=TextField(),
            )
        }
    )


def generate_display_methods(translated_fields, related_fields=None):
    """
    Dynamically generates display methods for translated fields.
    Example: for “label” → creates label_display() with
    - admin_order_field = “_label”
    - short_description = “Label”
    _label is for exemple generated with CustomTranslatableAdmin
    """
    methods = {}

    for field in translated_fields:

        def make_method(f):
            def _method(self, obj):
                return getattr(obj, f"_{f}")

            _method.admin_order_field = f"_{f}"
            _method.short_description = _(f.replace("_", " ").capitalize())
            return _method

        methods[f"{field}_display"] = make_method(field)

    if related_fields:
        for related_attr, translated_field in related_fields:

            def make_related_method(rel_attr, trans_field):
                def _method(self, obj):
                    related_obj = getattr(obj, rel_attr, None)
                    if not related_obj:
                        return "-"
                    # safe_translation_getter for Parler
                    return getattr(
                        related_obj,
                        "safe_translation_getter",
                        lambda f, any_language=True: "-",
                    )(trans_field, any_language=True)

                _method.short_description = _(rel_attr.replace("_", " ").capitalize())
                _method.admin_order_field = f"{rel_attr}__translations__{trans_field}"
                return _method

            methods[f"{related_attr}_display"] = make_related_method(related_attr, translated_field)

    return methods


def render_to_string_multi_languages(
    template_name,
    context,
    replace_email_variables=None,
    content=None,
    object=None,
):
    """
    Render a template in multiple languages.
    - 'content' and 'object' are ONLY used to replace variables
        in the content context in send_email() function.
    replace_email_variables is a function to be given depending of the module sending email,
    object is an object (incident, standard_answer) to be given depending of the module,
    """
    parts = []

    with translation.override(settings.LANGUAGE_CODE):
        if content and object and replace_email_variables:
            context["content"] = replace_email_variables(
                content.safe_translation_getter("content", language_code=settings.LANGUAGE_CODE),
                object,
            )
        baseline = render_to_string(template_name, context)

    for lang_code, lang_name in settings.LANGUAGES:
        with translation.override(lang_code):
            if content and object and replace_email_variables:
                context["content"] = replace_email_variables(
                    content.safe_translation_getter("content", language_code=lang_code),
                    object,
                )
                context["content"] = markdown(text=context["content"], output_format="html")
                context["content"] = sanitize_html(context["content"])
            rendered = render_to_string(template_name, context)

            if rendered == baseline and lang_code != settings.LANGUAGE_CODE:
                continue

            parts.append(
                f"""
                <h3>{translation.gettext(lang_name)} ({lang_code})</h3>
                {rendered}
                """.strip()
            )
    if not parts:
        return baseline
    return "<hr>".join(parts)


def sanitize_html(html, tags=None, attributes=None, styles=None):
    """
    Docstring for sanitize_html with bleach
    :param html: The HTML to sanitize
    :param tags: allowed tags in a set []
    :param attributes: allowed attributes in a dict {"key":["attribute1", "attribute2"]}
    :param styles: allowed styles in a set []
    """
    if tags is None:
        tags = [
            "p",
            "pre",
            "code",
            "h1",
            "h2",
            "h3",
            "h4",
            "h5",
            "h6",
            "hr",
            "table",
            "thead",
            "strong",
            "em",
            "del",
            "tr",
            "th",
            "td",
            "ul",
            "ol",
            "li",
            "br",
            "a",
            "abbr",
            "img",
        ]
    if attributes is None:
        attributes = {
            "a": ["href", "title"],
            "abbr": ["title"],
            "*": ["class", "style"],
            "img": ["alt", "src", "width"],
        }
    if styles is None:
        styles = ["color", "font-weight", "font-style", "text-decoration"]
    css_sanitizer = CSSSanitizer(allowed_css_properties=styles)

    return bleach.clean(
        html,
        tags=tags,
        attributes=attributes,
        strip=True,
        css_sanitizer=css_sanitizer,
    )


def sort_queryset_by_field(
    qs,
    sort_field,
    sort_direction,
    default_sort_field,
    allowed_sort_fields,
):

    config_field = allowed_sort_fields.get(sort_field)
    if not config_field:
        return qs.order_by(f"-{default_sort_field}")

    field = config_field["field"]
    is_string = config_field["type"] == "string"

    if "__translations__" in field:
        annotated_name = f"sort_{field.replace('__', '_')}"
        qs = annotate_translated_field_from_related_models(
            qs,
            full_path=field,
            annotated_name=annotated_name,
        )
        field = annotated_name

    ordering = []

    if is_string:
        expr = Lower(field)
        ordering.append(expr.desc() if sort_direction == "desc" else expr.asc())
    else:
        ordering.append(f"-{field}" if sort_direction == "desc" else field)

    if field != default_sort_field:
        ordering.append(f"-{default_sort_field}")

    return qs.order_by(*ordering)
