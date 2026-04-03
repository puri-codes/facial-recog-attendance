from django.urls import path
from . import views

app_name = 'academics'

urlpatterns = [
    # Dashboard
    path('dashboard/', views.admin_dashboard, name='admin_dashboard'),

    # Faculties
    path('faculties/', views.faculty_list, name='faculty_list'),
    path('faculties/create/', views.faculty_create, name='faculty_create'),
    path('faculties/<int:pk>/edit/', views.faculty_edit, name='faculty_edit'),
    path('faculties/<int:pk>/delete/', views.faculty_delete, name='faculty_delete'),

    # Classes
    path('classes/', views.class_list, name='class_list'),
    path('classes/create/', views.class_create, name='class_create'),
    path('classes/<int:pk>/edit/', views.class_edit, name='class_edit'),
    path('classes/<int:pk>/delete/', views.class_delete, name='class_delete'),

    # Students
    path('students/', views.student_list, name='student_list'),
    path('students/enroll/', views.student_enroll, name='student_enroll'),
    path('students/enroll/webcam/', views.student_enroll_webcam, name='student_enroll_webcam'),
    path('students/<int:pk>/edit/', views.student_edit, name='student_edit'),
    path('students/<int:pk>/toggle-phone-flag/', views.student_toggle_phone_flag, name='student_toggle_phone_flag'),
    path('students/<int:pk>/delete/', views.student_delete, name='student_delete'),
]
