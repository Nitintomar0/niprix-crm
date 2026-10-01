from django.test import TestCase

# Create your tests here.
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase
from rest_framework_simplejwt.tokens import RefreshToken

from .models import User


class AuthenticationTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="test_user",
            password="TestPassword123!",
            email="test@example.com",
        )

    def test_login_success(self):
        response = self.client.post(
            reverse("token_obtain_pair"),
            {
                "username": "test_user",
                "password": "TestPassword123!",
            },
            format= "json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("access", response.data)
        self.assertIn("refresh", response.data)

    def test_protected_endpoint_without_token(self):
        response = self.client.get("/api/auth/me/")

        self.assertEqual(
            response.status_code,
            status.HTTP_401_UNAUTHORIZED,
        )
    
    def test_me_endpoint_with_valid_token(self):
        login_response = self.client.post(
            reverse("token_obtain_pair"),
            {
                "username": "test_user",
                "password": "TestPassword123!",
            },
            format="json",
        )

        access_token = login_response.data["access"]

        self.client.credentials(
            HTTP_AUTHORIZATION=f"Bearer {access_token}"
        )

        response = self.client.get("/api/auth/me/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["username"], "test_user")
        self.assertEqual(response.data["role"], "EMPLOYEE")
    
    def test_logout_blacklists_refresh_token(self):
        login_response = self.client.post(
            reverse("token_obtain_pair"),
            {
                "username": "test_user",
                "password": "TestPassword123!",
            },
            format="json",
        )

        refresh_token = login_response.data["refresh"]

        self.client.force_authenticate(user=self.user)

        logout_response = self.client.post(
            reverse("logout"),
            {
                "refresh": refresh_token,
            },
            format="json",
        )

        self.assertEqual(
            logout_response.status_code,
            status.HTTP_200_OK,
        )

        refresh_response = self.client.post(
            reverse("token_refresh"),
            {
                "refresh": refresh_token,
            },
            format="json",
        )

        self.assertEqual(
            refresh_response.status_code,
            status.HTTP_401_UNAUTHORIZED,
        )
        

class RBACPermissionTests(APITestCase):
    def setUp(self):
        self.ceo = User.objects.create_user(
            username="test_ceo",
            password="TestPassword123!",
            role=User.Role.CEO,
        )

        self.employee = User.objects.create_user(
            username="test_employee",
            password="TestPassword123!",
            role=User.Role.EMPLOYEE,
        )

    def test_ceo_can_access_dashboard(self):
        self.client.force_authenticate(user=self.ceo)

        response = self.client.get("/api/auth/ceo-dashboard/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_employee_cannot_access_dashboard(self):
        self.client.force_authenticate(user=self.employee)

        response = self.client.get("/api/auth/ceo-dashboard/")

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)