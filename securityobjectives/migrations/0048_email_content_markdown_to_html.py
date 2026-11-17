from django.db import migrations
from markdown import markdown


def markdown_to_html(apps, schema_editor):
    # The content is edited as HTML from now on. The same conversion as the one sending
    # did until now, so the emails keep the formatting their recipients got.
    SecurityObjectiveEmailTranslation = apps.get_model("securityobjectives", "SecurityObjectiveEmailTranslation")
    for translation in SecurityObjectiveEmailTranslation.objects.all():
        translation.content = markdown(text=translation.content, output_format="html")
        translation.save(update_fields=["content"])


class Migration(migrations.Migration):
    dependencies = [
        ("securityobjectives", "0047_remove_email_content_help_text"),
    ]

    operations = [
        # No way back to the Markdown that was typed, and none needed: Markdown passes HTML
        # through, so the code before this migration still sends the HTML content.
        migrations.RunPython(markdown_to_html, migrations.RunPython.noop),
    ]
