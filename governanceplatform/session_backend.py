from django.contrib.sessions.backends.db import SessionStore as DBStore

_SESSION_KEY = "_auth_user_id"


class SessionStore(DBStore):
    @classmethod
    def get_model_class(cls):
        from django.apps import apps

        return apps.get_model("governanceplatform", "UserSession")

    def create_model_instance(self, data):
        obj = super().create_model_instance(data)
        obj.user_id = data.get(_SESSION_KEY)
        return obj

    async def acreate_model_instance(self, data):
        obj = await super().acreate_model_instance(data)
        obj.user_id = data.get(_SESSION_KEY)
        return obj
