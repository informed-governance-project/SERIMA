import logging
import os
import secrets
from collections import defaultdict
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, cast

import bleach
import redis
from bleach.css_sanitizer import CSSSanitizer
from celery import current_app
from django import forms
from django.conf import settings
from django.contrib import messages
from django.core.exceptions import ValidationError
from django.db import connection
from django.db.models import F, Max, Q, Value
from django.db.models.fields import TextField
from django.db.models.functions import Coalesce, Lower, NullIf
from django.http import HttpResponseRedirect
from django.shortcuts import redirect
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils import translation
from django.utils.html import format_html
from django.utils.http import url_has_allowed_host_and_scheme
from django.utils.translation import gettext_lazy as _
from markdown import markdown
from openpyxl.cell.cell import ILLEGAL_CHARACTERS_RE

from .globals import (
    CROCKFORD_ALPHABET,
    CROCKFORD_INPUT_TRANSLATION,
    DEFAULT_PER_PAGE,
    LIST_PREFERENCE_PAGES,
    PER_PAGE_CHOICES,
    REFERENCE_TOKEN_LENGTH,
    SESSION_ONLY_LIST_PARAMS,
)
from .models import UserPreference

if TYPE_CHECKING:
    from collections.abc import Callable

    from django.contrib.auth.models import AnonymousUser
    from django.db.models import QuerySet
    from django.http import HttpRequest
    from django.template.response import TemplateResponse
    from django.utils.functional import Promise
    from django_filters import FilterSet

    from .models import Company, Sector, User

logger = logging.getLogger(__name__)


def table_exists(table_name: str) -> bool:
    """Checks if a table exists."""
    all_tables = connection.introspection.table_names()
    return table_name in all_tables


def generate_token() -> str:
    """Generates a random token-safe text string."""
    return secrets.token_urlsafe(32)[:32]


# The role checks live on User. These wrappers exist only because callers pass
# request.user, which may be an AnonymousUser and so has no such methods.
def user_in_group(user: User | AnonymousUser, group_name: str) -> bool:
    """Check user group"""
    return user.is_authenticated and user.in_group(group_name)


def is_user_regulator(user: User | AnonymousUser) -> bool:
    return user.is_authenticated and user.is_regulator()


def is_user_operator(user: User | AnonymousUser) -> bool:
    return user.is_authenticated and user.is_operator()


def is_observer_user(user: User | AnonymousUser) -> bool:
    return user.is_authenticated and user.is_observer()


def get_active_company_from_session(request: HttpRequest) -> Company | None:
    company_in_use = request.session.get("company_in_use")
    return request.user.companies.filter(id=company_in_use).first() if company_in_use else None


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


def can_change_or_delete_obj(request: HttpRequest, obj: Any, message: str | Promise = "", ignore_in_use: bool = False) -> bool:
    """Whether the requesting regulator may still change or delete obj.

    ignore_in_use drops the "still referenced by answers" half of the rule and keeps
    the ownership half, for admins that expose fields which stay editable for the
    lifetime of the object.
    """
    # Cache per (type, pk, ignore_in_use) so multiple objects in one request are each
    # evaluated once, without a lenient answer being reused for a strict question.
    cache = getattr(request, "_can_change_or_delete_obj", {})
    cache_key = (type(obj).__name__, getattr(obj, "pk", None), ignore_in_use)
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

    # Models that can tell whether they are still referenced answer for themselves;
    # anything else is treated as in use, which is the conservative answer.
    in_use = False if ignore_in_use else (obj.is_in_use() if hasattr(obj, "is_in_use") else True)

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
def filter_languages_not_translated(form: TemplateResponse) -> TemplateResponse:
    tabs = form.context_data.get("language_tabs")
    if not tabs:
        return form

    tabs.allow_deletion = False
    tabs[:] = [lang for lang in tabs if lang[3] != "empty"]
    return form


def get_sectors_grouped(sectors: QuerySet[Sector]) -> list[tuple[str, list[list[Any]]]]:
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
def translated_queryset(
    qs: QuerySet,
    language: str,
    default_language: str,
    translated_fields: list[str] | None = None,
    orderable: bool = False,
) -> QuerySet:
    default_lang = default_language
    lang = language

    if translated_fields is None:
        translated_fields = []

    annotations = {}

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
    qs: QuerySet,
    *,
    full_path: str,
    annotated_name: str,
) -> QuerySet:
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


def generate_display_methods(
    translated_fields: list[str],
    related_fields: list[tuple[str, str]] | None = None,
) -> dict[str, Callable[..., Any]]:
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
    template_name: str,
    context: dict[str, Any],
    replace_email_variables: Callable[[str, Any], str] | None = None,
    content: Any = None,
    object: Any = None,
) -> str:
    """
    Render a template in multiple languages.
    - 'content' and 'object' are ONLY used to replace variables
        in the content context in send_email() function.
    replace_email_variables is a function to be given depending of the module sending email,
    object is an object (incident, standard_answer) to be given depending of the module,
    """

    def render(lang_code: str) -> str:
        with translation.override(lang_code):
            if content and object and replace_email_variables:
                context["content"] = replace_email_variables(
                    content.safe_translation_getter("content", language_code=lang_code),
                    object,
                )
                context["content"] = markdown(text=context["content"], output_format="html")
                context["content"] = sanitize_html(context["content"])
            return render_to_string(template_name, context)

    default_lang = settings.PARLER_DEFAULT_LANGUAGE_CODE
    baseline = render(default_lang)

    parts = []
    for lang_code, lang_name in settings.LANGUAGES:
        if lang_code == default_lang:
            rendered = baseline
        else:
            rendered = render(lang_code)
            if rendered == baseline:
                continue

        with translation.override(lang_code):
            parts.append(
                f"""
                <h3>{translation.gettext(lang_name)} ({lang_code})</h3>
                {rendered}
                """.strip()
            )
    return "<hr>".join(parts)


def sanitize_html(
    html: str,
    tags: list[str] | None = None,
    attributes: dict[str, list[str]] | None = None,
    styles: list[str] | None = None,
) -> str:
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
    qs: QuerySet,
    sort_field: str,
    sort_direction: str,
    default_key: str,
    allowed_sort_fields: dict[str, dict[str, str]],
) -> QuerySet:
    default_sort_field = allowed_sort_fields[default_key]["field"]
    config_field = allowed_sort_fields.get(sort_field)
    if not config_field:
        return qs.order_by(f"-{default_sort_field}")

    field = config_field["field"]
    is_string = config_field["type"] == "string"
    is_boolean = config_field["type"] == "boolean"

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
    elif is_boolean:
        ordering.append(field if sort_direction == "desc" else f"-{field}")
    else:
        ordering.append(f"-{field}" if sort_direction == "desc" else field)

    if field != default_sort_field:
        ordering.append(f"-{default_sort_field}")

    return qs.order_by(*ordering)


def delete_file_and_parents(file_field, label: str) -> None:
    """
    Delete a FileField file from storage and clean up empty parent directories
    up to (but not including) the storage root.
    """
    if not file_field:
        return
    try:
        # Resolve the absolute path before deleting the file
        storage = file_field.storage
        abs_path = os.path.realpath(storage.path(file_field.name))

        # Delete the file itself
        file_field.delete(save=False)

        # Walk up and remove empty directories until we hit the storage root
        storage_root = os.path.abspath(storage.location)
        current_dir = os.path.dirname(abs_path)

        while True:
            current_dir = os.path.realpath(current_dir)

            # Guard 1: never climb above storage root
            if not current_dir.startswith(storage_root + os.sep):
                break

            # Guard 2: universal filesystem root backstop
            if current_dir == os.path.dirname(current_dir):
                break
            try:
                os.rmdir(current_dir)  # only removes if empty
                current_dir = os.path.dirname(current_dir)
            except OSError:
                # Directory not empty or already gone — stop climbing
                break

    except Exception:
        logger.exception("Failed to delete %s: %s", label, file_field.name)


def build_crockford_token(length: int = REFERENCE_TOKEN_LENGTH) -> str:
    return "".join(secrets.choice(CROCKFORD_ALPHABET) for _ in range(length))


def normalize_crockford(value: str) -> str:
    """Map the characters Crockford excludes onto the ones they are mistaken for."""
    return value.upper().translate(CROCKFORD_INPUT_TRANSLATION)


def normalize_reference(value: str, prefix: str) -> str:
    """Read the value the way Crockford intends, but leave the prefix alone: NI_ carries
    an I and SO_ an O, and normalising those would stop the reference matching."""
    upper = value.upper()
    if upper.startswith(prefix):
        return prefix + normalize_crockford(upper[len(prefix) :])
    return normalize_crockford(upper)


def safe_redirect_to_referer(request: HttpRequest, fallback: str) -> HttpResponseRedirect:
    """Send the user back where they came from, or to the `fallback` URL name.

    The Referer header is set by the client, so redirecting to it unchecked lets a crafted
    link bounce an authenticated user onto an attacker's site with our styling and session.
    """
    referer = request.headers.get("referer", "")
    if url_has_allowed_host_and_scheme(referer, allowed_hosts={request.get_host()}, require_https=request.is_secure()):
        return HttpResponseRedirect(referer)
    return HttpResponseRedirect(reverse(fallback))


def render_error_messages(request: HttpRequest) -> str:
    return render_to_string(
        "django_bootstrap5/messages.html",
        {"messages": messages.get_messages(request)},
        request=request,
    )


def is_queue_consumed(queue: str) -> bool:
    """Whether a running worker reads this queue; one serving only other queues is no help."""
    try:
        active_queues = current_app.control.inspect().active_queues()
    except Exception:
        return False
    return any(consumed["name"] == queue for consumed_queues in (active_queues or {}).values() for consumed in consumed_queues)


def is_redis_available() -> bool:
    try:
        r = redis.Redis.from_url(settings.CELERY_BROKER_URL)
        r.ping()
        return True
    except redis.exceptions.RedisError:
        return False


def celery_health_check(queue: str) -> bool:
    """Whether a task queued now on this queue would actually be picked up by a worker."""
    return is_queue_consumed(queue) and is_redis_available()


def strip_control_characters(value: str) -> str:
    """Remove the control characters that XML, and so openpyxl, refuses; tab, line feed and carriage return are kept.

    Text pasted from Word or PDFs carries them invisibly, e.g. a PDF hyphen arriving as STX (\\x02).
    """
    return ILLEGAL_CHARACTERS_RE.sub("", value)


SPREADSHEET_FORMULA_PREFIXES = ("=", "+", "-", "@", "\t", "\r", "\n")


def sanitize_spreadsheet_cell(value: object) -> object:
    """Prevent spreadsheet applications from interpreting exported text as a formula."""
    if not isinstance(value, str):
        return value
    # Text saved before the forms stripped control characters still holds them. Strip them first so they
    # cannot hide a formula prefix either.
    value = strip_control_characters(value)
    if value.startswith(SPREADSHEET_FORMULA_PREFIXES):
        return f"'{value}"
    return value


@dataclass
class ListPreferences:
    """A list page's state: its filters (stored ones plus the session's search and page), sort, columns and legend."""

    filters: dict[str, Any]
    # The stored sort over the page's default, so it always holds sort_field and sort_direction on a sortable page.
    sort: dict[str, str]
    per_page: int
    columns: dict[str, bool]
    legend: bool


def default_sort_key(page: str) -> str:
    """The sort key a sortable list page falls back to, as named in its module's ALLOWED_SORT_FIELDS."""
    return LIST_PREFERENCE_PAGES[page]["default_sort"][0]


def preference_key(page: str, aspect: str) -> str:
    return f"{page}.{aspect}"


def get_preferences(user: User, page: str) -> dict[str, Any]:
    """Return every aspect of a list page, stored or default, in a single query."""
    config = LIST_PREFERENCE_PAGES[page]
    keys = {preference_key(page, aspect): aspect for aspect in config["aspects"]}
    stored = {keys[key]: value for key, value in UserPreference.objects.filter(user=user, key__in=keys).values_list("key", "value")}

    hidden_columns = config.get("hidden_columns", ())
    columns = {column: column not in hidden_columns for column in config.get("columns", ())}
    # Merged over the defaults so a column added after the user saved their choice still appears.
    columns.update({column: visible for column, visible in stored.get("columns", {}).items() if column in columns})

    return {
        "filters": stored.get("filters", {}),
        "sort": stored.get("sort", {}),
        "columns": columns,
        "legend": stored.get("legend", False),
    }


def set_preference(user: User, page: str, aspect: str, value: Any) -> None:
    UserPreference.objects.update_or_create(user=user, key=preference_key(page, aspect), defaults={"value": value})


def delete_preference(user: User, page: str, aspect: str) -> None:
    UserPreference.objects.filter(user=user, key=preference_key(page, aspect)).delete()


def clean_client_preference(page: str, aspect: str, value: Any) -> bool | dict[str, bool]:
    """Validate a columns or legend value sent by the browser; raise ValidationError otherwise."""
    if aspect == "legend":
        if not isinstance(value, bool):
            raise ValidationError(_("Invalid legend state."))
        return value

    columns = LIST_PREFERENCE_PAGES[page].get("columns", ())
    if (
        not isinstance(value, dict)
        or not value
        or any(column not in columns or not isinstance(visible, bool) for column, visible in value.items())
    ):
        raise ValidationError(_("Invalid choice of columns."))
    return value


def list_session_key(page: str) -> str:
    return f"{page}_list_params"


def get_list_filters(request: HttpRequest, page: str) -> dict[str, Any]:
    """The filters a list page currently applies, for a view acting on that list without displaying it."""
    user = cast("User", request.user)
    return {**get_preferences(user, page)["filters"], **request.session.get(list_session_key(page), {})}


def update_list_params(
    request: HttpRequest,
    page: str,
    filterset_class: type[FilterSet],
    allowed_sort_fields: dict[str, dict[str, str]] | None = None,
) -> ListPreferences | HttpResponseRedirect:
    """Apply the request's filter and sort parameters to the page's stored ones, and return the page's state.

    A reset returns a redirect instead, so the reset parameter leaves the URL.
    """
    # Only reached from views behind login_required.
    user = cast("User", request.user)
    session_key = list_session_key(page)
    session_params = request.session.get(session_key, {}).copy()

    if "reset_sort" in request.GET:
        delete_preference(user, page, "sort")
        session_params.pop("page", None)
        request.session[session_key] = session_params
        return redirect(request.path)

    if "reset" in request.GET:
        delete_preference(user, page, "filters")
        request.session.pop(session_key, None)
        return redirect(request.path)

    if request.GET.get("search") == "":
        session_params.pop("search", None)
        session_params.pop("page", None)
        request.session[session_key] = session_params
        return redirect(request.path)

    preferences = get_preferences(user, page)
    filters = dict(preferences["filters"])
    previous_search = session_params.get("search")
    if any(key in filterset_class.base_filters and key not in SESSION_ONLY_LIST_PARAMS for key in request.GET):
        # A filter form submission carries the whole filter set, and a multi-select left empty sends
        # nothing at all, so the submitted filters replace the stored ones instead of merging into them.
        filters = {key: value for key, value in filters.items() if key == "per_page"}
    multi_value_filters = {
        name
        for name, list_filter in filterset_class.base_filters.items()
        if issubclass(list_filter.field_class, (forms.MultipleChoiceField, forms.ModelMultipleChoiceField))
    }

    for key, values in request.GET.lists():
        if key in SESSION_ONLY_LIST_PARAMS:
            session_params[key] = values[0]
        elif key == "per_page":
            if values[0].isdigit() and int(values[0]) in PER_PAGE_CHOICES:
                filters[key] = int(values[0])
        elif key in filterset_class.base_filters:
            selected = [value for value in values if value != ""]
            if not selected:
                filters.pop(key, None)
            else:
                filters[key] = selected if key in multi_value_filters else selected[0]

    sort = dict(preferences["sort"])
    if allowed_sort_fields is not None:
        if request.GET.get("sort_field") in allowed_sort_fields:
            sort["sort_field"] = request.GET["sort_field"]
        if request.GET.get("sort_direction") in ("asc", "desc"):
            sort["sort_direction"] = request.GET["sort_direction"]

    filters_changed = filters != preferences["filters"]
    sort_changed = sort != preferences["sort"]
    if filters_changed:
        set_preference(user, page, "filters", filters)
    if sort_changed:
        set_preference(user, page, "sort", sort)
    if filters_changed or sort_changed or session_params.get("search") != previous_search:
        # The previous page number belongs to the previous result set.
        session_params.pop("page", None)
    request.session[session_key] = session_params

    default_sort = LIST_PREFERENCE_PAGES[page].get("default_sort")
    return ListPreferences(
        filters={**filters, **session_params},
        sort={"sort_field": default_sort[0], "sort_direction": default_sort[1], **sort} if default_sort else sort,
        per_page=int(filters.get("per_page", DEFAULT_PER_PAGE)),
        columns=preferences["columns"],
        legend=preferences["legend"],
    )


def bind_applicable_filters[F: FilterSet](
    make_filterset: Callable[[dict[str, Any]], F], params: dict[str, Any]
) -> tuple[F, dict[str, Any]]:
    """Bind a list's filters, leaving out the values the page rejects, and return the filters actually applied.

    A stored value can be valid only elsewhere: a year declared by another company of the operator, a year of
    another report project. It stays stored for when it applies again, but is neither applied nor reported as
    an error here, so the list, the form and the (Active) label agree.
    """
    filterset = make_filterset(params)
    if not filterset.errors:
        return filterset, params
    applicable = {key: value for key, value in params.items() if key not in filterset.errors}
    return make_filterset(applicable), applicable
