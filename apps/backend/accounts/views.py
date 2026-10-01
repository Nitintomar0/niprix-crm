from django.shortcuts import render

# Create your views here.
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenRefreshView
from .authentication import ActiveEmployeeTokenRefreshSerializer
from .permissions import IsCEO


class ActiveEmployeeTokenRefreshView(TokenRefreshView):
    serializer_class = ActiveEmployeeTokenRefreshSerializer


class MeView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response({
            "id": request.user.id,
            "username": request.user.username,
            "email": request.user.email,
            "role": request.user.role,
        })
        

class LogoutView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        refresh_token = request.data.get("refresh")

        if not refresh_token:
            return Response(
                {"detail": "Refresh token is required."},
                status=400,
            )

        token = RefreshToken(refresh_token)
        token.blacklist()

        return Response(
            {"detail": "Logout successful."},
            status=200,
        )
        
class CEODashboardView(APIView):
    permission_classes = [IsCEO]

    def get(self, request):
        return Response({
            "message": "CEO dashboard access granted.",
            "user": request.user.username,
            "role": request.user.role,
        })
