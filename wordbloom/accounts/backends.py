from django.contrib.auth.backends import BaseBackend
from django.contrib.auth import get_user_model
from django.contrib.auth.backends import ModelBackend
from . models import User

class EmailBackend(BaseBackend):
    def __init__(self):
        self.User = get_user_model()

    def authenticate(self, request, username=None, password=None, **kwargs):
        try:
            user = self.User.objects.get(email=username)
            if user.is_blocked:   # Blocked users should not proceed
                return None
            if user.check_password(password) and user.is_active:
                return user
        except self.User.DoesNotExist:
            return None

    def get_user(self, user_id):
        try:
            return self.User.objects.get(pk=user_id)
        except self.User.DoesNotExist:
            return None


class GoogleAuthBackend(ModelBackend):
    def authenticate(self, request, **kwargs):
        user = super().authenticate(request, **kwargs)  
        if user and user.social_auth.exists() and not user.is_blocked:  
            if not user.is_active:
                user.is_active = True
                user.save()

        return user


'''
Evaluating the Necessity of backends.py
1. Email-Based Login (EmailBackend)
Is it needed? Not necessary. Your custom user model already defines 
USERNAME_FIELD = 'email', 
meaning Django will automatically use email for authentication with the default ModelBackend.
Why? The default ModelBackend can handle email-based login if we ensure:

AUTHENTICATION_BACKENDS = (
    'django.contrib.auth.backends.ModelBackend',
    'social_core.backends.google.GoogleOAuth2',
)


2. Google OAuth Handling (GoogleAuthBackend)
Is it needed? Not necessary. The SOCIAL_AUTH_PIPELINE already handles user creation and 
activation. Specifically, these pipeline steps:
social_core.pipeline.user.create_user: Creates the user.
social_core.pipeline.user.user_details: Updates user details, including activating 
the user if needed.


Why You Can Simplify Without backends.py
Email Login: Already supported natively with USERNAME_FIELD = 'email'.
Google OAuth: Fully managed by the social-auth-app-django library and the SOCIAL_AUTH_PIPELINE.
By simplifying, our project becomes easier to maintain while achieving the same functionality.
'''