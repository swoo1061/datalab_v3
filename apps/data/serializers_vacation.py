from rest_framework import serializers

from apps.data.models import VacationRequest


class VacationRequestSerializer(serializers.ModelSerializer):
    requester_name = serializers.SerializerMethodField()
    requester_role = serializers.SerializerMethodField()
    reviewer_name = serializers.SerializerMethodField()

    class Meta:
        model = VacationRequest
        fields = [
            "id",
            "start_date",
            "end_date",
            "type",
            "days",
            "reason",
            "status",
            "reviewed_at",
            "review_note",
            "requester_name",
            "requester_role",
            "reviewer_name",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "days",
            "status",
            "reviewed_at",
            "review_note",
            "requester_name",
            "requester_role",
            "reviewer_name",
            "created_at",
            "updated_at",
        ]

    def get_requester_name(self, obj):
        profile = getattr(obj.user, "profile", None)
        return getattr(profile, "name", None) or obj.user.username

    def get_requester_role(self, obj):
        profile = getattr(obj.user, "profile", None)
        return getattr(profile, "position", None) or ""

    def get_reviewer_name(self, obj):
        if not obj.reviewed_by:
            return ""
        profile = getattr(obj.reviewed_by, "profile", None)
        return getattr(profile, "name", None) or obj.reviewed_by.username
