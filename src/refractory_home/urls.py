from django.urls import path
from .views import (
    RefractoryLoginView, PanelView,
    activate_instance, activate_world,
    login_to_instance, login_to_instance_as_user,
    login_to_instance_as_admin, login_to_instance_as_managed_gm,
)

urlpatterns = [
    path('login/', RefractoryLoginView.as_view()),
    path('admin/login/', RefractoryLoginView.as_view(), name='override_admin_login'),
    path('panel/', PanelView.as_view(), name='panel'),
    path('<slug:instance_slug>/vtt_login/', login_to_instance, name='vtt_choose_user'),
    path('<slug:instance_slug>/vtt_login/<int:user_ix>/', login_to_instance_as_user, name='vtt_login'),
    path('<slug:instance_slug>/activate/', activate_instance, name='activate_instance'),
    path('<slug:instance_slug>/admin_login/', login_to_instance_as_admin, name='instance_admin_login'),
    path('<slug:instance_slug>/gm_login/', login_to_instance_as_managed_gm, name='managed_admin_login'),
    path('<slug:instance_slug>/activate/<slug:world_id>/', activate_world, name="activate_world")
]
