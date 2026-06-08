from django.contrib import messages
from django.utils.translation import gettext_lazy as _

from .helpers import can_change_or_delete_obj, filter_languages_not_translated


class TranslationUpdateMixin:
    def after_save_instance(self, instance, using_transactions, dry_run):
        fields = instance._parler_meta.get_all_fields()
        defaults = {}
        for field in fields:
            field_value = getattr(instance, field)
            defaults[field] = field_value
        instance.translations.update_or_create(
            master_id=instance.id,
            language_code=instance.language_code,
            defaults=defaults,
        )


class PermissionMixin:
    def has_change_permission(self, request, obj=None):
        permission = super().has_change_permission(request, obj)
        if obj and permission:
            permission = can_change_or_delete_obj(request, obj)
        return permission

    def has_delete_permission(self, request, obj=None):
        permission = super().has_delete_permission(request, obj)
        if obj and permission:
            permission = can_change_or_delete_obj(request, obj)
        return permission

    def render_change_form(self, request, context, add=False, change=False, form_url="", obj=None):
        has_permission = obj and not self.has_change_permission(request, obj)
        if has_permission:
            context.update(
                {
                    "show_save": False,
                    "show_save_and_continue": False,
                    "show_save_and_add_another": False,
                }
            )
        form = super().render_change_form(request, context, add, change, form_url, obj)
        if has_permission:
            form = filter_languages_not_translated(form)
        return form


class ShowReminderForTranslationsMixin:
    reminder_message = _("Save your changes before you leave the tab of the respective language.")

    def _add_reminder_message(self, request):
        messages.warning(request, self.reminder_message)

    def change_view(self, request, object_id, form_url="", extra_context=None):
        self._add_reminder_message(request)
        return super().change_view(request, object_id, form_url, extra_context)

    def add_view(self, request, form_url="", extra_context=None):
        self._add_reminder_message(request)
        return super().add_view(request, form_url, extra_context)
