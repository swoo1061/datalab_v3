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
    review_subtype_label = serializers.SerializerMethodField()
    assignee = serializers.IntegerField(source="assignee_id", read_only=True)
    assignee_name = serializers.SerializerMethodField()
    photos = serializers.SerializerMethodField()

    class Meta:
        model = ClinicPost
        fields = [
            "id",
            "type",
            "platform",
            "platform_label",
            "review_subtype",
            "review_subtype_label",
            "assignee",
            "assignee_name",
            "title",
            "url",
            "views",
            "comments",
            "message_count",
            "photos",
            "status",
            "published_at",
            "updated_at",
            "last_crawled_at",
        ]

    def get_platform_label(self, obj):
        return obj.get_platform_display()

    def get_review_subtype_label(self, obj):
        if not obj.review_subtype:
            return None
        return obj.get_review_subtype_display()

    def get_assignee_name(self, obj):
        if not obj.assignee:
            return None
        return obj.assignee.get_full_name() or obj.assignee.username

    def get_photos(self, obj):
        request = self.context.get("request")
        urls = []
        for p in obj.photos.all():
            url = p.image.url
            if request:
                url = request.build_absolute_uri(url)
            urls.append({"id": p.id, "url": url})
        return urls
