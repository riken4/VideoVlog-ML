from django.contrib.auth.backends import ModelBackend


class BlockedUserAuthenticationBackend(ModelBackend):
    """Prevent accounts blocked by an administrator from authenticating."""

    def user_can_authenticate(self, user):
        return super().user_can_authenticate(user) and not user.is_blocked
