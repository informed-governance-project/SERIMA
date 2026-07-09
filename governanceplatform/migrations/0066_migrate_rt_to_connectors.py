from django.db import migrations


def migrate_rt_to_connectors(apps, schema_editor):
    Observer = apps.get_model("governanceplatform", "Observer")
    ObserverConnector = apps.get_model("governanceplatform", "ObserverConnector")

    for observer in Observer.objects.all():
        if not (observer.rt_url or observer._rt_token or observer.rt_queue):
            continue
        # _secret takes the Fernet ciphertext verbatim: CONNECTOR_SECRET_KEY
        # defaults to HASH_KEY, the key legacy RT tokens were encrypted with
        ObserverConnector.objects.create(
            observer=observer,
            connector_type="rt",
            name="RT",
            config={"url": observer.rt_url or "", "queue": observer.rt_queue or ""},
            _secret=observer._rt_token,
            is_active=bool(observer.rt_url and observer._rt_token and observer.rt_queue),
        )
        observer.allowed_connector_types = ["rt"]
        observer.save(update_fields=["allowed_connector_types"])
        # observers with an unusable RT config keep receiving plain e-mail through
        # the default notification mode — no e-mail connector rows are needed


def restore_rt_fields(apps, schema_editor):
    ObserverConnector = apps.get_model("governanceplatform", "ObserverConnector")

    for connector in ObserverConnector.objects.filter(connector_type="rt").select_related("observer"):
        observer = connector.observer
        observer.rt_url = connector.config.get("url") or None
        observer.rt_queue = connector.config.get("queue") or None
        observer._rt_token = connector._secret
        observer.allowed_connector_types = []
        observer.save()

    ObserverConnector.objects.filter(connector_type="rt").delete()


class Migration(migrations.Migration):
    dependencies = [
        ("governanceplatform", "0065_connectors"),
    ]

    operations = [
        migrations.RunPython(migrate_rt_to_connectors, restore_rt_fields),
    ]
