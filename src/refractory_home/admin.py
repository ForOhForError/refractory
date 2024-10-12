from django.contrib import admin

from refractory_home.models.foundry_models import (
    FoundryInstance, FoundryVersion, FoundryLicense,
    ManagedFoundryUser
)

from django.utils.translation import gettext_lazy as _
from django.contrib.auth.mixins import UserPassesTestMixin

from django import forms
from django.template.response import TemplateResponse
from django.urls import path

from django.views.generic.edit import FormView

from web_interaction import foundry_interaction
import requests

from twisted.internet import reactor
from web_interaction import foundry_interaction
from web_server import RefractoryServer

FOUNDRY_SESSION_COOKIE = "foundry_session"
FOUNDRY_USERNAME_COOKIE = "foundry_username"

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
                        "admin_url": "/manage/admin/foundry_login",
                        "view_only": True,
                    }
                ],
            }
        ]
        return app_list

    def get_urls(self):
        urls = super().get_urls()
        new_urls = [path("foundry_login/", FoundryLoginFormView.as_view(), name="Foundry Login")]
        return new_urls + urls

adminsite = RefractoryAdminSite()

class FoundryLoginForm(forms.Form):
    username = forms.CharField()
    password = forms.CharField(widget=forms.PasswordInput)

class FoundryLoginFormView(FormView, UserPassesTestMixin):
    template_name = "foundry_login.html"
    form_class = FoundryLoginForm
    success_url = "/manage/admin"
    redirect_authenticated_user = True
    
    def test_func(self):
        return self.request.user.is_superuser
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(adminsite.each_context(self.request))
        return context

    def form_valid(self, form):
        # This method is called when valid form data has been POSTed.
        # It should return an HttpResponse.
        username = form.cleaned_data["username"]
        password = form.cleaned_data["password"]
        with requests.Session() as rsession:
            tok = foundry_interaction.get_token(rsession)
            canon_username = foundry_interaction.login(rsession, tok, username, password)
            if canon_username:
                cookies = rsession.cookies.get_dict()
                session_id = cookies.get('sessionid')
                resp = super().form_valid(form)
                cookie_kwargs = {
                    "secure": True,
                    "httponly": True,
                    "samesite": "Strict"
                }
                resp.set_signed_cookie(FOUNDRY_SESSION_COOKIE, session_id, **cookie_kwargs)
                resp.set_signed_cookie(FOUNDRY_USERNAME_COOKIE, canon_username, **cookie_kwargs)
                return resp
        return super().form_valid(form)

def download_single_release(version_object,foundry_session):
    with requests.Session() as rsession:
        rsession.cookies.update({"sessionid":foundry_session})
        print(f"downloading release {version_object.version_string}")
        version_object.download_status = FoundryVersion.DownloadStatus.DOWNLOADING
        version_object.save()
        success = False
        try:
            success = foundry_interaction.download_and_write_release(rsession, version_string=version_object.version_string)
        except Exception as ex:
            print(f"Exception while downloading: {ex}")
        version_object.download_status = FoundryVersion.DownloadStatus.DOWNLOADED if success else FoundryVersion.DownloadStatus.NOT_DOWNLOADED
        version_object.save()

@admin.action(description=_("Download Release"))
def download_release(modeladmin, request, queryset):
    foundry_session = request.get_signed_cookie(FOUNDRY_SESSION_COOKIE, default=None)
    foundry_username = request.get_signed_cookie(FOUNDRY_USERNAME_COOKIE, default=None)
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
    foundry_session = request.get_signed_cookie(FOUNDRY_SESSION_COOKIE, default=None)
    foundry_username = request.get_signed_cookie(FOUNDRY_USERNAME_COOKIE, default=None)
    if foundry_session and foundry_username:
        for release in queryset:
            reactor.callInThread(load_licenses_threaded, foundry_session, foundry_username)
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
        form.base_fields['foundry_version'].queryset = FoundryVersion.objects.filter(
            download_status=FoundryVersion.DownloadStatus.DOWNLOADED
        )
        return form

adminsite.register(FoundryInstance,FoundryInstanceAdmin)
adminsite.register(FoundryLicense,FoundryLicenseAdmin)
adminsite.register(FoundryVersion,FoundryVersionAdmin)
adminsite.register(ManagedFoundryUser,ManagedUserAdmin)


