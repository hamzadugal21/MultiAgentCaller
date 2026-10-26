from django.urls import path

from calling.consumers import CallSessionStatusConsumer

websocket_urlpatterns = [
    path(
        "ws/calling/sessions/<uuid:session_id>/status/",
        CallSessionStatusConsumer.as_asgi(),
        name="call-session-status",
    ),
]
