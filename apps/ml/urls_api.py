from django.urls import path
from .views_api import (
    review_generate_api,
    review_save_edit_api,
    api_generate_gangnam_review,
    agent_chat_api,
    agent_chat_stream_api,
)

urlpatterns = [
    path("review/", review_generate_api),
    path("review/edit/", review_save_edit_api),
    path("gangnam_review/", api_generate_gangnam_review),
    path("agent/chat/", agent_chat_api),
    path("agent/chat/stream/", agent_chat_stream_api),
]
