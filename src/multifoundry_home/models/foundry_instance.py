from django.db import models

class FoundryInstance(models.Model):
    instance_name = models.CharField(max_length=30, unique=True)
    
class FoundryVersion(models.Model):
    pass
    
class FoundryLicense(models.Model):
    license_key = models.CharField(max_length=29, min_length=29)
    instance = models.OneToOneField(
        "FoundryInstance",
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name="foundry_licence",
    )
    