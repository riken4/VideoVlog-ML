from django.contrib.auth import authenticate, get_user_model
from django.test import TestCase
from django.urls import reverse


class BlockedUserAuthenticationTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="blocked-user",
            password="secure-password",
            is_blocked=True,
        )

    def test_blocked_user_cannot_authenticate(self):
        user = authenticate(username=self.user.username, password="secure-password")

        self.assertIsNone(user)

    def test_blocked_user_cannot_log_in_through_login_view(self):
        response = self.client.post(
            reverse("login"),
            {"username": self.user.username, "password": "secure-password"},
            follow=True,
        )

        self.assertRedirects(response, reverse("login"))
        self.assertFalse("_auth_user_id" in self.client.session)
        self.assertContains(response, "This account has been blocked by an administrator.")
