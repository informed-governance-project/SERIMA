from django.db import migrations

from governanceplatform.permissions import GROUP_PERMISSIONS


def update_permissions(apps, schema_editor):
    def permission_formatting(permissions):
        group_permissions = []
        for model, list_permissions in permissions.items():
            for permission in list_permissions:
                group_permissions.append(f"{permission}_{model}")
        return group_permissions

    def add_group_permissions(group_name, group_permissions):
        try:
            group = Group.objects.get(name=group_name)

            permissions_to_assign = Permission.objects.filter(
                codename__in=group_permissions
            )
            for permission in permissions_to_assign:
                group.permissions.add(permission)
            group.save()
        except Group.DoesNotExist:
            pass

    Group = apps.get_model("auth", "Group")
    Permission = apps.get_model("auth", "Permission")

    for group_name, permissions in GROUP_PERMISSIONS.items():
        group_permissions = permission_formatting(permissions)
        add_group_permissions(group_name, group_permissions)


class Migration(migrations.Migration):

    dependencies = [
        ('securityobjectives', '0038_alter_securityobjective_unique_code'),
    ]
    # update the permission to be sure the admin files can be downloaded
    # read has been added on standard
    operations = [
        migrations.RunPython(update_permissions),
    ]
