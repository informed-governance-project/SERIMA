import pytest

from selfregistration.models import (
    ProcedureTemplateChoice,
    ProcedureTemplatePage,
    ProcedureTemplateQuestion,
    ProcedureTemplateVersion,
)


@pytest.mark.parametrize(
    ("model", "field", "fields", "expected"),
    [
        (ProcedureTemplateVersion, "name", {"version_number": 2}, "Company details (version 2)"),
        (ProcedureTemplatePage, "title", {}, "Company details"),
        (ProcedureTemplateQuestion, "label", {}, "Company details"),
        (ProcedureTemplateChoice, "label", {"position": 1}, "Company details"),
    ],
)
def test_translatable_procedure_models_use_a_label_instead_of_the_default_object_name(model, field, fields, expected):
    obj = model(**fields)
    obj.set_current_language("en")
    setattr(obj, field, "Company details")

    assert str(obj) == expected
