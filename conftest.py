import pytest
from django.db import models
from django.test import Client
from django.urls import get_resolver
from django.utils.translation import activate
from parler.models import TranslatableModel


@pytest.fixture
def client():
    return Client()


@pytest.fixture
def otp_client(client):
    """
    Fixture to emulate 2FA connection
    """
    from django_otp import devices_for_user
    from django_otp.middleware import OTPMiddleware
    from django_otp.plugins.otp_static.models import StaticDevice

    def _login(user):
        client.force_login(user)
        devices = list(devices_for_user(user))
        # get or create the devices
        if devices:
            device = devices[0]
        else:
            device = StaticDevice.objects.create(user=user, name="test-device")
        session = client.session
        session["otp_device_id"] = device.persistent_id
        session.save()
        request = client.request().wsgi_request
        OTPMiddleware(lambda r: r)(request)
        request.user.otp_device = device
        return client

    return _login


# customize output generated with
# poetry run pytest --html=../report.html --self-contained-html
def pytest_html_results_table_row(report, cells):
    # fetch description
    desc = getattr(report, "description", "")
    # Limit size to don't break the array
    if len(desc) > 120:
        desc = desc[:117] + "..."
    # Replace name of the test by the description
    if desc:
        cells[1] = desc


def pytest_itemcollected(item):
    # fetch the docstring
    doc = item.function.__doc__
    if doc:
        item._obj.description = doc.strip()


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item, call):
    outcome = yield
    report = outcome.get_result()
    report.description = str(item.function.__doc__)


def list_urls(lis, prefix=""):
    """
    Get the list of all the urls
    """
    urls = []
    for entry in lis:
        if hasattr(entry, "url_patterns"):
            urls += list_urls(entry.url_patterns, prefix + str(entry.pattern))
        else:
            urls.append(prefix + str(entry.pattern))
    return urls


def list_admin_add_urls(module_name: str):
    """
    get the 'add/' road of the given module.
    """
    all_urls = list_urls(get_resolver().url_patterns)
    return [url for url in all_urls if url.startswith(f"admin/{module_name}/") and url.endswith("/add/")]


def list_url_freetext_filter(freetext="", exclude=""):
    all_urls = list_urls(get_resolver().url_patterns)
    return [url for url in all_urls if url.find(freetext) != -1 and url.find(exclude) == -1]


def test_get_with_otp(otp_client, users=None, authorized_users=None, module_unaccess_user=None, url=""):
    """
    Function to test the get with a connected user via 2FA
    """
    users = users or []
    authorized_users = authorized_users or []
    module_unaccess_user = module_unaccess_user or []
    for u in users:
        client = otp_client(u)
        response = client.get(url)
        if u in authorized_users:
            assert response.status_code == 200
        elif u in module_unaccess_user:
            assert response.status_code == 404
        else:
            assert response.status_code in (302, 403)


def get_unique_lookup(model, data: dict, import_not_null, only_simple_field):
    unique_fields = [f.name for f in model._meta.get_fields() if getattr(f, "unique", False)]

    for constraint in model._meta.constraints:
        if isinstance(constraint, models.UniqueConstraint):
            unique_fields.extend(constraint.fields)

    simple_fields = [f.name for f in model._meta.get_fields() if not (f.many_to_many or f.one_to_many or f.is_relation)]

    not_null_fields = []
    if import_not_null:
        not_null_fields = [
            f.name
            for f in model._meta.get_fields()
            if getattr(f, "null", True) is False  # null=False => NOT NULL
            and not (f.many_to_many)
        ]

    # Combine unique and not null
    relevant_fields = set(unique_fields + not_null_fields)

    # manage final lookup
    if only_simple_field:
        lookup = {f: data[f] for f in relevant_fields if f in data and f in simple_fields}
    else:
        lookup = {f: data[f] for f in relevant_fields if f in data}
    return lookup


def get_or_create_related(related_model, val: dict):
    if not isinstance(val, dict):
        raise ValueError(f"Unexpected value {related_model.__name__}: {val}")

    lookup = get_unique_lookup(related_model, val, False, True)
    found_obj = None
    if not lookup:
        # bypass when there is no unique field in the model, only get, no create
        found_obj = related_model.objects.filter(**lookup).first()
        if not found_obj:
            raise ValueError(f"Unexpected lookup for {related_model.__name__} with data={val}")

    if not found_obj:
        obj, created = related_model.objects.get_or_create(**lookup)
    else:
        created = False
        obj = found_obj

    if created:
        # update other field
        for k, v in val.items():
            if k not in lookup:
                setattr(obj, k, v)

        # update translations
        if isinstance(obj, TranslatableModel):
            obj.set_current_language("en")
            for f in obj._parler_meta.get_translated_fields():
                if f in val:
                    setattr(obj, f, val[f])

        obj.save()

    return obj


# import_not_null=True, is used to import field which have NOT NULL Constraint
# only_simple_field=False, is used to import FK which are mandatory
def import_from_json(model, data, import_not_null=False, only_simple_field=True):
    if isinstance(data, dict):
        data = [data]

    created_objects = []
    activate("en")
    for entry in data:
        # lookup via unique constraint
        lookup = get_unique_lookup(model, entry, import_not_null, only_simple_field)
        if not lookup:
            # fallback sur les champs simples
            lookup = {
                f.name: entry[f.name]
                for f in model._meta.get_fields()
                if f.name in entry and not (f.many_to_many or f.one_to_many or f.many_to_one)
            }
        if lookup and not only_simple_field:
            for field in model._meta.get_fields():
                fname = field.name
                if fname in lookup:
                    if isinstance(field, models.ForeignKey):
                        related_model = field.related_model
                        rel_obj = get_or_create_related(related_model, lookup[fname])
                        lookup[fname] = rel_obj

        obj = model.objects.create(**lookup)

        # Traduction
        if isinstance(obj, TranslatableModel):
            obj.set_current_language("en")
            for f in obj._parler_meta.get_translated_fields():
                if f in entry:
                    setattr(obj, f, entry[f])

        # normak field and FK
        for field in model._meta.get_fields():
            fname = field.name
            if fname in lookup or fname not in entry:
                continue

            value = entry[fname]

            if isinstance(field, models.ForeignKey):
                related_model = field.related_model
                rel_obj = get_or_create_related(related_model, value)
                setattr(obj, fname, rel_obj)
            elif not field.many_to_many and not field.one_to_many:
                setattr(obj, fname, value)

        obj.save()

        # manage m2m after save
        for field in model._meta.many_to_many:
            fname = field.name
            if fname not in entry:
                continue

            value = entry[fname]
            related_model = field.related_model
            rel_objs = [get_or_create_related(related_model, v) for v in value]
            obj.save()
            getattr(obj, fname).set(rel_objs)

        obj.save()
        obj.refresh_from_db()

        created_objects.append(obj)

    return created_objects
