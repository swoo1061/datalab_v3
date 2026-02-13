from rest_framework import serializers
from django.db.utils import OperationalError, ProgrammingError
from apps.data.models import (
    ClinicGuide,
    FavoriteClinic,
    ClinicPost,
    CalendarMemo,
    ReviewSchedule,
    InternalMessage,
    InternalMessageAttachment,
)


class FavoriteClinicSerializer(serializers.ModelSerializer):
    clinic_id = serializers.IntegerField(source="clinic.id", read_only=True)
    clinic_name = serializers.CharField(source="clinic.name", read_only=True)

    class Meta:
        model = FavoriteClinic
        fields = ["clinic_id", "clinic_name", "created_at"]

class ClinicPostSerializer(serializers.ModelSerializer):
    platform_label = serializers.SerializerMethodField()
    review_subtype_label = serializers.SerializerMethodField()
    opinion_subtype_label = serializers.SerializerMethodField()
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
            "opinion_subtype",
            "opinion_subtype_label",
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

    def get_opinion_subtype_label(self, obj):
        if not obj.opinion_subtype:
            return None
        return obj.get_opinion_subtype_display()

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


class ReviewScheduleSerializer(serializers.ModelSerializer):
    clinic_id = serializers.IntegerField(source="clinic.id", read_only=True)
    clinic_name = serializers.CharField(source="clinic.name", read_only=True)
    user_name = serializers.SerializerMethodField()
    platform = serializers.SerializerMethodField()
    platform_label = serializers.SerializerMethodField()
    content = serializers.SerializerMethodField()

    class Meta:
        model = ReviewSchedule
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
            "plan_id",
            "plan_title",
            "label",
            "detail",
            "draft",
        ]

    def get_platform(self, _obj):
        return "__review_schedule__"

    def get_platform_label(self, _obj):
        return "리뷰 스케줄"

    def get_content(self, obj):
        parts = []
        if obj.plan_id and obj.label:
            parts.append(f"[리뷰설계/{obj.plan_id}/{obj.label}] {obj.detail}")
        elif obj.label:
            parts.append(f"[리뷰설계/{obj.label}] {obj.detail}")
        else:
            parts.append(obj.detail or "")
        if obj.plan_title:
            parts.append(f"설계안 제목: {obj.plan_title}")
        if obj.draft:
            parts.append(f"리뷰: {obj.draft}")
        return "\n".join([p for p in parts if p]).strip()

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


class InternalMessageSerializer(serializers.ModelSerializer):
    sender_name = serializers.SerializerMethodField()
    recipient_name = serializers.SerializerMethodField()
    attachments = serializers.SerializerMethodField()

    class Meta:
        model = InternalMessage
        fields = [
            "id",
            "sender",
            "sender_name",
            "recipient",
            "recipient_name",
            "subject",
            "content",
            "attachments",
            "is_read",
            "read_at",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "sender", "is_read", "read_at", "created_at", "updated_at"]

    def _display_name(self, user):
        if not user:
            return "-"
        profile = getattr(user, "profile", None)
        if profile and getattr(profile, "name", None):
            return profile.name
        return user.get_full_name() or user.username

    def get_sender_name(self, obj):
        return self._display_name(obj.sender)

    def get_recipient_name(self, obj):
        return self._display_name(obj.recipient)

    def get_attachments(self, obj):
        request = self.context.get("request")
        rows = []
        try:
            attachments = obj.attachments.all()
            for att in attachments:
                url = att.file.url
                if request:
                    url = request.build_absolute_uri(url)
                rows.append(
                    {
                        "id": att.id,
                        "name": att.original_name or att.file.name.split("/")[-1],
                        "url": url,
                        "content_type": att.content_type,
                        "size": att.file_size,
                    }
                )
        except (OperationalError, ProgrammingError):
            # Migration not applied yet: return empty attachments to keep mail UI working.
            return []
        return rows
