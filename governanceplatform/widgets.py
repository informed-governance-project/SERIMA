from import_export import widgets

from .settings import LANGUAGES


# Custom widget to handle translated M2M relationships
class TranslatedNameM2MWidget(widgets.ManyToManyWidget):
    def clean(self, value, row=None, *args, **kwargs):
        if not value:
            return self.model.objects.none()

        names = value.split(self.separator)
        languages = [lang[0] for lang in LANGUAGES]

        instances = []
        for name in names:
            for lang_code in languages:
                instance = self.model._parler_meta.root_model.objects.filter(
                    **{self.field: name.strip()},
                    language_code=lang_code,
                ).first()

                if instance is not None:
                    instances.append(instance.master_id)
                    break

        return instances


# Custom widget to handle translated ForeignKey relationships
class TranslatedNameWidget(widgets.ForeignKeyWidget):
    def clean(self, value, row=None, *args, **kwargs):
        if not value:
            return self.model.objects.none()

        languages = [lang[0] for lang in LANGUAGES]

        for lang_code in languages:
            instance = self.model._parler_meta.root_model.objects.filter(
                **{self.field: value.strip()},
                language_code=lang_code,
            ).first()

            if instance is not None:
                return instance.master
        return self.model.objects.none()
