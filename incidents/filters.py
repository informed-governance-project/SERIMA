import django_filters
from django.db.models import Q
from django.utils.translation import gettext_lazy as _

from governanceplatform.helpers import get_sectors_grouped
from governanceplatform.models import Sector

from .forms import DropdownCheckboxSelectMultiple
from .models import Incident, SectorRegulation


# define specific query to get the regulation
def sector_regulation(request):
    return SectorRegulation.objects.distinct()


class IncidentFilter(django_filters.FilterSet):
    incident_id = django_filters.CharFilter(lookup_expr="icontains")
    affected_sectors = django_filters.MultipleChoiceFilter(widget=DropdownCheckboxSelectMultiple(), label=_("Sectors"))
    sector_regulation = django_filters.ModelChoiceFilter(queryset=sector_regulation)

    search = django_filters.CharFilter(method="filter_search", label=_("Search"))

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        grouped_choices = get_sectors_grouped(Sector.objects.all())
        self.filters["affected_sectors"].field.choices = grouped_choices

    class Meta:
        model = Incident
        fields = [
            "incident_id",
            "incident_status",
            "is_significative_impact",
            "affected_sectors",
            "sector_regulation",
        ]

    def filter_search(self, queryset, name, value):
        return queryset.filter(
            Q(incident_id__icontains=value)
            | Q(contact_firstname__icontains=value)
            | Q(contact_lastname__icontains=value)
            | Q(technical_firstname__icontains=value)
            | Q(technical_lastname__icontains=value)
            | Q(company_name__icontains=value)
            | Q(company__identifier__icontains=value)
            | Q(company__name__icontains=value)
            | Q(regulator__translations__name__icontains=value)
            | Q(regulator__translations__full_name__icontains=value)
            | Q(sector_regulation__regulation__translations__label__icontains=value)
            | Q(affected_sectors__translations__name__icontains=value)
        ).distinct()
