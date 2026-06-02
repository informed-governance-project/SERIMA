import datetime

from django.forms.widgets import TextInput


class TempusDominusV6Widget(TextInput):
    template_name = "widgets/tempus_dominus_v6.html"

    def __init__(self, attrs=None, max_date=None, min_date=None):
        self.format = "%Y-%m-%d %H:%M"
        self.max_date = max_date
        default_attrs = {
            "class": "form-control datetimepicker-input",
            "data-td-target": "#%(id)s",
            "autocomplete": "off",
        }
        if max_date:
            default_attrs["data-max-date"] = max_date
        else:
            default_attrs["data-max-date"] = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
        if min_date:
            default_attrs["data-min-date"] = min_date

        if attrs:
            default_attrs.update(attrs)
        super().__init__(default_attrs)

    def get_context(self, name, value, attrs):
        context = super().get_context(name, value, attrs)
        context["widget"]["td_id"] = attrs["id"]
        return context

    def format_value(self, value):
        if value is None:
            return ""
        if hasattr(value, "strftime"):
            return value.strftime(self.format)
        return value
