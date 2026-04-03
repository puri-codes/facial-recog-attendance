from django.contrib import admin
from .models import Attendance, AttendanceLog


@admin.register(Attendance)
class AttendanceAdmin(admin.ModelAdmin):
    list_display = ('student', 'date', 'status', 'check_in_time', 'is_face_recognized', 'is_override')
    list_filter = ('status', 'date', 'is_face_recognized', 'is_override')
    search_fields = ('student__full_name',)
    date_hierarchy = 'date'


@admin.register(AttendanceLog)
class AttendanceLogAdmin(admin.ModelAdmin):
    list_display = ('attendance', 'action', 'previous_status', 'new_status', 'changed_by', 'timestamp')
    list_filter = ('action', 'timestamp')
    readonly_fields = ('attendance', 'action', 'previous_status', 'new_status', 'changed_by', 'notes', 'timestamp')
