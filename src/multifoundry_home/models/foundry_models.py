from django.db import models
from django.core.validators import RegexValidator, validate_unicode_slug
from django.utils.translation import gettext_lazy as _

import requests
import os
import secrets

import json

DATA_PATH_BASE = "instance_data"
RELEASE_PATH_BASE = "foundry_releases"

from web_interaction.foundry_resource import INSTANCE_PATH
from web_server import get_foundry_resource, get_active_instance_names, add_foundry_instance, remove_foundry_instance
from web_interaction.vtt_interaction import get_join_info, get_setup_info, activate_license, wait_for_ready

from django.conf import settings

def generate_default_password():
    return secrets.token_hex(32)

class FoundryInstance(models.Model):
    instance_name = models.CharField(max_length=30, unique=True)
    instance_slug = models.CharField(max_length=30, null=True, validators=[validate_unicode_slug], unique=True)
    display_name = models.CharField(max_length=256, null=True)
    admin_pass = models.CharField(max_length=256, default=generate_default_password)
    foundry_version = models.ForeignKey(
        "FoundryVersion",
        blank=True,
        null=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )
    
    def __str__(self):
        return self.display_name if self.display_name else self.instance_name
    
    @classmethod
    def synch_to_multifoundry_hosting(cls):
        for instance in cls.objects.exclude(foundry_license=None):
            print(instance)
    
    @property
    def data_path(self):
        return os.path.join(DATA_PATH_BASE,self.instance_slug)
    
    @property
    def user_facing_base_url(self):
        url = f"/{INSTANCE_PATH}/{self.instance_slug}"
        return url
    
    @property
    def server_facing_base_url(self):
        foundry_resource = get_foundry_resource(self)
        if foundry_resource:
            url = f"{foundry_resource.get_base_url()}/{INSTANCE_PATH}/{self.instance_slug}"
            return url
        return None
    
    @property
    def is_active(self):
        return self.instance_name in get_active_instance_names()
    
    def inject_config(self, port=30000, clear_admin_pass=False):
        config_path = os.path.join(self.data_path, "Config")
        os.makedirs(config_path, exist_ok=True)
        config_file_path = os.path.join(config_path, "options.json")
        if os.path.exists(config_file_path):
            with open(config_file_path) as config_file:
                config_obj = json.load(config_file)
        else:
            config_obj = {}
        config_obj.update({
            "port": port,
            "routePrefix": INSTANCE_PATH+"/"+self.instance_slug
        })
        if clear_admin_pass:
            admin_file_path = os.path.join(config_path, "admin.txt")
            if os.path.exists(admin_file_path):
                os.remove(admin_file_path)
            
        with open(config_file_path, "w") as config_file:
            config_file.write(json.dumps(config_obj))
    
    def clear_unmatched_license(self):
        config_path = os.path.join(self.data_path, "Config")
        license_file_path = os.path.join(config_path, "license.json")
        if os.path.exists(license_file_path):
            with open(license_file_path) as license_file:
                license_obj = json.load(license_file)
        else:
            license_obj = {}
        license_string = None
        try:
            license_string = self.foundry_license.license_key.replace("-","")
        except FoundryLicense.DoesNotExist:
            pass
        if license_obj.get("license", None) != license_string:
            if os.path.exists(license_file_path):
                os.remove(license_file_path)
                
    def assign_license_if_able(self):
        try:
            if self.foundry_license:
                return True
        except FoundryLicense.DoesNotExist:
            available_license, to_shutdown = FoundryLicense.find_free_if_available()
            if available_license:
                available_license.instance = self
                if to_shutdown:
                    remove_foundry_instance(to_shutdown)
                available_license.save()

    @property
    def worlds(self):
        worlds_path = os.path.join(self.data_path, "Data", "worlds")
        all_worlds = []
        for file_handle in os.listdir(worlds_path):
            world_path = os.path.join(worlds_path, file_handle)
            if os.path.isdir(world_path):
                world_json_path = os.path.join(world_path, "world.json")
                if os.path.exists(world_json_path) and os.path.isfile(world_json_path):
                    with open(world_json_path) as world_json:
                        all_worlds.append(json.load(world_json))
        return all_worlds
    
    def get_join_info(self):
        return get_join_info(self)
    
    def get_setup_info(self):
        return get_setup_info(self)
    
    def activate_license(self):
        return activate_license(self)
    
    def wait_for_ready(self):
        wait_for_ready(self)
        
    def activate(self):
        add_foundry_instance(self)
        
    @classmethod
    def active_instances(cls):
        return cls.objects.filter(instance_name__in=get_active_instance_names())

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
    def executable_path(self):
        return os.path.join(RELEASE_PATH_BASE, self.version_string, "resources", "app", "main.js")
    
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
    license_name = models.CharField(max_length=255, default="")
    instance = models.OneToOneField(
        "FoundryInstance",
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name="foundry_license",
    )
    
    @classmethod
    def find_free_if_available(cls):
        free_licenses = cls.objects.exclude(instance__instance_name__in=get_active_instance_names())
        if free_licenses.exists():
            return free_licenses.first(), None
        else:
            available_instances = []
            for instance_name in get_active_instance_names():
                try:
                    instance = FoundryInstance.objects.get(instance_name=instance_name)
                    join_info = get_join_info(instance)
                    if len(join_info.get("activeUsers", [])) == 0:
                        return instance.foundry_license, instance
                except FoundryInstance.DoesNotExist:
                    pass
        return None, None

class ManagedFoundryUser(models.Model):
    user_name = models.CharField(max_length=255, default="")
    user_id = models.CharField(max_length=255, default="")
    user_password = models.CharField(max_length=64, default=generate_default_password)
    world_id = models.CharField(max_length=255, default="")
    instance = models.ForeignKey(FoundryInstance, on_delete=models.CASCADE)
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL)
    managed_gm = models.BooleanField(default=False)
