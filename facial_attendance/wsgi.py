"""
WSGI config for facial_attendance project.
"""
import os
from django.core.wsgi import get_wsgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'facial_attendance.settings')
application = get_wsgi_application()
