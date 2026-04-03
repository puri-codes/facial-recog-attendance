from django.db import models
from django.conf import settings


class Faculty(models.Model):
    """Academic faculty/department."""
    name = models.CharField(max_length=200, unique=True)
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name_plural = 'Faculties'
        ordering = ['name']

    def __str__(self):
        return self.name


class AcademicClass(models.Model):
    """Class belonging to a faculty, optionally assigned to a teacher."""
    name = models.CharField(max_length=200)
    faculty = models.ForeignKey(Faculty, on_delete=models.CASCADE, related_name='classes')
    teacher = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='assigned_classes',
        limit_choices_to={'role': 'teacher'},
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name_plural = 'Classes'
        ordering = ['faculty__name', 'name']
        unique_together = ['name', 'faculty']

    def __str__(self):
        return f"{self.name} — {self.faculty.name}"


class Student(models.Model):
    """Student profile with face recognition data."""
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='student_profile',
        null=True, blank=True,
    )
    full_name = models.CharField(max_length=300)
    profile_image = models.ImageField(upload_to='students/profiles/')
    face_encoding = models.BinaryField(null=True, blank=True, help_text='128-d face encoding as bytes')
    enrollment_year = models.PositiveIntegerField()
    faculty = models.ForeignKey(Faculty, on_delete=models.CASCADE, related_name='students')
    academic_class = models.ForeignKey(AcademicClass, on_delete=models.CASCADE, related_name='students')
    phone = models.CharField(max_length=20, blank=True)
    guardian_phone = models.CharField(max_length=20, blank=True)
    is_phone_flagged = models.BooleanField(
        default=False,
        help_text='Mark this when the student phone number is incorrect.',
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['full_name']

    def __str__(self):
        return f"{self.full_name} ({self.academic_class})"
