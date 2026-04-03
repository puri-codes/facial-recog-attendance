"""URL configuration for facial_attendance project."""
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from accounts.views import home_redirect, login_view, logout_view

urlpatterns = [
    path('django-admin/', admin.site.urls),
    path('', home_redirect, name='home'),
    path('login/', login_view, name='login'),
    path('logout/', logout_view, name='logout'),
    path('accounts/', include('accounts.urls')),
    path('academics/', include('academics.urls')),
    path('attendance/', include('attendance.urls')),
    path('api/', include('api.urls')),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
