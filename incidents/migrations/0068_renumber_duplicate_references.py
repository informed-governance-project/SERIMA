from django.db import migrations

from governanceplatform.globals import build_crockford_token

from incidents.globals import INCIDENT_REFERENCE_PREFIX


def parse_legacy_reference(reference: str) -> tuple[str, int, int] | None:
    """Split a reference issued before this migration into (prefix, number, year).

    Only the last two segments are fixed. The prefix holds an operator or regulator
    acronym followed by up to two sector acronyms, any of which may be empty or carry an
    underscore of its own — XXXXXXXXXX_SSS_SSS_NNNN_YYYY — so it is taken as whatever precedes the number and the year.
    Returns None when the reference was hand-edited into another shape."""
    parts = reference.rsplit("_", 2)
    if len(parts) != 3:
        return None

    prefix, number, year = parts
    if not number.isdigit() or not year.isdigit() or len(year) != 4:
        return None

    return prefix, int(number), int(year)


def plan_reference_renumbering(references: list[tuple[int, str]]) -> dict[int, str]:
    """Work out what the duplicated references become. The earliest incident of a group
    keeps the reference its operator already received; the later ones continue their own
    series, or take an opaque token when their reference cannot be read as a legacy one."""
    taken = {reference for _, reference in references}

    highest_number: dict[tuple[str, int], int] = {}
    for reference in taken:
        parsed = parse_legacy_reference(reference)
        if parsed:
            prefix, number, year = parsed
            key = (prefix, year)
            highest_number[key] = max(highest_number.get(key, 0), number)

    incidents_by_reference: dict[str, list[int]] = {}
    for incident_id, reference in sorted(references):
        incidents_by_reference.setdefault(reference, []).append(incident_id)

    renumbering = {}
    for reference, incident_ids in incidents_by_reference.items():
        parsed = parse_legacy_reference(reference)
        for incident_id in incident_ids[1:]:
            if parsed:
                prefix, _number, year = parsed
                key = (prefix, year)
                new_reference = f"{prefix}_{highest_number[key] + 1:04}_{year}"
                while new_reference in taken:
                    highest_number[key] += 1
                    new_reference = f"{prefix}_{highest_number[key] + 1:04}_{year}"
                highest_number[key] += 1
            else:
                new_reference = f"{INCIDENT_REFERENCE_PREFIX}{build_crockford_token()}"
                while new_reference in taken:
                    new_reference = f"{INCIDENT_REFERENCE_PREFIX}{build_crockford_token()}"

            taken.add(new_reference)
            renumbering[incident_id] = new_reference

    return renumbering


def renumber_duplicate_references(apps, schema_editor):
    """
    Incident references were numbered from a count of the company's incidents, so a
    deletion, a notification date moved to another year, or two simultaneous
    submissions all handed the same number out twice. Free the duplicates before
    incident_id becomes unique.
    """
    Incident = apps.get_model("incidents", "Incident")

    references = list(Incident.objects.values_list("id", "incident_id"))
    previous_reference = dict(references)

    for incident_id, new_reference in plan_reference_renumbering(references).items():
        Incident.objects.filter(pk=incident_id).update(incident_id=new_reference)
        print(f"incident {incident_id}: {previous_reference[incident_id]} -> {new_reference}")


class Migration(migrations.Migration):
    dependencies = [
        ("incidents", "0067_delete_orphan_report_timelines"),
    ]

    operations = [
        # Restoring the duplicates would only put the collisions back.
        migrations.RunPython(renumber_duplicate_references, migrations.RunPython.noop),
    ]
