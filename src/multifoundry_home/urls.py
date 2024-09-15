from django.urls import path
from .views import RefractoryLoginView

urlpatterns = [
    path('login/', RefractoryLoginView.as_view()),
    path('admin/login/', RefractoryLoginView.as_view(), name='override_admin_login')
]