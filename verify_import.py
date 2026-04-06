import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'facial_attendance.settings')
django.setup()

from academics.models import Student
from accounts.models import User

print("\n📊 IMPORTED STUDENTS:\n")
students = Student.objects.all()
for student in students:
    print(f"ID: {student.id}")
    print(f"  Full Name: {student.full_name}")
    print(f"  User: {student.user}")
    print(f"  Phone: {student.phone}")
    print(f"  Guardian Phone: {student.guardian_phone}")
    print(f"  Faculty: {student.faculty}")
    print(f"  Academic Class: {student.academic_class}")
    print(f"  Enrollment Year: {student.enrollment_year}")
    print(f"  Profile Image: {bool(student.profile_image)}")
    print(f"  Is Active: {student.is_active}")
    print()

print(f"✅ Total Students: {students.count()}")
print(f"✅ Total Student Users: {User.objects.filter(role='student').count()}")
