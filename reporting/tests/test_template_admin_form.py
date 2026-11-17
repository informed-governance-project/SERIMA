from unfold.widgets import UnfoldAdminFileFieldWidget, UnfoldAdminSelectWidget

from reporting.forms import TemplateAdminForm
from reporting.models import Template


def test_template_form_uses_the_unfold_widgets():
    form = TemplateAdminForm()

    assert isinstance(form.fields["template_file"].widget, UnfoldAdminFileFieldWidget)
    assert isinstance(form.fields["language"].widget, UnfoldAdminSelectWidget)
    assert 'accept=".docx"' in str(form["template_file"])


def test_template_form_with_a_stored_file_offers_a_new_upload():
    """The file is stored as bytes, not as a FieldFile: the widget must not look for its url."""
    form = TemplateAdminForm(instance=Template(language="en", template_file=b"PK\x03\x04"))

    rendered = str(form["template_file"])

    assert "Choose file to upload" in rendered
    assert "download" not in rendered
