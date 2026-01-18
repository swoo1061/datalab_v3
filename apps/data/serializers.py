from rest_framework import serializers
from apps.data.models import ClinicGuide, FavoriteClinic, ClinicPost


class FavoriteClinicSerializer(serializers.ModelSerializer):
    clinic_id = serializers.IntegerField(source="clinic.id", read_only=True)
    clinic_name = serializers.CharField(source="clinic.name", read_only=True)

    class Meta:
        model = FavoriteClinic
        fields = ["clinic_id", "clinic_name", "created_at"]

class ClinicPostSerializer(serializers.ModelSerializer):
    platform_label = serializers.SerializerMethodField()

    class Meta:
        model = ClinicPost
        fields = [
            "id",
            "type",
            "platform",
            "platform_label",
            "title",
            "url",
            "views",
            "comments",
            "status",
            "published_at",
            "updated_at",
            "last_crawled_at",
        ]

    def get_platform_label(self, obj):
        return obj.get_platform_display()