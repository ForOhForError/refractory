import requests
from django.contrib import admin
from django.contrib.auth import get_user_model
from django.contrib.auth.admin import UserAdmin
from django.template.response import TemplateResponse
from django.urls import path, reverse, reverse_lazy
from django.utils.translation import gettext_lazy as _
from twisted.internet import reactor

from refractory_home.models.foundry_models import (
    FoundryLicense,
    ManagedFoundryUser,
    FoundryInvite,
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


class FoundryInviteAdmin(admin.ModelAdmin):
    list_display = ["invite_code", "uses"]


adminsite.register(FoundryInvite, FoundryInviteAdmin)
adminsite.register(FoundryLicense, FoundryLicenseAdmin)
adminsite.register(ManagedFoundryUser, ManagedUserAdmin)
adminsite.register(get_user_model(), UserAdmin)
