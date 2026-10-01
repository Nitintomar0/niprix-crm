from rest_framework.exceptions import AuthenticationFailed
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.serializers import TokenRefreshSerializer
from rest_framework_simplejwt.settings import api_settings

from .models import User


class ActiveEmployeeJWTAuthentication(JWTAuthentication):
    """Reject access tokens as soon as their employee profile is inactive."""

    def get_user(self, validated_token):
        user = super().get_user(validated_token)
        try:
            profile = user.employee_profile
        except User.employee_profile.RelatedObjectDoesNotExist:
            profile = None
        if profile is not None and not profile.is_active:
            raise AuthenticationFailed("Employee account is inactive.", code="user_inactive")
        return user


class ActiveEmployeeTokenRefreshSerializer(TokenRefreshSerializer):
    """Refresh tokens must honor current account/profile state, not issue time."""

    def validate(self, attrs):
        refresh = self.token_class(attrs["refresh"])
        user_id = refresh.payload.get(api_settings.USER_ID_CLAIM)
        user = User.objects.filter(**{api_settings.USER_ID_FIELD: user_id}).first()
        if not user or not user.is_active:
            raise AuthenticationFailed("Employee account is inactive.", code="user_inactive")
        try:
            if not user.employee_profile.is_active:
                raise AuthenticationFailed("Employee account is inactive.", code="user_inactive")
        except User.employee_profile.RelatedObjectDoesNotExist:
            pass
        return super().validate(attrs)
