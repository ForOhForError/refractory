from django.db import models
from django.core.validators import RegexValidator

class FoundryInstance(models.Model):
    instance_name = models.CharField(max_length=30, unique=True)
    
class FoundryVersion(models.Model):
    version_string = models.CharField(max_length=30, unique=True)

FOUNDRY_LICENSE_REGEX = "^[A-Z1-9]{4}-[A-Z1-9]{4}-[A-Z1-9]{4}-[A-Z1-9]{4}-[A-Z1-9]{4}-[A-Z1-9]{4}$"
foundry_license_validator = RegexValidator(FOUNDRY_LICENSE_REGEX, "Foundry Licenses are of format XXXX-XXXX-XXXX-XXXX-XXXX-XXXX")

class FoundryLicense(models.Model):
    license_key = models.CharField(max_length=29, validators=[foundry_license_validator])
    instance = models.OneToOneField(
        "FoundryInstance",
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name="foundry_licence",
    )
    