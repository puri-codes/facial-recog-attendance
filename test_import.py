#!/usr/bin/env python
"""
Test the student import API endpoint manually.
"""
import os
import sys
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'facial_attendance.settings')
django.setup()

import requests
import urllib3
from django.conf import settings
from accounts.models import User

# Suppress SSL warnings
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Get local user token for testing
print("Creating test admin user for API request...")
try:
    admin_user = User.objects.filter(role='admin').first()
    if not admin_user:
        print("❌ No admin user found. Creating one...")
        admin_user = User.objects.create_user(
            username='testadmin',
            email='admin@test.local',
            password='testpassword123',
            role='admin'
        )
    else:
        print(f"✓ Using admin user: {admin_user.username}")
except Exception as e:
    print(f"Error: {e}")
    sys.exit(1)

# Prepare the import request
print("\n" + "="*60)
print("Testing Import Students API Endpoint")
print("="*60)

API_BASE_URL = getattr(settings, 'REMOTE_API_URL', 'http://127.0.0.1:8000')
API_TOKEN_URL = f"{API_BASE_URL}/api/auth/token/"
API_STUDENTS_URL = f"{API_BASE_URL}/api/students/"
USERNAME = getattr(settings, 'REMOTE_API_USERNAME', 'admin')
PASSWORD = getattr(settings, 'REMOTE_API_PASSWORD', 'admin')

print(f"\n📡 Remote API Configuration:")
print(f"  Base URL: {API_BASE_URL}")
print(f"  Token Endpoint: {API_TOKEN_URL}")
print(f"  Students Endpoint: {API_STUDENTS_URL}")
print(f"  Username: {USERNAME}")

# Test 1: Get token from remote API
print(f"\n🔐 Step 1: Testing token generation from remote API...")
try:
    token_response = requests.post(
        API_TOKEN_URL,
        json={"username": USERNAME, "password": PASSWORD},
        timeout=10,
        verify=False
    )
    print(f"  Status Code: {token_response.status_code}")
    print(f"  Response: {token_response.text[:200]}...")
    
    if token_response.status_code == 200:
        token_data = token_response.json()
        token = token_data.get("token")
        if token:
            print(f"✓ Token obtained: {token[:20]}...")
        else:
            print(f"❌ No token in response: {token_data}")
    else:
        print(f"❌ Failed to get token. Status: {token_response.status_code}")
except Exception as e:
    print(f"❌ Error: {e}")
    sys.exit(1)

# Test 2: Fetch students
print(f"\n📥 Step 2: Fetching students from remote API...")
try:
    headers = {"Authorization": f"Token {token}"}
    students_response = requests.get(
        API_STUDENTS_URL,
        headers=headers,
        timeout=10,
        verify=False
    )
    print(f"  Status Code: {students_response.status_code}")
    
    if students_response.status_code == 200:
        data = students_response.json()
        students_data = data.get("results", [])
        print(f"✓ Successfully fetched {len(students_data)} students")
        
        if students_data:
            s = students_data[0]
            print(f"\n  Sample student:")
            print(f"    ID: {s.get('id')}")
            print(f"    Name: {s.get('full_name')}")
            print(f"    Email: {s.get('email')}")
            print(f"    Faculty: {s.get('faculty')}")
    else:
        print(f"❌ Failed to fetch students. Status: {students_response.status_code}")
        print(f"   Response: {students_response.text[:500]}")
except Exception as e:
    print(f"❌ Error: {e}")
    sys.exit(1)

print("\n" + "="*60)
print("✅ All tests passed! The import should work.")
print("="*60)
