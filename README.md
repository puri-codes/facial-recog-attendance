# Facial Attendance System

A production-level Django-based attendance management system with real-time facial recognition, role-based access control, and comprehensive reporting.

## Features

- **Face Recognition**: Real-time face detection and matching using OpenCV + `face_recognition`
- **Role-Based Access**: Admin, Teacher, and Student roles with appropriate permissions
- **Student Enrollment**: Via image upload or live webcam capture
- **Attendance Management**: Automated (face scan), manual marking, and admin override
- **Reporting**: Daily/monthly attendance reports with filtering and percentages
- **Audit Logging**: Complete change history for all attendance records
- **REST APIs**: Endpoints for face recognition, attendance marking, and dashboard data
- **Modern UI**: Dark theme with glassmorphism, responsive design, micro-animations

## Tech Stack

- **Backend**: Django 4.2+, Django REST Framework
- **Face Recognition**: `face_recognition` + OpenCV
- **Database**: SQLite (configurable to PostgreSQL)
- **Frontend**: Django Templates, Vanilla CSS/JS

## Quick Start

### 1. Create Virtual Environment

```bash
python -m venv venv
# Windows:
venv\Scripts\activate
# Linux/Mac:
source venv/bin/activate
```

### 2. Install Dependencies

```bash
pip install -r requirements.txt
```

> **Note**: `face-recognition` requires `dlib`, which needs CMake and a C++ compiler.
> On Windows, install Visual Studio Build Tools first, or use:
> ```bash
> pip install cmake
> pip install dlib
> pip install face-recognition
> ```

### 3. Run Migrations

```bash
python manage.py makemigrations accounts academics attendance
python manage.py migrate
```

### 4. Create Admin User

```bash
python manage.py createsuperuser
```

When prompted, set the username and password. Then update the user's role:

```bash
python manage.py shell -c "
from accounts.models import User
u = User.objects.get(username='admin')
u.role = 'admin'
u.save()
print('Admin role set!')
"
```

### 5. Run the Server

```bash
python manage.py runserver
```

Visit **http://127.0.0.1:8000/** and log in.

## Project Structure

```
├── manage.py
├── requirements.txt
├── facial_attendance/      # Django project settings
├── accounts/               # Auth & RBAC (User model, login/logout)
├── academics/              # Faculty, Class, Student models & CRUD
├── attendance/             # Attendance models, face recognition, reports
├── api/                    # REST API router
├── templates/              # HTML templates
│   ├── base.html           # Responsive layout with sidebar
│   ├── accounts/           # Login page
│   ├── dashboard/          # Admin, Teacher, Student dashboards
│   ├── academics/          # CRUD forms and lists
│   └── attendance/         # Camera, manual marking, reports
├── static/
│   ├── css/style.css       # Complete design system
│   └── js/                 # Camera, table sorting utilities
└── media/                  # Student profile images (auto-created)
```

## User Roles

| Role    | Access                                                      |
|---------|-------------------------------------------------------------|
| Admin   | Full access — CRUD all entities, override attendance        |
| Teacher | View assigned class students, mark/correct attendance       |
| Student | View own attendance (today + monthly)                       |

## API Endpoints

| Method | Endpoint              | Description                         |
|--------|-----------------------|-------------------------------------|
| POST   | `/api/recognize/`     | Send base64 frame, match & mark     |
| GET    | `/api/attendance/`    | List attendance (filterable)         |
| POST   | `/api/attendance/mark/` | Mark attendance manually          |
| GET    | `/api/dashboard/`     | Dashboard summary statistics        |

## Attendance Logic

- Detected **before** threshold time (`10:00 AM`) → **Present**
- Detected **after** threshold → **Late**
- Not detected → **Absent**
- Admin manual mark → **Informed**
- Duplicate marks per day are prevented

## Configuration

Key settings in `facial_attendance/settings.py`:

```python
ATTENDANCE_THRESHOLD_TIME = '10:00'    # Present/Late cutoff
ATTENDANCE_CUTOFF_TIME = '12:00'       # No more face scans after this
FACE_RECOGNITION_TOLERANCE = 0.5       # Lower = stricter matching
```
