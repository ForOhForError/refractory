from django.contrib import admin
from django.contrib.auth import get_user_model
from django.contrib.auth.admin import UserAdmin
from django.urls import reverse_lazy
from django.utils.translation import gettext_lazy as _

from refractory_home.models.foundry_models import (
    ManagedFoundryUser,
)


class RefractoryAdminSite(admin.AdminSite):
    site_header = _("Refractory Administration")
    site_title = _("Refractory Administration")


adminsite = RefractoryAdminSite()


class ManagedUserAdmin(admin.ModelAdmin):
    list_display = ["user_name", "world_id"]


adminsite.register(ManagedFoundryUser, ManagedUserAdmin)
adminsite.register(get_user_model(), UserAdmin)
adminsite.site_url = reverse_lazy("panel")
