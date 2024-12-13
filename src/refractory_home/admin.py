import requests
from django.contrib import admin
from django.contrib.auth import get_user_model
from django.contrib.auth.admin import UserAdmin
from django.template.response import TemplateResponse
from django.urls import path, reverse, reverse_lazy
from django.utils.translation import gettext_lazy as _
from twisted.internet import reactor

from refractory_home.models.foundry_models import (
    FoundryInstance,
    FoundryLicense,
    FoundryVersion,
    ManagedFoundryUser,
)
from web_interaction import foundry_interaction
from web_server import RefractoryServer


class RefractoryAdminSite(admin.AdminSite):
    site_header = _("Refractory Administration")
    site_title = _("Refractory Administration")

    def get_app_list(self, request, *args, **kwargs):
        app_list = super().get_app_list(request, *args, **kwargs)
        app_list += [
            {
                "name": _("Foundry Site"),
                "app_label": "foundry_site",
                "models": [
                    {
                        "name": _("Foundry Login"),
                        "object_name": "foundry_site",
                        "admin_url": f"{reverse_lazy('foundry_site_login')}",
                        "view_only": True,
                    }
                ],
            }
        ]
        return app_list


adminsite = RefractoryAdminSite()


def download_single_release(version_object, foundry_session):
    with requests.Session() as rsession:
        rsession.cookies.update({"sessionid": foundry_session})
        print(f"downloading release {version_object.version_string}")
        version_object.download_status = FoundryVersion.DownloadStatus.DOWNLOADING
        version_object.save()
        success = False
        try:
            success = foundry_interaction.download_and_write_release(
                rsession, version_string=version_object.version_string
            )
        except Exception as ex:
            print(f"Exception while downloading: {ex}")
        version_object.download_status = (
            FoundryVersion.DownloadStatus.DOWNLOADED
            if success
            else FoundryVersion.DownloadStatus.NOT_DOWNLOADED
        )
        version_object.save()


@admin.action(description=_("Download Release"))
def download_release(modeladmin, request, queryset):
    foundry_session = request.get_signed_cookie(
        foundry_interaction.FOUNDRY_SESSION_COOKIE, default=None
    )
    foundry_username = request.get_signed_cookie(
        foundry_interaction.FOUNDRY_USERNAME_COOKIE, default=None
    )
    if foundry_session and foundry_username:
        for release in queryset:
            reactor.callInThread(download_single_release, release, foundry_session)
    else:
        print("not logged in")


@admin.action(description=_("Fetch Version List"))
def load_releases(modeladmin, request, queryset):
    reactor.callInThread(FoundryVersion.load_versions)


class FoundryVersionAdmin(admin.ModelAdmin):
    actions = [download_release, load_releases]
    list_display = ["version_string", "update_type", "update_category", "downloaded"]


def load_licenses_threaded(foundry_session, foundry_username):
    FoundryLicense.load_from_foundry_account(foundry_session, foundry_username)


@admin.action(description=_("Fetch Licenses"))
def load_licences(modeladmin, request, queryset):
    foundry_session = request.get_signed_cookie(
        foundry_interaction.FOUNDRY_SESSION_COOKIE, default=None
    )
    foundry_username = request.get_signed_cookie(
        foundry_interaction.FOUNDRY_USERNAME_COOKIE, default=None
    )
    if foundry_session and foundry_username:
        for release in queryset:
            reactor.callInThread(
                load_licenses_threaded, foundry_session, foundry_username
            )
    else:
        print("not logged in")


class ManagedUserAdmin(admin.ModelAdmin):
    list_display = ["user_name", "world_id"]


class FoundryLicenseAdmin(admin.ModelAdmin):
    list_display = ["license_name"]

    actions = [load_licences]


@admin.action(description=_("Launch Instances"))
def launch_instances(modeladmin, request, queryset):
    for instance in queryset:
        RefractoryServer.get_server().add_foundry_instance(instance)


@admin.action(description=_("Log Instance Info"))
def log_info(modeladmin, request, queryset):
    for instance in queryset:
        print(instance.instance_name)
        print(instance.get_join_info())
        print(instance.get_setup_info())


class FoundryInstanceAdmin(admin.ModelAdmin):
    actions = [launch_instances, log_info]

    def get_form(self, request, obj=None, **kwargs):
        form = super().get_form(request, obj, **kwargs)
        form.base_fields["foundry_version"].queryset = FoundryVersion.objects.filter(
            download_status=FoundryVersion.DownloadStatus.DOWNLOADED
        )
        return form


adminsite.register(FoundryInstance, FoundryInstanceAdmin)
adminsite.register(FoundryLicense, FoundryLicenseAdmin)
adminsite.register(FoundryVersion, FoundryVersionAdmin)
adminsite.register(ManagedFoundryUser, ManagedUserAdmin)
adminsite.register(get_user_model(), UserAdmin)
