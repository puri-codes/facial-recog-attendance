import os
import django
import re

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'facial_attendance.settings')
django.setup()

from accounts.models import User
from academics.models import Faculty, AcademicClass, Student
from django.utils import timezone


def _username_from_name(name):
    base = re.sub(r'[^a-z0-9]+', '_', (name or '').strip().lower()).strip('_')
    return base or 'student'


def _unique_username(base, exclude_user_id=None):
    username = base
    counter = 1
    while True:
        qs = User.objects.filter(username=username)
        if exclude_user_id:
            qs = qs.exclude(id=exclude_user_id)
        if not qs.exists():
            return username
        username = f"{base}_{counter}"
        counter += 1


def _sync_all_student_credentials(default_password='presidential'):
    """Set student usernames from student names and a shared password for all students."""
    updated = 0

    students = Student.objects.select_related('user').all()
    for student in students:
        desired_base = _username_from_name(student.full_name)

        if student.user:
            user = student.user
            user.username = _unique_username(desired_base, exclude_user_id=user.id)
            user.role = 'student'
            user.is_active = True
            user.is_staff = False
            user.is_superuser = False
            if not user.first_name:
                user.first_name = (student.full_name.split()[0] if student.full_name else '')
            if not user.last_name:
                user.last_name = (' '.join(student.full_name.split()[1:]) if len(student.full_name.split()) > 1 else '')
            user.set_password(default_password)
            user.save()
        else:
            username = _unique_username(desired_base)
            user = User.objects.create_user(
                username=username,
                password=default_password,
                first_name=(student.full_name.split()[0] if student.full_name else ''),
                last_name=(' '.join(student.full_name.split()[1:]) if len(student.full_name.split()) > 1 else ''),
                role='student',
            )
            student.user = user
            student.save(update_fields=['user'])

        updated += 1

    return updated

def setup_demo_data():
    print("Setting up demo data...")

    # 1. Create Faculty
    faculty, _ = Faculty.objects.get_or_create(
        name="Science & Technology",
        defaults={'description': 'Main engineering faculty'}
    )

    # 2. Create Admin (separate credentials)
    admin_user, created = User.objects.get_or_create(
        username='admin',
        defaults={
            'first_name': 'System',
            'last_name': 'Admin',
            'email': 'admin@example.com',
            'role': 'admin',
            'is_staff': True,
            'is_superuser': True,
        }
    )
    admin_user.role = 'admin'
    admin_user.is_staff = True
    admin_user.is_superuser = True
    admin_user.is_active = True
    admin_user.set_password('admin123')
    admin_user.save()
    print("Admin ready:   admin / admin123")

    # 3. Create Teacher (separate credentials)
    teacher_user, created = User.objects.get_or_create(
        username='teacher1',
        defaults={
            'first_name': 'John',
            'last_name': 'Doe',
            'email': 'teacher@example.com',
            'role': 'teacher',
        }
    )
    teacher_user.role = 'teacher'
    teacher_user.is_staff = False
    teacher_user.is_superuser = False
    teacher_user.is_active = True
    teacher_user.set_password('teacher123')
    teacher_user.save()
    print("Teacher ready: teacher1 / teacher123")

    # 4. Create Class
    academic_class, _ = AcademicClass.objects.get_or_create(
        name="Computer Science - Year 1",
        faculty=faculty,
        defaults={'teacher': teacher_user}
    )

    # 5. Create Student User (bootstrap student profile)
    student_user, created = User.objects.get_or_create(
        username='alice_smith',
        defaults={
            'first_name': 'Alice',
            'last_name': 'Smith',
            'email': 'student@example.com',
            'role': 'student',
        }
    )
    student_user.role = 'student'
    student_user.is_staff = False
    student_user.is_superuser = False
    student_user.is_active = True
    student_user.set_password('presidential')
    student_user.save()
    print("Student bootstrap ready: alice_smith / presidential")

    # 6. Create Student Profile
    student_profile, created = Student.objects.get_or_create(
        user=student_user,
        defaults={
            'full_name': 'Alice Smith',
            'enrollment_year': 2025,
            'faculty': faculty,
            'academic_class': academic_class,
            'phone': '9876543210',
        }
    )
    student_profile.full_name = 'Alice Smith'
    student_profile.enrollment_year = 2025
    student_profile.faculty = faculty
    student_profile.academic_class = academic_class
    if not student_profile.phone:
        student_profile.phone = '9876543210'
    student_profile.is_active = True
    student_profile.save()
    if created:
        print("Created Student Profile for Alice Smith")
    else:
        print("Student Profile updated for Alice Smith")

    updated_students = _sync_all_student_credentials(default_password='presidential')
    print(f"Updated credentials for {updated_students} student account(s).")

    print("\n--- Setup Complete ---")
    print("Admin:   admin / admin123")
    print("Teacher: teacher1 / teacher123")
    print("Student: <student_name_as_username> / presidential")

if __name__ == "__main__":
    setup_demo_data()
