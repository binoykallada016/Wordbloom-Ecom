from django.db import models
from django.contrib.auth.models import BaseUserManager, AbstractBaseUser, PermissionsMixin
from django.utils import timezone

# Create your models here.

class UserManager(BaseUserManager):
    def create_user(self, email, first_name, last_name, phone_number, password = None):
        if not email:
            raise ValueError('Users must have an email address')
        email = self.normalize_email(email)
        user = self.model(email = email, first_name = first_name, last_name = last_name, phone_number = phone_number)
        user.set_password(password)
        user.is_active = False
        user.is_blocked = False
        user.date_joined = timezone.now()
        user.save(using = self.db)
        return user
    
    def create_superuser(self, email, first_name, last_name, phone_number, password):
        user = self.create_user(email, first_name, last_name, phone_number, password)
        user.is_admin = True
        user.is_staff = True
        user.is_superuser = True
        user.is_active = True
        user.date_joined = timezone.now()
        user.save(using = self.db)
        return user

class User(AbstractBaseUser, PermissionsMixin):
    first_name = models.CharField(max_length = 30)
    last_name = models.CharField(max_length = 30)
    email = models.EmailField(unique = True)
    # username = models.CharField(max_length=30, unique=True, blank=True, null=True)  # New field added
    phone_number = models.CharField(max_length = 15)
    is_active = models.BooleanField(default = False)
    is_admin = models.BooleanField(default = False)
    is_staff = models.BooleanField(default = False)
    is_superuser = models.BooleanField(default = False)
    is_blocked = models.BooleanField(default = False)
    date_joined = models.DateTimeField(default = timezone.now)

    objects = UserManager()

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['first_name', 'last_name', 'phone_number']


    def __str__(self):
        return self.email
    
    def has_perm(self, perm, obj = None):
        return self.is_superuser
    
    def has_module_pers(self,app_label):
        return self.is_superuser
    
    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}".strip()
    
    @full_name.setter
    def full_name(self, value):
        names = value.split(" ", 1)
        self.first_name = names[0]
        self.last_name = names[1] if len(names) > 1 else ""