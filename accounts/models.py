from django.db import models
from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin
from common.models import BaseModel
from .choices import DeviceType, OTPPurpose, LoginMethod, LoginStatus, UserType
from .managers import UserManager
from django.utils import timezone


class User(AbstractBaseUser, PermissionsMixin, BaseModel):
    email = models.EmailField(blank=True, null=True, db_index=True)
    phone_number = models.CharField(max_length=30, unique=True, db_index=True)
    full_name = models.CharField(max_length=100, blank=True)
    country_code = models.CharField(max_length=10, blank=True)
    profile_picture = models.ImageField(upload_to="users/profile/", blank=True, null=True)
    user_type = models.CharField(max_length=20, choices=UserType.choices, default=UserType.CLIENT)

    is_phone_verified = models.BooleanField(default=False)
    failed_login_attempts = models.PositiveSmallIntegerField(default=0)
    last_password_changed_at = models.DateTimeField(blank=True, null=True)
    last_activity_at = models.DateTimeField(blank=True, null=True, db_index=True)
    is_staff = models.BooleanField(default=False)

    objects = UserManager()
    USERNAME_FIELD = "phone_number"
    REQUIRED_FIELDS = []

    class Meta:
        db_table = "users"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["phone_number"]),
            models.Index(fields=["email"]),
            models.Index(fields=["status"]),
            models.Index(fields=["last_activity_at"]),
        ]

    def __str__(self):
        return self.phone_number

class Device(BaseModel):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="devices")
    device_id = models.CharField(max_length=255)
    device_name = models.CharField(max_length=255)
    device_type = models.CharField(max_length=20, choices=DeviceType.choices)
    
    os_version = models.CharField(max_length=100, blank=True)
    app_version = models.CharField(max_length=50, blank=True)
    manufacturer = models.CharField(max_length=100, blank=True)
    model = models.CharField(max_length=100, blank=True)
    
    fcm_token = models.TextField(blank=True)
    ip_address = models.GenericIPAddressField(blank=True, null=True)
    last_seen_at = models.DateTimeField(auto_now=True, db_index=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = "user_devices"
        ordering = ["-last_seen_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["user", "device_id"],
                name="unique_user_device",
            )
        ]

        indexes = [
            models.Index(fields=["user"]),
            models.Index(fields=["device_type"]),
            models.Index(fields=["last_seen_at"]),
        ]

    def __str__(self):
        return f"{self.user.phone_number} - {self.device_name}"

class OTPVerification(BaseModel):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="otp_verifications")
    phone_number = models.CharField(max_length=30)
    otp_hash = models.CharField(max_length=255)
    otp_code = models.CharField(max_length=10, blank=True, null=True)
    purpose = models.CharField(max_length=30, choices=OTPPurpose.choices)
    expires_at = models.DateTimeField()
    verified_at = models.DateTimeField(blank=True, null=True)
    attempt_count = models.PositiveSmallIntegerField(default=0)
    max_attempts = models.PositiveSmallIntegerField(default=5)
    is_used = models.BooleanField(default=False)
    
    class Meta:
        db_table = "otp_verifications"

        indexes = [
            models.Index(fields=["user"]),
            models.Index(fields=["phone_number"]),
            models.Index(fields=["purpose"]),
            models.Index(fields=["expires_at"]),
        ]
    
    def verify(self, otp: str):
        if self.is_used:
            return False, "OTP already used."
        if timezone.now() >= self.expires_at:
            return False, "OTP has expired."
        if self.attempt_count >= self.max_attempts:
            return False, "Maximum verification attempts exceeded."
        
        hashed_otp = self.__class__.objects.hash_otp(otp)
        if hashed_otp != self.otp_hash:
            self.attempt_count += 1
            self.save(update_fields=["attempt_count"])
            return False, "Invalid OTP."
    
        self.is_used = True
        self.verified_at = timezone.now()
        self.save(update_fields=["is_used", "verified_at"])
        return True, "OTP verified successfully."

class LoginHistory(BaseModel):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    phone_number = models.CharField(max_length=30)
    device = models.ForeignKey(Device, on_delete=models.SET_NULL, null=True, blank=True)
    ip_address = models.GenericIPAddressField(null=True)
    login_method = models.CharField(max_length=20, choices=LoginMethod.choices)
    status = models.CharField(max_length=20, choices=LoginStatus.choices)
    failure_reason = models.CharField(max_length=100, blank=True)

