from collections.abc import Iterable
from typing import Any, cast

from django.utils import timezone

from governanceplatform.models import Sector
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

FORMAT_NAME = "governance-platform-sector-regulation"
FORMAT_VERSION = 1


def _translations(instance, field_names: tuple[str, ...]) -> list[dict[str, Any]]:
    return [
        {
            "language_code": translation.language_code,
            **{field_name: getattr(translation, field_name) for field_name in field_names},
        }
        for translation in sorted(
            instance.translations.all(),
            key=lambda item: item.language_code,
        )
    ]


def _key_map(instances: Iterable[Any], prefix: str) -> dict[int, str]:
    return {instance.pk: f"{prefix}_{position}" for position, instance in enumerate(instances, start=1)}


def _regulation_reference(regulation) -> dict[str, Any]:
    return {"translations": _translations(regulation, ("label",))}


class SectorRegulationConfigurationExporter:
    """Build a portable representation of one incident configuration."""

    def __init__(self, sector_regulation: SectorRegulation) -> None:
        self.sector_regulation = sector_regulation

    def export(self) -> dict[str, Any]:
        sector_regulation = self.sector_regulation
        linked_sectors = list(sector_regulation.sectors.select_related("parent").prefetch_related("translations").order_by("acronym", "pk"))
        workflow_links = list(
            SectorRegulationWorkflow.objects.filter(sector_regulation=sector_regulation)
            .select_related("workflow", "workflow__submission_email")
            .prefetch_related("workflow__translations")
            .order_by("position", "pk")
        )
        workflows = list(dict.fromkeys(link.workflow for link in workflow_links))
        question_options = list(
            QuestionOptions.objects.filter(
                report__in=workflows,
                deleted_date__isnull=True,
            )
            .select_related("report", "question", "category_option__question_category")
            .prefetch_related(
                "question__translations",
                "category_option__question_category__translations",
            )
            .order_by("report__name", "category_option__position", "position", "pk")
        )
        questions = self._unique(
            (option.question for option in question_options),
            key=lambda question: (question.reference, question.pk),
        )
        category_options = self._unique(
            (option.category_option for option in question_options),
            key=lambda option: (option.position, option.pk),
        )
        categories = self._unique(
            (option.question_category for option in category_options),
            key=lambda category: category.pk,
        )
        predefined_answers = list(
            PredefinedAnswer.objects.filter(question__in=questions)
            .prefetch_related("translations")
            .order_by("question__reference", "position", "pk")
        )
        conditional_questions = list(
            ConditionalQuestionOption.objects.filter(
                question_options__in=question_options,
                next_question_options__in=question_options,
                deleted_at__isnull=True,
            ).order_by("question_options_id", "predefined_answer_id", "pk")
        )
        reminder_emails = list(
            SectorRegulationWorkflowEmail.objects.filter(
                sector_regulation_workflow__in=workflow_links,
            )
            .select_related("sector_regulation_workflow", "email")
            .prefetch_related("translations", "email__translations")
            .order_by("sector_regulation_workflow__position", "pk")
        )
        emails = self._collect_emails(workflows, reminder_emails)
        impacts = self._collect_impacts()
        sectors = self._collect_sectors(linked_sectors, impacts)

        email_keys = _key_map(emails, "email")
        workflow_keys = _key_map(workflows, "report")
        category_keys = _key_map(categories, "category")
        category_option_keys = _key_map(category_options, "category_option")
        question_keys = _key_map(questions, "question")
        answer_keys = _key_map(predefined_answers, "answer")
        question_option_keys = _key_map(question_options, "question_option")

        return {
            "format": FORMAT_NAME,
            "format_version": FORMAT_VERSION,
            "exported_at": timezone.now().isoformat(),
            "sector_regulation": {
                "active": sector_regulation.active,
                "is_detection_date_needed": sector_regulation.is_detection_date_needed,
                "translations": _translations(sector_regulation, ("name",)),
                "regulation": _regulation_reference(sector_regulation.regulation),
                "regulator": {
                    "country": sector_regulation.regulator.country,
                    "address": sector_regulation.regulator.address,
                    "email_for_notification": (sector_regulation.regulator.email_for_notification),
                    "translations": _translations(
                        sector_regulation.regulator,
                        ("name", "full_name", "description"),
                    ),
                },
                "sectors": [self._sector_data(sector) for sector in linked_sectors],
                "opening_email": self._optional_key(email_keys, sector_regulation.opening_email_id),
                "closing_email": self._optional_key(email_keys, sector_regulation.closing_email_id),
                "report_status_changed_email": self._optional_key(
                    email_keys,
                    sector_regulation.report_status_changed_email_id,
                ),
            },
            "sectors": [self._sector_data(sector) for sector in sectors],
            "emails": [self._email_data(email, email_keys) for email in emails],
            "reports": [self._workflow_data(workflow, workflow_keys, email_keys) for workflow in workflows],
            "categories": [self._category_data(category, category_keys) for category in categories],
            "category_options": [self._category_option_data(option, category_option_keys, category_keys) for option in category_options],
            "questions": [
                self._question_data(
                    question,
                    question_keys,
                    predefined_answers,
                    answer_keys,
                )
                for question in questions
            ],
            "question_options": [
                self._question_option_data(
                    option,
                    question_option_keys,
                    workflow_keys,
                    question_keys,
                    category_option_keys,
                )
                for option in question_options
            ],
            "conditional_questions": [
                {
                    "question_option": question_option_keys[conditional.question_options_id],
                    "predefined_answer": answer_keys[conditional.predefined_answer_id],
                    "next_question_option": question_option_keys[conditional.next_question_options_id],
                    "creator_name": conditional.creator_name,
                }
                for conditional in conditional_questions
            ],
            "sector_regulation_reports": [
                {
                    "report": workflow_keys[link.workflow_id],
                    "position": link.position,
                    "delay_in_hours_before_deadline": link.delay_in_hours_before_deadline,
                    "trigger_event_before_deadline": link.trigger_event_before_deadline,
                    "reminder_emails": [
                        {
                            "email": email_keys[reminder.email_id],
                            "trigger_event": reminder.trigger_event,
                            "delay_in_hours": reminder.delay_in_hours,
                            "translations": _translations(reminder, ("headline",)),
                        }
                        for reminder in reminder_emails
                        if reminder.sector_regulation_workflow_id == link.pk
                    ],
                }
                for link in workflow_links
            ],
            "impacts": [self._impact_data(impact) for impact in impacts],
        }

    @staticmethod
    def _unique(instances: Iterable[Any], key) -> list[Any]:
        unique = {instance.pk: instance for instance in instances}
        return sorted(unique.values(), key=key)

    def _collect_emails(
        self,
        workflows: list[Workflow],
        reminder_emails: list[SectorRegulationWorkflowEmail],
    ) -> list[Email]:
        sector_regulation = self.sector_regulation
        email_ids = {
            email_id
            for email_id in (
                sector_regulation.opening_email_id,
                sector_regulation.closing_email_id,
                sector_regulation.report_status_changed_email_id,
                *(workflow.submission_email_id for workflow in workflows),
                *(reminder.email_id for reminder in reminder_emails),
            )
            if email_id is not None
        }
        return list(Email.objects.filter(pk__in=email_ids).prefetch_related("translations").order_by("name", "pk"))

    def _collect_impacts(self) -> list[Impact]:
        return list(
            Impact.objects.filter(regulations=self.sector_regulation.regulation)
            .distinct()
            .prefetch_related("translations", "regulations__translations", "sectors__translations")
            .order_by("pk")
        )

    @staticmethod
    def _collect_sectors(
        linked_sectors: list[Sector],
        impacts: list[Impact],
    ) -> list[Sector]:
        sector_ids = {sector.pk for sector in linked_sectors}
        sector_ids.update(sector.pk for impact in impacts for sector in impact.sectors.all())
        sectors: dict[int, Sector] = {}
        pending_ids = sector_ids
        while pending_ids:
            batch = list(Sector.objects.filter(pk__in=pending_ids).select_related("parent").prefetch_related("translations"))
            pending_ids = {sector.parent_id for sector in batch if sector.parent_id is not None and sector.parent_id not in sectors}
            sectors.update({sector.pk: sector for sector in batch})
        return sorted(sectors.values(), key=lambda sector: (sector.acronym, sector.pk))

    @staticmethod
    def _optional_key(keys: dict[int, str], object_id: int | None) -> str | None:
        return keys.get(object_id) if object_id is not None else None

    @staticmethod
    def _sector_data(sector: Sector) -> dict[str, Any]:
        return {
            "acronym": sector.acronym,
            "parent_acronym": (sector.parent.acronym if sector.parent else None),
            "translations": _translations(sector, ("name",)),
        }

    @staticmethod
    def _email_data(email: Email, keys: dict[int, str]) -> dict[str, Any]:
        return {
            "key": keys[email.pk],
            "name": email.name,
            "creator_name": email.creator_name,
            "translations": _translations(email, ("subject", "content")),
        }

    @staticmethod
    def _workflow_data(
        workflow: Workflow,
        workflow_keys: dict[int, str],
        email_keys: dict[int, str],
    ) -> dict[str, Any]:
        return {
            "key": workflow_keys[workflow.pk],
            "name": workflow.name,
            "is_impact_needed": workflow.is_impact_needed,
            "submission_email": SectorRegulationConfigurationExporter._optional_key(
                email_keys,
                workflow.submission_email_id,
            ),
            "creator_name": workflow.creator_name,
            "translations": _translations(workflow, ("label", "description")),
        }

    @staticmethod
    def _category_data(
        category: QuestionCategory,
        category_keys: dict[int, str],
    ) -> dict[str, Any]:
        return {
            "key": category_keys[category.pk],
            "creator_name": category.creator_name,
            "translations": _translations(category, ("label",)),
        }

    @staticmethod
    def _category_option_data(
        option: QuestionCategoryOptions,
        option_keys: dict[int, str],
        category_keys: dict[int, str],
    ) -> dict[str, Any]:
        return {
            "key": option_keys[option.pk],
            "category": category_keys[option.question_category_id],
            "position": option.position,
        }

    @staticmethod
    def _question_data(
        question: Question,
        question_keys: dict[int, str],
        predefined_answers: list[PredefinedAnswer],
        answer_keys: dict[int, str],
    ) -> dict[str, Any]:
        return {
            "key": question_keys[question.pk],
            "reference": question.reference,
            "question_type": question.question_type,
            "creator_name": question.creator_name,
            "translations": _translations(question, ("label", "tooltip")),
            "predefined_answers": [
                {
                    "key": answer_keys[answer.pk],
                    "position": answer.position,
                    "creator_name": answer.creator_name,
                    "translations": _translations(answer, ("predefined_answer",)),
                }
                for answer in predefined_answers
                if answer.question_id == question.pk
            ],
        }

    @staticmethod
    def _question_option_data(
        option: QuestionOptions,
        option_keys: dict[int, str],
        workflow_keys: dict[int, str],
        question_keys: dict[int, str],
        category_option_keys: dict[int, str],
    ) -> dict[str, Any]:
        return {
            "key": option_keys[option.pk],
            "report": workflow_keys[cast("int", option.report_id)],
            "question": question_keys[option.question_id],
            "category_option": category_option_keys[option.category_option_id],
            "position": option.position,
            "is_mandatory": option.is_mandatory,
            "is_conditional": option.is_conditional,
        }

    @staticmethod
    def _impact_data(impact: Impact) -> dict[str, Any]:
        return {
            "creator_name": impact.creator_name,
            "translations": _translations(impact, ("label", "headline")),
            "regulations": [
                _regulation_reference(regulation)
                for regulation in sorted(
                    impact.regulations.all(),
                    key=lambda item: item.pk,
                )
            ],
            "sectors": [
                sector.acronym
                for sector in sorted(
                    impact.sectors.all(),
                    key=lambda item: (item.acronym, item.pk),
                )
            ],
        }
