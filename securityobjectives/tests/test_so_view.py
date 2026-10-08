import json

import pytest
from django.urls import reverse

from conftest import (
    list_admin_add_urls,
    list_url_freetext_filter,
    test_get_with_otp,
)
from governanceplatform.helpers import (
    user_in_group,
)
from securityobjectives.globals import SO_DECLARATION_COLUMNS
from securityobjectives.models import SecurityMeasureAnswer, SecurityObjectiveStatus


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
