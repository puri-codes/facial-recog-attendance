import base64
import io
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.files.base import ContentFile
from django.db.models import Count, Q
from django.utils import timezone

from accounts.decorators import admin_required, admin_or_teacher_required
from .models import Faculty, AcademicClass, Student
from .forms import FacultyForm, AcademicClassForm, StudentForm, StudentWebcamForm
from attendance.models import Attendance


@login_required
@admin_required
def admin_dashboard(request):
    """Admin dashboard with overview statistics."""
    today = timezone.localdate()
    total_students = Student.objects.filter(is_active=True).count()
    total_faculties = Faculty.objects.count()
    total_classes = AcademicClass.objects.count()
    today_attendance = Attendance.objects.filter(date=today)
    present_count = today_attendance.filter(status__in=['present', 'late']).count()
    absent_count = today_attendance.filter(status='absent').count()

    recent_students = Student.objects.filter(is_active=True).order_by('-created_at')[:10]
    faculties = Faculty.objects.annotate(student_count=Count('students'))
    classes = AcademicClass.objects.select_related('faculty', 'teacher').annotate(
        student_count=Count('students')
    )

    context = {
        'total_students': total_students,
        'total_faculties': total_faculties,
        'total_classes': total_classes,
        'present_count': present_count,
        'absent_count': absent_count,
        'attendance_rate': round(present_count / total_students * 100, 1) if total_students else 0,
        'recent_students': recent_students,
        'faculties': faculties,
        'classes': classes,
        'today': today,
    }
    return render(request, 'dashboard/admin.html', context)


# ─── Faculty CRUD ───────────────────────────────────────────────

@login_required
@admin_required
def faculty_list(request):
    faculties = Faculty.objects.annotate(
        class_count=Count('classes', distinct=True),
        student_count=Count('students', distinct=True),
    )
    return render(request, 'academics/faculty_list.html', {'faculties': faculties})


@login_required
@admin_required
def faculty_create(request):
    if request.method == 'POST':
        form = FacultyForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Faculty created successfully.')
            return redirect('academics:faculty_list')
    else:
        form = FacultyForm()
    return render(request, 'academics/faculty_form.html', {'form': form, 'title': 'Create Faculty'})


@login_required
@admin_required
def faculty_edit(request, pk):
    faculty = get_object_or_404(Faculty, pk=pk)
    if request.method == 'POST':
        form = FacultyForm(request.POST, instance=faculty)
        if form.is_valid():
            form.save()
            messages.success(request, 'Faculty updated successfully.')
            return redirect('academics:faculty_list')
    else:
        form = FacultyForm(instance=faculty)
    return render(request, 'academics/faculty_form.html', {'form': form, 'title': 'Edit Faculty'})


@login_required
@admin_required
def faculty_delete(request, pk):
    faculty = get_object_or_404(Faculty, pk=pk)
    if request.method == 'POST':
        faculty.delete()
        messages.success(request, 'Faculty deleted successfully.')
        return redirect('academics:faculty_list')
    return render(request, 'academics/confirm_delete.html', {
        'object': faculty, 'type': 'Faculty'
    })


# ─── Class CRUD ─────────────────────────────────────────────────

@login_required
@admin_required
def class_list(request):
    classes = AcademicClass.objects.select_related('faculty', 'teacher').annotate(
        student_count=Count('students')
    )
    return render(request, 'academics/class_list.html', {'classes': classes})


@login_required
@admin_required
def class_create(request):
    if request.method == 'POST':
        form = AcademicClassForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Class created successfully.')
            return redirect('academics:class_list')
    else:
        form = AcademicClassForm()
    return render(request, 'academics/class_form.html', {'form': form, 'title': 'Create Class'})


@login_required
@admin_required
def class_edit(request, pk):
    ac = get_object_or_404(AcademicClass, pk=pk)
    if request.method == 'POST':
        form = AcademicClassForm(request.POST, instance=ac)
        if form.is_valid():
            form.save()
            messages.success(request, 'Class updated successfully.')
            return redirect('academics:class_list')
    else:
        form = AcademicClassForm(instance=ac)
    return render(request, 'academics/class_form.html', {'form': form, 'title': 'Edit Class'})


@login_required
@admin_required
def class_delete(request, pk):
    ac = get_object_or_404(AcademicClass, pk=pk)
    if request.method == 'POST':
        ac.delete()
        messages.success(request, 'Class deleted successfully.')
        return redirect('academics:class_list')
    return render(request, 'academics/confirm_delete.html', {
        'object': ac, 'type': 'Class'
    })


# ─── Student Management ────────────────────────────────────────

@login_required
@admin_or_teacher_required
def student_list(request):
    """Student database with filters."""
    students = Student.objects.filter(is_active=True).select_related('faculty', 'academic_class')

    # Filters
    faculty_id = request.GET.get('faculty')
    class_id = request.GET.get('class')
    search = request.GET.get('search', '')
    year = request.GET.get('year')

    if faculty_id:
        students = students.filter(faculty_id=faculty_id)
    if class_id:
        students = students.filter(academic_class_id=class_id)
    if search:
        students = students.filter(
            Q(full_name__icontains=search) | Q(phone__icontains=search)
        )
    if year:
        students = students.filter(enrollment_year=year)

    # Get today's attendance for each student
    today = timezone.localdate()
    attendance_map = {}
    for att in Attendance.objects.filter(date=today, student__in=students):
        attendance_map[att.student_id] = att.status

    students = list(students)
    for s in students:
        s.today_status = attendance_map.get(s.id)

    faculties = Faculty.objects.all()
    classes = AcademicClass.objects.all()

    context = {
        'students': students,
        'faculties': faculties,
        'classes': classes,
        'search': search,
        'selected_faculty': faculty_id,
        'selected_class': class_id,
        'selected_year': year,
    }
    return render(request, 'academics/student_list.html', context)


@login_required
@admin_required
def student_enroll(request):
    """Enroll student via image upload and create User account."""
    if request.method == 'POST':
        form = StudentForm(request.POST, request.FILES)
        if form.is_valid():
            student = form.save(commit=False)
            
            # Create User account for student if not already linked
            if not student.user:
                from accounts.models import User
                # Generate username from student name
                base_username = student.full_name.lower().replace(' ', '_')
                username = base_username
                counter = 1
                while User.objects.filter(username=username).exists():
                    username = f"{base_username}_{counter}"
                    counter += 1
                
                user = User.objects.create_user(
                    username=username,
                    email=f"{username}@students.local",
                    first_name=student.full_name.split()[0] if student.full_name else '',
                    last_name=' '.join(student.full_name.split()[1:]) if len(student.full_name.split()) > 1 else '',
                    role='student',
                )
                student.user = user
            
            student.save()
            
            # Generate face encoding from uploaded image
            try:
                from attendance.face_utils import encode_face_from_image
                encoding = encode_face_from_image(student.profile_image.path)
                if encoding is not None:
                    student.face_encoding = encoding.tobytes()
                    student.save()
                    messages.success(request, f'{student.full_name} enrolled with face encoding and user account created.')
                else:
                    messages.warning(request, f'{student.full_name} enrolled but no face detected in image.')
            except Exception as e:
                messages.warning(request, f'{student.full_name} enrolled. Face encoding failed: {str(e)}')
            return redirect('academics:student_list')
    else:
        form = StudentForm()
    return render(request, 'academics/student_enroll.html', {'form': form, 'title': 'Enroll Student'})


@login_required
@admin_required
def student_enroll_webcam(request):
    """Enroll student via webcam capture and create User account."""
    if request.method == 'POST':
        form = StudentWebcamForm(request.POST)
        if form.is_valid():
            # Decode webcam image
            image_data = form.cleaned_data['webcam_image']
            if ',' in image_data:
                image_data = image_data.split(',')[1]
            image_bytes = base64.b64decode(image_data)

            # Create User account for student
            from accounts.models import User
            full_name = form.cleaned_data['full_name']
            base_username = full_name.lower().replace(' ', '_')
            username = base_username
            counter = 1
            while User.objects.filter(username=username).exists():
                username = f"{base_username}_{counter}"
                counter += 1
            
            user = User.objects.create_user(
                username=username,
                email=f"{username}@students.local",
                first_name=full_name.split()[0] if full_name else '',
                last_name=' '.join(full_name.split()[1:]) if len(full_name.split()) > 1 else '',
                role='student',
            )

            student = Student(
                full_name=full_name,
                enrollment_year=form.cleaned_data['enrollment_year'],
                faculty=form.cleaned_data['faculty'],
                academic_class=form.cleaned_data['academic_class'],
                phone=form.cleaned_data.get('phone', ''),
                guardian_phone=form.cleaned_data.get('guardian_phone', ''),
                user=user,
            )
            student.profile_image.save(
                f"{full_name.replace(' ', '_')}.jpg",
                ContentFile(image_bytes),
                save=False,
            )
            student.save()

            # Generate face encoding
            try:
                from attendance.face_utils import encode_face_from_image
                encoding = encode_face_from_image(student.profile_image.path)
                if encoding is not None:
                    student.face_encoding = encoding.tobytes()
                    student.save()
                    messages.success(request, f'{student.full_name} enrolled with face encoding and user account created.')
                else:
                    messages.warning(request, f'{student.full_name} enrolled but no face detected.')
            except Exception as e:
                messages.warning(request, f'{student.full_name} enrolled. Face encoding failed: {str(e)}')
            return redirect('academics:student_list')
    else:
        form = StudentWebcamForm()
    return render(request, 'academics/student_enroll_webcam.html', {'form': form, 'title': 'Enroll via Webcam'})


@login_required
@admin_required
def student_edit(request, pk):
    student = get_object_or_404(Student, pk=pk)
    if request.method == 'POST':
        form = StudentForm(request.POST, request.FILES, instance=student)
        if form.is_valid():
            student = form.save()
            # Re-generate face encoding if image changed
            if 'profile_image' in request.FILES:
                try:
                    from attendance.face_utils import encode_face_from_image
                    encoding = encode_face_from_image(student.profile_image.path)
                    if encoding is not None:
                        student.face_encoding = encoding.tobytes()
                        student.save()
                except Exception:
                    pass
            messages.success(request, 'Student updated successfully.')
            return redirect('academics:student_list')
    else:
        form = StudentForm(instance=student)
    return render(request, 'academics/student_enroll.html', {
        'form': form, 'title': 'Edit Student', 'student': student
    })


@login_required
@admin_required
def student_delete(request, pk):
    student = get_object_or_404(Student, pk=pk)
    if request.method == 'POST':
        student.is_active = False
        student.save()
        messages.success(request, 'Student deactivated successfully.')
        return redirect('academics:student_list')
    return render(request, 'academics/confirm_delete.html', {
        'object': student, 'type': 'Student'
    })


@login_required
@admin_or_teacher_required
def student_toggle_phone_flag(request, pk):
    if request.method != 'POST':
        return redirect('academics:student_list')

    student = get_object_or_404(Student, pk=pk, is_active=True)
    student.is_phone_flagged = not student.is_phone_flagged
    student.save()

    if student.is_phone_flagged:
        messages.warning(request, f'Flagged guardian number for {student.full_name}.')
    else:
        messages.success(request, f'Removed wrong guardian-number flag for {student.full_name}.')

    next_url = request.POST.get('next')
    if next_url:
        return redirect(next_url)
    return redirect('academics:student_list')
