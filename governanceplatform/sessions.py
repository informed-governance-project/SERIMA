from django.apps import apps
from django.contrib.sessions.backends.db import SessionStore as DBStore

_SESSION_KEY = "_auth_user_id"


class SessionStore(DBStore):
    @classmethod
    def get_model_class(cls):
        return apps.get_model("governanceplatform", "UserSession")

    def create_model_instance(self, data):
        obj = super().create_model_instance(data)
        try:
            user_id = int(data.get(_SESSION_KEY))
        except (ValueError, TypeError):
            user_id = None
        obj.user_id = user_id
        return obj
