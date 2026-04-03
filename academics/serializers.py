from rest_framework import serializers
from .models import Faculty, AcademicClass, Student


class FacultySerializer(serializers.ModelSerializer):
    class Meta:
        model = Faculty
        fields = '__all__'


class AcademicClassSerializer(serializers.ModelSerializer):
    faculty_name = serializers.CharField(source='faculty.name', read_only=True)
    teacher_name = serializers.SerializerMethodField()

    class Meta:
        model = AcademicClass
        fields = ['id', 'name', 'faculty', 'faculty_name', 'teacher', 'teacher_name']

    def get_teacher_name(self, obj):
        return obj.teacher.get_full_name() if obj.teacher else None


class StudentSerializer(serializers.ModelSerializer):
    faculty_name = serializers.CharField(source='faculty.name', read_only=True)
    class_name = serializers.CharField(source='academic_class.name', read_only=True)

    class Meta:
        model = Student
        fields = [
            'id', 'full_name', 'profile_image', 'enrollment_year',
            'faculty', 'faculty_name', 'academic_class', 'class_name',
            'phone', 'guardian_phone', 'is_active',
        ]
