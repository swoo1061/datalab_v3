from rest_framework import serializers
from apps.data.models import ClinicGuide, FavoriteClinic, ClinicPost, CalendarMemo


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
            "doctor_name",
            "assignee",
            "assignee_name",
            "title",
            "url",
            "account",
            "account_password",
            "memo",
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
        profile = getattr(obj.assignee, "profile", None)
        if profile and getattr(profile, "name", None):
            position = getattr(profile, "position", None)
            position_label_map = {
                "admin": "계정",
                "manager": "매니저",
                "leader": "팀장",
                "ceo": "대표이사",
            }
            label = position_label_map.get(position, position)
            return f"{profile.name} {label}".strip() if label else profile.name
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


class CalendarMemoSerializer(serializers.ModelSerializer):
    clinic_id = serializers.IntegerField(source="clinic.id", read_only=True)
    clinic_name = serializers.CharField(source="clinic.name", read_only=True)
    user_name = serializers.SerializerMethodField()
    platform_label = serializers.SerializerMethodField()

    class Meta:
        model = CalendarMemo
        fields = [
            "id",
            "date",
            "content",
            "platform",
            "platform_label",
            "account",
            "account_password",
            "remind_at",
            "is_read",
            "clinic_id",
            "clinic_name",
            "user_name",
            "created_at",
            "updated_at",
        ]

    def get_platform_label(self, obj):
        if not obj.platform:
            return ""
        label_map = {
            "naver": "네이버",
            "gn_jp": "JP강남언니",
            "gangnam": "강남언니",
            "babytok": "바비톡",
            "todaktok": "토닥톡",
            "yeoshin": "여신티켓",
            "seongyesa": "성예사",
            "dadamo": "대다모",
        }
        return label_map.get(obj.platform, obj.platform)

    def get_user_name(self, obj):
        profile = getattr(obj.user, "profile", None)
        if profile and getattr(profile, "name", None):
            position = getattr(profile, "position", None)
            position_label_map = {
                "admin": "계정",
                "manager": "매니저",
                "leader": "팀장",
                "ceo": "대표이사",
            }
            label = position_label_map.get(position, position)
            return f"{profile.name} {label}".strip() if label else profile.name
        return obj.user.get_full_name() or obj.user.username
