from django.urls import path
from .views import RefractoryLoginView, PanelView

urlpatterns = [
    path('login/', RefractoryLoginView.as_view()),
    path('admin/login/', RefractoryLoginView.as_view(), name='override_admin_login'),
    path('panel/', PanelView.as_view(), name='panel')
]