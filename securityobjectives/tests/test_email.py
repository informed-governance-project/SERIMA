import pytest
from django.core import mail
from django.template import TemplateDoesNotExist
from django.template.loader import get_template
from django.urls import reverse

from governanceplatform.models import User
from securityobjectives.email import SO_EMAIL_PLACEHOLDERS, replace_email_variables
from securityobjectives.models import SecurityObjectiveEmail, StandardAnswer

REVIEW_COMMENT = "Review comment from the regulator"


@pytest.fixture
def declaration(populate_so_db):
    return populate_so_db["sas"][0]


def _with(declaration, **fields):
    StandardAnswer.objects.filter(pk=declaration.pk).update(**fields)
    declaration.refresh_from_db()
    return declaration


@pytest.mark.django_db
def test_public_url_placeholder_uses_settings(declaration, settings):
    settings.PUBLIC_URL = "https://serima.example.lu"
    assert replace_email_variables("Go to #PUBLIC_URL#", declaration) == "Go to https://serima.example.lu"


@pytest.mark.django_db
def test_reference_placeholder_is_the_group_id(declaration):
    declaration.group.group_id = "SO_0042"
    declaration.group.save()
    assert replace_email_variables("Declaration #SO_REFERENCE#", declaration) == "Declaration SO_0042"


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("stored_status", "shown_status"),
    [
        ("DELIV", "Under review"),
        ("PASS", "Under review"),
        ("FAIL", "Under review"),
        ("PASSM", "Passed"),
        ("FAILM", "Revision required"),
    ],
)
def test_status_placeholder_is_the_status_the_operator_sees(declaration, stored_status, shown_status):
    _with(declaration, status=stored_status)
    assert replace_email_variables("#SO_STATUS#", declaration) == shown_status


@pytest.mark.django_db
@pytest.mark.parametrize("stored_status", ["PASSM", "FAILM"])
def test_comment_added_placeholder_announces_a_sent_review_comment(declaration, stored_status):
    _with(declaration, status=stored_status, review_comment=REVIEW_COMMENT)
    assert replace_email_variables("#SO_REVIEW_COMMENT_ADDED#", declaration) == "New comment added"


@pytest.mark.django_db
@pytest.mark.parametrize("stored_status", ["UNDE", "DELIV", "PASS", "FAIL"])
def test_comment_added_placeholder_is_empty_until_the_review_is_sent(declaration, stored_status):
    _with(declaration, status=stored_status, review_comment=REVIEW_COMMENT)
    assert replace_email_variables("#SO_REVIEW_COMMENT_ADDED#", declaration) == ""


@pytest.mark.django_db
@pytest.mark.parametrize("review_comment", [None, ""])
def test_comment_added_placeholder_is_empty_without_comment(declaration, review_comment):
    _with(declaration, status="PASSM", review_comment=review_comment)
    assert replace_email_variables("#SO_REVIEW_COMMENT_ADDED#", declaration) == ""


@pytest.mark.django_db
def test_comment_added_placeholder_never_carries_the_comment(declaration):
    _with(declaration, status="PASSM", review_comment=REVIEW_COMMENT)
    assert REVIEW_COMMENT not in replace_email_variables("#SO_REVIEW_COMMENT_ADDED#", declaration)


@pytest.mark.django_db
def test_unknown_placeholder_is_left_untouched(declaration):
    assert replace_email_variables("Hello #NOT_A_PLACEHOLDER#", declaration) == "Hello #NOT_A_PLACEHOLDER#"


# --- the email sent when the regulator sends the review ----------------------------------------


@pytest.fixture
def status_changed_email(declaration):
    email = SecurityObjectiveEmail(name="Status changed")
    email.set_current_language("en")
    email.subject = "Declaration #SO_REFERENCE# - #SO_STATUS# #SO_REVIEW_COMMENT_ADDED#"
    email.content = "Your declaration is now #SO_STATUS#."
    email.save()
    declaration.standard.security_objective_status_changed_email = email
    declaration.standard.save()
    return email


def _send_review(otp_client, declaration, verdict):
    _with(declaration, status=verdict)
    regulator = User.objects.get(email="regadmin@reg1.lu")
    return otp_client(regulator).post(
        reverse("review_comment_so_declaration", args=[declaration.pk]),
        {"review_comment": REVIEW_COMMENT},
    )


@pytest.mark.django_db
@pytest.mark.parametrize(("verdict", "shown_status"), [("PASS", "Passed"), ("FAIL", "Revision required")])
def test_sending_the_review_mails_the_new_status(otp_client, declaration, status_changed_email, verdict, shown_status):
    _send_review(otp_client, declaration, verdict)

    assert len(mail.outbox) == 1
    assert shown_status in mail.outbox[0].subject
    assert f"Your declaration is now {shown_status}." in mail.outbox[0].body


@pytest.mark.django_db
def test_sending_the_review_mails_that_a_comment_was_added(otp_client, declaration, status_changed_email):
    _send_review(otp_client, declaration, "PASS")

    assert mail.outbox[0].subject.endswith("New comment added")
    assert REVIEW_COMMENT not in mail.outbox[0].body


# --- the placeholder help dialog on the change form -------------------------------------------


@pytest.fixture
def email_change_form(otp_client, populate_so_db):
    try:
        get_template("admin/includes/email_placeholders_help.html")
    except TemplateDoesNotExist:
        pytest.skip("theme does not provide the placeholder dialog")
    regulator = User.objects.get(email="regadmin@reg1.lu")
    email = SecurityObjectiveEmail(name="Status changed", creator=regulator.regulators.first())
    email.set_current_language("en")
    email.subject = "Subject"
    email.content = "Content"
    email.save()
    return otp_client(regulator).get(reverse("admin:securityobjectives_securityobjectiveemail_change", args=[email.pk]))


@pytest.mark.django_db
def test_the_change_form_offers_a_button_opening_the_placeholder_dialog(email_change_form):
    content = email_change_form.content.decode()
    assert "data-placeholders-help-open" in content
    assert '<dialog id="email-placeholders-help"' in content


@pytest.mark.django_db
def test_the_dialog_lists_every_registered_placeholder(email_change_form):
    content = email_change_form.content.decode()
    for placeholder in SO_EMAIL_PLACEHOLDERS:
        assert placeholder.token in content


@pytest.mark.django_db
def test_the_change_form_loads_the_dialog_script(email_change_form):
    assert "js/admin_email_placeholders.js" in email_change_form.content.decode()
