from django.db import migrations

DEFAULT_EMAIL_CONFIG = {
    "send_to_observer_email": True,
    "send_to_observer_users": True,
    "additional_recipients": [],
    "attach_incident_json": False,
    "gpg_public_key": "",
}


def rt_config_complete(observer):
    return bool(observer.rt_url and observer._rt_token and observer.rt_queue)


def migrate_rt_to_connectors(apps, schema_editor):
    Observer = apps.get_model("governanceplatform", "Observer")
    ObserverConnector = apps.get_model("governanceplatform", "ObserverConnector")

    for observer in Observer.objects.all():
        complete = rt_config_complete(observer)
        if observer.rt_url or observer._rt_token or observer.rt_queue:
            # _secret takes the Fernet ciphertext verbatim: CONNECTOR_SECRET_KEY
            # falls back to RT_SECRET_KEY, so it stays decryptable
            ObserverConnector.objects.create(
                observer=observer,
                connector_type="rt",
                name="RT",
                config={"url": observer.rt_url or "", "queue": observer.rt_queue or ""},
                _secret=observer._rt_token,
                is_active=complete,
            )
        # preserves the legacy fallback semantics: email fires exactly when
        # the RT configuration is unusable
        ObserverConnector.objects.create(
            observer=observer,
            connector_type="email",
            name="Email",
            config=dict(DEFAULT_EMAIL_CONFIG),
            is_active=not complete,
        )


def restore_rt_fields(apps, schema_editor):
    ObserverConnector = apps.get_model("governanceplatform", "ObserverConnector")

    for connector in ObserverConnector.objects.filter(connector_type="rt").select_related("observer"):
        observer = connector.observer
        observer.rt_url = connector.config.get("url") or None
        observer.rt_queue = connector.config.get("queue") or None
        observer._rt_token = connector._secret
        observer.save()

    ObserverConnector.objects.filter(connector_type__in=["rt", "email"]).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("governanceplatform", "0065_observerconnector"),
    ]

    operations = [
        migrations.RunPython(migrate_rt_to_connectors, restore_rt_fields),
    ]
