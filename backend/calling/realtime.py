from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.db import transaction

from calling.models import CallSession


def session_group_name(session_id):
    return f"call_session_{str(session_id).replace('-', '')}"


def session_status_payload(session):
    return {
        "type": "session.status",
        "session_id": str(session.pk),
        "status": session.status,
        "current_question_index": session.current_question_index,
        "simulated_mode": session.simulated_mode,
    }


def broadcast_session_status(session_id):
    try:
        session = CallSession.objects.only(
            "id",
            "status",
            "current_question_index",
            "simulated_mode",
        ).get(pk=session_id)
    except CallSession.DoesNotExist:
        return
    channel_layer = get_channel_layer()
    if channel_layer is None:
        return
    try:
        async_to_sync(channel_layer.group_send)(
            session_group_name(session.pk),
            {
                "type": "session.status",
                "payload": session_status_payload(session),
            },
        )
    except Exception:
        # Real-time delivery is an optional status enhancement. The committed
        # HTTP workflow remains authoritative when the channel layer is down.
        return


def queue_session_status_update(session_id):
    transaction.on_commit(lambda: broadcast_session_status(session_id))
