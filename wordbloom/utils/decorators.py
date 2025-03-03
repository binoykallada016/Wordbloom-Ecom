from django.shortcuts import redirect
from functools import wraps
from django.urls import reverse

def admin_required(view_func):
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        if not request.user.is_staff:
            # return redirect('admin_login')
            return redirect(reverse('admindashboard:admin_login'))
        return view_func(request, *args, **kwargs)
    return _wrapped_view