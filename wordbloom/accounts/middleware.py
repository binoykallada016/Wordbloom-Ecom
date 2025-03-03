from django.shortcuts import redirect
from django.contrib import messages

class BlockedUserMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.user.is_authenticated and getattr(request.user, 'is_blocked', False):
            messages.error(request, "Your account has been blocked by the admin.")
            from django.contrib.auth import logout
            logout(request)
            return redirect('accounts:user_login')  # Redirect to the login page
        return self.get_response(request)