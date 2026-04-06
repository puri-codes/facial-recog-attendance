#!/usr/bin/env python
"""
Script to fetch students from remote API and update local database.
"""
import os
import sys
import django
import requests
import json
from io import BytesIO
from urllib.parse import urlparse
from PIL import Image

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'facial_attendance.settings')
django.setup()

from django.conf import settings
from django.core.files.base import ContentFile
from django.db import models
from academics.models import Student, Faculty, AcademicClass
from accounts.models import User

# API Configuration
API_BASE_URL = getattr(settings, 'REMOTE_API_URL', 'http://127.0.0.1:8000')
API_TOKEN_URL = f"{API_BASE_URL}/api/auth/token/"
API_STUDENTS_URL = f"{API_BASE_URL}/api/students/"

# Credentials
USERNAME = getattr(settings, 'REMOTE_API_USERNAME', 'admin')
PASSWORD = getattr(settings, 'REMOTE_API_PASSWORD', 'admin')


def get_auth_token():
    """Fetch authentication token from API."""
    print("🔐 Fetching authentication token...")
    response = requests.post(
        API_TOKEN_URL,
        json={"username": USERNAME, "password": PASSWORD}
    )
    response.raise_for_status()
    token = response.json().get("token")
    print(f"✓ Token obtained: {token[:20]}...")
    return token


def fetch_students(token):
    """Fetch all students from API."""
    print("\n📥 Fetching students from API...")
    headers = {"Authorization": f"Token {token}"}
    response = requests.get(API_STUDENTS_URL, headers=headers)
    response.raise_for_status()
    data = response.json()
    students = data.get("results", [])
    print(f"✓ Fetched {len(students)} students")
    return students


def download_profile_image(image_url):
    """Download image from URL and return as Django file."""
    if not image_url:
        return None
    
    try:
        # Handle relative URLs
        if image_url.startswith('/'):
            image_url = API_BASE_URL + image_url
        
        print(f"  📸 Downloading: {image_url[:60]}...")
        response = requests.get(image_url, timeout=10)
        response.raise_for_status()
        
        # Get filename from URL
        parsed_url = urlparse(image_url)
        filename = os.path.basename(parsed_url.path)
        if not filename:
            filename = "profile.jpg"
        
        return ContentFile(response.content, name=filename)
    except Exception as e:
        print(f"  ⚠️  Error downloading image: {e}")
        return None


def get_or_create_faculty(faculty_name):
    """Get or create faculty."""
    faculty, created = Faculty.objects.get_or_create(
        name=faculty_name.upper(),
        defaults={'description': f'{faculty_name} Faculty'}
    )
    return faculty


def get_or_create_academic_class(faculty, academic_year):
    """Get or create academic class."""
    academic_class, created = AcademicClass.objects.get_or_create(
        name=academic_year,
        faculty=faculty,
    )
    return academic_class


def get_or_create_user(student_data):
    """Get or create user account for student."""
    email = student_data.get('email', '')
    student_id = student_data.get('student_id_number', '')
    
    if not email:
        email = f"{student_id}@school.local"
    
    # Try to find by email first
    user = User.objects.filter(email=email).first()
    
    if user:
        return user
    
    # Create new user
    username = student_id or f"student_{student_data['id']}"
    user, created = User.objects.get_or_create(
        username=username,
        defaults={
            'email': email,
            'first_name': student_data.get('full_name', '').split()[0],
            'last_name': ' '.join(student_data.get('full_name', '').split()[1:]),
            'role': User.Role.STUDENT,
            'phone': student_data.get('phone_number', ''),
        }
    )
    if created:
        print(f"  👤 Created user account: {username}")
    return user


def update_student(student_data):
    """Update or create student record."""
    student_id_number = student_data.get('student_id_number', '')
    
    try:
        # Try to find existing student by student_id_number or API id
        student = Student.objects.filter(
            models.Q(id=student_data['id']) |
            models.Q(user__username=student_id_number)
        ).first()
        
        is_new = False
        if not student:
            student = Student()
            is_new = True
        
        # Get or create faculty
        faculty_name = student_data.get('faculty', 'BSIT')
        faculty = get_or_create_faculty(faculty_name)
        
        # Get or create academic class
        academic_year = student_data.get('academic_year', 'year_1')
        academic_class = get_or_create_academic_class(faculty, academic_year)
        
        # Get or create user
        user = get_or_create_user(student_data)
        
        # Update student fields
        student.user = user
        student.full_name = student_data.get('full_name', '')
        student.enrollment_year = student_data.get('year_of_enrollment', 2024)
        student.faculty = faculty
        student.academic_class = academic_class
        student.phone = student_data.get('phone_number', '')
        student.guardian_phone = student_data.get('guardian_phone_number', '')
        student.is_active = True
        
        # Download and update profile image
        profile_image_url = student_data.get('profile_image')
        if profile_image_url:
            profile_file = download_profile_image(profile_image_url)
            if profile_file:
                student.profile_image = profile_file
        
        student.save()
        
        status = "✨ Created" if is_new else "📝 Updated"
        print(f"{status}: {student.full_name} ({student_id_number})")
        return True
        
    except Exception as e:
        print(f"❌ Error processing student {student_data.get('full_name')}: {e}")
        return False


def main():
    """Main function."""
    print("=" * 60)
    print("🎓 Student Data Import Script")
    print("=" * 60)
    
    try:
        # Get token
        token = get_auth_token()
        
        # Fetch students
        students = fetch_students(token)
        
        if not students:
            print("⚠️  No students to import")
            return
        
        # Import students
        print(f"\n🔄 Importing {len(students)} students...\n")
        
        success_count = 0
        for student_data in students:
            if update_student(student_data):
                success_count += 1
        
        # Summary
        print("\n" + "=" * 60)
        print(f"✅ Import Complete: {success_count}/{len(students)} students processed")
        print("=" * 60)
        
    except Exception as e:
        print(f"\n❌ Fatal error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
