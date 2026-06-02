from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.shortcuts import redirect

urlpatterns = [
    path('admin/',         admin.site.urls),
    path('accounts/',      include('accounts.urls', namespace='accounts')),
    path('teams/',         include('teams.urls', namespace='teams')),
    path('projects/',      include('projects.urls', namespace='projects')),
    path('milestones/',    include('milestones.urls')),
    path('submissions/',   include('submissions.urls', namespace='submissions')),
    path('reviews/',       include('reviews.urls')),
    path('notifications/', include('notifications.urls')),
    path('meetings/',      include('meetings.urls')),
    path('dashboard/',     include('dashboard.urls', namespace='dashboard')),
    path('',               lambda request: redirect('dashboard:index')),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
