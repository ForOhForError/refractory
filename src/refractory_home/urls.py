from django.urls import path
from .views import RefractoryLoginView, PanelView, login_to_instance, login_to_instance_as_user, activate_instance, login_to_instance_as_admin

urlpatterns = [
    path('login/', RefractoryLoginView.as_view()),
    path('admin/login/', RefractoryLoginView.as_view(), name='override_admin_login'),
    path('panel/', PanelView.as_view(), name='panel'),
    path('vtt_login/<slug:instance_slug>/', login_to_instance, name='vtt_choose_user'),
    path('vtt_login/<slug:instance_slug>/<int:user_ix>', login_to_instance_as_user, name='vtt_login'),
    path('activate/<slug:instance_slug>/', activate_instance, name='activate_instance'),
    path('admin_login/<slug:instance_slug>/', login_to_instance_as_admin, name='instance_admin_login'),
]