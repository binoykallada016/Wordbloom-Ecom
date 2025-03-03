from django import forms
from django.core.exceptions import ValidationError
from django.contrib.auth.password_validation import validate_password
from django.core.validators import RegexValidator
from .models import User
import re

class NoLeadingSpacesValidator:
    """
    Validator to ensure no leading spaces exist in the input.
    """
    def __call__(self, value):
        # Check if value is None or empty
        if not value:
            return
        # Check if the value starts with a space
        if value.startswith(' '):
            raise ValidationError(
                'Spaces at the beginning of the field are not allowed.',
                code='leading_spaces'
            )

class StrongPasswordValidator:
    """
    Validator to enforce strong password requirements.
    """
    def __call__(self, value):
        if not re.search(r'[A-Z]', value):
            raise ValidationError("Password must contain at least one uppercase letter.")
        if not re.search(r'[a-z]', value):
            raise ValidationError("Password must contain at least one lowercase letter.")
        if not re.search(r'\d', value):
            raise ValidationError("Password must contain at least one digit.")
        if not re.search(r'[!@#$%^&*(),.?\":{}|<>]', value):
            raise ValidationError("Password must contain at least one special character.")

class UserRegisterForm(forms.ModelForm):
    email = forms.EmailField(
        widget=forms.EmailInput(attrs={'class': 'form-input', 'placeholder': 'Email'}),
        validators=[NoLeadingSpacesValidator()],
        error_messages={
            'required': 'Email is required.',
            'invalid': 'Enter a valid email address.',
            'leading_spaces': 'Spaces at the beginning of the email are not allowed.'
        }
    )
    first_name = forms.CharField(
        widget=forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'First Name'}),
        validators=[NoLeadingSpacesValidator()],
        error_messages={
            'required': 'First name is required.',
            'leading_spaces': 'Spaces at the beginning of the first name are not allowed.'
        }
    )
    last_name = forms.CharField(
        widget=forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'Last Name'}),
        validators=[NoLeadingSpacesValidator()],
        error_messages={
            'required': 'Last name is required.',
            'leading_spaces': 'Spaces at the beginning of the last name are not allowed.'
        }
    )
    phone_number = forms.CharField(
        widget=forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'Mobile Number'}),
        validators=[
            RegexValidator(
                regex=r'^\d{10}$',
                message='Phone number must be 10 digits'
            ),
            NoLeadingSpacesValidator()
        ],
        help_text='Enter a valid mobile number without country code.',
        error_messages={
            'required': 'Mobile number is required.',
            'invalid': 'Enter a valid mobile number.',
            'leading_spaces': 'Spaces at the beginning of the phone number are not allowed.'
        }
    )
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={'class': 'form-input', 'placeholder': 'Password'}),
        label="Password",
        validators=[
            validate_password,  # Django's built-in validation
            NoLeadingSpacesValidator(),
            StrongPasswordValidator()  # Custom validation
        ],
        min_length=8,
        help_text=(
            "Your password must be at least 8 characters long, include one uppercase letter, "
            "one lowercase letter, one number, and one special character."
        ),
        error_messages={
            'required': 'Please enter a password.',
            'min_length': 'Password must be at least 8 characters long.',
            'leading_spaces': 'Spaces at the beginning of the password are not allowed.'
        }
    )
    confirm_password = forms.CharField(
        widget=forms.PasswordInput(attrs={'class': 'form-input', 'placeholder': 'Confirm Password'}),
        label="Confirm Password",
        validators=[NoLeadingSpacesValidator()],
        help_text="Re-enter the same password as above for verification.",
        error_messages={
            'required': 'Please confirm your password.',
            'leading_spaces': 'Spaces at the beginning of the confirm password are not allowed.'
        }
    )

    class Meta:
        model = User
        fields = ['email', 'first_name', 'last_name', 'phone_number', 'password']

    def clean_email(self):
        email = self.cleaned_data.get('email')
        # Check if email already exists
        if User.objects.filter(email=email).exists():
            raise forms.ValidationError("This email is already registered")
        return email

    def clean_phone_number(self):
        phone_number = self.cleaned_data.get('phone_number')
        # Check if phone number already exists
        if User.objects.filter(phone_number=phone_number).exists():
            raise forms.ValidationError("This phone number is already registered")
        return phone_number

    def clean(self):
        cleaned_data = super().clean()
        password = cleaned_data.get("password")
        confirm_password = cleaned_data.get("confirm_password")
        
        # Validate password match
        if password and confirm_password:
            if password != confirm_password:
                self.add_error('confirm_password', "Passwords do not match")
        
        return cleaned_data
