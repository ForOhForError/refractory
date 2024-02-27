from django.db import models
from django.core.validators import RegexValidator
from django.utils.translation import gettext_lazy as _

from web_interaction import foundry_interaction
import requests

class FoundryInstance(models.Model):
    instance_name = models.CharField(max_length=30, unique=True)
    foundry_version = models.ForeignKey(
        "FoundryVersion",
        blank=True,
        null=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )
    
    def __str__(self):
        return self.instance_name
    
    @classmethod
    def synch_to_multifoundry_hosting(cls):
        for instance in cls.objects.exclude(foundry_license=None):
            print(instance)

class FoundryVersion(models.Model):
    class UpdateType(models.TextChoices):
        FULL = "Full", _("Full")
        UPDATE = "Update", _("Update")

    class UpdateCategory(models.TextChoices):
        PROTOTYPE = "Prototype", _("Prototype")
        DEVELOPMENT = "Development", _("Development")
        TESTING = "Testing", _("Testing")
        STABLE = "Stable", _("Stable")
        
    class DownloadStatus(models.TextChoices):
        NOT_DOWNLOADED = "Not Downloaded", _("Not Downloaded")
        DOWNLOADING = "Downloading", _("Downloading")
        DOWNLOADED = "Downloaded", _("Downloaded")

    version_string = models.CharField(max_length=30, unique=True)
    update_type = models.CharField(max_length=10, choices=UpdateType.choices, default=UpdateType.FULL)
    update_category = models.CharField(max_length=15, choices=UpdateCategory.choices, default=UpdateCategory.STABLE)
    download_status = models.CharField(max_length=15, choices=DownloadStatus.choices, default=DownloadStatus.NOT_DOWNLOADED)
    
    @property
    def downloaded(self):
        return self.download_status == FoundryVersion.DownloadStatus.DOWNLOADED
    
    def __str__(self):
        return self.version_string
    
    @classmethod
    def load_versions(cls):
        with requests.Session() as rsession:
            qset = cls.objects.all()
            versions = foundry_interaction.get_releases(rsession)
            for release in versions:
                version_string = release.get("version")
                update_type, update_category = cls.UpdateType.FULL, cls.UpdateCategory.STABLE
                for tag in release.get("tags"):
                    if tag in cls.UpdateType:
                        update_type = tag
                    elif tag in cls.UpdateCategory:
                        update_category = tag
                if not qset.filter(version_string=version_string).exists():
                    cls(version_string=version_string, update_type=update_type, update_category=update_category).save()

FOUNDRY_LICENSE_REGEX = "^[A-Z1-9]{4}-[A-Z1-9]{4}-[A-Z1-9]{4}-[A-Z1-9]{4}-[A-Z1-9]{4}-[A-Z1-9]{4}$"
foundry_license_validator = RegexValidator(FOUNDRY_LICENSE_REGEX, _("Foundry Licenses are of format XXXX-XXXX-XXXX-XXXX-XXXX-XXXX"))

class FoundryLicense(models.Model):
    license_key = models.CharField(max_length=29, validators=[foundry_license_validator])
    instance = models.OneToOneField(
        "FoundryInstance",
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name="foundry_license",
    )
    