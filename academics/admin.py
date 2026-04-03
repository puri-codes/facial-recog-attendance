from django.contrib import admin
from .models import Faculty, AcademicClass, Student


@admin.register(Faculty)
class FacultyAdmin(admin.ModelAdmin):
    list_display = ('name', 'created_at')
    search_fields = ('name',)


@admin.register(AcademicClass)
class AcademicClassAdmin(admin.ModelAdmin):
    list_display = ('name', 'faculty', 'teacher', 'created_at')
    list_filter = ('faculty',)
    search_fields = ('name',)


@admin.register(Student)
class StudentAdmin(admin.ModelAdmin):
    list_display = ('full_name', 'academic_class', 'faculty', 'enrollment_year', 'is_active')
    list_filter = ('faculty', 'academic_class', 'enrollment_year', 'is_active')
    search_fields = ('full_name', 'phone')
