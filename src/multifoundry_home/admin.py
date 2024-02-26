from django.contrib import admin

from multifoundry_home.models.foundry_models import (
    FoundryInstance, FoundryVersion, FoundryLicense
)

from django.utils.translation import gettext_lazy as _

from django import forms
from django.template.response import TemplateResponse
from django.urls import path

from django.views.generic.edit import FormView

from web_interaction import foundry_interaction
import requests

class FoundryLoginForm(forms.Form):
    username = forms.CharField()
    password = forms.CharField(widget=forms.PasswordInput)

    def send_email(self):
        # send email using the self.cleaned_data dictionary
        pass

class FoundryLoginFormView(FormView):
    template_name = "foundry_login.html"
    form_class = FoundryLoginForm
    success_url = "/manage/admin"
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(MultifoundryAdminSite().each_context(self.request))
        return context

    def form_valid(self, form):
        # This method is called when valid form data has been POSTed.
        # It should return an HttpResponse.
        username = form.cleaned_data["username"]
        password = form.cleaned_data["password"]
        print(username, password)
        with requests.Session() as rsession:
            tok = foundry_interaction.get_token(rsession)
            canon_username = foundry_interaction.login(rsession, tok, username, password)
            if canon_username:
                cookies = rsession.cookies.get_dict()
                session_id = cookies.get('sessionid')
                resp = super().form_valid(form)
                resp.set_cookie("foundry_session", session_id)
                resp.set_cookie("foundry_username", canon_username)
                return resp
        return super().form_valid(form)

class MultifoundryAdminSite(admin.AdminSite):
    site_header = _("Multifoundry Administration")
    site_title = _("Multifoundry Administration")
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

@admin.register(FoundryInstance, FoundryVersion, FoundryLicense)
class MultifoundryAdmin(admin.ModelAdmin):
    pass
