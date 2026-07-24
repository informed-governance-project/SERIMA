from dataclasses import dataclass

import tablib
from django.db.models import Prefetch
from import_export import fields
from import_export_extensions.resources import CeleryModelResource, TaskState

from incidents.models import (
    ConditionalQuestionOption,
    PredefinedAnswer,
    QuestionOptions,
    Workflow,
)


@dataclass(frozen=True)
class WorkflowExportRow:
    workflow: Workflow
    question_options: QuestionOptions | None = None
    predefined_answer: PredefinedAnswer | None = None


class WorkflowResource(CeleryModelResource):
    """Export a complete workflow, flattened to predefined-answer rows."""

    workflow_id = fields.Field(column_name="workflow_id", readonly=True)
    workflow_name = fields.Field(column_name="workflow_name", readonly=True)
    workflow_label = fields.Field(column_name="workflow_label", readonly=True)
    workflow_description = fields.Field(column_name="workflow_description", readonly=True)
    workflow_is_impact_needed = fields.Field(column_name="workflow_is_impact_needed", readonly=True)
    submission_email_id = fields.Field(column_name="submission_email_id", readonly=True)
    submission_email_name = fields.Field(column_name="submission_email_name", readonly=True)
    creator_id = fields.Field(column_name="creator_id", readonly=True)
    creator_name = fields.Field(column_name="creator_name", readonly=True)

    category_options_id = fields.Field(column_name="category_options_id", readonly=True)
    category_id = fields.Field(column_name="category_id", readonly=True)
    category_position = fields.Field(column_name="category_position", readonly=True)
    category_label = fields.Field(column_name="category_label", readonly=True)

    question_options_id = fields.Field(column_name="question_options_id", readonly=True)
    question_position = fields.Field(column_name="question_position", readonly=True)
    question_id = fields.Field(column_name="question_id", readonly=True)
    question_reference = fields.Field(column_name="question_reference", readonly=True)
    question_type = fields.Field(column_name="question_type", readonly=True)
    question_type_label = fields.Field(column_name="question_type_label", readonly=True)
    question_label = fields.Field(column_name="question_label", readonly=True)
    question_tooltip = fields.Field(column_name="question_tooltip", readonly=True)
    question_is_mandatory = fields.Field(column_name="question_is_mandatory", readonly=True)
    question_is_conditional = fields.Field(column_name="question_is_conditional", readonly=True)

    predefined_answer_id = fields.Field(column_name="predefined_answer_id", readonly=True)
    predefined_answer_position = fields.Field(column_name="predefined_answer_position", readonly=True)
    predefined_answer = fields.Field(column_name="predefined_answer", readonly=True)

    conditional_next_question_options_id = fields.Field(
        column_name="conditional_next_question_options_id",
        readonly=True,
    )
    conditional_next_question_reference = fields.Field(
        column_name="conditional_next_question_reference",
        readonly=True,
    )
    conditional_next_question_label = fields.Field(
        column_name="conditional_next_question_label",
        readonly=True,
    )

    class Meta:
        model = Workflow
        fields = (
            "workflow_id",
            "workflow_name",
            "workflow_label",
            "workflow_description",
            "workflow_is_impact_needed",
            "submission_email_id",
            "submission_email_name",
            "creator_id",
            "creator_name",
            "category_options_id",
            "category_id",
            "category_position",
            "category_label",
            "question_options_id",
            "question_position",
            "question_id",
            "question_reference",
            "question_type",
            "question_type_label",
            "question_label",
            "question_tooltip",
            "question_is_mandatory",
            "question_is_conditional",
            "predefined_answer_id",
            "predefined_answer_position",
            "predefined_answer",
            "conditional_next_question_options_id",
            "conditional_next_question_reference",
            "conditional_next_question_label",
        )
        export_order = fields

    def __init__(self, *args, language_code=None, **kwargs):
        self.language_code = language_code
        super().__init__(*args, **kwargs)

    def _translated_value(self, obj, field_name):
        if obj is None:
            return ""
        return (
            obj.safe_translation_getter(
                field_name,
                language_code=self.language_code,
                any_language=True,
            )
            or ""
        )

    @classmethod
    def _prepare_export_queryset(cls, queryset):
        active_conditional_triggers = (
            ConditionalQuestionOption.objects.filter(deleted_at__isnull=True)
            .select_related("next_question_options__question")
            .prefetch_related("next_question_options__question__translations")
        )
        predefined_answers = PredefinedAnswer.objects.order_by("position", "pk").prefetch_related(
            "translations",
            Prefetch(
                "conditional_questions",
                queryset=active_conditional_triggers,
                to_attr="export_conditional_triggers",
            ),
        )
        question_options = (
            QuestionOptions.objects.filter(deleted_date__isnull=True)
            .order_by("category_option__position", "position", "pk")
            .select_related("question", "category_option__question_category")
            .prefetch_related(
                "question__translations",
                "category_option__question_category__translations",
                Prefetch(
                    "question__predefinedanswer_set",
                    queryset=predefined_answers,
                    to_attr="export_predefined_answers",
                ),
            )
        )
        return queryset.select_related("submission_email", "creator").prefetch_related(
            "translations",
            "creator__translations",
            Prefetch(
                "questionoptions_set",
                queryset=question_options,
                to_attr="export_question_options",
            ),
        )

    @classmethod
    def get_model_queryset(cls):
        return Workflow.objects.order_by("name", "pk")

    def _export(self, queryset, **kwargs):
        """Flatten workflows without losing questions which have no choices."""
        queryset = self._prepare_export_queryset(queryset)
        self.before_export(queryset, **kwargs)
        selected_fields = kwargs.get("export_fields")
        dataset = tablib.Dataset(headers=self.get_export_headers(selected_fields=selected_fields))

        for workflow in self.iter_queryset(queryset):
            question_options = workflow.export_question_options
            if not question_options:
                dataset.append(
                    self._export_resource(
                        WorkflowExportRow(workflow=workflow),
                        selected_fields=selected_fields,
                        **kwargs,
                    )
                )

            for option in question_options:
                predefined_answers = option.question.export_predefined_answers
                if not predefined_answers:
                    predefined_answers = [None]
                for answer in predefined_answers:
                    dataset.append(
                        self._export_resource(
                            WorkflowExportRow(
                                workflow=workflow,
                                question_options=option,
                                predefined_answer=answer,
                            ),
                            selected_fields=selected_fields,
                            **kwargs,
                        )
                    )
            self.update_task_state(state=TaskState.EXPORTING.name)

        self.after_export(queryset, dataset, **kwargs)
        dataset.title = self.generate_dataset_title()
        return dataset

    def dehydrate_workflow_id(self, row):
        return row.workflow.pk

    def dehydrate_workflow_name(self, row):
        return row.workflow.name

    def dehydrate_workflow_label(self, row):
        return self._translated_value(row.workflow, "label")

    def dehydrate_workflow_description(self, row):
        return self._translated_value(row.workflow, "description")

    def dehydrate_workflow_is_impact_needed(self, row):
        return row.workflow.is_impact_needed

    def dehydrate_submission_email_id(self, row):
        return row.workflow.submission_email_id or ""

    def dehydrate_submission_email_name(self, row):
        return row.workflow.submission_email.name if row.workflow.submission_email else ""

    def dehydrate_creator_id(self, row):
        return row.workflow.creator_id or ""

    def dehydrate_creator_name(self, row):
        return self._translated_value(row.workflow.creator, "name")

    def dehydrate_category_options_id(self, row):
        return row.question_options.category_option_id if row.question_options else ""

    def dehydrate_category_id(self, row):
        if not row.question_options:
            return ""
        return row.question_options.category_option.question_category_id

    def dehydrate_category_position(self, row):
        return row.question_options.category_option.position if row.question_options else ""

    def dehydrate_category_label(self, row):
        if not row.question_options:
            return ""
        return self._translated_value(row.question_options.category_option.question_category, "label")

    def dehydrate_question_options_id(self, row):
        return row.question_options.pk if row.question_options else ""

    def dehydrate_question_position(self, row):
        return row.question_options.position if row.question_options else ""

    def dehydrate_question_id(self, row):
        return row.question_options.question_id if row.question_options else ""

    def dehydrate_question_reference(self, row):
        return row.question_options.question.reference if row.question_options else ""

    def dehydrate_question_type(self, row):
        return row.question_options.question.question_type if row.question_options else ""

    def dehydrate_question_type_label(self, row):
        return row.question_options.question.get_question_type_display() if row.question_options else ""

    def dehydrate_question_label(self, row):
        return self._translated_value(row.question_options.question, "label") if row.question_options else ""

    def dehydrate_question_tooltip(self, row):
        return self._translated_value(row.question_options.question, "tooltip") if row.question_options else ""

    def dehydrate_question_is_mandatory(self, row):
        return row.question_options.is_mandatory if row.question_options else ""

    def dehydrate_question_is_conditional(self, row):
        return row.question_options.is_conditional if row.question_options else ""

    def dehydrate_predefined_answer_id(self, row):
        return row.predefined_answer.pk if row.predefined_answer else ""

    def dehydrate_predefined_answer_position(self, row):
        return row.predefined_answer.position if row.predefined_answer else ""

    def dehydrate_predefined_answer(self, row):
        return self._translated_value(row.predefined_answer, "predefined_answer")

    @staticmethod
    def _conditional_trigger(row):
        if not row.question_options or not row.predefined_answer:
            return None
        return next(
            (
                trigger
                for trigger in row.predefined_answer.export_conditional_triggers
                if trigger.question_options_id == row.question_options.pk
            ),
            None,
        )

    def dehydrate_conditional_next_question_options_id(self, row):
        trigger = self._conditional_trigger(row)
        return trigger.next_question_options_id if trigger else ""

    def dehydrate_conditional_next_question_reference(self, row):
        trigger = self._conditional_trigger(row)
        return trigger.next_question_options.question.reference if trigger else ""

    def dehydrate_conditional_next_question_label(self, row):
        trigger = self._conditional_trigger(row)
        return self._translated_value(trigger.next_question_options.question, "label") if trigger else ""
