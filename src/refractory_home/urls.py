from django.conf import settings
from django.contrib.auth.views import LogoutView
from django.urls import path

from .views import (
    FoundryLoginFormView,
    PanelView,
    RefractoryLoginView,
    activate_instance,
    activate_world,
    login_to_instance,
    login_to_instance_as_admin,
    login_to_instance_as_managed_gm,
    login_to_instance_as_user,
)

urlpatterns = [
    path("login/", RefractoryLoginView.as_view(), name="base_login"),
    path(
        "logout/",
        LogoutView.as_view(),
        {"next_page": settings.LOGOUT_REDIRECT_URL},
        name="logout",
    ),
    path("admin/login/", RefractoryLoginView.as_view(), name="override_admin_login"),
    path(
        "admin/foundry_login/",
        FoundryLoginFormView.as_view(),
        name="foundry_site_login",
    ),
    path("panel/", PanelView.as_view(), name="panel"),
    path(
        "instance/<slug:instance_slug>/vtt_login/",
        login_to_instance,
        name="vtt_choose_user",
    ),
    path(
        "instance/<slug:instance_slug>/vtt_login/<int:user_ix>/",
        login_to_instance_as_user,
        name="vtt_login",
    ),
    path(
        "instance/<slug:instance_slug>/activate/",
        activate_instance,
        name="activate_instance",
    ),
    path(
        "instance/<slug:instance_slug>/admin_login/",
        login_to_instance_as_admin,
        name="instance_admin_login",
    ),
    path(
        "instance/<slug:instance_slug>/gm_login/",
        login_to_instance_as_managed_gm,
        name="managed_admin_login",
    ),
    path(
        "instance/<slug:instance_slug>/activate/<slug:world_id>/",
        activate_world,
        name="activate_world",
    ),
]
