from __future__ import annotations

from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from governanceplatform.models import User
from incidents.models import Incident
from reporting.models import Project
from securityobjectives.globals import OPERATOR_STATUS
from securityobjectives.models import SecurityMeasureAnswer, StandardAnswer


class CurrentUserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ("email", "first_name", "last_name")
        read_only_fields = fields


class IncidentSerializer(serializers.ModelSerializer):
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
        )
        read_only_fields = fields


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
    measures = SecurityMeasureAnswerSerializer(source="securitymeasureanswers", many=True, read_only=True)

    @extend_schema_field(serializers.CharField())
    def get_status(self, obj: StandardAnswer) -> str:
        return obj.status if self.context["request"].user.is_regulator() else OPERATOR_STATUS[obj.status]

    class Meta:
        model = StandardAnswer
        fields = (
            "reference",
            "standard",
            "company",
            "year_of_submission",
            "creation_date",
            "last_update",
            "submit_date",
            "status",
            "measures",
        )
        read_only_fields = fields


class ProjectSerializer(serializers.ModelSerializer):
    reference = serializers.UUIDField(source="api_id", read_only=True)
    standard = serializers.StringRelatedField()

    class Meta:
        model = Project
        fields = ("reference", "name", "standard", "created_at", "updated_at", "years", "reference_year", "task_status")
        read_only_fields = fields
