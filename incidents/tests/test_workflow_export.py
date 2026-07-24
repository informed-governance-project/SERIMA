from typing import TYPE_CHECKING, cast

import pytest
from import_export.formats.base_formats import XLS

from governanceplatform.admin import admin_site
from incidents.models import Workflow
from incidents.resources import WorkflowResource

if TYPE_CHECKING:
    from incidents.admin import WorkflowAdmin


def test_workflow_export_permission_is_temporarily_bypassed():
    workflow_admin = cast("WorkflowAdmin", admin_site._registry[Workflow])

    assert workflow_admin.has_export_permission(request=None)


@pytest.mark.django_db
def test_workflow_export_is_flattened_to_predefined_answers(populate_incident_db):
    workflows = Workflow.objects.filter(pk__in=[1, 2]).order_by("pk")

    dataset = WorkflowResource().export(workflows)

    assert len(dataset) == 7
    assert dataset["question_reference"] == ["1", "1", "2", "2", "3", "4", "5"]
    assert dataset["predefined_answer"] == ["Yes", "No", "Yes", "No", "", "", ""]
    assert dataset["workflow_name"] == ["Reg 1 preli"] * 4 + ["Reg 1 final"] * 3
    assert dataset["category_label"] == ["Reg 1 categ 1"] * 4 + ["Reg 1 categ 2"] * 3


@pytest.mark.django_db
def test_workflow_resource_exports_legacy_xls(populate_incident_db):
    dataset = WorkflowResource().export(Workflow.objects.filter(pk=1))

    exported_data = XLS().export_data(dataset)

    assert isinstance(exported_data, bytes)
    assert exported_data.startswith(b"\xd0\xcf\x11\xe0")
