from django.db.models.signals import post_delete
from django.dispatch import receiver

from .models import IncidentWorkflow, ReportTimeline


@receiver(post_delete, sender=IncidentWorkflow)
def delete_orphan_report_timeline(sender, instance, **kwargs):
    """
    The foreign key lives on IncidentWorkflow, so deleting a report — including through the
    cascade from its incident — leaves its timeline behind with nothing pointing at it.
    """
    if instance.report_timeline_id:
        ReportTimeline.objects.filter(pk=instance.report_timeline_id, incident_workflow__isnull=True).delete()
