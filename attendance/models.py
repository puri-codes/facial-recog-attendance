from django.db import models
from django.conf import settings
from academics.models import Student


class Attendance(models.Model):
    """Daily attendance record for a student."""

    class Status(models.TextChoices):
        PRESENT = 'present', 'Present'
        ABSENT = 'absent', 'Absent'
        LATE = 'late', 'Late'
        INFORMED = 'informed', 'Informed'

    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name='attendances')
    date = models.DateField()
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.ABSENT)
    check_in_time = models.TimeField(null=True, blank=True)
    marked_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='marked_attendances',
    )
    is_face_recognized = models.BooleanField(default=False)
    is_override = models.BooleanField(default=False)
    confidence = models.FloatField(null=True, blank=True, help_text='Face recognition confidence score')
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ['student', 'date']
        ordering = ['-date', 'student__full_name']

    def __str__(self):
        return f"{self.student.full_name} — {self.date} — {self.get_status_display()}"


class AttendanceLog(models.Model):
    """Audit log for attendance changes."""

    class Action(models.TextChoices):
        CREATED = 'created', 'Created'
        UPDATED = 'updated', 'Updated'
        OVERRIDDEN = 'overridden', 'Overridden'
        CORRECTED = 'corrected', 'Corrected'

    attendance = models.ForeignKey(Attendance, on_delete=models.CASCADE, related_name='logs')
    action = models.CharField(max_length=12, choices=Action.choices)
    previous_status = models.CharField(max_length=10, blank=True)
    new_status = models.CharField(max_length=10)
    changed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='attendance_logs',
    )
    notes = models.TextField(blank=True)
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-timestamp']

    def __str__(self):
        return f"{self.attendance} — {self.get_action_display()} at {self.timestamp}"
