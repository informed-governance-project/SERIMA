from typing import TYPE_CHECKING, Any

from governanceplatform.models import Sector
from incidents.configuration_export import FORMAT_NAME, FORMAT_VERSION
from incidents.globals import (
    INCIDENT_EMAIL_TRIGGER_EVENT,
    QUESTION_TYPES,
    SECTOR_REGULATION_WORKFLOW_TRIGGER_EVENT,
)
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

if TYPE_CHECKING:
    from collections.abc import Iterable

INCIDENT_EMAIL_TRIGGER_VALUES = {value for value, _label in INCIDENT_EMAIL_TRIGGER_EVENT}
QUESTION_TYPE_VALUES = {value for value, _label in QUESTION_TYPES}
WORKFLOW_TRIGGER_VALUES = {value for value, _label in SECTOR_REGULATION_WORKFLOW_TRIGGER_EVENT}


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
        reuse_all: bool = False,
    ) -> None:
        self.data = data
        self.target = target
        self.create_all = create_all
        self.reuse_all = reuse_all
        self.creator = target.regulator
        self.creator_name = target.regulator.safe_translation_getter("name", any_language=True) or str(target.regulator)
        self.reused_question_keys: set[str] = set()
        self.reused_answer_keys: set[str] = set()
        self.reused_email_keys: set[str] = set()
        self.reused_report_keys: set[str] = set()
        self.reused_category_keys: set[str] = set()
        self.reused_category_option_keys: set[str] = set()
        self.reused_question_option_keys: set[str] = set()
        self.reused_question_options: dict[str, QuestionOptions] = {}
        self.skipped_answer_keys: set[str] = set()
        self.sectors_by_acronym: dict[str, list[Sector]] | None = None

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
        sector_data = self._sector_catalog()

        sector_regulation_data = self.data["sector_regulation"]
        for field in (
            "opening_email",
            "closing_email",
            "report_status_changed_email",
        ):
            self._optional_reference(
                email_data,
                sector_regulation_data.get(field),
                "email",
            )

        for item in report_data.values():
            self._optional_reference(
                email_data,
                item.get("submission_email"),
                "email",
            )
        for item in category_option_data.values():
            self._reference(
                category_data,
                item.get("category"),
                "category",
            )
        for item in question_option_data.values():
            self._reference(report_data, item.get("report"), "report")
            self._reference(question_data, item.get("question"), "question")
            self._reference(
                category_option_data,
                item.get("category_option"),
                "category option",
            )

        answer_data = {}
        for question_key, item in question_data.items():
            answer_items = item.get("predefined_answers", [])
            if not isinstance(answer_items, list):
                raise ConfigurationImportError(f"predefined_answers for question {question_key!r} must be a list.")
            for answer_item in answer_items:
                if not isinstance(answer_item, dict):
                    raise ConfigurationImportError(f"Invalid predefined answer for question {question_key!r}.")
                answer_key = self._string(answer_item, "key")
                if answer_key in answer_data:
                    raise ConfigurationImportError(f"Duplicate predefined answer key {answer_key!r}.")
                answer_data[answer_key] = answer_item

        conditional_items = self.data.get("conditional_questions", [])
        if not isinstance(conditional_items, list):
            raise ConfigurationImportError("conditional_questions must be a list.")
        for item in conditional_items:
            if not isinstance(item, dict):
                raise ConfigurationImportError("Invalid conditional question.")
            self._reference(
                question_option_data,
                item.get("question_option"),
                "question option",
            )
            self._reference(
                answer_data,
                item.get("predefined_answer"),
                "predefined answer",
            )
            self._reference(
                question_option_data,
                item.get("next_question_option"),
                "next question option",
            )

        report_link_items = self.data.get("sector_regulation_reports", [])
        if not isinstance(report_link_items, list):
            raise ConfigurationImportError("sector_regulation_reports must be a list.")
        for item in report_link_items:
            if not isinstance(item, dict):
                raise ConfigurationImportError("Invalid sector regulation report.")
            self._reference(report_data, item.get("report"), "report")
            reminder_items = item.get("reminder_emails", [])
            if not isinstance(reminder_items, list):
                raise ConfigurationImportError("reminder_emails must be a list.")
            for reminder_item in reminder_items:
                if not isinstance(reminder_item, dict):
                    raise ConfigurationImportError("Invalid reminder email.")
                self._reference(
                    email_data,
                    reminder_item.get("email"),
                    "email",
                )

        emails = self._import_emails(email_data)
        categories = self._import_categories(category_data)
        category_options = self._import_category_options(
            category_option_data,
            categories,
        )
        questions, answers = self._import_questions(question_data)
        reports = self._import_reports(
            report_data,
            emails,
            question_option_data,
            questions,
            category_options,
        )
        question_options = self._import_question_options(
            question_option_data,
            reports,
            questions,
            category_options,
        )
        conditional_created, conditional_reused = self._import_conditional_questions(
            answers,
            question_options,
        )
        report_link_count, reminder_count = self._import_report_links(
            reports,
            emails,
        )
        sectors_created, sectors_reused = self._import_sectors(sector_data)
        impacts_created, impacts_reused = self._import_impacts()
        sector_count = self._update_target(emails)

        return {
            "emails_created": len(emails) - len(self.reused_email_keys),
            "emails_reused": len(self.reused_email_keys),
            "reports_created": len(reports) - len(self.reused_report_keys),
            "reports_reused": len(self.reused_report_keys),
            "categories_created": len(categories) - len(self.reused_category_keys),
            "categories_reused": len(self.reused_category_keys),
            "category_options_created": len(category_options) - len(self.reused_category_option_keys),
            "category_options_reused": len(self.reused_category_option_keys),
            "questions_created": len(questions) - len(self.reused_question_keys),
            "questions_reused": len(self.reused_question_keys),
            "predefined_answers_created": len(answers) - len(self.reused_answer_keys),
            "predefined_answers_reused": len(self.reused_answer_keys),
            "predefined_answers_skipped": len(self.skipped_answer_keys),
            "question_options_created": len(question_options) - len(self.reused_question_option_keys),
            "question_options_reused": len(self.reused_question_option_keys),
            "conditional_questions_created": conditional_created,
            "conditional_questions_reused": conditional_reused,
            "report_links": report_link_count,
            "reminder_emails": reminder_count,
            "impacts_created": impacts_created,
            "impacts_reused": impacts_reused,
            "sectors_created": sectors_created,
            "sectors_reused": sectors_reused,
            "sectors_linked": sector_count,
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

    def _sector_catalog(self) -> dict[str, dict[str, Any]]:
        items = self.data.get(
            "sectors",
            self.data["sector_regulation"].get("sectors", []),
        )
        if not isinstance(items, list):
            raise ConfigurationImportError("sectors must be a list.")
        catalog: dict[str, dict[str, Any]] = {}
        max_length = Sector._meta.get_field("acronym").max_length
        for item in items:
            if not isinstance(item, dict):
                raise ConfigurationImportError("Every sector must be an object.")
            acronym = self._string(item, "acronym")
            if not acronym or len(acronym) > max_length:
                raise ConfigurationImportError(f"Sector acronym {acronym!r} must contain between 1 and {max_length} characters.")
            if acronym in catalog:
                raise ConfigurationImportError(f"Duplicate sector acronym {acronym!r}.")
            parent_acronym = item.get("parent_acronym")
            if parent_acronym is not None and not isinstance(parent_acronym, str):
                raise ConfigurationImportError("parent_acronym must be a string or null.")
            catalog[acronym] = item
        return catalog

    def _import_emails(
        self,
        catalog: dict[str, dict[str, Any]],
    ) -> dict[str, Email]:
        imported = {}
        for key, item in catalog.items():
            if self.reuse_all:
                existing = next(
                    (
                        email
                        for email in Email.objects.filter(
                            name=self._string(item, "name"),
                        )
                        .prefetch_related("translations")
                        .order_by("pk")
                        if self._translations_match(
                            email,
                            item.get("translations"),
                            ("subject", "content"),
                        )
                    ),
                    None,
                )
                if existing is not None:
                    imported[key] = existing
                    self.reused_email_keys.add(key)
                    continue
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
        question_option_catalog: dict[str, dict[str, Any]],
        questions: dict[str, Question],
        category_options: dict[str, QuestionCategoryOptions],
    ) -> dict[str, Workflow]:
        imported = {}
        for key, item in catalog.items():
            original_name = self._string(item, "name")
            if self.reuse_all:
                existing = (
                    Workflow.objects.filter(name=original_name).select_related("submission_email").prefetch_related("translations").first()
                )
                report_matches = (
                    existing is not None
                    and existing.is_impact_needed == self._boolean(item, "is_impact_needed", default=False)
                    and existing.submission_email
                    == self._optional_reference(
                        emails,
                        item.get("submission_email"),
                        "email",
                    )
                    and self._translations_match(
                        existing,
                        item.get("translations"),
                        ("label", "description"),
                    )
                )
                expected_options = [
                    (option_key, option_item)
                    for option_key, option_item in question_option_catalog.items()
                    if option_item.get("report") == key
                ]
                available_options = (
                    list(
                        QuestionOptions.objects.filter(
                            report=existing,
                            deleted_date__isnull=True,
                        )
                        .select_related("question", "category_option")
                        .order_by("pk")
                    )
                    if existing is not None
                    else []
                )
                report_matches = report_matches and len(available_options) == len(expected_options)
                reused_options: dict[str, QuestionOptions] = {}
                for option_key, option_item in expected_options:
                    question = self._reference(
                        questions,
                        option_item.get("question"),
                        "question",
                    )
                    category_option = self._reference(
                        category_options,
                        option_item.get("category_option"),
                        "category option",
                    )
                    match = next(
                        (
                            option
                            for option in available_options
                            if option.question == question
                            and option.category_option == category_option
                            and option.position == self._integer(option_item, "position")
                            and option.is_mandatory
                            == self._boolean(
                                option_item,
                                "is_mandatory",
                                default=False,
                            )
                            and option.is_conditional
                            == self._boolean(
                                option_item,
                                "is_conditional",
                                default=False,
                            )
                        ),
                        None,
                    )
                    if match is None:
                        report_matches = False
                        break
                    reused_options[option_key] = match
                    available_options.remove(match)
                if existing is not None and report_matches:
                    imported[key] = existing
                    self.reused_report_keys.add(key)
                    self.reused_question_options.update(reused_options)
                    self.reused_question_option_keys.update(reused_options)
                    continue
            name = self._unique_value(
                Workflow,
                "name",
                original_name,
                " (import {number})",
            )
            report = Workflow.objects.create(
                name=name,
                is_impact_needed=self._boolean(
                    item,
                    "is_impact_needed",
                    default=False,
                ),
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
            if self.reuse_all:
                existing = next(
                    (
                        category
                        for category in QuestionCategory.objects.prefetch_related(
                            "translations",
                        ).order_by("pk")
                        if self._translations_match(
                            category,
                            item.get("translations"),
                            ("label",),
                        )
                    ),
                    None,
                )
                if existing is not None:
                    imported[key] = existing
                    self.reused_category_keys.add(key)
                    continue
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
            category = self._reference(
                categories,
                item.get("category"),
                "category",
            )
            position = self._integer(item, "position")
            if self.reuse_all:
                existing = QuestionCategoryOptions.objects.filter(
                    question_category=category,
                    position=position,
                ).first()
                if existing is not None:
                    imported[key] = existing
                    self.reused_category_option_keys.add(key)
                    continue
            imported[key] = QuestionCategoryOptions.objects.create(
                question_category=category,
                position=position,
            )
        return imported

    def _import_questions(
        self,
        catalog: dict[str, dict[str, Any]],
    ) -> tuple[dict[str, Question], dict[str, PredefinedAnswer]]:
        questions: dict[str, Question] = {}
        answers: dict[str, PredefinedAnswer] = {}
        known_answer_keys: set[str] = set()
        for key, item in catalog.items():
            reference = self._string(item, "reference")
            answer_items = item.get("predefined_answers", [])
            if not isinstance(answer_items, list):
                raise ConfigurationImportError(f"predefined_answers for question {key!r} must be a list.")
            validated_answers = []
            for answer_item in answer_items:
                if not isinstance(answer_item, dict):
                    raise ConfigurationImportError(f"Invalid predefined answer for question {key!r}.")
                answer_key = self._string(answer_item, "key")
                if answer_key in known_answer_keys:
                    raise ConfigurationImportError(f"Duplicate predefined answer key {answer_key!r}.")
                known_answer_keys.add(answer_key)
                validated_answers.append((answer_key, answer_item))

            existing = (
                Question.objects.filter(reference=reference)
                .prefetch_related(
                    "translations",
                    "predefinedanswer_set__translations",
                )
                .first()
            )
            if existing is not None and self.reuse_all:
                available_answers = list(existing.predefinedanswer_set.all())
                existing_answers: dict[str, PredefinedAnswer] = {}
                question_matches = (
                    existing.question_type
                    == self._choice(
                        item,
                        "question_type",
                        QUESTION_TYPE_VALUES,
                    )
                    and self._translations_match(
                        existing,
                        item.get("translations"),
                        ("label", "tooltip"),
                    )
                    and len(available_answers) == len(validated_answers)
                )
                for answer_key, answer_item in validated_answers:
                    match = next(
                        (
                            answer
                            for answer in available_answers
                            if answer.position
                            == self._optional_integer(
                                answer_item,
                                "position",
                            )
                            and self._translations_match(
                                answer,
                                answer_item.get("translations"),
                                ("predefined_answer",),
                            )
                        ),
                        None,
                    )
                    if match is None:
                        question_matches = False
                        break
                    existing_answers[answer_key] = match
                    available_answers.remove(match)
                if question_matches:
                    questions[key] = existing
                    answers.update(existing_answers)
                    self.reused_question_keys.add(key)
                    self.reused_answer_keys.update(existing_answers)
                    continue
            if existing is not None and not self.create_all and not self.reuse_all:
                questions[key] = existing
                self.reused_question_keys.add(key)
                self.skipped_answer_keys.update(answer_key for answer_key, _answer_item in validated_answers)
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
                question_type=self._choice(
                    item,
                    "question_type",
                    QUESTION_TYPE_VALUES,
                ),
                creator=self.creator,
                creator_name=self.creator_name,
            )
            self._set_translations(
                question,
                item.get("translations"),
                ("label", "tooltip"),
            )
            questions[key] = question

            for answer_key, answer_item in validated_answers:
                answer = PredefinedAnswer.objects.create(
                    question=question,
                    position=self._optional_integer(answer_item, "position"),
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
            if key in self.reused_question_options:
                imported[key] = self.reused_question_options[key]
                continue
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
                is_mandatory=self._boolean(
                    item,
                    "is_mandatory",
                    default=False,
                ),
                is_conditional=self._boolean(
                    item,
                    "is_conditional",
                    default=False,
                ),
            )
        return imported

    def _import_conditional_questions(
        self,
        answers: dict[str, PredefinedAnswer],
        question_options: dict[str, QuestionOptions],
    ) -> tuple[int, int]:
        items = self.data.get("conditional_questions", [])
        if not isinstance(items, list):
            raise ConfigurationImportError("conditional_questions must be a list.")
        count = 0
        reused_count = 0
        for item in items:
            if not isinstance(item, dict):
                raise ConfigurationImportError("Invalid conditional question.")
            answer_key = item.get("predefined_answer")
            if answer_key in self.skipped_answer_keys:
                continue
            question_option = self._reference(
                question_options,
                item.get("question_option"),
                "question option",
            )
            predefined_answer = self._reference(
                answers,
                answer_key,
                "predefined answer",
            )
            next_question_option = self._reference(
                question_options,
                item.get("next_question_option"),
                "next question option",
            )
            if (
                self.reuse_all
                and ConditionalQuestionOption.objects.filter(
                    question_options=question_option,
                    predefined_answer=predefined_answer,
                    next_question_options=next_question_option,
                    deleted_at__isnull=True,
                ).exists()
            ):
                reused_count += 1
                continue
            ConditionalQuestionOption.objects.create(
                question_options=question_option,
                predefined_answer=predefined_answer,
                next_question_options=next_question_option,
                creator=self.creator,
                creator_name=self.creator_name,
            )
            count += 1
        return count, reused_count

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
                position=self._optional_integer(item, "position"),
                delay_in_hours_before_deadline=self._integer(
                    item,
                    "delay_in_hours_before_deadline",
                ),
                trigger_event_before_deadline=self._choice(
                    item,
                    "trigger_event_before_deadline",
                    WORKFLOW_TRIGGER_VALUES,
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
                    trigger_event=self._choice(
                        reminder_item,
                        "trigger_event",
                        INCIDENT_EMAIL_TRIGGER_VALUES,
                    ),
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

    def _import_sectors(
        self,
        catalog: dict[str, dict[str, Any]],
    ) -> tuple[int, int]:
        self._load_sectors()
        assert self.sectors_by_acronym is not None
        pending = {}
        reused_count = 0
        for acronym, item in catalog.items():
            matches = self.sectors_by_acronym.get(acronym, [])
            if len(matches) > 1:
                raise ConfigurationImportError(f"Sector acronym {acronym!r} is ambiguous.")
            if matches:
                reused_count += 1
            else:
                pending[acronym] = item

        created_count = 0
        while pending:
            imported_in_pass = False
            for acronym, item in list(pending.items()):
                parent_acronym = item.get("parent_acronym")
                parent = None
                if parent_acronym is not None:
                    parent_matches = self.sectors_by_acronym.get(parent_acronym, [])
                    if len(parent_matches) > 1:
                        raise ConfigurationImportError(f"Sector acronym {parent_acronym!r} is ambiguous.")
                    if not parent_matches:
                        if parent_acronym in pending:
                            continue
                        raise ConfigurationImportError(f"Parent sector with acronym {parent_acronym!r} does not exist.")
                    parent = parent_matches[0]

                sector = Sector.objects.create(
                    acronym=acronym,
                    parent=parent,
                    creator=self.creator,
                    creator_name=self.creator_name,
                )
                self._set_translations(
                    sector,
                    item.get("translations"),
                    ("name",),
                )
                self.sectors_by_acronym[acronym] = [sector]
                del pending[acronym]
                created_count += 1
                imported_in_pass = True

            if not imported_in_pass:
                raise ConfigurationImportError("Sector parent relationships contain a cycle.")

        return created_count, reused_count

    def _import_impacts(self) -> tuple[int, int]:
        items = self.data.get("impacts", [])
        if not isinstance(items, list):
            raise ConfigurationImportError("impacts must be a list.")
        created_count = 0
        reused_count = 0
        for item in items:
            if not isinstance(item, dict):
                raise ConfigurationImportError("Invalid impact.")
            sector_acronyms = item.get("sectors", [])
            if not isinstance(sector_acronyms, list):
                raise ConfigurationImportError("Impact sectors must be a list.")
            sectors = self._resolve_sectors(sector_acronyms)
            if self.reuse_all:
                regulation_ids = {self.target.regulation_id}
                sector_ids = {sector.pk for sector in sectors}
                existing = next(
                    (
                        impact
                        for impact in Impact.objects.filter(
                            regulations=self.target.regulation,
                        )
                        .distinct()
                        .prefetch_related(
                            "translations",
                            "regulations",
                            "sectors",
                        )
                        .order_by("pk")
                        if {regulation.pk for regulation in impact.regulations.all()} == regulation_ids
                        and {sector.pk for sector in impact.sectors.all()} == sector_ids
                        and self._translations_match(
                            impact,
                            item.get("translations"),
                            ("label", "headline"),
                        )
                    ),
                    None,
                )
                if existing is not None:
                    reused_count += 1
                    continue
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
            impact.sectors.set(sectors)
            created_count += 1
        return created_count, reused_count

    def _update_target(self, emails: dict[str, Email]) -> int:
        item = self.data["sector_regulation"]
        self.target.active = self._boolean(item, "active", default=True)
        self.target.is_detection_date_needed = self._boolean(
            item,
            "is_detection_date_needed",
            default=False,
        )
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
        acronyms = []
        for sector_item in sector_items:
            if not isinstance(sector_item, dict):
                raise ConfigurationImportError("Every sector_regulation sector must be an object.")
            acronyms.append(self._string(sector_item, "acronym"))
        self.target.sectors.set(self._resolve_sectors(acronyms))
        return len(acronyms)

    @classmethod
    def _set_translations(
        cls,
        instance,
        translations: Any,
        fields: tuple[str, ...],
    ) -> None:
        values_by_language = cls._translation_values(translations, fields)
        for language_code, values in values_by_language.items():
            instance.set_current_language(language_code)
            for field, value in zip(fields, values, strict=True):
                setattr(instance, field, value)
            instance.save()

    @classmethod
    def _translations_match(
        cls,
        instance,
        translations: Any,
        fields: tuple[str, ...],
    ) -> bool:
        expected = cls._translation_values(translations, fields)
        actual = {
            translation.language_code: tuple(getattr(translation, field) for field in fields) for translation in instance.translations.all()
        }
        return actual == expected

    @staticmethod
    def _translation_values(
        translations: Any,
        fields: tuple[str, ...],
    ) -> dict[str, tuple[Any, ...]]:
        if not isinstance(translations, list) or not translations:
            raise ConfigurationImportError("Missing translations.")
        values_by_language = {}
        for translation in translations:
            if not isinstance(translation, dict):
                raise ConfigurationImportError("Invalid translation object.")
            language_code = translation.get("language_code")
            if not isinstance(language_code, str) or not language_code:
                raise ConfigurationImportError("Every translation requires a language_code.")
            if language_code in values_by_language:
                raise ConfigurationImportError(f"Duplicate translation language {language_code!r}.")
            values = []
            for field in fields:
                if field not in translation:
                    raise ConfigurationImportError(f"Translation {language_code!r} is missing {field!r}.")
                values.append(translation[field])
            values_by_language[language_code] = tuple(values)
        return values_by_language

    def _resolve_sectors(self, acronyms: Iterable[Any]) -> list[Sector]:
        self._load_sectors()
        assert self.sectors_by_acronym is not None

        sectors = []
        for acronym in acronyms:
            if not isinstance(acronym, str):
                raise ConfigurationImportError("Sector acronyms must be strings.")
            matches = self.sectors_by_acronym.get(acronym, [])
            if not matches:
                raise ConfigurationImportError(f"Sector with acronym {acronym!r} does not exist.")
            if len(matches) > 1:
                raise ConfigurationImportError(f"Sector acronym {acronym!r} is ambiguous.")
            sectors.append(matches[0])
        return sectors

    def _load_sectors(self) -> None:
        if self.sectors_by_acronym is None:
            self.sectors_by_acronym = {}
            for sector in Sector.objects.all().order_by("pk"):
                self.sectors_by_acronym.setdefault(sector.acronym, []).append(sector)

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
    def _optional_integer(item: dict[str, Any], field: str) -> int | None:
        value = item.get(field)
        if value is None:
            return None
        if not isinstance(value, int) or isinstance(value, bool):
            raise ConfigurationImportError(f"{field} must be an integer or null.")
        return value

    @staticmethod
    def _boolean(
        item: dict[str, Any],
        field: str,
        *,
        default: bool,
    ) -> bool:
        value = item.get(field, default)
        if not isinstance(value, bool):
            raise ConfigurationImportError(f"{field} must be a boolean.")
        return value

    @classmethod
    def _choice(
        cls,
        item: dict[str, Any],
        field: str,
        choices: set[str],
    ) -> str:
        value = cls._string(item, field)
        if value not in choices:
            raise ConfigurationImportError(f"{field} contains unsupported value {value!r}.")
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
