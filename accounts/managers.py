from django.contrib.auth.base_user import BaseUserManager
import hashlib
import secrets
from datetime import timedelta
from django.db import models
from django.utils import timezone


class UserManager(BaseUserManager):
    def create_user(self, phone_number, password=None, **extra_fields):
        if not phone_number: raise ValueError("Phone Number is required.")
        phone_number = self.normalize_email(phone_number)
        user = self.model(phone_number=phone_number, **extra_fields )
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, phone_number, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        return self.create_user(phone_number, password, **extra_fields )

