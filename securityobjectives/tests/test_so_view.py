import json
import re
from unittest.mock import patch

import pytest
from django.urls import reverse
from django.utils import timezone

from conftest import (
    list_admin_add_urls,
    list_url_freetext_filter,
    test_get_with_otp,
)
from governanceplatform.helpers import (
    user_in_group,
)
from securityobjectives.globals import SO_DECLARATION_COLUMNS
from securityobjectives.models import (
    Domain,
    SecurityMeasure,
    SecurityMeasureAnswer,
    SecurityObjective,
    SecurityObjectivesInStandard,
    SecurityObjectiveStatus,
    StandardAnswer,
)
from securityobjectives.templatetags.SO_custom_filters import get_all_versions, status_tooltip


@pytest.mark.django_db
def test_so_user_access_without_2FA(client, populate_so_db):
    """
    Verify if the security objective main pages are not accessible without 2FA
    """
    users = populate_so_db["users"]

    for user in users:
        client.force_login(user)
        url_list = list_url_freetext_filter("securityobjectives", "")
        for url in url_list:
            response = client.get("/" + url)
            assert response.status_code in (
                302,
                403,
            ), f"User {user.email} should not access to the admin without 2FA"


@pytest.mark.django_db
def test_so_admin_roles_addition_rights(otp_client, populate_so_db):
    """
    Test the rights of each groups on the model of security objectives
    """
    users = populate_so_db["users"]
    regulator_admin_rights = [
        "domain",
        "securityobjectiveemail",
        "maturitylevel",
        "securitymeasure",
        "securityobjective",
        "standard",
    ]
    authorized_users = [u for u in users if user_in_group(u, "RegulatorAdmin")]
    for u in list_admin_add_urls("securityobjective"):
        if any(model in u for model in regulator_admin_rights):
            url = "/" + u
            test_get_with_otp(otp_client, users, authorized_users, [], url)


@pytest.mark.django_db
def test_can_access_so(otp_client, populate_so_db):
    """
    Test if the SO is accessible by the correct user
    """
    users = populate_so_db["users"]
    sas = populate_so_db["sas"]
    # operator admin
    authorized_users = [u for u in users if u.email == "opadmin@com1.lu" or u.email == "opuser@com1.lu" or u.email == "regadmin@reg1.lu"]
    unaccess_module_users = [
        u
        for u in users
        if u.email == "reguser@reg2.lu"
        or u.email == "regadmin@reg2.lu"
        or u.email == "obsadm@cert1.lu"
        or u.email == "iu1@iu.lu"
        or u.email == "iu2@iu.lu"
    ]
    # standard answer
    sa = sas[0]

    url = "/securityobjectives/declaration?id=" + str(sa.pk)
    test_get_with_otp(otp_client, users, authorized_users, unaccess_module_users, url)


@pytest.mark.django_db
def test_pdf_download_so(otp_client, populate_so_db):
    """
    Test if the PDF download is accessible to the right users
    """
    users = populate_so_db["users"]
    sas = populate_so_db["sas"]
    # authorized user
    authorized_users = [u for u in users if u.email == "opadmin@com1.lu" or u.email == "opuser@com1.lu" or u.email == "regadmin@reg1.lu"]
    # user with 404
    unauthorized_user = [
        u
        for u in users
        if u.email == "regadmin@reg2.lu"
        or u.email == "reguser@reg2.lu"
        or u.email == "obsadm@cert1.lu"
        or u.email == "iu1@iu.lu"
        or u.email == "iu2@iu.lu"
    ]
    # only one Standard answers in the DB
    sa = next((u for u in sas), None)
    url = "/securityobjectives/download/" + str(sa.id)
    test_get_with_otp(otp_client, users, authorized_users, unauthorized_user, url)


@pytest.mark.django_db
def test_cannot_update_security_objective_from_another_standard(
    otp_client,
    populate_so_db,
    security_measure_from_another_standard,
):
    standard_answer = populate_so_db["sas"][0]
    regulator = next(user for user in populate_so_db["users"] if user.email == "regadmin@reg1.lu")
    client = otp_client(regulator)
    foreign_objective = security_measure_from_another_standard.security_objective

    response = client.post(
        f"{reverse('so_declaration')}?id={standard_answer.pk}",
        data=json.dumps({"id": foreign_objective.pk, "status": "PASS"}),
        content_type="application/json",
    )

    assert response.status_code == 404
    assert not SecurityObjectiveStatus.objects.filter(
        standard_answer=standard_answer,
        security_objective=foreign_objective,
    ).exists()


@pytest.mark.django_db
def test_cannot_update_security_measure_from_another_standard(
    otp_client,
    populate_so_db,
    security_measure_from_another_standard,
):
    standard_answer = populate_so_db["sas"][0]
    standard_answer.status = "UNDE"
    standard_answer.save()
    operator = next(user for user in populate_so_db["users"] if user.email == "opadmin@com1.lu")
    client = otp_client(operator)
    session = client.session
    session["company_in_use"] = standard_answer.submitter_company_id
    session.save()

    response = client.post(
        f"{reverse('so_declaration')}?id={standard_answer.pk}",
        data=json.dumps({"id": security_measure_from_another_standard.pk, "is_implemented": True}),
        content_type="application/json",
    )

    assert response.status_code == 404
    assert not SecurityMeasureAnswer.objects.filter(
        standard_answer=standard_answer,
        security_measure=security_measure_from_another_standard,
    ).exists()


def _declaration_as_operator(otp_client, populate_so_db):
    """Log an operator in and return (client, url) for their declaration page."""
    standard_answer = populate_so_db["sas"][0]
    operator = next(user for user in populate_so_db["users"] if user.email == "opadmin@com1.lu")
    client = otp_client(operator)
    session = client.session
    session["company_in_use"] = standard_answer.submitter_company_id
    session.save()
    return client, f"{reverse('so_declaration')}?id={standard_answer.pk}"


@pytest.mark.django_db
def test_declaration_columns_use_default_labels(otp_client, populate_so_db):
    """Without configuration a standard keeps the built-in column names."""
    client, url = _declaration_as_operator(otp_client, populate_so_db)

    content = client.get(url).content.decode()

    for column in SO_DECLARATION_COLUMNS.values():
        assert str(column["label"]) in content


@pytest.mark.django_db
def test_declaration_column_uses_custom_label(otp_client, populate_so_db):
    """A label set on the standard replaces the default column name."""
    standard = populate_so_db["so_standard"][0]
    standard.set_current_language("en")
    standard.evidence_label = "Supporting proof"
    standard.save()
    client, url = _declaration_as_operator(otp_client, populate_so_db)

    content = client.get(url).content.decode()

    assert "Supporting proof" in content
    assert ">\n                        Evidence\n" not in content


@pytest.mark.django_db
def test_declaration_custom_label_does_not_leak_across_languages(otp_client, populate_so_db):
    """A label set only in French must not surface on the English page."""
    standard = populate_so_db["so_standard"][0]
    standard.set_current_language("fr")
    standard.label = "Standard FR"
    standard.evidence_label = "Preuve justificative"
    standard.save()
    client, url = _declaration_as_operator(otp_client, populate_so_db)

    content = client.get(url).content.decode()

    assert "Preuve justificative" not in content
    assert "Evidence" in content


@pytest.mark.django_db
def test_declaration_hides_evidence_column(otp_client, populate_so_db):
    """Hiding Evidence removes both its header and the measure evidence text."""
    standard = populate_so_db["so_standard"][0]
    standard.set_current_language("en")
    standard.evidence_label = "Supporting proof"
    standard.show_evidence_column = False
    standard.save()
    measure = populate_so_db["so_security_measures"][0]
    client, url = _declaration_as_operator(otp_client, populate_so_db)

    content = client.get(url).content.decode()

    assert "Supporting proof" not in content
    assert measure.evidence not in content


@pytest.mark.django_db
def test_declaration_hides_maturity_level_column_but_keeps_score(otp_client, populate_so_db):
    """Hiding Maturity Level is presentational: the SO score still renders."""
    standard = populate_so_db["so_standard"][0]
    standard.set_current_language("en")
    standard.maturity_level_label = "Tier"
    standard.show_maturity_level_column = False
    standard.save()
    client, url = _declaration_as_operator(otp_client, populate_so_db)

    content = client.get(url).content.decode()

    assert "Tier" not in content
    assert "rowspan" not in content
    assert 'id="so-score"' in content


@pytest.mark.django_db
def test_answers_are_saved_while_columns_are_hidden(otp_client, populate_so_db):
    """Hidden columns must not block saving an answer."""
    standard_answer = populate_so_db["sas"][0]
    standard_answer.status = "UNDE"
    standard_answer.save()
    standard = populate_so_db["so_standard"][0]
    standard.show_evidence_column = False
    standard.show_maturity_level_column = False
    standard.save()
    measure = populate_so_db["so_security_measures"][0]
    client, url = _declaration_as_operator(otp_client, populate_so_db)

    response = client.post(
        url,
        data=json.dumps({"id": measure.pk, "is_implemented": True}),
        content_type="application/json",
    )

    assert response.status_code == 200
    assert SecurityMeasureAnswer.objects.get(
        standard_answer=standard_answer,
        security_measure=measure,
    ).is_implemented


@pytest.mark.django_db
def test_pdf_export_works_while_columns_are_hidden(otp_client, populate_so_db):
    """Hidden columns must not break the WeasyPrint export."""
    standard_answer = populate_so_db["sas"][0]
    standard = populate_so_db["so_standard"][0]
    standard.show_evidence_column = False
    standard.show_maturity_level_column = False
    standard.save()
    operator = next(user for user in populate_so_db["users"] if user.email == "opadmin@com1.lu")
    client = otp_client(operator)
    session = client.session
    session["company_in_use"] = standard_answer.submitter_company_id
    session.save()

    response = client.get(f"/securityobjectives/download/{standard_answer.pk}")

    assert response.status_code == 200
    assert response["Content-Type"] == "application/pdf"


@pytest.mark.django_db
def test_hiding_a_column_widens_the_remaining_columns_in_the_rendered_table(otp_client, populate_so_db):
    """The computed width must reach the markup, not just the context."""
    standard = populate_so_db["so_standard"][0]
    standard.show_evidence_column = False
    standard.save()
    # An operator sees the review comment column once the review is sent.
    StandardAnswer.objects.filter(pk=populate_so_db["sas"][0].pk).update(status="PASSM")
    client, url = _declaration_as_operator(otp_client, populate_so_db)

    content = client.get(url).content.decode()
    # The page holds other tables, so anchor on the declaration table's own header.
    header = content.split('id="declaration_table"')[1].split("<thead>")[1].split("</thead>")[0]

    # Evidence frees 3 columns, shared out in proportion: measure 3 -> 4, justification 2 -> 3.
    assert "col-4" in header
    assert "col-3" in header
    assert "col-5" not in header


@pytest.mark.django_db
def test_hiding_the_review_comment_column_hides_it_from_the_regulator(otp_client, populate_so_db):
    """The toggle must reach the one role that always saw this column."""
    standard_answer = populate_so_db["sas"][0]
    standard = populate_so_db["so_standard"][0]
    standard.set_current_language("en")
    standard.review_comment_label = "Regulator remarks"
    standard.show_review_comment_column = False
    standard.save()
    regulator = next(user for user in populate_so_db["users"] if user.email == "regadmin@reg1.lu")
    client = otp_client(regulator)

    content = client.get(f"{reverse('so_declaration')}?id={standard_answer.pk}").content.decode()

    assert "Regulator remarks" not in content


@pytest.mark.django_db
def test_showing_the_review_comment_column_does_not_reveal_it_to_an_operator(otp_client, populate_so_db):
    """The toggle narrows the existing rule; it must never widen it."""
    standard_answer = populate_so_db["sas"][0]
    standard_answer.status = "UNDE"
    standard_answer.review_comment = None
    standard_answer.save()
    standard = populate_so_db["so_standard"][0]
    standard.set_current_language("en")
    standard.review_comment_label = "Regulator remarks"
    standard.show_review_comment_column = True
    standard.save()
    client, url = _declaration_as_operator(otp_client, populate_so_db)

    content = client.get(url).content.decode()

    assert "Regulator remarks" not in content


@pytest.mark.django_db
def test_the_justification_placeholder_follows_the_configured_column_label(otp_client, populate_so_db):
    """The script reads this from the page, so a renamed column must reach the markup."""
    standard = populate_so_db["so_standard"][0]
    standard.set_current_language("en")
    standard.justification_label = "Rationale"
    standard.save()
    client, url = _declaration_as_operator(otp_client, populate_so_db)

    content = client.get(url).content.decode()

    assert 'data-justification-placeholder="Rationale required"' in content


@pytest.mark.django_db
def test_the_justification_placeholder_falls_back_to_the_default_label(otp_client, populate_so_db):
    client, url = _declaration_as_operator(otp_client, populate_so_db)

    content = client.get(url).content.decode()

    assert 'data-justification-placeholder="Justification required"' in content


@pytest.mark.django_db
def test_the_score_and_its_maximum_are_shown_by_default(otp_client, populate_so_db):
    client, url = _declaration_as_operator(otp_client, populate_so_db)

    content = client.get(url).content.decode()

    assert 'id="so-score"' in content
    assert 'id="score_container"' in content


@pytest.mark.django_db
def test_showing_the_score_only_drops_its_maximum(otp_client, populate_so_db):
    """The score stays; the "/ n" out of the top maturity level goes."""
    standard = populate_so_db["so_standard"][0]
    standard.score_display = "SCORE"
    standard.save()
    client, url = _declaration_as_operator(otp_client, populate_so_db)

    content = client.get(url).content.decode()

    assert 'id="so-score"' in content
    assert "<span>/</span>" not in content


@pytest.mark.django_db
def test_hiding_the_score_removes_it_entirely(otp_client, populate_so_db):
    standard = populate_so_db["so_standard"][0]
    standard.score_display = "NONE"
    standard.save()
    client, url = _declaration_as_operator(otp_client, populate_so_db)

    content = client.get(url).content.decode()

    assert 'id="so-score"' not in content
    assert 'id="score_container"' not in content


@pytest.mark.django_db
def test_the_pdf_export_honours_a_hidden_score(otp_client, populate_so_db):
    """Hiding the score must not break WeasyPrint rendering."""
    standard_answer = populate_so_db["sas"][0]
    standard = populate_so_db["so_standard"][0]
    standard.score_display = "NONE"
    standard.save()
    operator = next(user for user in populate_so_db["users"] if user.email == "opadmin@com1.lu")
    client = otp_client(operator)
    session = client.session
    session["company_in_use"] = standard_answer.submitter_company_id
    session.save()

    response = client.get(f"/securityobjectives/download/{standard_answer.pk}")

    assert response.status_code == 200
    assert response["Content-Type"] == "application/pdf"


@pytest.mark.django_db
def test_the_score_setting_stays_editable_on_a_standard_in_use(otp_client, populate_so_db):
    """It is presentation, so the in-use lock must not freeze it."""
    standard = populate_so_db["so_standard"][0]
    assert standard.is_in_use() is True

    from governanceplatform.admin import admin_site
    from securityobjectives.models import Standard

    readonly = admin_site._registry[Standard].STRUCTURAL_FIELDS

    assert "score_display" not in readonly


@pytest.mark.django_db
def test_the_default_score_display_renders_the_maximum(otp_client, populate_so_db):
    """Counterpart to the score-only case, so that assertion cannot pass vacuously."""
    client, url = _declaration_as_operator(otp_client, populate_so_db)

    content = client.get(url).content.decode()

    assert "<span>/</span>" in content


@pytest.mark.django_db
def test_the_score_is_recentred_when_its_maximum_is_hidden(otp_client, populate_so_db):
    """Centred on the anchor, the number would drift right once the "/ n" goes."""
    standard = populate_so_db["so_standard"][0]
    standard.score_display = "SCORE"
    standard.save()
    client, url = _declaration_as_operator(otp_client, populate_so_db)

    content = client.get(url).content.decode()

    assert "score-only" in content
    assert "start-50" in content
    assert "start-40" not in content


@pytest.mark.django_db
def test_the_full_score_keeps_its_original_position(otp_client, populate_so_db):
    client, url = _declaration_as_operator(otp_client, populate_so_db)

    content = client.get(url).content.decode()

    assert "start-40" in content
    assert "score-only" not in content


def _implement_every_measure(populate_so_db, standard_answer):
    """Tick every measure, leaving justification and planned measures blank."""
    SecurityMeasureAnswer.objects.filter(standard_answer=standard_answer).update(
        is_implemented=True,
        justification="",
        review_comment="",
    )


@pytest.mark.django_db
def test_a_blank_justification_leaves_the_objective_incomplete_by_default(populate_so_db):
    """The default rule: implemented without a reason is only partially answered."""
    from securityobjectives.views import get_completion_objective

    standard_answer = populate_so_db["sas"][0]
    objective = populate_so_db["so_security_objectives"][0]
    _implement_every_measure(populate_so_db, standard_answer)

    state = get_completion_objective(objective, standard_answer)

    assert state["is_completed"] is False


@pytest.mark.django_db
def test_a_justification_on_an_unimplemented_measure_completes_the_objective(populate_so_db):
    """Explaining why a measure is not implemented is a valid answer (#920)."""
    from securityobjectives.views import get_completion_objective

    standard_answer = populate_so_db["sas"][0]
    standard = standard_answer.standard
    standard.actions_mandatory = False
    standard.save()
    objective = populate_so_db["so_security_objectives"][0]
    SecurityMeasureAnswer.objects.filter(standard_answer=standard_answer).update(
        is_implemented=False,
        justification="Not applicable to our infrastructure.",
    )

    state = get_completion_objective(objective, standard_answer)

    assert state["is_completed"] is True
    assert state["is_partially"] is False


@pytest.mark.django_db
def test_an_optional_justification_completes_the_objective_when_blank(populate_so_db):
    """With justification optional, ticking the measures is a complete answer."""
    from securityobjectives.views import get_completion_objective

    standard_answer = populate_so_db["sas"][0]
    standard = standard_answer.standard
    standard.justification_mandatory = False
    standard.actions_mandatory = False
    standard.save()
    objective = populate_so_db["so_security_objectives"][0]
    _implement_every_measure(populate_so_db, standard_answer)

    state = get_completion_objective(objective, standard_answer)

    assert state["is_completed"] is True
    assert state["is_partially"] is False


@pytest.mark.django_db
def test_optional_planned_measures_do_not_block_completion(populate_so_db):
    """Planned measures alone must not hold an objective open when optional."""
    from securityobjectives.views import get_completion_objective

    standard_answer = populate_so_db["sas"][0]
    standard = standard_answer.standard
    standard.actions_mandatory = False
    standard.save()
    objective = populate_so_db["so_security_objectives"][0]
    SecurityMeasureAnswer.objects.filter(standard_answer=standard_answer).update(
        is_implemented=True,
        justification="Because.",
    )
    SecurityObjectiveStatus.objects.filter(standard_answer=standard_answer, security_objective=objective).update(actions="")

    state = get_completion_objective(objective, standard_answer)

    assert state["is_completed"] is True


@pytest.mark.django_db
def test_the_planned_measures_label_can_be_renamed(otp_client, populate_so_db):
    standard = populate_so_db["so_standard"][0]
    standard.set_current_language("en")
    standard.actions_label = "Remediation plan"
    standard.save()
    client, url = _declaration_as_operator(otp_client, populate_so_db)

    content = client.get(url).content.decode()

    assert "Remediation plan" in content
    assert "Planned Measures" not in content


@pytest.mark.django_db
def test_the_planned_measures_label_falls_back_to_the_default(otp_client, populate_so_db):
    client, url = _declaration_as_operator(otp_client, populate_so_db)

    content = client.get(url).content.decode()

    assert "Planned Measures" in content


@pytest.mark.django_db
def test_an_optional_justification_is_not_flagged_as_required_in_the_markup(otp_client, populate_so_db):
    """The script skips .not-required fields, so the class must reach every one."""
    standard = populate_so_db["so_standard"][0]
    standard.justification_mandatory = False
    standard.save()
    client, url = _declaration_as_operator(otp_client, populate_so_db)

    content = client.get(url).content.decode()

    assert 'data-actions-mandatory="true"' in content
    assert content.count("not-required") > 0


@pytest.mark.django_db
def test_hiding_the_justification_column_removes_it_from_the_table(otp_client, populate_so_db):
    standard = populate_so_db["so_standard"][0]
    standard.set_current_language("en")
    standard.justification_label = "Rationale"
    standard.show_justification_column = False
    standard.save()
    client, url = _declaration_as_operator(otp_client, populate_so_db)

    content = client.get(url).content.decode()
    table = content.split('id="declaration_table"')[1]

    assert "Rationale" not in table
    assert 'data-justification-placeholder=""' in content


@pytest.mark.django_db
def test_hiding_the_planned_measures_row_removes_it_from_the_table(otp_client, populate_so_db):
    standard = populate_so_db["so_standard"][0]
    standard.set_current_language("en")
    standard.actions_label = "Remediation plan"
    standard.show_actions = False
    standard.save()
    client, url = _declaration_as_operator(otp_client, populate_so_db)

    content = client.get(url).content.decode()

    assert "Remediation plan" not in content


@pytest.mark.django_db
def test_a_hidden_justification_cannot_hold_an_objective_open(populate_so_db):
    """Hidden but still flagged mandatory would be a declaration nobody can submit."""
    from securityobjectives.views import get_completion_objective

    standard_answer = populate_so_db["sas"][0]
    standard = standard_answer.standard
    standard.show_justification_column = False
    standard.justification_mandatory = True
    standard.show_actions = False
    standard.actions_mandatory = True
    standard.save()
    objective = populate_so_db["so_security_objectives"][0]
    _implement_every_measure(populate_so_db, standard_answer)

    state = get_completion_objective(objective, standard_answer)

    assert state["is_completed"] is True


@pytest.mark.django_db
def test_hiding_the_justification_column_widens_the_others(otp_client, populate_so_db):
    """It is a table column, so the row must still span the grid without it."""
    standard = populate_so_db["so_standard"][0]
    standard.show_justification_column = False
    standard.save()
    client, url = _declaration_as_operator(otp_client, populate_so_db)

    content = client.get(url).content.decode()
    header = content.split('id="declaration_table"')[1].split("<thead>")[1].split("</thead>")[0]

    assert "col-4" in header


def _dashboard_with_status(otp_client, populate_so_db, email, stored_status, status_filter):
    declaration = populate_so_db["sas"][0]
    StandardAnswer.objects.filter(pk=declaration.pk).update(status=stored_status)
    user = next(u for u in populate_so_db["users"] if u.email == email)
    return otp_client(user).get(reverse("securityobjectives"), {"status": status_filter}), declaration


@pytest.mark.django_db
def test_operator_status_filter_offers_only_the_statuses_operators_see(otp_client, populate_so_db):
    response, _ = _dashboard_with_status(otp_client, populate_so_db, "opadmin@com1.lu", "UNDE", "")

    choices = [code for code, _ in response.context["filter"].form.fields["status"].choices if code]
    assert choices == ["UNDE", "DELIV", "PASS", "FAIL"]


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("stored_status", "status_filter"),
    [("PASSM", "PASS"), ("FAILM", "FAIL"), ("PASS", "DELIV"), ("FAIL", "DELIV")],
)
def test_operator_status_filter_matches_the_status_operators_see(otp_client, populate_so_db, stored_status, status_filter):
    response, declaration = _dashboard_with_status(otp_client, populate_so_db, "opadmin@com1.lu", stored_status, status_filter)

    assert [sa.pk for sa in response.context["standard_answers"]] == [declaration.pk]


@pytest.mark.django_db
@pytest.mark.parametrize(("stored_status", "status_filter"), [("PASS", "PASS"), ("FAIL", "FAIL")])
def test_operator_status_filter_hides_an_unsent_verdict(otp_client, populate_so_db, stored_status, status_filter):
    response, _ = _dashboard_with_status(otp_client, populate_so_db, "opadmin@com1.lu", stored_status, status_filter)

    assert list(response.context["standard_answers"]) == []


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("stored_status", "shown"),
    [("PASS", "Under review"), ("FAIL", "Under review"), ("PASSM", "Passed"), ("FAILM", "Revision required")],
)
def test_operator_sees_a_verdict_only_once_sent(otp_client, populate_so_db, stored_status, shown):
    response, declaration = _dashboard_with_status(otp_client, populate_so_db, "opadmin@com1.lu", stored_status, "")
    StandardAnswer.objects.filter(pk=declaration.pk).update(submit_date=timezone.now())
    context = {"is_regulator": False}

    assert status_tooltip(context, stored_status) == shown
    assert [version["status_tooltip"] for version in json.loads(get_all_versions(context, declaration))] == [shown]


@pytest.mark.django_db
def test_regulator_sees_the_unsent_verdict(populate_so_db):
    assert status_tooltip({"is_regulator": True}, "PASS") == "Passed"


@pytest.mark.django_db
def test_regulator_status_filter_tells_sent_reviews_apart(otp_client, populate_so_db):
    response, _ = _dashboard_with_status(otp_client, populate_so_db, "regadmin@reg1.lu", "PASSM", "PASS")

    choices = [code for code, _ in response.context["filter"].form.fields["status"].choices if code]
    assert "PASSM" in choices and "FAILM" in choices
    assert list(response.context["standard_answers"]) == []

    response, declaration = _dashboard_with_status(otp_client, populate_so_db, "regadmin@reg1.lu", "PASSM", "PASSM")
    assert [sa.pk for sa in response.context["standard_answers"]] == [declaration.pk]


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("stored_status", "verdict_shown"),
    [("PASS", False), ("FAIL", False), ("PASSM", True), ("FAILM", True)],
)
def test_operator_declaration_shows_objective_verdicts_only_once_sent(otp_client, populate_so_db, stored_status, verdict_shown):
    """A substring test such as `status in ",PASSM,FAILM,"` also matches PASS and FAIL."""
    declaration = populate_so_db["sas"][0]
    StandardAnswer.objects.filter(pk=declaration.pk).update(status=stored_status)
    SecurityObjectiveStatus.objects.filter(standard_answer=declaration).update(status=stored_status[:4])
    operator = next(u for u in populate_so_db["users"] if u.email == "opadmin@com1.lu")

    response = otp_client(operator).get(reverse("so_declaration"), {"id": declaration.pk})

    html = response.content.decode()
    assert ("border-passed" in html or "border-failed" in html) is verdict_shown


def _filled_out_declaration(otp_client, populate_so_db, objective_status):
    """An unsubmitted declaration with every objective filled out, as the operator who submits it."""
    declaration = populate_so_db["sas"][0]
    StandardAnswer.objects.filter(pk=declaration.pk).update(status="UNDE")
    statuses = SecurityObjectiveStatus.objects.filter(standard_answer=declaration)
    statuses.update(is_completely_filled_out=True, status="NOT_REVIEWED")
    statuses.filter(pk=statuses.earliest("pk").pk).update(status=objective_status)
    client, _url = _declaration_as_operator(otp_client, populate_so_db)
    return client, declaration


@pytest.mark.django_db
@pytest.mark.parametrize(("objective_status", "submitted"), [("PASS", True), ("FAIL", False)])
def test_an_objective_to_revise_blocks_the_submission(otp_client, populate_so_db, objective_status, submitted):
    """A new version keeps the verdicts of the review it copies, FAIL included, until the operator revises it."""
    client, declaration = _filled_out_declaration(otp_client, populate_so_db, objective_status)

    client.post(reverse("submit_so_declaration", args=[declaration.pk]))

    declaration.refresh_from_db()
    assert (declaration.status == "DELIV") is submitted


@pytest.mark.django_db
@pytest.mark.parametrize(("objective_status", "offered"), [("PASS", True), ("FAIL", False)])
def test_the_dashboard_offers_to_submit_only_what_can_be_submitted(otp_client, populate_so_db, objective_status, offered):
    client, declaration = _filled_out_declaration(otp_client, populate_so_db, objective_status)

    content = client.get(reverse("securityobjectives")).content.decode()

    assert (reverse("submit_so_declaration", args=[declaration.pk]) in content) is offered


MEASURE_COMMENT = "Measure comment from the regulator"
DECLARATION_COMMENT = "Declaration comment from the regulator"
REVIEW_IN_PROGRESS = ["DELIV", "PASS", "FAIL"]
REVIEW_SENT = ["PASSM", "FAILM"]


def _reviewed_declaration(populate_so_db, stored_status):
    declaration = populate_so_db["sas"][0]
    StandardAnswer.objects.filter(pk=declaration.pk).update(
        status=stored_status, review_comment=DECLARATION_COMMENT, submit_date=timezone.now()
    )
    SecurityMeasureAnswer.objects.filter(standard_answer=declaration).update(review_comment=MEASURE_COMMENT)
    declaration.refresh_from_db()
    return declaration


def _operator(populate_so_db):
    return next(u for u in populate_so_db["users"] if u.email == "opadmin@com1.lu")


@pytest.mark.django_db
@pytest.mark.parametrize(("stored_status", "allowed"), [(s, False) for s in REVIEW_IN_PROGRESS] + [(s, True) for s in REVIEW_SENT])
def test_operator_reads_the_review_comment_only_once_sent(otp_client, populate_so_db, stored_status, allowed):
    declaration = _reviewed_declaration(populate_so_db, stored_status)

    response = otp_client(_operator(populate_so_db)).get(reverse("review_comment_so_declaration", args=[declaration.pk]))

    assert (response.status_code == 200) is allowed
    assert (DECLARATION_COMMENT in response.content.decode()) is allowed


@pytest.mark.django_db
@pytest.mark.parametrize(("stored_status", "shown"), [(s, False) for s in REVIEW_IN_PROGRESS] + [(s, True) for s in REVIEW_SENT])
def test_operator_version_history_holds_the_review_comment_only_once_sent(populate_so_db, stored_status, shown):
    declaration = _reviewed_declaration(populate_so_db, stored_status)

    versions = json.loads(get_all_versions({"is_regulator": False}, declaration))

    assert (versions[0]["review_comment"] == DECLARATION_COMMENT) is shown


@pytest.mark.django_db
def test_regulator_version_history_holds_the_draft_review_comment(populate_so_db):
    declaration = _reviewed_declaration(populate_so_db, "PASS")

    versions = json.loads(get_all_versions({"is_regulator": True}, declaration))

    assert versions[0]["review_comment"] == DECLARATION_COMMENT


@pytest.mark.django_db
@pytest.mark.parametrize(("stored_status", "shown"), [(s, False) for s in REVIEW_IN_PROGRESS] + [(s, True) for s in REVIEW_SENT])
def test_operator_declaration_shows_measure_comments_only_once_sent(otp_client, populate_so_db, stored_status, shown):
    declaration = _reviewed_declaration(populate_so_db, stored_status)

    response = otp_client(_operator(populate_so_db)).get(reverse("so_declaration"), {"id": declaration.pk})

    assert (MEASURE_COMMENT in response.content.decode()) is shown


@pytest.mark.django_db
def test_regulator_declaration_shows_draft_measure_comments(otp_client, populate_so_db):
    declaration = _reviewed_declaration(populate_so_db, "PASS")
    regulator = next(u for u in populate_so_db["users"] if u.email == "regadmin@reg1.lu")

    response = otp_client(regulator).get(reverse("so_declaration"), {"id": declaration.pk})

    assert MEASURE_COMMENT in response.content.decode()


def _pdf_html(otp_client, declaration, user):
    with patch("securityobjectives.views.HTML") as html:
        html.return_value.write_pdf.return_value = b""
        otp_client(user).get(reverse("download_so_declaration_pdf", args=[declaration.pk]))
    return html.call_args.kwargs["string"]


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("stored_status", "comments_shown", "cover_status"),
    [(s, False, "Under review") for s in REVIEW_IN_PROGRESS] + [("PASSM", True, "Passed"), ("FAILM", True, "Revision required")],
)
def test_operator_pdf_hides_the_review_until_sent(otp_client, populate_so_db, stored_status, comments_shown, cover_status):
    declaration = _reviewed_declaration(populate_so_db, stored_status)

    rendered = _pdf_html(otp_client, declaration, _operator(populate_so_db))

    assert (MEASURE_COMMENT in rendered) is comments_shown
    assert re.search(rf"Review status\s*:\s*</span>\s*{cover_status}\s*<", rendered)


@pytest.mark.django_db
def test_regulator_pdf_shows_the_draft_review(otp_client, populate_so_db):
    declaration = _reviewed_declaration(populate_so_db, "PASS")
    regulator = next(u for u in populate_so_db["users"] if u.email == "regadmin@reg1.lu")

    rendered = _pdf_html(otp_client, declaration, regulator)

    assert MEASURE_COMMENT in rendered
    assert re.search(r"Review status\s*:\s*</span>\s*Passed\s*<", rendered)


@pytest.mark.django_db
@pytest.mark.parametrize(("stored_status", "shown"), [(s, False) for s in REVIEW_IN_PROGRESS] + [(s, True) for s in REVIEW_SENT])
def test_operator_pdf_shows_objective_statuses_only_once_sent(otp_client, populate_so_db, stored_status, shown):
    declaration = _reviewed_declaration(populate_so_db, stored_status)
    SecurityObjectiveStatus.objects.filter(standard_answer=declaration).update(status="PASS")

    rendered = _pdf_html(otp_client, declaration, _operator(populate_so_db))

    assert ("[Passed]" in rendered) is shown


@pytest.mark.django_db
@pytest.mark.parametrize("stored_status", REVIEW_IN_PROGRESS + REVIEW_SENT)
def test_regulator_pdf_shows_objective_statuses(otp_client, populate_so_db, stored_status):
    declaration = _reviewed_declaration(populate_so_db, stored_status)
    SecurityObjectiveStatus.objects.filter(standard_answer=declaration).update(status="PASS")
    regulator = next(u for u in populate_so_db["users"] if u.email == "regadmin@reg1.lu")

    rendered = _pdf_html(otp_client, declaration, regulator)

    assert "[Passed]" in rendered


DOMAIN_SIZES = [4, 4, 6, 3, 3, 2, 5, 2]


@pytest.fixture
def domain_layout(populate_so_db):
    """Spread the objectives over the eight domains and give each one a measure.

    The shared fixture links every objective to the first domain and every measure to the
    first objective, which leaves a single bullet in the bar. Updates bypass the model
    saves, which would unlink the objectives from the standard.
    """
    declaration = populate_so_db["sas"][0]
    links = list(declaration.standard.security_objectives_set.order_by("position").select_related("security_objective"))
    domains = list(Domain.objects.filter(standard=declaration.standard).order_by("position"))
    measures = list(SecurityMeasure.objects.order_by("pk"))
    owners = [domain for domain, size in zip(domains, DOMAIN_SIZES, strict=True) for _ in range(size)]
    for link, domain, measure in zip(links, owners, measures, strict=False):
        SecurityObjective.objects.filter(pk=link.security_objective_id).update(domain=domain)
        SecurityMeasure.objects.filter(pk=measure.pk).update(security_objective=link.security_objective_id)
    return declaration


def _regulator(populate_so_db):
    return next(u for u in populate_so_db["users"] if u.email == "regadmin@reg1.lu")


def _navigation(otp_client, user, declaration):
    response = otp_client(user).get(reverse("so_declaration"), {"id": declaration.pk})
    return response, response.context["navigation"]


def _unique_codes(navigation):
    return [[so.unique_code for so in domain["objectives"]] for domain in navigation["domains"]]


@pytest.mark.django_db
def test_declaration_groups_objectives_by_domain_in_position_order(otp_client, populate_so_db, domain_layout):
    declaration = domain_layout

    _response, navigation = _navigation(otp_client, _regulator(populate_so_db), declaration)

    assert navigation["is_grouped"] is True
    assert [domain["code"] for domain in navigation["domains"]] == [f"D{position}" for position in range(1, 9)]


@pytest.mark.django_db
def test_domain_order_wins_over_objective_position(otp_client, populate_so_db, domain_layout):
    """Positions are set per standard, independently of the domains, so they may interleave them."""
    declaration = domain_layout
    links = list(SecurityObjectivesInStandard.objects.filter(standard=declaration.standard).order_by("position"))
    for position, link in enumerate(reversed(links)):
        SecurityObjectivesInStandard.objects.filter(pk=link.pk).update(position=position)

    _response, navigation = _navigation(otp_client, _regulator(populate_so_db), declaration)

    assert [domain["code"] for domain in navigation["domains"]] == [f"D{position}" for position in range(1, 9)]
    in_first_domain = set(
        SecurityObjective.objects.filter(domain__standard=declaration.standard, domain__position=1).values_list("pk", flat=True)
    )
    first_domain = [link.security_objective.unique_code for link in links if link.security_objective_id in in_first_domain]
    assert _unique_codes(navigation)[0] == list(reversed(first_domain))


@pytest.mark.django_db
def test_numbers_follow_the_domains(otp_client, populate_so_db, domain_layout):
    declaration = domain_layout

    _response, navigation = _navigation(otp_client, _regulator(populate_so_db), declaration)

    numbers = [so.nav_number for domain in navigation["domains"] for so in domain["objectives"]]
    assert numbers == list(range(1, len(numbers) + 1))


@pytest.mark.django_db
def test_objectives_without_a_domain_come_last(otp_client, populate_so_db, domain_layout):
    declaration = domain_layout
    orphan = declaration.standard.security_objectives_set.order_by("position").first().security_objective
    SecurityObjective.objects.filter(pk=orphan.pk).update(domain=None)

    _response, navigation = _navigation(otp_client, _regulator(populate_so_db), declaration)

    last = navigation["domains"][-1]
    assert (last["code"], str(last["label"])) == ("–", "No domain")
    assert [so.pk for so in last["objectives"]] == [orphan.pk]


@pytest.mark.django_db
def test_single_domain_standard_keeps_the_flat_bar(otp_client, populate_so_db, domain_layout):
    declaration = domain_layout
    domain = Domain.objects.get(position=1)
    SecurityObjective.objects.filter(standard_link__standard=declaration.standard).update(domain=domain)

    response, navigation = _navigation(otp_client, _regulator(populate_so_db), declaration)

    assert navigation["is_grouped"] is False
    assert "so-nav-domain" not in response.content.decode()


@pytest.mark.django_db
def test_regulator_lands_on_the_first_objective_not_reviewed(otp_client, populate_so_db, domain_layout):
    declaration = domain_layout
    SecurityObjectiveStatus.objects.filter(standard_answer=declaration).update(status="PASS")
    _response, navigation = _navigation(otp_client, _regulator(populate_so_db), declaration)
    fifth = [so for domain in navigation["domains"] for so in domain["objectives"]][4]
    SecurityObjectiveStatus.objects.filter(standard_answer=declaration, security_objective=fifth).update(status="NOT_REVIEWED")

    response, navigation = _navigation(otp_client, _regulator(populate_so_db), declaration)

    assert navigation["initial_slide"] == 4
    assert re.search(rf'id="slide_{fifth.pk}"\s+class="carousel-item\s+active', response.content.decode())


@pytest.mark.django_db
def test_regulator_domain_symbols_once_reviewed(otp_client, populate_so_db, domain_layout):
    declaration = domain_layout
    SecurityObjectiveStatus.objects.filter(standard_answer=declaration).update(status="PASS")
    _response, navigation = _navigation(otp_client, _regulator(populate_so_db), declaration)
    revised = navigation["domains"][0]["objectives"][1]
    SecurityObjectiveStatus.objects.filter(standard_answer=declaration, security_objective=revised).update(status="FAIL")

    _response, navigation = _navigation(otp_client, _regulator(populate_so_db), declaration)

    assert [domain["symbol"] for domain in navigation["domains"][:2]] == ["failed", "passed"]


@pytest.mark.django_db
def test_operator_lands_on_the_first_objective_when_nothing_is_filled(otp_client, populate_so_db, domain_layout):
    declaration = domain_layout
    StandardAnswer.objects.filter(pk=declaration.pk).update(status="UNDE")
    SecurityMeasureAnswer.objects.filter(standard_answer=declaration).delete()

    _response, navigation = _navigation(otp_client, _operator(populate_so_db), declaration)

    assert navigation["initial_slide"] == 0
    assert {domain["symbol"] for domain in navigation["domains"]} == {"outline-uninitiated"}


@pytest.mark.django_db
def test_slide_shows_its_domain_and_its_place_in_it(otp_client, populate_so_db, domain_layout):
    declaration = domain_layout

    response, navigation = _navigation(otp_client, _regulator(populate_so_db), declaration)

    total = len(navigation["domains"][0]["objectives"])
    assert f"Objective 1 of {total} in this domain" in response.content.decode()
