from django.db import migrations
from markdown import markdown


def markdown_to_html(apps, schema_editor):
    # The content is edited as HTML from now on. The same conversion as the one sending
    # did until now, so the emails keep the formatting their recipients got.
    EmailTranslation = apps.get_model("incidents", "EmailTranslation")
    for translation in EmailTranslation.objects.all():
        translation.content = markdown(text=translation.content, output_format="html")
        translation.save(update_fields=["content"])


class Migration(migrations.Migration):
    dependencies = [
        ("incidents", "0070_alter_answer_options_alter_incident_options_and_more"),
    ]

    operations = [
        # No way back to the Markdown that was typed, and none needed: Markdown passes HTML
        # through, so the code before this migration still sends the HTML content.
        migrations.RunPython(markdown_to_html, migrations.RunPython.noop),
    ]
