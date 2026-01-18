from rest_framework import serializers
from apps.data.models_worklog import DailyWorkLog


class DailyWorkLogSerializer(serializers.ModelSerializer):
    user_name = serializers.CharField(source="user.username", read_only=True)
    clinic_name = serializers.CharField(source="clinic.name", read_only=True)

    class Meta:
        model = DailyWorkLog
        fields = [
            "id",
            "clinic",
            "clinic_name",
            "user",
            "user_name",
            "date",
            "posts_count",
            "comments_count",
            "reviews_count",
            "memo",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "clinic",
            "clinic_name",
            "user",
            "user_name",
            "created_at",
            "updated_at",
        ]