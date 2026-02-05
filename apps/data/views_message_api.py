from django.contrib.auth import get_user_model
from django.db.models import Q
from django.db import transaction
from django.db.utils import OperationalError, ProgrammingError
from django.shortcuts import get_object_or_404

from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.data.models import InternalMessage, InternalMessageAttachment
from apps.data.serializers import InternalMessageSerializer
from apps.data.views_api import CsrfExemptSessionAuthentication, HeaderSessionAuthentication


class InternalMessageListCreateView(APIView):
    authentication_classes = [HeaderSessionAuthentication, CsrfExemptSessionAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        box = (request.GET.get("box") or "inbox").strip().lower()
        q = (request.GET.get("q") or "").strip()
        limit_raw = request.GET.get("limit") or "100"
        try:
            limit = max(1, min(300, int(limit_raw)))
        except ValueError:
            limit = 100

        if box == "sent":
            qs = InternalMessage.objects.filter(sender=request.user).select_related("sender", "recipient")
        else:
            qs = InternalMessage.objects.filter(recipient=request.user).select_related("sender", "recipient")

        if q:
            qs = qs.filter(Q(subject__icontains=q) | Q(content__icontains=q))

        rows = list(qs.order_by("-created_at")[:limit])
        unread = InternalMessage.objects.filter(recipient=request.user, is_read=False).count()
        inbox_count = InternalMessage.objects.filter(recipient=request.user).count()
        sent_count = InternalMessage.objects.filter(sender=request.user).count()

        return Response(
            {
                "box": box,
                "count": len(rows),
                "unread_count": unread,
                "inbox_count": inbox_count,
                "sent_count": sent_count,
                "results": InternalMessageSerializer(rows, many=True, context={"request": request}).data,
            },
            status=status.HTTP_200_OK,
        )

    def post(self, request):
        payload = request.data or {}
        recipient_id = payload.get("recipient_id")
        subject = (payload.get("subject") or "").strip()
        content = (payload.get("content") or "").strip()

        if not recipient_id:
            return Response({"message": "recipient_required"}, status=status.HTTP_400_BAD_REQUEST)
        if not subject:
            return Response({"message": "subject_required"}, status=status.HTTP_400_BAD_REQUEST)
        if not content:
            return Response({"message": "content_required"}, status=status.HTTP_400_BAD_REQUEST)

        User = get_user_model()
        recipient = get_object_or_404(User, id=recipient_id, is_active=True)
        attachments = request.FILES.getlist("attachments")
        if len(attachments) > 10:
            return Response({"message": "attachments_limit_exceeded"}, status=status.HTTP_400_BAD_REQUEST)
        max_size = 20 * 1024 * 1024
        for f in attachments:
            if (getattr(f, "size", 0) or 0) > max_size:
                return Response({"message": "attachment_too_large"}, status=status.HTTP_400_BAD_REQUEST)

        with transaction.atomic():
            msg = InternalMessage.objects.create(
                sender=request.user,
                recipient=recipient,
                subject=subject,
                content=content,
                is_read=False,
            )
            try:
                for f in attachments:
                    InternalMessageAttachment.objects.create(
                        message=msg,
                        file=f,
                        original_name=(getattr(f, "name", "") or "")[:255],
                        content_type=(getattr(f, "content_type", "") or "")[:120],
                        file_size=getattr(f, "size", 0) or 0,
                    )
            except (OperationalError, ProgrammingError):
                return Response({"message": "attachment_feature_not_ready"}, status=status.HTTP_503_SERVICE_UNAVAILABLE)

        return Response(
            {"ok": True, "message": InternalMessageSerializer(msg, context={"request": request}).data},
            status=status.HTTP_201_CREATED,
        )


class InternalMessageDetailView(APIView):
    authentication_classes = [HeaderSessionAuthentication, CsrfExemptSessionAuthentication]
    permission_classes = [IsAuthenticated]

    def patch(self, request, message_id):
        msg = get_object_or_404(
            InternalMessage.objects.select_related("sender", "recipient"),
            id=message_id,
        )
        if msg.recipient_id != request.user.id and msg.sender_id != request.user.id:
            return Response({"message": "forbidden"}, status=status.HTTP_403_FORBIDDEN)

        payload = request.data or {}
        if "is_read" in payload and msg.recipient_id == request.user.id and payload.get("is_read"):
            msg.mark_read()

        return Response(InternalMessageSerializer(msg, context={"request": request}).data, status=status.HTTP_200_OK)
