from django.db import models
from django.contrib.auth.models import AbstractUser


class User(AbstractUser):
    """Custom user model with role-based access control."""

    class Role(models.TextChoices):
        ADMIN = 'admin', 'Admin'
        TEACHER = 'teacher', 'Teacher'
        STUDENT = 'student', 'Student'

    role = models.CharField(
        max_length=10,
        choices=Role.choices,
        default=Role.STUDENT,
    )
    phone = models.CharField(max_length=20, blank=True)
    profile_image = models.ImageField(upload_to='profiles/', blank=True, null=True)

    @property
    def is_admin_user(self):
        return self.role == self.Role.ADMIN

    @property
    def is_teacher(self):
        return self.role == self.Role.TEACHER

    @property
    def is_student(self):
        return self.role == self.Role.STUDENT

    def __str__(self):
        return f"{self.get_full_name()} ({self.get_role_display()})"
