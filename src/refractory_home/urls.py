from django.conf import settings
from django.contrib.auth.views import LogoutView
from django.urls import path

from .views import (
    FoundryLoginFormView,
    InstanceCreateView,
    InstanceDeleteView,
    InstanceListView,
    InstanceUpdateView,
    PanelView,
    RefractoryLoginView,
    VersionListView,
    SignupFormView,
    GroupUpdateView,
    GroupListView,
    GroupCreateView,
    RegisterUserView,
    ConfirmSetupView,
    ActivateInstance,
    ActivateWorld,
    DownloadInstanceBackup,
    DownloadVersion,
    InstanceLoginView,
    InstanceSetupLogin,
    InstanceManagedGMLogin,
    InstanceUserLogin,
    LicenseListView,
    LicenseCreateView,
    LicenseDeleteView,
    LicenseUpdateView,
    ImportLicenses,
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
        "foundry_login/",
        FoundryLoginFormView.as_view(),
        name="foundry_site_login",
    ),
    path("panel/", PanelView.as_view(), name="panel"),
    path(
        "instances/<slug:instance_slug>/vtt_login/",
        InstanceLoginView.as_view(),
        name="vtt_choose_user",
    ),
    path(
        "instances/<slug:instance_slug>/vtt_login/<int:user_ix>/",
        InstanceUserLogin.as_view(),
        name="vtt_login",
    ),
    path(
        "signup/",
        SignupFormView.as_view(),
        name="signup",
    ),
    path(
        "groups/",
        GroupListView.as_view(),
        name="group_list",
    ),
    path(
        "groups/<int:group_id>/",
        GroupUpdateView.as_view(),
        name="group_update",
    ),
    path("create-group/", GroupCreateView.as_view(), name="group_create"),
    path(
        "instances/<slug:instance_slug>/activate/",
        ActivateInstance.as_view(),
        name="activate_instance",
    ),
    path(
        "instances/<slug:instance_slug>/register/",
        RegisterUserView.as_view(),
        name="register_instance_user",
    ),
    path(
        "instances/<slug:instance_slug>/confirm_setup/",
        ConfirmSetupView.as_view(),
        name="confirm_instance_setup",
    ),
    path(
        "instances/<slug:instance_slug>/admin_login/",
        InstanceSetupLogin.as_view(),
        name="instance_admin_login",
    ),
    # Managed GM Login, no longer needed
    # path(
    #     "instances/<slug:instance_slug>/gm_login/",
    #     InstanceManagedGMLogin.as_view(),
    #     name="managed_admin_login",
    # ),
    path(
        "instances/<slug:instance_slug>/activate/<slug:world_id>/",
        ActivateWorld.as_view(),
        name="activate_world",
    ),
    path("instances/", InstanceListView.as_view(), name="instance_list"),
    path(
        "instances/<slug:instance_slug>/",
        InstanceUpdateView.as_view(),
        name="instance_update",
    ),
    path(
        "instances/<slug:instance_slug>/delete/",
        InstanceDeleteView.as_view(),
        name="instance_delete",
    ),
    path("create-instance/", InstanceCreateView.as_view(), name="instance_create"),
    path(
        "instances/<slug:instance_slug>/download-backup/",
        DownloadInstanceBackup.as_view(),
        name="instance_download_backup",
    ),
    path(
        "versions/",
        VersionListView.as_view(),
        name="version_list",
    ),
    path(
        "versions/download/<str:version_string>",
        DownloadVersion.as_view(),
        name="version_download",
    ),
    path(
        "licenses/",
        LicenseListView.as_view(),
        name="license_list",
    ),
    path(
        "create-license/",
        LicenseCreateView.as_view(),
        name="license_create",
    ),
    path(
        "licenses/<int:id>/",
        LicenseUpdateView.as_view(),
        name="license_update",
    ),
    path(
        "licenses/<int:id>/delete/",
        LicenseDeleteView.as_view(),
        name="license_delete",
    ),
    path(
        "licenses/import/",
        ImportLicenses.as_view(),
        name="license_import",
    ),
]
