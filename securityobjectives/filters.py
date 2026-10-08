import django_filters
from django.db.models import Q
from django.utils.translation import gettext_lazy as _

from governanceplatform.helpers import get_sectors_grouped, normalize_reference
from governanceplatform.models import Company, Sector, User
from incidents.forms import DropdownCheckboxSelectMultiple

from .globals import REFERENCE_PREFIX
from .models import StandardAnswer


def group_id_matches(value: str) -> Q:
    """Match the group id as typed and as Crockford reads it, so an id transcribed with
    O for 0 is still found."""
    lookup = Q(group__group_id__icontains=value)
    normalized = normalize_reference(value, REFERENCE_PREFIX)
    if normalized != value.upper():
        lookup |= Q(group__group_id__icontains=normalized)
    return lookup


class YearChoiceFilter(django_filters.ChoiceFilter):
    def filter(self, qs, value):
        if value:
            return qs.filter(year_of_submission=value)
        return qs


class StandardAnswerFilter(django_filters.FilterSet):
    year_of_submission = YearChoiceFilter()
    sectors = django_filters.MultipleChoiceFilter(widget=DropdownCheckboxSelectMultiple(), label=_("Sectors"))
    search = django_filters.CharFilter(method="filter_search", label=_("Search"))

    class Meta:
        model = StandardAnswer
        fields = [
            "standard",
            "status",
            "submitter_user",
            "submitter_company",
            "year_of_submission",
            "sectors",
        ]

    def __init__(self, *args, **kwargs):
        queryset = kwargs.get("queryset", StandardAnswer.objects.none())
        super().__init__(*args, **kwargs)
        submitter_user_ids = set(queryset.values_list("submitter_user", flat=True))

        submitter_companies_ids = set(queryset.values_list("submitter_company", flat=True))

        self.filters["submitter_user"].queryset = User.objects.filter(id__in=submitter_user_ids)

        self.filters["submitter_company"].queryset = Company.objects.filter(id__in=submitter_companies_ids)

        years = set(self.queryset.values_list("year_of_submission", flat=True))
        self.filters["year_of_submission"].extra["choices"] = [(year, year) for year in sorted(years)]
        grouped_choices = get_sectors_grouped(Sector.objects.all())
        self.filters["sectors"].field.choices = grouped_choices

    def filter_search(self, queryset, name, value):
        return queryset.filter(
            Q(standard__translations__label__icontains=value)
            | Q(standard__translations__description__icontains=value)
            | Q(creator_name__icontains=value)
            | Q(submitter_company__name__icontains=value)
            | Q(year_of_submission__icontains=value)
            | Q(sectors__translations__name__icontains=value)
            | group_id_matches(value)
        ).distinct()
