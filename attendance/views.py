import numpy as np
import logging
from datetime import datetime
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.auth import login as auth_login
from django.contrib import messages
from django.http import JsonResponse
from django.utils import timezone
from django.conf import settings
from django.db.models import Count, Q
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

# Suppress urllib3 SSL warnings for development
try:
    import urllib3
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
except Exception:
    pass

from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response

from accounts.decorators import admin_required, teacher_required, student_required, admin_or_teacher_required
from accounts.models import User
from academics.models import Faculty, AcademicClass, Student
from .models import Attendance, AttendanceLog
from .serializers import AttendanceSerializer, FaceRecognitionSerializer
from .face_utils import (
    decode_base64_image, detect_faces, encode_face_from_array,
    match_face, FACE_RECOGNITION_AVAILABLE,
)

logger = logging.getLogger(__name__)


def _parse_time_setting(setting_name, fallback):
    """Parse HH:MM / HH:MM:SS time from settings with a safe fallback."""
    value = getattr(settings, setting_name, fallback)
    for fmt in ('%H:%M', '%H:%M:%S'):
        try:
            return datetime.strptime(value, fmt).time()
        except (TypeError, ValueError):
            continue
    return datetime.strptime(fallback, '%H:%M').time()


def _resolve_attendance_window(validated_data):
    """Resolve class/threshold/end times from request data or settings."""
    class_start_time = validated_data.get('class_start_time') or _parse_time_setting(
        'ATTENDANCE_CLASS_TIME', '09:00'
    )
    threshold_time = validated_data.get('threshold_time') or _parse_time_setting(
        'ATTENDANCE_THRESHOLD_TIME', '10:00'
    )
    end_time = validated_data.get('end_time') or _parse_time_setting(
        'ATTENDANCE_CUTOFF_TIME', '12:00'
    )
    return class_start_time, threshold_time, end_time


def _initialize_absent_attendance(students, target_date, user, class_start_time, threshold_time, end_time):
    """
    Ensure every student has an attendance record for the day.
    Unscanned students stay absent by default.
    """
    created_count = 0
    marker = user if getattr(user, 'is_authenticated', False) else None
    notes = (
        f"Auto-absent initialized. Class: {class_start_time.strftime('%H:%M')}, "
        f"Threshold: {threshold_time.strftime('%H:%M')}, End: {end_time.strftime('%H:%M')}"
    )

    for student in students:
        attendance, created = Attendance.objects.get_or_create(
            student=student,
            date=target_date,
            defaults={
                'status': 'absent',
                'marked_by': marker,
                'notes': notes,
            },
        )
        if created:
            created_count += 1
            AttendanceLog.objects.create(
                attendance=attendance,
                action='created',
                new_status='absent',
                changed_by=marker,
                notes='Automatically marked absent until scanned.',
            )

    return created_count


# ─── Face Recognition Login ──────────────────────────────────────

def face_login(request):
    """24/7 Face Recognition Attendance System."""
    return render(request, 'attendance/face_attendance.html', {
        'face_recognition_available': FACE_RECOGNITION_AVAILABLE,
    })


@api_view(['POST'])
@permission_classes([AllowAny])
def api_mark_attendance(request):
    """
    API endpoint: Detect face and automatically mark attendance.
    Returns attendance status (present/late) based on current time.
    """
    if not FACE_RECOGNITION_AVAILABLE:
        return Response({'error': 'Face recognition not available'}, status=503)
    
    serializer = FaceRecognitionSerializer(data=request.data)
    if not serializer.is_valid():
        return Response({'error': serializer.errors}, status=400)

    image_data = serializer.validated_data['image']

    # Decode image
    try:
        image_array = decode_base64_image(image_data)
    except Exception as e:
        return Response({'error': f'Invalid image: {str(e)}'}, status=400)

    if image_array is None:
        return Response({'error': 'Could not decode image'}, status=400)

    # Detect faces
    face_locations = detect_faces(image_array)

    # Get all student encodings
    students_qs = Student.objects.filter(
        face_encoding__isnull=False,
        is_active=True,
    )

    known_encodings = []
    known_ids = []
    for s in students_qs:
        try:
            enc = np.frombuffer(s.face_encoding, dtype=np.float64)
            if enc.shape == (128,):
                known_encodings.append(enc)
                known_ids.append(s.id)
        except Exception:
            continue

    # Process detected faces for attendance marking
    from django.utils import timezone
    from datetime import time as dtime
    
    results = []
    
    for face_loc in face_locations:
        top, right, bottom, left = face_loc
        
        # Add safety bounds for crop
        h, w = image_array.shape[:2]
        top = max(0, top - 20)
        bottom = min(h, bottom + 20)
        left = max(0, left - 20)
        right = min(w, right + 20)
        
        # Get encoding for this face
        face_crop = image_array[top:bottom, left:right]
        face_encoding = encode_face_from_array(face_crop)

        if face_encoding is None:
            results.append({
                'bbox': {'top': top, 'right': right, 'bottom': bottom, 'left': left},
                'matched': False,
                'message': 'Could not encode face',
            })
            continue

        matched_id, confidence = match_face(
            face_encoding, known_encodings, known_ids,
            tolerance=getattr(settings, 'FACE_RECOGNITION_TOLERANCE', 0.6),
        )

        if matched_id:
            student = Student.objects.get(id=matched_id)
            current_time = timezone.now()
            current_date = current_time.date()
            check_in_time = current_time.time()
            
            # Determine if present or late (before/after 10:00 AM)
            cutoff_time = dtime(10, 0, 0)  # 10:00 AM cutoff
            is_late = check_in_time > cutoff_time
            status = 'late' if is_late else 'present'
            
            # Get or create attendance record for today
            attendance, created = Attendance.objects.get_or_create(
                student=student,
                date=current_date,
                defaults={
                    'status': status,
                    'check_in_time': check_in_time,
                    'is_face_recognized': True,
                    'confidence': confidence,
                }
            )
            
            # If record already exists but not yet marked as present, update it
            if not created and attendance.status == 'absent':
                attendance.status = status
                attendance.check_in_time = check_in_time
                attendance.is_face_recognized = True
                attendance.confidence = confidence
                attendance.save()
            
            results.append({
                'bbox': {'top': top, 'right': right, 'bottom': bottom, 'left': left},
                'matched': True,
                'student_id': student.id,
                'student_name': student.full_name,
                'attendance_status': attendance.status,
                'check_in_time': check_in_time.strftime('%H:%M:%S'),
                'confidence': int(confidence * 100),
                'message': f'{student.full_name} marked {attendance.status}',
                'created': created,
            })
        else:
            results.append({
                'bbox': {'top': top, 'right': right, 'bottom': bottom, 'left': left},
                'matched': False,
                'message': 'Face not recognized',
            })

    return Response({
        'faces_detected': len(face_locations),
        'results': results,
    })


# ─── Real-Time Face Encoding ────────────────────────────────────

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def api_encode_face(request):
    """
    Real-time face encoding API endpoint.
    Accept base64 image, extract face, generate encoding, and optionally save to student.
    Returns encoding status and face detection details.
    """
    if not FACE_RECOGNITION_AVAILABLE:
        return Response({'error': 'Face recognition not available'}, status=503)

    serializer = FaceRecognitionSerializer(data=request.data)
    if not serializer.is_valid():
        return Response({'error': serializer.errors}, status=400)

    image_data = serializer.validated_data['image']
    student_id = request.data.get('student_id')

    # Decode image
    try:
        image_array = decode_base64_image(image_data)
    except Exception as e:
        return Response({'error': f'Invalid image: {str(e)}'}, status=400)

    if image_array is None:
        return Response({'error': 'Could not decode image'}, status=400)

    # Detect faces
    face_locations = detect_faces(image_array)
    if not face_locations:
        return Response({
            'success': False,
            'message': 'No faces detected in image',
            'faces_detected': 0,
        })

    if len(face_locations) > 1:
        return Response({
            'success': False,
            'message': f'Multiple faces detected ({len(face_locations)}). Please provide only one face.',
            'faces_detected': len(face_locations),
        })

    # Extract and encode the single face
    top, right, bottom, left = face_locations[0]
    h, w = image_array.shape[:2]
    
    # Add safety bounds for crop
    top_crop = max(0, top - 20)
    bottom_crop = min(h, bottom + 20)
    left_crop = max(0, left - 20)
    right_crop = min(w, right + 20)

    face_crop = image_array[top_crop:bottom_crop, left_crop:right_crop]
    face_encoding = encode_face_from_array(face_crop)

    if face_encoding is None:
        return Response({
            'success': False,
            'message': 'Could not generate face encoding from detected face',
            'faces_detected': 1,
        })

    # If student_id provided, save encoding to database
    updated = False
    if student_id:
        try:
            student = Student.objects.get(id=student_id)
            student.face_encoding = face_encoding.tobytes()
            student.save()
            updated = True
        except Student.DoesNotExist:
            return Response({'error': 'Student not found'}, status=404)

    return Response({
        'success': True,
        'message': 'Face encoding generated successfully' + (' and saved to student' if updated else ''),
        'faces_detected': 1,
        'face_bbox': {
            'top': int(top),
            'right': int(right),
            'bottom': int(bottom),
            'left': int(left),
        },
        'encoding_generated': True,
        'encoding_saved': updated,
    })


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def api_import_students_from_database(request):
    """
    Import students from remote API and update local database.
    Admin only.
    """
    # Check admin permission
    if request.user.role != 'admin':
        return Response({'error': 'Admin access required'}, status=403)

    import json
    import ssl
    from django.core.files.base import ContentFile
    from urllib.error import HTTPError, URLError
    from urllib.request import Request, urlopen
    from urllib.parse import urlparse
    import os
    
    try:
        # API Configuration
        API_BASE_URL = getattr(settings, 'REMOTE_API_URL', 'http://10.20.46.165:8000')
        API_TOKEN_URL = f"{API_BASE_URL}/api/auth/token/"
        API_STUDENTS_URL = f"{API_BASE_URL}/api/students/"
        API_COURSES_URL = f"{API_BASE_URL}/api/courses/"
        USERNAME = getattr(settings, 'REMOTE_API_USERNAME', 'admin')
        PASSWORD = getattr(settings, 'REMOTE_API_PASSWORD', 'admin')

        try:
            import requests as requests_lib
        except ModuleNotFoundError:
            requests_lib = None

        session = None
        if requests_lib:
            session = requests_lib.Session()
            session.verify = False  # Development setup on local network API

        ssl_context = ssl._create_unverified_context()

        def http_get_json(url, headers=None, timeout=15, allow_unauthorized=False):
            if requests_lib and session:
                response = session.get(url, headers=headers, timeout=timeout)
                if allow_unauthorized and response.status_code == 401:
                    return None, 401
                response.raise_for_status()
                return response.json(), response.status_code

            req = Request(url, headers=headers or {}, method='GET')
            try:
                with urlopen(req, timeout=timeout, context=ssl_context) as response:
                    payload = response.read().decode('utf-8')
                    status_code = getattr(response, 'status', 200)
                    return json.loads(payload or '{}'), status_code
            except HTTPError as e:
                if allow_unauthorized and e.code == 401:
                    return None, 401
                raise

        def http_post_json(url, payload, headers=None, timeout=10):
            if requests_lib and session:
                response = session.post(url, json=payload, headers=headers, timeout=timeout)
                response.raise_for_status()
                return response.json()

            body = json.dumps(payload).encode('utf-8')
            request_headers = {'Content-Type': 'application/json'}
            if headers:
                request_headers.update(headers)
            req = Request(url, data=body, headers=request_headers, method='POST')
            with urlopen(req, timeout=timeout, context=ssl_context) as response:
                text = response.read().decode('utf-8')
                return json.loads(text or '{}')

        def http_get_binary(url, headers=None, timeout=10):
            if requests_lib and session:
                response = session.get(url, headers=headers, timeout=timeout)
                response.raise_for_status()
                return response.content

            req = Request(url, headers=headers or {}, method='GET')
            with urlopen(req, timeout=timeout, context=ssl_context) as response:
                return response.read()

        def fetch_paginated(url, auth_headers=None):
            """Fetch all pages for DRF-style paginated endpoints."""
            records = []
            next_url = url
            page_count = 0
            max_pages = 200

            while next_url and page_count < max_pages:
                page_count += 1
                payload, status_code = http_get_json(
                    next_url,
                    headers=auth_headers,
                    timeout=15,
                    allow_unauthorized=True,
                )

                # Retry without auth if endpoint is public and token auth fails.
                if status_code == 401 and auth_headers:
                    payload, _ = http_get_json(next_url, headers=None, timeout=15)

                if isinstance(payload, dict) and 'results' in payload:
                    records.extend(payload.get('results') or [])
                    next_url = payload.get('next')
                elif isinstance(payload, list):
                    records.extend(payload)
                    next_url = None
                else:
                    next_url = None

            return records

        token = None
        headers = None
        logger.info(f"Attempting token authentication with {API_TOKEN_URL}")

        try:
            token_payload = http_post_json(
                API_TOKEN_URL,
                payload={"username": USERNAME, "password": PASSWORD},
                timeout=10,
            )
            token = token_payload.get("token")
            if token:
                headers = {"Authorization": f"Token {token}"}
                logger.info("Token authentication succeeded")
            else:
                logger.warning("Token endpoint responded without token; using public endpoint access")
        except Exception as auth_err:
            logger.warning(f"Token authentication unavailable: {auth_err}. Falling back to public GET endpoints.")

        logger.info(f"Fetching all student pages from {API_STUDENTS_URL}")
        try:
            students_data = fetch_paginated(API_STUDENTS_URL, auth_headers=headers)
            logger.info(f"Fetched {len(students_data)} students from remote API")
        except TimeoutError:
            return Response({'error': 'Student API request timed out'}, status=504)
        except URLError as e:
            return Response({'error': f'Cannot connect to API server: {str(e)}'}, status=503)
        except Exception as e:
            return Response({'error': f'Failed to fetch students: {str(e)}'}, status=400)

        courses_data = []
        try:
            courses_data = fetch_paginated(API_COURSES_URL, auth_headers=headers)
            logger.info(f"Fetched {len(courses_data)} courses from remote API")
        except Exception as courses_err:
            logger.warning(f"Could not fetch courses endpoint: {courses_err}")
        
        results = {
            'total': len(students_data),
            'created': 0,
            'updated': 0,
            'failed': 0,
            'errors': [],
            'remote_students_fetched': len(students_data),
            'remote_courses_fetched': len(courses_data),
        }
        
        for student_data in students_data:
            try:
                # Get or create faculty
                faculty_name = student_data.get('faculty', 'BSIT').upper()
                faculty, _ = Faculty.objects.get_or_create(
                    name=faculty_name,
                    defaults={'description': f'{faculty_name} Faculty'}
                )
                
                # Get or create academic class
                academic_year = student_data.get('academic_year', 'year_1')
                academic_class, _ = AcademicClass.objects.get_or_create(
                    name=academic_year,
                    faculty=faculty,
                )
                
                # Handle user account
                email = student_data.get('email', '')
                student_id = student_data.get('student_id_number', '')
                
                if not email:
                    email = f"{student_id}@school.local"
                
                user = User.objects.filter(email=email).first()
                
                if not user:
                    username = student_id or f"student_{student_data['id']}"
                    full_name = student_data.get('full_name', '')
                    user, _ = User.objects.get_or_create(
                        username=username,
                        defaults={
                            'email': email,
                            'first_name': full_name.split()[0] if full_name else '',
                            'last_name': ' '.join(full_name.split()[1:]) if len(full_name.split()) > 1 else '',
                            'role': 'student',
                            'phone': student_data.get('phone_number', ''),
                        }
                    )
                
                # Get or create student
                student, created = Student.objects.get_or_create(
                    id=student_data['id'],
                    defaults={
                        'full_name': student_data.get('full_name', ''),
                        'enrollment_year': student_data.get('year_of_enrollment', 2024),
                        'faculty': faculty,
                        'academic_class': academic_class,
                        'phone': student_data.get('phone_number', ''),
                        'guardian_phone': student_data.get('guardian_phone_number', ''),
                        'user': user,
                        'is_active': True,
                    }
                )
                
                if not created:
                    # Update existing student
                    student.full_name = student_data.get('full_name', student.full_name)
                    student.enrollment_year = student_data.get('year_of_enrollment', student.enrollment_year)
                    student.faculty = faculty
                    student.academic_class = academic_class
                    student.phone = student_data.get('phone_number', student.phone)
                    student.guardian_phone = student_data.get('guardian_phone_number', student.guardian_phone)
                    student.user = user
                    student.is_active = True
                    student.save()
                    results['updated'] += 1
                else:
                    results['created'] += 1
                
                # Download profile image if available
                profile_image_url = student_data.get('profile_image')
                if profile_image_url:
                    try:
                        if profile_image_url.startswith('/'):
                            profile_image_url = API_BASE_URL + profile_image_url

                        image_bytes = http_get_binary(profile_image_url, timeout=10)
                        
                        parsed_url = urlparse(profile_image_url)
                        filename = os.path.basename(parsed_url.path)
                        if not filename:
                            filename = f"profile_{student_data['id']}.jpg"
                        
                        student.profile_image.save(
                            filename,
                            ContentFile(image_bytes),
                            save=True
                        )
                    except Exception as e:
                        logger.warning(f"Image download failed for {student_data.get('full_name')}: {str(e)}")
                        results['errors'].append(f"{student_data.get('full_name')}: Image download failed - {str(e)}")
                
            except Exception as e:
                results['failed'] += 1
                logger.error(f"Error processing student {student_data.get('id')}: {str(e)}")
                results['errors'].append(f"ID {student_data.get('id')}: {str(e)}")
        
        logger.info(f"Import complete: {results['created']} created, {results['updated']} updated, {results['failed']} failed")
        
        return Response({
            'success': True,
            'message': f'Imported {results["created"]} new students, updated {results["updated"]}, failed {results["failed"]}',
            'results': results,
        })
    
    except Exception as e:
        logger.exception(f"Unexpected error in import: {str(e)}")
        return Response({'error': f'Import failed: {str(e)}'}, status=500)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def api_bulk_encode_faces(request):
    """
    Bulk face encoding API endpoint.
    Re-encode faces for all students with profile images.
    Useful for batch processing or re-encoding with improved algorithm.
    Admin only.
    """
    # Check admin permission
    if request.user.role != 'admin':
        return Response({'error': 'Admin access required'}, status=403)

    if not FACE_RECOGNITION_AVAILABLE:
        return Response({'error': 'Face recognition not available'}, status=503)

    from .face_utils import encode_face_from_image
    
    students = Student.objects.filter(is_active=True, profile_image__isnull=False).exclude(profile_image='')
    
    results = {
        'total': students.count(),
        'encoded': 0,
        'failed': 0,
        'no_face': 0,
        'errors': [],
    }

    for student in students:
        try:
            encoding = encode_face_from_image(student.profile_image.path)
            if encoding is not None:
                student.face_encoding = encoding.tobytes()
                student.save()
                results['encoded'] += 1
            else:
                results['no_face'] += 1
                results['errors'].append(f"{student.full_name}: No face detected")
        except Exception as e:
            results['failed'] += 1
            results['errors'].append(f"{student.full_name}: {str(e)}")

    return Response({
        'success': True,
        'message': f'Encoded {results["encoded"]} students, {results["no_face"]} had no face, {results["failed"]} failed',
        'results': results,
    })


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def api_link_students_to_users(request):
    """
    Link existing students without User accounts to new User accounts.
    Admin only. Useful for migrating existing student profiles.
    """
    # Check admin permission
    if request.user.role != 'admin':
        return Response({'error': 'Admin access required'}, status=403)

    from accounts.models import User
    
    # Find all students without User accounts (including inactive ones)
    students_without_users = Student.objects.filter(user__isnull=True)
    
    results = {
        'total': students_without_users.count(),
        'linked': 0,
        'skipped': 0,
        'errors': [],
    }

    for student in students_without_users:
        try:
            # Generate username from student name
            base_username = student.full_name.lower().replace(' ', '_')
            username = base_username
            counter = 1
            while User.objects.filter(username=username).exists():
                username = f"{base_username}_{counter}"
                counter += 1
            
            # Create User account
            user = User.objects.create_user(
                username=username,
                email=f"{username}@students.local",
                first_name=student.full_name.split()[0] if student.full_name else '',
                last_name=' '.join(student.full_name.split()[1:]) if len(student.full_name.split()) > 1 else '',
                role='student',
            )
            
            # Link to student
            student.user = user
            student.save()
            results['linked'] += 1
        except Exception as e:
            results['errors'].append(f"{student.full_name}: {str(e)}")
            results['skipped'] += 1

    return Response({
        'success': True,
        'message': f'Linked {results["linked"]} students to User accounts, skipped {results["skipped"]}',
        'results': results,
    })


# ─── Face Recognition Attendance ─────────────────────────────────

@login_required
def attendance_camera(request):
    """Live camera page with role-based scope."""
    if request.user.role == 'student':
        return render(request, 'attendance/face_attendance.html', {
            'face_recognition_available': FACE_RECOGNITION_AVAILABLE,
        })

    if request.user.role not in ['admin', 'teacher']:
        messages.error(request, 'You do not have permission to access camera attendance.')
        return redirect('home')

    classes = AcademicClass.objects.select_related('faculty')
    if request.user.role == 'teacher':
        classes = classes.filter(teacher=request.user)

    return render(request, 'attendance/camera.html', {
        'classes': classes,
        'face_recognition_available': FACE_RECOGNITION_AVAILABLE,
        'default_class_time': getattr(settings, 'ATTENDANCE_CLASS_TIME', '09:00'),
        'default_threshold_time': getattr(settings, 'ATTENDANCE_THRESHOLD_TIME', '10:00'),
        'default_end_time': getattr(settings, 'ATTENDANCE_CUTOFF_TIME', '12:00'),
    })


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def api_recognize_face(request):
    """
    API endpoint: Accept base64 image, detect & match face, mark attendance.
    """
    serializer = FaceRecognitionSerializer(data=request.data)
    if not serializer.is_valid():
        return Response({'error': serializer.errors}, status=400)

    image_data = serializer.validated_data['image']
    class_id = serializer.validated_data.get('class_id')
    initialize_absent = serializer.validated_data.get('initialize_absent', False)
    class_start_time, threshold_time, end_time = _resolve_attendance_window(serializer.validated_data)

    if not (class_start_time <= threshold_time <= end_time):
        return Response({
            'error': 'Invalid time window. Class time must be <= threshold time <= end time.'
        }, status=400)

    # Decode image
    try:
        image_array = decode_base64_image(image_data)
    except Exception as e:
        return Response({'error': f'Invalid image: {str(e)}'}, status=400)

    if image_array is None:
        return Response({'error': 'Could not decode image'}, status=400)

    # Detect faces
    face_locations = detect_faces(image_array)

    # Determine student scope
    eligible_students_qs = Student.objects.filter(is_active=True)
    if request.user.role == 'teacher':
        eligible_students_qs = eligible_students_qs.filter(academic_class__teacher=request.user)
    if class_id:
        eligible_students_qs = eligible_students_qs.filter(academic_class_id=class_id)

    today = timezone.localdate()
    now = timezone.localtime().time()
    created_absent_count = 0
    if initialize_absent:
        created_absent_count = _initialize_absent_attendance(
            students=eligible_students_qs,
            target_date=today,
            user=request.user,
            class_start_time=class_start_time,
            threshold_time=threshold_time,
            end_time=end_time,
        )

    if not face_locations:
        return Response({
            'faces_detected': 0,
            'auto_absent_created': created_absent_count,
            'message': 'No faces detected',
            'results': [],
        })

    # Get known encodings
    students_qs = eligible_students_qs.filter(face_encoding__isnull=False)

    known_encodings = []
    known_ids = []
    for s in students_qs:
        try:
            enc = np.frombuffer(s.face_encoding, dtype=np.float64)
            if enc.shape == (128,):
                known_encodings.append(enc)
                known_ids.append(s.id)
        except Exception:
            continue

    # Process each detected face
    results = []

    h, w = image_array.shape[:2]
    
    for face_loc in face_locations:
        top, right, bottom, left = face_loc
        
        # Add safety bounds for crop
        top_crop = max(0, top - 20)
        bottom_crop = min(h, bottom + 20)
        left_crop = max(0, left - 20)
        right_crop = min(w, right + 20)
        
        # Get encoding for this face
        face_crop = image_array[top_crop:bottom_crop, left_crop:right_crop]
        face_encoding = encode_face_from_array(face_crop)

        if face_encoding is None:
            results.append({
                'bbox': {'top': top, 'right': right, 'bottom': bottom, 'left': left},
                'matched': False,
                'message': 'Could not encode face',
            })
            continue

        matched_id, confidence = match_face(
            face_encoding, known_encodings, known_ids,
            tolerance=getattr(settings, 'FACE_RECOGNITION_TOLERANCE', 0.5),
        )

        if matched_id:
            student = Student.objects.get(id=matched_id)

            if now > end_time:
                detected_status = 'absent'
            elif now > threshold_time:
                detected_status = 'late'
            else:
                detected_status = 'present'

            # Check for duplicate
            attendance, created = Attendance.objects.get_or_create(
                student=student,
                date=today,
                defaults={
                    'status': detected_status,
                    'check_in_time': now,
                    'marked_by': request.user,
                    'is_face_recognized': True,
                    'confidence': confidence,
                    'notes': (
                        f"Scanned within class window "
                        f"({class_start_time.strftime('%H:%M')} - {end_time.strftime('%H:%M')})."
                    ),
                },
            )

            was_updated = False
            if not created and (
                attendance.status == 'absent'
                or (attendance.status == 'late' and detected_status == 'present')
            ):
                old_status = attendance.status
                attendance.status = detected_status
                attendance.check_in_time = now
                attendance.marked_by = request.user
                attendance.is_face_recognized = True
                attendance.confidence = confidence
                attendance.notes = (
                    f"Updated by face scan at {now.strftime('%H:%M:%S')} "
                    f"(threshold {threshold_time.strftime('%H:%M')}, end {end_time.strftime('%H:%M')})."
                )
                attendance.save(
                    update_fields=[
                        'status',
                        'check_in_time',
                        'marked_by',
                        'is_face_recognized',
                        'confidence',
                        'notes',
                        'updated_at',
                    ]
                )
                was_updated = True

                AttendanceLog.objects.create(
                    attendance=attendance,
                    action='updated',
                    previous_status=old_status,
                    new_status=attendance.status,
                    changed_by=request.user,
                    notes='Status updated by face recognition scan.',
                )

            if created:
                AttendanceLog.objects.create(
                    attendance=attendance,
                    action='created',
                    new_status=attendance.status,
                    changed_by=request.user,
                    notes=f'Face recognized with {confidence}% confidence',
                )
                result_msg = f'{student.full_name} marked as {attendance.get_status_display()}'
            elif was_updated:
                result_msg = f'{student.full_name} updated to {attendance.get_status_display()}'
            else:
                result_msg = f'{student.full_name} already marked for today'

            results.append({
                'bbox': {'top': top, 'right': right, 'bottom': bottom, 'left': left},
                'matched': True,
                'student_id': student.id,
                'student_name': student.full_name,
                'confidence': confidence,
                'status': attendance.get_status_display(),
                'attendance_status': attendance.status,
                'already_marked': (not created and not was_updated),
                'message': result_msg,
            })
        else:
            results.append({
                'bbox': {'top': top, 'right': right, 'bottom': bottom, 'left': left},
                'matched': False,
                'message': 'Face not recognized',
            })

    return Response({
        'faces_detected': len(face_locations),
        'auto_absent_created': created_absent_count,
        'results': results,
    })


# ─── Manual Attendance ────────────────────────────────────────────

@login_required
@admin_or_teacher_required
def manual_attendance(request):
    """Mark attendance manually for a class."""
    classes = AcademicClass.objects.select_related('faculty')
    if request.user.role == 'teacher':
        classes = classes.filter(teacher=request.user)

    students = []
    selected_class = None
    today = timezone.localdate()
    selected_date = request.GET.get('date', today.isoformat())
    class_id = request.GET.get('class_id')

    if request.method == 'POST':
        class_id = request.POST.get('class_id') or class_id
        selected_date = request.POST.get('date', selected_date)

    if class_id:
        selected_class = get_object_or_404(classes, pk=class_id)
        students = Student.objects.filter(
            academic_class=selected_class, is_active=True
        ).order_by('full_name')

        # Get existing attendance
        existing = {}
        for att in Attendance.objects.filter(
            student__in=students, date=selected_date
        ):
            existing[att.student_id] = att

        students_with_attendance = []
        for s in students:
            att = existing.get(s.id)
            students_with_attendance.append({
                'student': s,
                'attendance': att,
                'status': att.status if att else '',
            })
        students = students_with_attendance

    if request.method == 'POST' and selected_class:
        date_str = request.POST.get('date', today.isoformat())
        for key, value in request.POST.items():
            if key.startswith('status_'):
                try:
                    student_id = int(key.replace('status_', ''))
                except ValueError:
                    continue

                if value in ['present', 'absent', 'late', 'informed']:
                    try:
                        student = Student.objects.get(
                            pk=student_id,
                            academic_class=selected_class,
                            is_active=True,
                        )
                    except Student.DoesNotExist:
                        continue

                    att, created = Attendance.objects.update_or_create(
                        student=student,
                        date=date_str,
                        defaults={
                            'status': value,
                            'marked_by': request.user,
                            'check_in_time': timezone.localtime().time() if value in ['present', 'late'] else None,
                        },
                    )
                    action = 'created' if created else 'updated'
                    AttendanceLog.objects.create(
                        attendance=att,
                        action=action,
                        new_status=value,
                        changed_by=request.user,
                        notes=f'Manually marked by {request.user.get_full_name()}',
                    )
        messages.success(request, 'Attendance saved successfully.')
        return redirect(f'{request.path}?class_id={selected_class.pk}&date={date_str}')

    if request.method == 'POST' and not selected_class:
        messages.error(request, 'Please select a valid class.')
        return redirect('attendance:manual')

    return render(request, 'attendance/manual.html', {
        'classes': classes,
        'students': students,
        'selected_class': selected_class,
        'selected_date': selected_date,
        'today': today,
    })


@login_required
@admin_required
def attendance_override(request, pk):
    """Override/correct an attendance record (dispute resolution)."""
    attendance = get_object_or_404(Attendance, pk=pk)

    if request.method == 'POST':
        new_status = request.POST.get('status')
        notes = request.POST.get('notes', '')
        if new_status in ['present', 'absent', 'late', 'informed']:
            old_status = attendance.status
            attendance.status = new_status
            attendance.is_override = True
            attendance.marked_by = request.user
            attendance.notes = notes
            attendance.save()

            AttendanceLog.objects.create(
                attendance=attendance,
                action='overridden',
                previous_status=old_status,
                new_status=new_status,
                changed_by=request.user,
                notes=notes,
            )
            messages.success(request, f'Attendance overridden for {attendance.student.full_name}.')
        return redirect('attendance:daily_report')

    return render(request, 'attendance/override.html', {'attendance': attendance})


# ─── Teacher Dashboard ────────────────────────────────────────────

@login_required
@teacher_required
def teacher_dashboard(request):
    """Teacher dashboard: class students, attendance overview."""
    teacher = request.user
    classes = AcademicClass.objects.filter(teacher=teacher)
    today = timezone.localdate()

    class_data = []
    for cls in classes:
        students = Student.objects.filter(academic_class=cls, is_active=True)
        total = students.count()
        today_att = Attendance.objects.filter(student__in=students, date=today)
        present = today_att.filter(status__in=['present', 'late']).count()
        absent = today_att.filter(status='absent').count()

        class_data.append({
            'class': cls,
            'total_students': total,
            'present': present,
            'absent': absent,
            'rate': round(present / total * 100, 1) if total else 0,
        })

    return render(request, 'dashboard/teacher.html', {
        'class_data': class_data,
        'today': today,
    })


@login_required
@teacher_required
def teacher_class_attendance(request, class_id):
    """Teacher view: detailed attendance for a specific class."""
    ac = get_object_or_404(AcademicClass, pk=class_id, teacher=request.user)
    students = Student.objects.filter(academic_class=ac, is_active=True)
    today = timezone.localdate()
    selected_date = request.GET.get('date', today.isoformat())

    search = request.GET.get('search', '')
    if search:
        students = students.filter(full_name__icontains=search)

    attendance_records = Attendance.objects.filter(
        student__in=students, date=selected_date
    ).select_related('student')
    att_map = {a.student_id: a for a in attendance_records}

    student_list = []
    for s in students:
        att = att_map.get(s.id)
        student_list.append({
            'student': s,
            'attendance': att,
            'status': att.status if att else 'unmarked',
        })

    return render(request, 'attendance/teacher_class.html', {
        'class': ac,
        'student_list': student_list,
        'selected_date': selected_date,
        'search': search,
        'today': today,
    })


@login_required
@teacher_required
def teacher_correct_attendance(request, pk):
    """Teacher: correct a student's attendance."""
    attendance = get_object_or_404(Attendance, pk=pk)
    # Verify teacher owns this class
    if attendance.student.academic_class.teacher != request.user:
        messages.error(request, 'You can only correct attendance for your own class.')
        return redirect('attendance:teacher_dashboard')

    if request.method == 'POST':
        new_status = request.POST.get('status')
        notes = request.POST.get('notes', '')
        if new_status in ['present', 'absent', 'late', 'informed']:
            old_status = attendance.status
            attendance.status = new_status
            attendance.marked_by = request.user
            attendance.notes = notes
            attendance.save()

            AttendanceLog.objects.create(
                attendance=attendance,
                action='corrected',
                previous_status=old_status,
                new_status=new_status,
                changed_by=request.user,
                notes=notes,
            )
            messages.success(request, 'Attendance corrected successfully.')
        return redirect('attendance:teacher_class', class_id=attendance.student.academic_class_id)

    return render(request, 'attendance/override.html', {
        'attendance': attendance,
        'is_teacher': True,
    })


# ─── Student Dashboard ────────────────────────────────────────────

@login_required
@student_required
def student_dashboard(request):
    """Student dashboard: today's status and monthly overview."""
    try:
        student = request.user.student_profile
    except Student.DoesNotExist:
        messages.error(request, 'No student profile linked to your account.')
        return render(request, 'dashboard/student.html', {'student': None})

    today = timezone.localdate()
    today_att = Attendance.objects.filter(student=student, date=today).first()

    # Monthly data
    month_start = today.replace(day=1)
    monthly_att = Attendance.objects.filter(
        student=student,
        date__gte=month_start,
        date__lte=today,
    ).order_by('date')

    total_days = monthly_att.count()
    present_days = monthly_att.filter(status__in=['present', 'late']).count()
    percentage = round(present_days / total_days * 100, 1) if total_days else 0

    return render(request, 'dashboard/student.html', {
        'student': student,
        'today_attendance': today_att,
        'monthly_attendance': monthly_att,
        'total_days': total_days,
        'present_days': present_days,
        'percentage': percentage,
        'today': today,
    })


# ─── Reports ─────────────────────────────────────────────────────

@login_required
@admin_or_teacher_required
def daily_report(request):
    """Daily attendance report with filters."""
    today = timezone.localdate()
    selected_date = request.GET.get('date', today.isoformat())
    faculty_id = request.GET.get('faculty')
    class_id = request.GET.get('class')
    search = request.GET.get('search', '')

    records = Attendance.objects.filter(date=selected_date).select_related(
        'student', 'student__academic_class', 'student__faculty', 'marked_by'
    )

    teacher_classes = None
    if request.user.role == 'teacher':
        teacher_classes = AcademicClass.objects.filter(teacher=request.user).select_related('faculty')
        records = records.filter(student__academic_class__in=teacher_classes)

    if faculty_id:
        records = records.filter(student__faculty_id=faculty_id)
    if class_id:
        records = records.filter(student__academic_class_id=class_id)
    if search:
        records = records.filter(student__full_name__icontains=search)

    summary = {
        'total': records.count(),
        'present': records.filter(status='present').count(),
        'late': records.filter(status='late').count(),
        'absent': records.filter(status='absent').count(),
        'informed': records.filter(status='informed').count(),
    }

    if request.user.role == 'teacher':
        faculties = Faculty.objects.filter(classes__in=teacher_classes).distinct()
        classes = teacher_classes
    else:
        faculties = Faculty.objects.all()
        classes = AcademicClass.objects.all()

    return render(request, 'attendance/daily_report.html', {
        'records': records,
        'summary': summary,
        'faculties': faculties,
        'classes': classes,
        'selected_date': selected_date,
        'selected_faculty': faculty_id,
        'selected_class': class_id,
        'search': search,
    })


@login_required
@admin_or_teacher_required
def monthly_report(request):
    """Monthly aggregated attendance report."""
    today = timezone.localdate()
    month = int(request.GET.get('month', today.month))
    year = int(request.GET.get('year', today.year))
    faculty_id = request.GET.get('faculty')
    class_id = request.GET.get('class')

    students = Student.objects.filter(is_active=True).select_related('faculty', 'academic_class')

    if faculty_id:
        students = students.filter(faculty_id=faculty_id)
    if class_id:
        students = students.filter(academic_class_id=class_id)
    if request.user.role == 'teacher':
        students = students.filter(academic_class__teacher=request.user)

    report_data = []
    for s in students:
        att = Attendance.objects.filter(
            student=s, date__month=month, date__year=year
        )
        total = att.count()
        present = att.filter(status__in=['present', 'late']).count()
        absent = att.filter(status='absent').count()
        percentage = round(present / total * 100, 1) if total else 0

        report_data.append({
            'student': s,
            'total': total,
            'present': present,
            'absent': absent,
            'percentage': percentage,
        })

    if request.user.role == 'teacher':
        teacher_classes = AcademicClass.objects.filter(teacher=request.user).select_related('faculty')
        faculties = Faculty.objects.filter(classes__in=teacher_classes).distinct()
        classes = teacher_classes
    else:
        faculties = Faculty.objects.all()
        classes = AcademicClass.objects.all()

    return render(request, 'attendance/monthly_report.html', {
        'report_data': report_data,
        'month': month,
        'year': year,
        'faculties': faculties,
        'classes': classes,
        'selected_faculty': faculty_id,
        'selected_class': class_id,
    })


@login_required
def attendance_logs(request, pk):
    """View audit logs for an attendance record."""
    attendance = get_object_or_404(Attendance, pk=pk)

    if request.user.role == 'teacher' and attendance.student.academic_class.teacher_id != request.user.id:
        messages.error(request, 'You can only view logs for your own classes.')
        return redirect('attendance:teacher_dashboard')

    if request.user.role == 'student':
        if attendance.student.user_id != request.user.id:
            messages.error(request, 'You can only view your own attendance logs.')
            return redirect('attendance:student_dashboard')

    if request.user.role not in ['admin', 'teacher', 'student']:
        messages.error(request, 'You do not have permission to view attendance logs.')
        return redirect('home')

    logs = attendance.logs.all()
    return render(request, 'attendance/logs.html', {
        'attendance': attendance,
        'logs': logs,
    })


# ─── API Endpoints ───────────────────────────────────────────────

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def api_attendance_list(request):
    """API: List attendance records with filters."""
    date = request.query_params.get('date', timezone.localdate().isoformat())
    class_id = request.query_params.get('class_id')
    faculty_id = request.query_params.get('faculty_id')

    qs = Attendance.objects.filter(date=date).select_related(
        'student',
        'student__academic_class',
        'student__faculty',
        'marked_by',
    )

    if request.user.role == 'teacher':
        qs = qs.filter(student__academic_class__teacher=request.user)
    elif request.user.role == 'student':
        try:
            qs = qs.filter(student=request.user.student_profile)
        except Student.DoesNotExist:
            qs = Attendance.objects.none()
    elif request.user.role != 'admin':
        return Response({'error': 'Access denied'}, status=403)

    if class_id:
        qs = qs.filter(student__academic_class_id=class_id)
    if faculty_id:
        qs = qs.filter(student__faculty_id=faculty_id)

    serializer = AttendanceSerializer(qs, many=True)
    return Response(serializer.data)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def api_manual_mark_attendance(request):
    """API: Manually mark attendance for a student."""
    student_id = request.data.get('student_id')
    status = request.data.get('status', 'present')
    date = request.data.get('date', timezone.localdate().isoformat())
    notes = request.data.get('notes', '')

    if not student_id:
        return Response({'error': 'student_id required'}, status=400)

    if request.user.role not in ['admin', 'teacher']:
        return Response({'error': 'Only admin or teacher can mark attendance manually.'}, status=403)

    try:
        student = Student.objects.get(id=student_id, is_active=True)
    except Student.DoesNotExist:
        return Response({'error': 'Student not found'}, status=404)

    if request.user.role == 'teacher' and student.academic_class.teacher_id != request.user.id:
        return Response({'error': 'You can only mark attendance for your own class students.'}, status=403)

    att, created = Attendance.objects.update_or_create(
        student=student,
        date=date,
        defaults={
            'status': status,
            'marked_by': request.user,
            'check_in_time': timezone.localtime().time() if status in ['present', 'late'] else None,
            'notes': notes,
        },
    )

    AttendanceLog.objects.create(
        attendance=att,
        action='created' if created else 'updated',
        new_status=status,
        changed_by=request.user,
        notes=notes,
    )

    serializer = AttendanceSerializer(att)
    return Response(serializer.data, status=201 if created else 200)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def api_dashboard_data(request):
    """API: Dashboard summary data."""
    today = timezone.localdate()
    if request.user.role == 'admin':
        student_scope = Student.objects.filter(is_active=True)
        today_att = Attendance.objects.filter(date=today)
    elif request.user.role == 'teacher':
        student_scope = Student.objects.filter(is_active=True, academic_class__teacher=request.user)
        today_att = Attendance.objects.filter(date=today, student__in=student_scope)
    elif request.user.role == 'student':
        try:
            student_scope = Student.objects.filter(pk=request.user.student_profile.pk)
            today_att = Attendance.objects.filter(date=today, student=request.user.student_profile)
        except Student.DoesNotExist:
            student_scope = Student.objects.none()
            today_att = Attendance.objects.none()
    else:
        return Response({'error': 'Access denied'}, status=403)

    total_students = student_scope.count()

    data = {
        'date': today.isoformat(),
        'total_students': total_students,
        'present': today_att.filter(status='present').count(),
        'late': today_att.filter(status='late').count(),
        'absent': today_att.filter(status='absent').count(),
        'informed': today_att.filter(status='informed').count(),
        'attendance_rate': 0,
    }
    marked = data['present'] + data['late']
    data['attendance_rate'] = round(marked / total_students * 100, 1) if total_students else 0
    return Response(data)
