from django.urls import path
from attendance import views

app_name = 'api'

urlpatterns = [
    # Face Recognition - Attendance Marking
    path('face-login/', views.api_mark_attendance, name='face_login'),
    path('mark-attendance/', views.api_mark_attendance, name='mark_attendance'),
    path('recognize/', views.api_recognize_face, name='recognize'),
    path('encode-face/', views.api_encode_face, name='encode_face'),
    path('bulk-encode/', views.api_bulk_encode_faces, name='bulk_encode'),
    path('link-students/', views.api_link_students_to_users, name='link_students'),
    
    # Attendance - Manual Marking
    path('attendance/', views.api_attendance_list, name='attendance_list'),
    path('attendance/mark/', views.api_manual_mark_attendance, name='manual_mark'),
    path('dashboard/', views.api_dashboard_data, name='dashboard_data'),
]
