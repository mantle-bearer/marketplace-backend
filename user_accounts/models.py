import uuid

from django.contrib.auth.base_user import AbstractBaseUser, BaseUserManager
from django.contrib.auth.models import PermissionsMixin
from django.db import models
from django.db.models import Q
from django.utils import timezone


class Role(models.TextChoices):
    CUSTOMER = "customer", "Customer"
    PROVIDER = "provider", "Provider"
    ADMIN = "admin", "Admin"


class UserManager(BaseUserManager):
    use_in_migrations = True

    def _create_user(self, email, password, **extra):
        if not email:
            raise ValueError("Email is required")
        email = self.normalize_email(email).lower()
        user = self.model(email=email, **extra)
        if password:
            user.set_password(password)
        else:
            user.set_unusable_password()
        user.save(using=self._db)
        return user

    def create_user(self, email, password=None, **extra):
        extra.setdefault("is_staff", False)
        extra.setdefault("is_superuser", False)
        extra.setdefault("role", Role.CUSTOMER)
        return self._create_user(email, password, **extra)

    def create_superuser(self, email, password=None, **extra):
        extra.setdefault("is_staff", True)
        extra.setdefault("is_superuser", True)
        extra.setdefault("role", Role.ADMIN)
        if not extra["is_staff"] or not extra["is_superuser"]:
            raise ValueError("Superuser needs is_staff and is_superuser True")
        return self._create_user(email, password, **extra)


class User(AbstractBaseUser, PermissionsMixin):
    id = models.UUIDField(primary_key=True, default=uuid.uuid7, editable=False)
    full_name = models.CharField(max_length=255, null=True, blank=True)
    username = models.CharField(max_length=150, null=True, blank=True)
    email = models.EmailField(unique=True)
    role = models.CharField(
        max_length=20, choices=Role.choices, default=Role.CUSTOMER
    )

    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)

    email_verified = models.BooleanField(default=False)
    email_verified_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(default=timezone.now, editable=False)
    updated_at = models.DateTimeField(auto_now=True)

    objects = UserManager()

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = []

    class Meta:
        abstract = False
        db_table = "users"
        indexes = [
            models.Index(fields=["role"], name="user_role_idx"),
            models.Index(fields=["email"], name="user_email_idx"),
            models.Index(fields=["created_at"], name="user_created_at_idx"),
        ]
        constraints = [
            models.CheckConstraint(
                condition=Q(role__in=Role.values),
                name="user_role_valid",
            ),
            models.CheckConstraint(
                condition=(
                    Q(email_verified=False, email_verified_at__isnull=True)
                    | Q(email_verified=True, email_verified_at__isnull=False)
                ),
                name="user_email_verified_consistent",
            ),
        ]

    def __str__(self):
        return f"{self.email} ({self.role})"

    @property
    def is_customer(self):
        return self.role == Role.CUSTOMER

    @property
    def is_provider(self):
        return self.role == Role.PROVIDER

    @property
    def is_admin_role(self):
        return self.role == Role.ADMIN or self.is_staff or self.is_superuser