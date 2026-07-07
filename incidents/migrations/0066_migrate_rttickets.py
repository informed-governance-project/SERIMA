from django.db import migrations


def migrate_rttickets_to_deliveries(apps, schema_editor):
    RTTicket = apps.get_model("incidents", "RTTicket")
    ConnectorDelivery = apps.get_model("incidents", "ConnectorDelivery")
    ObserverConnector = apps.get_model("governanceplatform", "ObserverConnector")

    for ticket in RTTicket.objects.all():
        connector = ObserverConnector.objects.filter(observer=ticket.observer, connector_type="rt").first()
        if connector is None:
            continue
        delivery = ConnectorDelivery.objects.create(
            incident=ticket.incident,
            connector=connector,
            external_ref=ticket.ticket_id,
            status="sent",
            attempts=1,
        )
        # auto_now_add ignores assigned values, so backfill with update()
        ConnectorDelivery.objects.filter(pk=delivery.pk).update(created_at=ticket.created_at)


def restore_rttickets(apps, schema_editor):
    RTTicket = apps.get_model("incidents", "RTTicket")
    ConnectorDelivery = apps.get_model("incidents", "ConnectorDelivery")

    deliveries = (
        ConnectorDelivery.objects.filter(connector__connector_type="rt", status="sent")
        .exclude(external_ref="")
        .select_related("connector")
    )
    for delivery in deliveries:
        ticket = RTTicket.objects.create(
            incident=delivery.incident,
            observer=delivery.connector.observer,
            ticket_id=delivery.external_ref,
        )
        RTTicket.objects.filter(pk=ticket.pk).update(created_at=delivery.created_at)

    ConnectorDelivery.objects.filter(connector__connector_type="rt").delete()


class Migration(migrations.Migration):
    dependencies = [
        ("incidents", "0065_connectordelivery"),
        ("governanceplatform", "0066_migrate_rt_to_connectors"),
    ]

    operations = [
        migrations.RunPython(migrate_rttickets_to_deliveries, restore_rttickets),
    ]
