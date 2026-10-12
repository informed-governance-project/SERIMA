from django.db import migrations, models

ACRONYM_MAX_LENGTH = 4


def plan_acronym_renaming(acronyms: list[tuple[int, str]], max_length: int = ACRONYM_MAX_LENGTH) -> dict[int, str]:
    """Work out what the duplicated acronyms become. The earliest sector of a group keeps
    its acronym; each later one gets a digit appended, or replacing its last letter when
    the acronym is already at max_length. The digit goes up until the acronym is free."""
    taken = {acronym for _, acronym in acronyms}

    sectors_by_acronym: dict[str, list[int]] = {}
    for sector_id, acronym in sorted(acronyms):
        sectors_by_acronym.setdefault(acronym, []).append(sector_id)

    renaming = {}
    for acronym, sector_ids in sectors_by_acronym.items():
        suffix = 1
        for sector_id in sector_ids[1:]:
            new_acronym = acronym[: max_length - len(str(suffix))] + str(suffix)
            while new_acronym in taken:
                suffix += 1
                new_acronym = acronym[: max_length - len(str(suffix))] + str(suffix)

            taken.add(new_acronym)
            renaming[sector_id] = new_acronym

    return renaming


def rename_duplicate_acronyms(apps, schema_editor):
    """
    Exporting and importing a workflow matches sectors by acronym, so two sectors sharing
    one block the import. Free the duplicates before acronym becomes unique, and print
    each change so the administrator can adapt the new acronyms by hand.
    """
    Sector = apps.get_model("governanceplatform", "Sector")

    acronyms = list(Sector.objects.values_list("id", "acronym"))
    previous_acronym = dict(acronyms)

    for sector_id, new_acronym in plan_acronym_renaming(acronyms).items():
        Sector.objects.filter(pk=sector_id).update(acronym=new_acronym)
        print(f"sector {sector_id}: {previous_acronym[sector_id]} -> {new_acronym}")


class Migration(migrations.Migration):
    dependencies = [
        ("governanceplatform", "0068_functionality_roles"),
    ]

    operations = [
        # Restoring the duplicates would only put the collisions back.
        migrations.RunPython(rename_duplicate_acronyms, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="sector",
            name="acronym",
            field=models.CharField(max_length=4, unique=True, verbose_name="Acronym"),
        ),
    ]
