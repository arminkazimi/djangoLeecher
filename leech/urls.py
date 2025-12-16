from django.urls import path

from . import views

app_name = 'leech'

urlpatterns = [
    path('', views.home, name='home'),
    path('job/<uuid:job_id>/', views.detail, name='detail'),
    path('stream/<uuid:job_id>/', views.stream, name='stream'),
]
