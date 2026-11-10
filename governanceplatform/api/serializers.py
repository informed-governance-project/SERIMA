from __future__ import annotations

from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from governanceplatform.models import User
from incidents.models import Answer, Impact, Incident, IncidentWorkflow
from reporting.models import Project
from securityobjectives.globals import OPERATOR_STATUS
from securityobjectives.models import SecurityMeasureAnswer, StandardAnswer


class CurrentUserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ("email", "first_name", "last_name")
        read_only_fields = fields


class IncidentAnswerSerializer(serializers.ModelSerializer):
    category = serializers.StringRelatedField(source="question_options.category_option")
    question_reference = serializers.CharField(source="question_options.question.reference", read_only=True)
    question = serializers.StringRelatedField(source="question_options.question")
    question_type = serializers.CharField(source="question_options.question.question_type", read_only=True)
    choices = serializers.StringRelatedField(source="predefined_answers", many=True)

    class Meta:
        model = Answer
        fields = ("category", "question_reference", "question", "question_type", "choices", "answer")
        read_only_fields = fields


class ImpactSerializer(serializers.ModelSerializer):
    headline = serializers.CharField(read_only=True, allow_null=True)
    label = serializers.CharField(read_only=True)

    class Meta:
        model = Impact
        fields = ("headline", "label")
        read_only_fields = fields


class IncidentReportSerializer(serializers.ModelSerializer):
    report = serializers.StringRelatedField(source="workflow")
    detection_date = serializers.DateTimeField(source="report_timeline.incident_detection_date", allow_null=True)
    starting_date = serializers.DateTimeField(source="report_timeline.incident_starting_date", allow_null=True)
    resolution_date = serializers.DateTimeField(source="report_timeline.incident_resolution_date", allow_null=True)

    class Meta:
        model = IncidentWorkflow
        fields: tuple[str, ...] = ("report", "timestamp", "review_status", "detection_date", "starting_date", "resolution_date")
        read_only_fields = fields


class IncidentReportDetailSerializer(IncidentReportSerializer):
    impacts = ImpactSerializer(many=True, read_only=True)
    answers = serializers.SerializerMethodField()

    @extend_schema_field(serializers.DictField(child=IncidentAnswerSerializer()))
    def get_answers(self, obj: IncidentWorkflow) -> dict[str, dict]:
        answers = IncidentAnswerSerializer(obj.answer_set.all(), many=True, context=self.context).data
        return {answer["question_reference"]: answer for answer in answers}

    class Meta(IncidentReportSerializer.Meta):
        fields = (*IncidentReportSerializer.Meta.fields, "impacts", "answers")
        read_only_fields = fields


class IncidentSerializer(serializers.ModelSerializer):
    reports = IncidentReportSerializer(source="incidentworkflow_set", many=True, read_only=True)

    class Meta:
        model = Incident
        fields = (
            "incident_id",
            "company_name",
            "incident_notification_date",
            "incident_detection_date",
            "incident_last_update",
            "incident_status",
            "is_significative_impact",
            "incident_reference",
            "complaint_reference",
            "reports",
        )
        read_only_fields = fields


class IncidentDetailSerializer(IncidentSerializer):
    reports = IncidentReportDetailSerializer(source="incidentworkflow_set", many=True, read_only=True)


class SecurityMeasureAnswerSerializer(serializers.ModelSerializer):
    measure = serializers.StringRelatedField(source="security_measure")

    class Meta:
        model = SecurityMeasureAnswer
        fields = ("measure", "justification", "is_implemented")
        read_only_fields = fields


class DeclarationSerializer(serializers.ModelSerializer):
    reference = serializers.CharField(source="group.group_id", read_only=True)
    standard = serializers.StringRelatedField()
    company = serializers.StringRelatedField(source="submitter_company")
    status = serializers.SerializerMethodField()

    @extend_schema_field(serializers.CharField())
    def get_status(self, obj: StandardAnswer) -> str:
        return obj.status if self.context["request"].user.is_regulator() else OPERATOR_STATUS[obj.status]

    class Meta:
        model = StandardAnswer
        fields: tuple[str, ...] = (
            "reference",
            "standard",
            "company",
            "year_of_submission",
            "creation_date",
            "last_update",
            "submit_date",
            "status",
        )
        read_only_fields = fields


class DeclarationDetailSerializer(DeclarationSerializer):
    measures = SecurityMeasureAnswerSerializer(source="securitymeasureanswers", many=True, read_only=True)

    class Meta(DeclarationSerializer.Meta):
        fields = (*DeclarationSerializer.Meta.fields, "measures")
        read_only_fields = fields


class ProjectSerializer(serializers.ModelSerializer):
    reference = serializers.UUIDField(source="api_id", read_only=True)
    standard = serializers.StringRelatedField()

    class Meta:
        model = Project
        fields = ("reference", "name", "standard", "created_at", "updated_at", "years", "reference_year", "task_status")
        read_only_fields = fields
