from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncJsonWebsocketConsumer

from accounts.models import User
from calling.models import CallSession
from calling.realtime import session_group_name, session_status_payload
from calling.services import CallSessionServiceError, get_call_session_for_actor


@database_sync_to_async
def _authorized_snapshot(session_id, user_id):
    try:
        user = User.objects.get(pk=user_id, is_active=True)
        session = CallSession.objects.get(pk=session_id)
        session = get_call_session_for_actor(session=session, actor=user)
    except (User.DoesNotExist, CallSession.DoesNotExist, CallSessionServiceError):
        return None
    return session_status_payload(session)


class CallSessionStatusConsumer(AsyncJsonWebsocketConsumer):
    async def connect(self):
        user = self.scope.get("user")
        if user is None or not user.is_authenticated:
            await self.close(code=4401)
            return
        self.session_id = self.scope["url_route"]["kwargs"]["session_id"]
        payload = await _authorized_snapshot(self.session_id, user.pk)
        if payload is None:
            await self.close(code=4403)
            return
        self.group_name = session_group_name(self.session_id)
        try:
            await self.channel_layer.group_add(self.group_name, self.channel_name)
        except Exception:
            await self.close(code=1013)
            return
        await self.accept()
        await self.send_json(payload)

    async def disconnect(self, close_code):
        group_name = getattr(self, "group_name", None)
        if group_name:
            try:
                await self.channel_layer.group_discard(group_name, self.channel_name)
            except Exception:
                return

    async def receive_json(self, content, **kwargs):
        if not isinstance(content, dict) or content.get("type") != "status.request":
            await self.send_json(
                {"type": "session.error", "code": "unsupported_message"}
            )
            return
        payload = await _authorized_snapshot(
            self.session_id,
            self.scope["user"].pk,
        )
        if payload is None:
            await self.close(code=4403)
            return
        await self.send_json(payload)

    async def session_status(self, event):
        payload = await _authorized_snapshot(
            self.session_id,
            self.scope["user"].pk,
        )
        if payload is None:
            await self.close(code=4403)
            return
        await self.send_json(payload)
