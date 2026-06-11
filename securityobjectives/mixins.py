from governanceplatform.helpers import set_creator


class CreatorMixin:
    def save_model(self, request, obj, form, change):
        set_creator(request, obj, change)
        super().save_model(request, obj, form, change)
