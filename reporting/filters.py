import django_filters
from django.db.models import F, Q
from django.utils.translation import gettext_lazy as _

from governanceplatform.helpers import get_sectors_grouped
from governanceplatform.models import Regulation, Sector, User
from incidents.forms import DropdownCheckboxSelectMultiple
from securityobjectives.models import Standard

from .models import CompanyProject, ObservationRecommendation, Project


class RecommendationFilter(django_filters.FilterSet):
    code = django_filters.CharFilter(
        lookup_expr="icontains",
        label=_("Name"),
    )

    description = django_filters.CharFilter(
        lookup_expr="icontains",
        field_name="translations__description",
        label=_("Description"),
    )

    sectors = django_filters.ModelMultipleChoiceFilter(
        queryset=Sector.objects.filter(
            ~Q(id__in=Sector.objects.exclude(parent=None).values_list("parent_id", flat=True)) | Q(id=F("parent_id"))
        ).order_by("parent"),
        widget=DropdownCheckboxSelectMultiple(attrs={"data-selected-text-format": "count > 2"}),
        method="filter_by_sector",
        label=_("Sectors"),
    )

    class Meta:
        model = ObservationRecommendation
        fields = ["code", "description", "sectors"]

    def filter_by_sector(self, queryset, name, value):
        if not value:
            return queryset

        sector_ids = [sector.id for sector in value]

        return queryset.filter(Q(sectors__in=sector_ids) | Q(sectors=None)).distinct()


class ProjectFilter(django_filters.FilterSet):
    reference_year = django_filters.MultipleChoiceFilter(widget=DropdownCheckboxSelectMultiple())
    sectors = django_filters.MultipleChoiceFilter(widget=DropdownCheckboxSelectMultiple())
    search = django_filters.CharFilter(method="filter_search", label=_("Search"))

    class Meta:
        model = Project
        fields = [
            "reference_year",
            "sectors",
            "author",
            "standard__regulation",
            "standard",
        ]

    def __init__(self, *args, **kwargs):
        queryset = kwargs.get("queryset", Project.objects.none())
        super().__init__(*args, **kwargs)
        author_user_ids = queryset.values_list("author", flat=True).distinct()

        sectors = Sector.objects.filter(project__in=queryset).distinct()
        grouped_choices = get_sectors_grouped(sectors)
        reference_years = queryset.values_list("reference_year", flat=True).order_by("-reference_year").distinct()

        self.filters["reference_year"].field.choices = [(year, year) for year in reference_years]
        self.filters["sectors"].field.choices = grouped_choices
        self.filters["author"].queryset = User.objects.filter(id__in=author_user_ids)
        self.filters["author"].field.label_from_instance = self.user_label
        self.filters["standard"].queryset = Standard.objects.filter(project__in=queryset).distinct()
        self.filters["standard__regulation"].queryset = Regulation.objects.filter(standard__project__in=queryset).distinct()

    def user_label(self, user):
        full_name = user.get_full_name()
        return full_name if full_name else user.email

    def filter_search(self, queryset, name, value):
        query = (
            Q(standard__translations__label__icontains=value)
            | Q(standard__translations__description__icontains=value)
            | Q(standard__regulation__translations__label__icontains=value)
            | Q(author__first_name__icontains=value)
            | Q(author__last_name__icontains=value)
            | Q(sectors__translations__name__icontains=value)
            | Q(name__icontains=value)
        )

        if value.isdigit():
            query |= Q(reference_year=int(value))

        return queryset.filter(query).distinct()


class CompanyProjectFilter(django_filters.FilterSet):
    year = django_filters.MultipleChoiceFilter(widget=DropdownCheckboxSelectMultiple())
    sector = django_filters.MultipleChoiceFilter(widget=DropdownCheckboxSelectMultiple())
    search = django_filters.CharFilter(method="filter_search", label=_("Search"))

    class Meta:
        model = CompanyProject
        fields = [
            "sector",
            "year",
        ]

    def __init__(self, *args, **kwargs):
        self.project = kwargs.pop("project", None)
        super().__init__(*args, **kwargs)

        if self.project:
            sectors = Sector.objects.filter(project=self.project).distinct()
            grouped_choices = get_sectors_grouped(sectors)
            years = self.project.years
            years.insert(0, self.project.reference_year)
        else:
            years = []
            grouped_choices = []

        self.filters["sector"].field.choices = grouped_choices
        self.filters["year"].field.choices = [(year, year) for year in years]

    def filter_search(self, queryset, name, value):
        query = Q(company__name__icontains=value) | Q(sector__translations__name__icontains=value)

        if value.isdigit():
            query |= Q(year=int(value))

        return queryset.filter(query).distinct()
