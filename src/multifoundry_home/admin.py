from django.contrib import admin

# Register your models here.
from multifoundry_home.models.foundry_models import (
    FoundryInstance, FoundryVersion, FoundryLicense
)

@admin.register(FoundryInstance, FoundryVersion, FoundryLicense)
class MultifoundryAdmin(admin.ModelAdmin):
    pass