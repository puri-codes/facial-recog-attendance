from django.urls import path
from . import views

app_name = 'attendance'

urlpatterns = [
    # Face Recognition Login
    path('face-login/', views.face_login, name='face_login'),

    # Camera-based attendance
    path('camera/', views.attendance_camera, name='camera'),

    # Manual attendance
    path('manual/', views.manual_attendance, name='manual'),
    path('override/<int:pk>/', views.attendance_override, name='override'),

    # Teacher views
    path('teacher/', views.teacher_dashboard, name='teacher_dashboard'),
    path('teacher/class/<int:class_id>/', views.teacher_class_attendance, name='teacher_class'),
    path('teacher/correct/<int:pk>/', views.teacher_correct_attendance, name='teacher_correct'),

    # Student views
    path('student/', views.student_dashboard, name='student_dashboard'),

    # Reports
    path('daily/', views.daily_report, name='daily_report'),
    path('monthly/', views.monthly_report, name='monthly_report'),
    path('logs/<int:pk>/', views.attendance_logs, name='logs'),
]
