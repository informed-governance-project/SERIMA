from collections.abc import Iterable
from typing import Any

from governanceplatform.models import Sector
from incidents.configuration_export import FORMAT_NAME, FORMAT_VERSION
from incidents.models import (
    ConditionalQuestionOption,
    Email,
    Impact,
    PredefinedAnswer,
    Question,
    QuestionCategory,
    QuestionCategoryOptions,
    QuestionOptions,
    SectorRegulation,
    SectorRegulationWorkflow,
    SectorRegulationWorkflowEmail,
    Workflow,
)


class ConfigurationImportError(ValueError):
    pass


class SectorRegulationConfigurationImporter:
    """Import a configuration into an existing empty SectorRegulation."""

    def __init__(
        self,
        data: dict[str, Any],
        target: SectorRegulation,
        *,
        create_all: bool = False,
    ):
        self.data = data
        self.target = target
        self.create_all = create_all
        self.creator = target.regulator
        self.creator_name = target.regulator.safe_translation_getter("name", any_language=True) or str(target.regulator)
        self.reused_question_keys: set[str] = set()

    def import_configuration(self) -> dict[str, int]:
        self._validate_document()
        if SectorRegulationWorkflow.objects.filter(sector_regulation=self.target).exists():
            raise ConfigurationImportError(f"SectorRegulation {self.target.pk} is not blank: it already has reports.")

        email_data = self._catalog("emails")
        report_data = self._catalog("reports")
        category_data = self._catalog("categories")
        category_option_data = self._catalog("category_options")
        question_data = self._catalog("questions")
        question_option_data = self._catalog("question_options")

        emails = self._import_emails(email_data)
        reports = self._import_reports(report_data, emails)
        categories = self._import_categories(category_data)
        category_options = self._import_category_options(
            category_option_data,
            categories,
        )
        questions, answers = self._import_questions(question_data)
        question_options = self._import_question_options(
            question_option_data,
            reports,
            questions,
            category_options,
        )
        conditional_count = self._import_conditional_questions(
            answers,
            question_options,
        )
        report_link_count, reminder_count = self._import_report_links(
            reports,
            emails,
        )
        impact_count = self._import_impacts()
        self._update_target(emails)

        return {
            "emails": len(emails),
            "reports": len(reports),
            "categories": len(categories),
            "category_options": len(category_options),
            "questions_created": len(questions) - len(self.reused_question_keys),
            "questions_reused": len(self.reused_question_keys),
            "predefined_answers": len(answers),
            "question_options": len(question_options),
            "conditional_questions": conditional_count,
            "report_links": report_link_count,
            "reminder_emails": reminder_count,
            "impacts": impact_count,
        }

    def _validate_document(self) -> None:
        if self.data.get("format") != FORMAT_NAME:
            raise ConfigurationImportError("Unsupported configuration format.")
        if self.data.get("format_version") != FORMAT_VERSION:
            raise ConfigurationImportError(f"Unsupported format version {self.data.get('format_version')!r}; expected {FORMAT_VERSION}.")
        if not isinstance(self.data.get("sector_regulation"), dict):
            raise ConfigurationImportError("Missing sector_regulation object.")

    def _catalog(self, name: str) -> dict[str, dict[str, Any]]:
        items = self.data.get(name)
        if not isinstance(items, list):
            raise ConfigurationImportError(f"{name} must be a list.")
        catalog: dict[str, dict[str, Any]] = {}
        for item in items:
            if not isinstance(item, dict) or not isinstance(item.get("key"), str):
                raise ConfigurationImportError(f"Every {name} item must contain a string key.")
            key = item["key"]
            if key in catalog:
                raise ConfigurationImportError(f"Duplicate {name} key {key!r}.")
            catalog[key] = item
        return catalog

    def _import_emails(
        self,
        catalog: dict[str, dict[str, Any]],
    ) -> dict[str, Email]:
        imported = {}
        for key, item in catalog.items():
            email = Email.objects.create(
                name=self._string(item, "name"),
                creator=self.creator,
                creator_name=self.creator_name,
            )
            self._set_translations(
                email,
                item.get("translations"),
                ("subject", "content"),
            )
            imported[key] = email
        return imported

    def _import_reports(
        self,
        catalog: dict[str, dict[str, Any]],
        emails: dict[str, Email],
    ) -> dict[str, Workflow]:
        imported = {}
        for key, item in catalog.items():
            name = self._unique_value(
                Workflow,
                "name",
                self._string(item, "name"),
                " (import {number})",
            )
            report = Workflow.objects.create(
                name=name,
                is_impact_needed=bool(item.get("is_impact_needed", False)),
                submission_email=self._optional_reference(
                    emails,
                    item.get("submission_email"),
                    "email",
                ),
                creator=self.creator,
                creator_name=self.creator_name,
            )
            self._set_translations(
                report,
                item.get("translations"),
                ("label", "description"),
            )
            imported[key] = report
        return imported

    def _import_categories(
        self,
        catalog: dict[str, dict[str, Any]],
    ) -> dict[str, QuestionCategory]:
        imported = {}
        for key, item in catalog.items():
            category = QuestionCategory.objects.create(
                creator=self.creator,
                creator_name=self.creator_name,
            )
            self._set_translations(
                category,
                item.get("translations"),
                ("label",),
            )
            imported[key] = category
        return imported

    def _import_category_options(
        self,
        catalog: dict[str, dict[str, Any]],
        categories: dict[str, QuestionCategory],
    ) -> dict[str, QuestionCategoryOptions]:
        imported = {}
        for key, item in catalog.items():
            imported[key] = QuestionCategoryOptions.objects.create(
                question_category=self._reference(
                    categories,
                    item.get("category"),
                    "category",
                ),
                position=self._integer(item, "position"),
            )
        return imported

    def _import_questions(
        self,
        catalog: dict[str, dict[str, Any]],
    ) -> tuple[dict[str, Question], dict[str, PredefinedAnswer]]:
        questions: dict[str, Question] = {}
        answers: dict[str, PredefinedAnswer] = {}
        for key, item in catalog.items():
            reference = self._string(item, "reference")
            existing = Question.objects.filter(reference=reference).first()
            if existing is not None and not self.create_all:
                questions[key] = existing
                self.reused_question_keys.add(key)
                continue

            if existing is not None:
                reference = self._unique_value(
                    Question,
                    "reference",
                    reference,
                    "_import_{number}",
                )
            question = Question.objects.create(
                reference=reference,
                question_type=self._string(item, "question_type"),
                creator=self.creator,
                creator_name=self.creator_name,
            )
            self._set_translations(
                question,
                item.get("translations"),
                ("label", "tooltip"),
            )
            questions[key] = question

            answer_items = item.get("predefined_answers", [])
            if not isinstance(answer_items, list):
                raise ConfigurationImportError(f"predefined_answers for question {key!r} must be a list.")
            for answer_item in answer_items:
                if not isinstance(answer_item, dict):
                    raise ConfigurationImportError(f"Invalid predefined answer for question {key!r}.")
                answer_key = self._string(answer_item, "key")
                if answer_key in answers:
                    raise ConfigurationImportError(f"Duplicate predefined answer key {answer_key!r}.")
                answer = PredefinedAnswer.objects.create(
                    question=question,
                    position=answer_item.get("position"),
                    creator=self.creator,
                    creator_name=self.creator_name,
                )
                self._set_translations(
                    answer,
                    answer_item.get("translations"),
                    ("predefined_answer",),
                )
                answers[answer_key] = answer
        return questions, answers

    def _import_question_options(
        self,
        catalog: dict[str, dict[str, Any]],
        reports: dict[str, Workflow],
        questions: dict[str, Question],
        category_options: dict[str, QuestionCategoryOptions],
    ) -> dict[str, QuestionOptions]:
        imported = {}
        for key, item in catalog.items():
            imported[key] = QuestionOptions.objects.create(
                report=self._reference(reports, item.get("report"), "report"),
                question=self._reference(
                    questions,
                    item.get("question"),
                    "question",
                ),
                category_option=self._reference(
                    category_options,
                    item.get("category_option"),
                    "category option",
                ),
                position=self._integer(item, "position"),
                is_mandatory=bool(item.get("is_mandatory", False)),
                is_conditional=bool(item.get("is_conditional", False)),
            )
        return imported

    def _import_conditional_questions(
        self,
        answers: dict[str, PredefinedAnswer],
        question_options: dict[str, QuestionOptions],
    ) -> int:
        items = self.data.get("conditional_questions", [])
        if not isinstance(items, list):
            raise ConfigurationImportError("conditional_questions must be a list.")
        count = 0
        for item in items:
            if not isinstance(item, dict):
                raise ConfigurationImportError("Invalid conditional question.")
            answer_key = item.get("predefined_answer")
            if answer_key not in answers:
                continue
            ConditionalQuestionOption.objects.create(
                question_options=self._reference(
                    question_options,
                    item.get("question_option"),
                    "question option",
                ),
                predefined_answer=answers[answer_key],
                next_question_options=self._reference(
                    question_options,
                    item.get("next_question_option"),
                    "next question option",
                ),
                creator=self.creator,
                creator_name=self.creator_name,
            )
            count += 1
        return count

    def _import_report_links(
        self,
        reports: dict[str, Workflow],
        emails: dict[str, Email],
    ) -> tuple[int, int]:
        items = self.data.get("sector_regulation_reports", [])
        if not isinstance(items, list):
            raise ConfigurationImportError("sector_regulation_reports must be a list.")
        reminder_count = 0
        for item in items:
            if not isinstance(item, dict):
                raise ConfigurationImportError("Invalid sector regulation report.")
            link = SectorRegulationWorkflow.objects.create(
                sector_regulation=self.target,
                workflow=self._reference(
                    reports,
                    item.get("report"),
                    "report",
                ),
                position=item.get("position"),
                delay_in_hours_before_deadline=self._integer(
                    item,
                    "delay_in_hours_before_deadline",
                ),
                trigger_event_before_deadline=self._string(
                    item,
                    "trigger_event_before_deadline",
                ),
            )
            reminder_items = item.get("reminder_emails", [])
            if not isinstance(reminder_items, list):
                raise ConfigurationImportError("reminder_emails must be a list.")
            for reminder_item in reminder_items:
                if not isinstance(reminder_item, dict):
                    raise ConfigurationImportError("Invalid reminder email.")
                reminder = SectorRegulationWorkflowEmail.objects.create(
                    sector_regulation_workflow=link,
                    email=self._reference(
                        emails,
                        reminder_item.get("email"),
                        "email",
                    ),
                    trigger_event=self._string(reminder_item, "trigger_event"),
                    delay_in_hours=self._integer(
                        reminder_item,
                        "delay_in_hours",
                    ),
                )
                self._set_translations(
                    reminder,
                    reminder_item.get("translations"),
                    ("headline",),
                )
                reminder_count += 1
        return len(items), reminder_count

    def _import_impacts(self) -> int:
        items = self.data.get("impacts", [])
        if not isinstance(items, list):
            raise ConfigurationImportError("impacts must be a list.")
        for item in items:
            if not isinstance(item, dict):
                raise ConfigurationImportError("Invalid impact.")
            impact = Impact.objects.create(
                creator=self.creator,
                creator_name=self.creator_name,
            )
            self._set_translations(
                impact,
                item.get("translations"),
                ("label", "headline"),
            )
            impact.regulations.add(self.target.regulation)
            sector_acronyms = item.get("sectors", [])
            if not isinstance(sector_acronyms, list):
                raise ConfigurationImportError("Impact sectors must be a list.")
            impact.sectors.set(self._resolve_sectors(sector_acronyms))
        return len(items)

    def _update_target(self, emails: dict[str, Email]) -> None:
        item = self.data["sector_regulation"]
        self.target.active = bool(item.get("active", True))
        self.target.is_detection_date_needed = bool(item.get("is_detection_date_needed", False))
        self.target.opening_email = self._optional_reference(
            emails,
            item.get("opening_email"),
            "email",
        )
        self.target.closing_email = self._optional_reference(
            emails,
            item.get("closing_email"),
            "email",
        )
        self.target.report_status_changed_email = self._optional_reference(
            emails,
            item.get("report_status_changed_email"),
            "email",
        )
        self.target.save()
        self.target.translations.all().delete()
        self._set_translations(
            self.target,
            item.get("translations"),
            ("name",),
        )
        sector_items = item.get("sectors", [])
        if not isinstance(sector_items, list):
            raise ConfigurationImportError("sector_regulation.sectors must be a list.")
        self.target.sectors.set(
            self._resolve_sectors([self._string(sector_item, "acronym") for sector_item in sector_items if isinstance(sector_item, dict)])
        )

    @staticmethod
    def _set_translations(
        instance,
        translations: Any,
        fields: tuple[str, ...],
    ) -> None:
        if not isinstance(translations, list) or not translations:
            raise ConfigurationImportError(f"Missing translations for {instance.__class__.__name__}.")
        for translation in translations:
            if not isinstance(translation, dict):
                raise ConfigurationImportError("Invalid translation object.")
            language_code = translation.get("language_code")
            if not isinstance(language_code, str) or not language_code:
                raise ConfigurationImportError("Every translation requires a language_code.")
            instance.set_current_language(language_code)
            for field in fields:
                if field not in translation:
                    raise ConfigurationImportError(f"Translation {language_code!r} is missing {field!r}.")
                setattr(instance, field, translation[field])
            instance.save()

    @staticmethod
    def _resolve_sectors(acronyms: Iterable[Any]) -> list[Sector]:
        sectors = []
        for acronym in acronyms:
            if not isinstance(acronym, str):
                raise ConfigurationImportError("Sector acronyms must be strings.")
            matches = list(Sector.objects.filter(acronym=acronym)[:2])
            if not matches:
                raise ConfigurationImportError(f"Sector with acronym {acronym!r} does not exist.")
            if len(matches) > 1:
                raise ConfigurationImportError(f"Sector acronym {acronym!r} is ambiguous.")
            sectors.append(matches[0])
        return sectors

    @staticmethod
    def _reference(mapping: dict[str, Any], key: Any, label: str):
        if not isinstance(key, str) or key not in mapping:
            raise ConfigurationImportError(f"Unknown {label} reference {key!r}.")
        return mapping[key]

    @classmethod
    def _optional_reference(
        cls,
        mapping: dict[str, Any],
        key: Any,
        label: str,
    ):
        return None if key is None else cls._reference(mapping, key, label)

    @staticmethod
    def _string(item: dict[str, Any], field: str) -> str:
        value = item.get(field)
        if not isinstance(value, str):
            raise ConfigurationImportError(f"{field} must be a string.")
        return value

    @staticmethod
    def _integer(item: dict[str, Any], field: str) -> int:
        value = item.get(field)
        if not isinstance(value, int) or isinstance(value, bool):
            raise ConfigurationImportError(f"{field} must be an integer.")
        return value

    @staticmethod
    def _unique_value(model, field: str, value: str, suffix: str) -> str:
        model_field = model._meta.get_field(field)
        max_length = model_field.max_length
        candidate = value
        number = 2
        while model.objects.filter(**{field: candidate}).exists():
            rendered_suffix = suffix.format(number=number)
            candidate = f"{value[: max_length - len(rendered_suffix)]}{rendered_suffix}"
            number += 1
        return candidate
