from datetime import date
from threading import local

from django.contrib.admin.models import LogEntry
from django.contrib.auth.models import Group
from django.contrib.auth.signals import user_logged_in, user_logged_out
from django.db import transaction
from django.db.models.signals import post_delete, post_save, pre_delete, pre_save
from django.dispatch import receiver

from governanceplatform.models import User, UserSession

from .helpers import user_in_group
from .models import CompanyUser, ObserverUser, PasswordUserHistory, RegulatorUser
from .permissions import (
    set_incident_user_permissions,
    set_observer_admin_permissions,
    set_observer_user_permissions,
    set_operator_admin_permissions,
    set_operator_user_permissions,
    set_regulator_admin_permissions,
    set_regulator_staff_permissions,
)

_thread_locals = local()
_thread_locals.deleting_users = set()


@receiver(pre_save, sender=User)
def save_old_password(sender, instance, **kwargs):
    if not instance.pk:
        return
    old_password = sender.objects.filter(pk=instance.pk).values_list("password", flat=True).first()

    if old_password and old_password != instance.password:
        PasswordUserHistory.objects.create(user=instance, hashed_password=old_password)


# Add logs for user connection
def add_log_for_connection(sender, user, request, **kwargs):
    if user_in_group(user, "RegulatorAdmin") or user_in_group(user, "RegulatorUser") or user_in_group(user, "PlatformAdmin"):
        LogEntry.objects.log_actions(
            user_id=user.id,
            queryset=User.objects.filter(id=user.id),
            action_flag=5,
        )


user_logged_in.connect(add_log_for_connection)


# Add logs for user deconnection
def log_user_logout(sender, request, user, **kwargs):
    if user_in_group(user, "RegulatorAdmin") or user_in_group(user, "RegulatorUser") or user_in_group(user, "PlatformAdmin"):
        LogEntry.objects.log_actions(
            user_id=user.id,
            queryset=User.objects.filter(id=user.id),
            action_flag=6,
        )


user_logged_out.connect(log_user_logout)


@receiver(post_save, sender=CompanyUser)
def update_user_groups(sender, instance, created, **kwargs):
    user = instance.user
    user.is_staff = False
    user.is_superuser = False

    some_company_is_administrator = user.companyuser_set.filter(company=instance.company, is_company_administrator=True)
    # force user to reconnect
    force_logout_user(user)

    # Operator Administrator permission
    if some_company_is_administrator.exists():
        set_operator_admin_permissions(user)
    elif user_in_group(user, "IncidentUser") and not instance.approved:
        set_incident_user_permissions(user)
    else:
        set_operator_user_permissions(user)


# Update incidents from IncidentUser
@receiver(pre_save, sender=CompanyUser)
def update_user_incidents(sender, instance, **kwargs):
    user = instance.user
    company = instance.company
    if (
        user
        and instance.approved
        and user_in_group(user, "IncidentUser")
        and company
        and company.identifier
        and not user.companyuser_set.exclude(pk=instance.pk).exclude(approved=False).exists()
    ):
        with transaction.atomic():
            current_year = date.today().year
            incidents = user.incident_set.filter(company__isnull=True, regulator__isnull=True)
            incidents_per_company = (
                company.incident_set.exclude(contact_user=user).filter(incident_notification_date__year=current_year).count()
            )
            for incident in incidents:
                sector_for_ref = ""
                subsector_for_ref = ""
                sector = incident.affected_sectors.first()
                if sector:
                    subsector_for_ref = sector.acronym[:3]
                    if sector.parent:
                        sector_for_ref = sector.parent.acronym[:3]

                incidents_per_company += 1
                number_of_incident = f"{incidents_per_company:04}"

                incident.incident_id = f"{company.identifier}_{sector_for_ref}_{subsector_for_ref}_{number_of_incident}_{current_year}"
                incident.company = company
                incident.company_name = company.identifier
                incident.save()


@receiver(pre_save, sender=RegulatorUser)
def force_logout_regulator_user(sender, instance, **kwargs):
    user = instance.user

    if instance.pk:
        old_instance = sender.objects.get(pk=instance.pk)

        if old_instance.is_regulator_administrator != instance.is_regulator_administrator:
            force_logout_user(user)


@receiver(post_save, sender=RegulatorUser)
def update_regulator_user_groups(sender, instance, created, **kwargs):
    user = instance.user
    user.is_staff = False
    user.is_superuser = False
    user.is_active = True

    # Regulator Administrator permissions
    if instance.is_regulator_administrator:
        set_regulator_admin_permissions(user)
        return
    set_regulator_staff_permissions(user)


@receiver(pre_save, sender=ObserverUser)
def force_logout_observer_user(sender, instance, **kwargs):
    user = instance.user

    if instance.pk:
        old_instance = sender.objects.get(pk=instance.pk)

        if old_instance.is_observer_administrator != instance.is_observer_administrator:
            force_logout_user(user)


@receiver(post_save, sender=ObserverUser)
def update_observer_user_groups(sender, instance, created, **kwargs):
    user = instance.user
    user.is_staff = False
    user.is_superuser = False
    user.is_active = True

    # Regulator Administrator permissions
    if instance.is_observer_administrator:
        set_observer_admin_permissions(user)
        return
    set_observer_user_permissions(user)


# mark use for deletion to avoid removing group on inexisting object
@receiver(pre_delete, sender=User)
def mark_user_for_deletion(sender, instance, **kwargs):
    if not hasattr(_thread_locals, "deleting_users"):
        _thread_locals.deleting_users = set()
    _thread_locals.deleting_users.add(instance.pk)


# check if a user is being deleted
def is_user_being_deleted(user):
    return user.pk in getattr(_thread_locals, "deleting_users", set())


@receiver(post_delete, sender=CompanyUser)
@receiver(post_delete, sender=RegulatorUser)
@receiver(post_delete, sender=ObserverUser)
def delete_user_groups(sender, instance, **kwargs):
    user = instance.user

    if is_user_being_deleted(user):
        return

    def get_group(name):
        return Group.objects.get_or_create(name=name)[0]

    # --- REGULATOR ---
    if sender is RegulatorUser:
        if user.groups.filter(name="RegulatorAdmin").exists() and not user.regulatoruser_set.exists():
            user.groups.remove(get_group("RegulatorAdmin"))
            user.groups.add(get_group("RegulatorUser"))
            user.is_active = False

        elif user.groups.filter(name="RegulatorUser").exists():
            user.is_active = False

        user.save()
        force_logout_user(user)
        return

    # --- OBSERVER  ---
    if sender is ObserverUser:
        if user.groups.filter(name="ObserverAdmin").exists() and not user.observeruser_set.filter(is_observer_administrator=True).exists():
            user.is_active = False

        user.save()
        force_logout_user(user)
        return

    # --- OPERATOR ---
    if sender is CompanyUser:
        if user.groups.filter(name="OperatorAdmin").exists() and not user.companyuser_set.filter(is_company_administrator=True).exists():
            user.groups.remove(get_group("OperatorAdmin"))
            user.groups.add(get_group("OperatorUser"))

    # --- GLOBAL CLEANUP ---
    if not user.companyuser_set.exists():
        user.is_staff = False
        user.is_superuser = False
        user.groups.clear()
        user.groups.add(get_group("IncidentUser"))
        user.incident_set.filter(company__isnull=False).update(contact_user=None)
    else:
        user_companies = user.companyuser_set.values_list("company_id", flat=True)
        user.incident_set.filter(company__isnull=False).exclude(company__in=user_companies).update(contact_user=None)

    user.save()
    force_logout_user(user)


def force_logout_user(user):
    user_pk = user.pk
    transaction.on_commit(lambda: UserSession.objects.filter(user_id=user_pk).delete())
