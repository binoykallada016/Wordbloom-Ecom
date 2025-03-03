from accounts.models import User

def create_or_update_user(backend, details, response, *args, **kwargs):
    """
    Custom function to create or update the user during social authentication.
    """
    user = kwargs.get('user')
    if user:
        return {'is_new': False}

    email = details.get('email')
    first_name = details.get('first_name', '')
    last_name = details.get('last_name', '')

    # Ensure email exists
    if not email:
        return None

    user, created = User.objects.get_or_create(
        email=email,
        defaults={
            'first_name': first_name,
            'last_name': last_name,
            'is_active': True,
        },
    )
    return {'is_new': created, 'user': user}
