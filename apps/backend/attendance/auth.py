"""JWT authentication for the narrowly scoped live-location WebSocket."""

from urllib.parse import parse_qs

from channels.db import database_sync_to_async
from channels.middleware import BaseMiddleware
from django.contrib.auth.models import AnonymousUser
from rest_framework_simplejwt.tokens import AccessToken

from accounts.models import User


@database_sync_to_async
def user_for_token(token: str):
    try:
        user_id = AccessToken(token)["user_id"]
        return User.objects.select_related("company").get(pk=user_id, is_active=True)
    except Exception:  # An invalid or expired token is simply unauthenticated.
        return AnonymousUser()


class JwtAuthMiddleware(BaseMiddleware):
    async def __call__(self, scope, receive, send):
        query = parse_qs(scope.get("query_string", b"").decode())
        token = query.get("token", [""])[0]
        scope["user"] = await user_for_token(token) if token else AnonymousUser()
        return await super().__call__(scope, receive, send)
