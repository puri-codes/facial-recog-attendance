from rest_framework import serializers
from .models import Attendance, AttendanceLog


class AttendanceSerializer(serializers.ModelSerializer):
    student_name = serializers.CharField(source='student.full_name', read_only=True)
    class_name = serializers.CharField(source='student.academic_class.name', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)

    class Meta:
        model = Attendance
        fields = [
            'id', 'student', 'student_name', 'class_name', 'date',
            'status', 'status_display', 'check_in_time',
            'is_face_recognized', 'confidence', 'is_override', 'notes',
        ]


class AttendanceLogSerializer(serializers.ModelSerializer):
    changed_by_name = serializers.SerializerMethodField()

    class Meta:
        model = AttendanceLog
        fields = [
            'id', 'attendance', 'action', 'previous_status',
            'new_status', 'changed_by', 'changed_by_name', 'notes', 'timestamp',
        ]

    def get_changed_by_name(self, obj):
        return obj.changed_by.get_full_name() if obj.changed_by else 'System'


class FaceRecognitionSerializer(serializers.Serializer):
    """Serializer for face recognition API input."""
    image = serializers.CharField(help_text='Base64-encoded image frame')
    class_id = serializers.IntegerField(required=False, allow_null=True)
    class_start_time = serializers.TimeField(
        required=False,
        input_formats=['%H:%M', '%H:%M:%S'],
    )
    threshold_time = serializers.TimeField(
        required=False,
        input_formats=['%H:%M', '%H:%M:%S'],
    )
    end_time = serializers.TimeField(
        required=False,
        input_formats=['%H:%M', '%H:%M:%S'],
    )
    initialize_absent = serializers.BooleanField(required=False, default=False)
