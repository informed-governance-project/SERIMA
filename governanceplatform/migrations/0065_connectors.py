import django.db.models.deletion
import governanceplatform.connectors.registry
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("governanceplatform", "0064_alter_applicationconfig_id_alter_company_id_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="observer",
            name="allowed_connector_types",
            field=models.JSONField(blank=True, default=list, verbose_name="Available connectors"),
        ),
        migrations.AddField(
            model_name="observer",
            name="notification_mode",
            field=models.CharField(
                choices=[
                    ("default", "Default (e-mail when no active connector)"),
                    ("default_and_connectors", "E-mail and connectors"),
                    ("connectors_only", "Connectors only (never e-mail)"),
                ],
                default="default",
                max_length=32,
                verbose_name="Notification mode",
            ),
        ),
        migrations.CreateModel(
            name="ObserverConnector",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                (
                    "connector_type",
                    models.CharField(
                        choices=governanceplatform.connectors.registry.connector_type_choices,
                        max_length=32,
                        verbose_name="Type",
                    ),
                ),
                ("name", models.CharField(max_length=100, verbose_name="Name")),
                ("is_active", models.BooleanField(default=True, verbose_name="Active")),
                ("config", models.JSONField(blank=True, default=dict, verbose_name="Configuration")),
                ("_secret", models.CharField(blank=True, db_column="secret", max_length=512, null=True, verbose_name="Secret")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "observer",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="connectors",
                        to="governanceplatform.observer",
                        verbose_name="Observer",
                    ),
                ),
            ],
            options={
                "verbose_name": "Observer connector",
                "verbose_name_plural": "Observer connectors",
                "constraints": [models.UniqueConstraint(fields=("observer", "name"), name="unique_connector_name_per_observer")],
            },
        ),
    ]
