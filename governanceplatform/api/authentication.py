from __future__ import annotations

import hashlib
from typing import TYPE_CHECKING

from django.utils import timezone
from drf_spectacular.extensions import OpenApiAuthenticationExtension
from rest_framework.authentication import BaseAuthentication, get_authorization_header
from rest_framework.exceptions import AuthenticationFailed

from governanceplatform.models import APIKey

if TYPE_CHECKING:
    from drf_spectacular.openapi import AutoSchema
    from rest_framework.request import Request

    from governanceplatform.models import User


class APIKeyAuthentication(BaseAuthentication):
    def authenticate(self, request: Request) -> tuple[User, APIKey] | None:
        header = get_authorization_header(request).split()
        if not header:
            return None
        if len(header) != 2 or header[0].lower() != b"bearer":
            raise AuthenticationFailed("Use Authorization: Bearer <API key>.")
        if not header[1].startswith(b"serima_") or len(header[1]) != 50:
            raise AuthenticationFailed("Invalid or expired API key.")
        digest = hashlib.sha256(header[1]).hexdigest()
        key = (
            APIKey.objects.select_related("user")
            .prefetch_related("user__groups")
            .filter(digest=digest, revoked_at__isnull=True, expires_at__gt=timezone.now(), user__is_active=True)
            .first()
        )
        if key is None:
            raise AuthenticationFailed("Invalid or expired API key.")
        return key.user, key

    def authenticate_header(self, request: Request) -> str:
        return "Bearer"


class APIKeyAuthenticationScheme(OpenApiAuthenticationExtension):
    target_class = "governanceplatform.api.authentication.APIKeyAuthentication"
    name = "APIKey"

    def get_security_definition(self, auto_schema: AutoSchema) -> dict[str, str]:
        return {"type": "http", "scheme": "bearer", "description": "A personal SERIMA API key. Create one in Account → API keys."}
