from django.apps import apps
from django.contrib.auth import SESSION_KEY as _SESSION_KEY
from django.contrib.sessions.backends.db import SessionStore as DBStore


class SessionStore(DBStore):
    @classmethod
    def get_model_class(cls):
        return apps.get_model("governanceplatform", "UserSession")

    def _extract_user_id(self, data):
        try:
            return int(data.get(_SESSION_KEY))
        except (ValueError, TypeError):
            return None

    def create_model_instance(self, data):
        obj = super().create_model_instance(data)
        obj.user_id = self._extract_user_id(data)
        return obj

    async def acreate_model_instance(self, data):
        obj = await super().acreate_model_instance(data)
        obj.user_id = self._extract_user_id(data)
        return obj
