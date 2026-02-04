from rest_framework import serializers

from apps.data.models import AttendanceRecord, AttendanceCorrectionRequest


class AttendanceRecordSerializer(serializers.ModelSerializer):
    class Meta:
        model = AttendanceRecord
        fields = [
            "id",
            "work_date",
            "check_in_at",
            "check_out_at",
            "worked_minutes",
            "status",
            "note",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "worked_minutes", "created_at", "updated_at"]


class AttendanceCorrectionRequestSerializer(serializers.ModelSerializer):
    reviewer_name = serializers.SerializerMethodField()

    class Meta:
        model = AttendanceCorrectionRequest
        fields = [
            "id",
            "work_date",
            "current_check_in_at",
            "current_check_out_at",
            "requested_check_in_at",
            "requested_check_out_at",
            "reason",
            "status",
            "reviewed_at",
            "review_note",
            "reviewer_name",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "status",
            "reviewed_at",
            "review_note",
            "reviewer_name",
            "created_at",
            "updated_at",
        ]

    def get_reviewer_name(self, obj):
        if not obj.reviewed_by:
            return ""
        profile = getattr(obj.reviewed_by, "profile", None)
        return getattr(profile, "name", None) or obj.reviewed_by.username
