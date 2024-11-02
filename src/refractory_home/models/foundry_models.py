import json
import re
import requests
import os
import time
import secrets
import shutil
from enum import Enum

from django.db import models
from django.core.validators import RegexValidator, validate_unicode_slug
from django.utils.translation import gettext_lazy as _
from django.conf import settings
from django.templatetags.static import static as static_url

from django.db.models.signals import pre_save, post_save, pre_delete, post_delete
from django.dispatch import receiver

from websockets.sync.client import connect

from bs4 import BeautifulSoup
import bs4.element

from web_interaction import foundry_interaction
from web_interaction.foundry_resource import INSTANCE_PATH
from web_server import RefractoryServer

import socketio

from refractory_settings import SERVER_PORT

DATA_PATH_BASE = "instance_data"
RELEASE_PATH_BASE = "foundry_releases"

class FoundryState(Enum):
    INACTIVE = 0
    LICENSE = 1
    LICENSE_EULA = 2
    SETUP = 3
    JOIN = 4
    ACTIVE_UNKNOWN = 99

URL_TO_STATE = {
    "license": FoundryState.LICENSE_EULA,
    "setup": FoundryState.SETUP,
    "auth": FoundryState.SETUP,
    "join": FoundryState.JOIN
}

LICENSE_STATE_SEARCH_STRING = 'form id="license-key"' # scuffed but works

from web_interaction.template_rewrite import REWRITE_RULES

def generate_default_password():
    return secrets.token_hex(32)

class FoundryInstance(models.Model):
    instance_name = models.CharField(max_length=30, unique=True)
    instance_slug = models.CharField(max_length=30, null=True, validators=[validate_unicode_slug], unique=True)
    display_name = models.CharField(max_length=256, null=True)
    admin_pass = models.CharField(max_length=256, default=generate_default_password)
    eula_accepted = models.BooleanField(default=False, blank=False, null=False)
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
    def synch_to_refractory_hosting(cls):
        for instance in cls.objects.exclude(foundry_license=None):
            print(instance)
    
    @property
    def data_path(self):
        return os.path.join(DATA_PATH_BASE,self.instance_slug)
    
    def make_instance_folder(self):
        os.makedirs(self.data_path, exist_ok=True)
        
    def delete_instance_folder(self):
        shutil.rmtree(self.data_path)
    
    @property
    def user_facing_base_url(self):
        url = f"/{INSTANCE_PATH}/{self.instance_slug}"
        return url
    
    @property
    def socketio_path(self):
        return f"{INSTANCE_PATH}/{self.instance_slug}/socket.io/"
    
    @property
    def server_facing_base_url(self):
        foundry_resource = RefractoryServer.get_server().get_foundry_resource(self)
        if foundry_resource:
            url = f"{foundry_resource.get_base_url()}/{INSTANCE_PATH}/{self.instance_slug}"
            return url
        return None
    
    def amend_invite_url(self, invite_url):
        foundry_resource = RefractoryServer.get_server().get_foundry_resource(self)
        if foundry_resource:
            replace_path = f":{foundry_resource.port}/{INSTANCE_PATH}/{self.instance_slug}/"
            return invite_url.replace(replace_path, f":{SERVER_PORT}/")
        return invite_url
    
    @property
    def instance_state(self):
        foundry_resource = RefractoryServer.get_server().get_foundry_resource(self)
        if foundry_resource:
            response = requests.get(self.server_facing_base_url)
            if LICENSE_STATE_SEARCH_STRING in response.content.decode():
                return FoundryState.LICENSE
            else:
                url = response.url
                if len(url):
                    page = url.split("/")[-1]
                    return URL_TO_STATE.get(page, FoundryState.ACTIVE_UNKNOWN)
                else:
                    return FoundryState.ACTIVE_UNKNOWN
        else:
            return FoundryState.INACTIVE
    
    def register_managed_gm(self, world_id, user_id, user_name):
        managed_gm = ManagedFoundryUser(
            instance=self,
            world_id=world_id,
            user_id=user_id,
            user_name=user_name,
            managed_gm=True,
            user_password="",
            owner=None
        ).save()
        
    def get_managed_gm(self):
        world_id = self.active_world_id
        if world_id:
            managed_gms = ManagedFoundryUser.objects.filter(managed_gm=True, instance=self, world_id=world_id)
            if len(managed_users):
                return managed_gms.first()
        return None
    
    def pre_activate(self, port):
        self.inject_config(port=port, clear_admin_pass=True)
        self.clear_unmatched_license()
        return self.assign_license_if_able()

    def post_activate(self):
        self.wait_for_ready()
        self.activate_license()
        self.accept_eula_if_able()
    
    @property
    def is_active(self):
        return self.instance_name in RefractoryServer.get_server().get_active_instance_names()
    
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
    
    def deactivate_world(self):
        if self.instance_state == FoundryState.JOIN:
            join_url = f"{self.server_facing_base_url}/join"
            response = requests.post(
                join_url,
                data={
                    "adminPassword":self.admin_pass,
                    "adminKey":self.admin_pass,
                    "action":"shutdown"
                }
            )
            if response.ok:
                return True
            else:
                return False
        else:
            return True

    def activate_world(self, world_id, force=False):
        # preamble to deactivate an activated world
        if self.instance_state == FoundryState.JOIN:
            if self.active_world_id != world_id:
                if force or not self.has_active_players():
                    self.deactivate_world()
                    tries = 0
                    while tries < 10 and self.instance_state != FoundryState.SETUP:
                        time.sleep(0.2)
                        tries += 1
                else:
                    return False
        # actually launch the new world
        if self.instance_state == FoundryState.SETUP:
            with requests.Session() as session:
                self.admin_session_login(session)
                activate_url = f"{self.server_facing_base_url}/setup"
                payload = {
                    "world":world_id,
                    "action":"launchWorld"
                }
                resp = session.post(
                    activate_url,
                    data=payload
                )
                if resp.ok:
                    return True
        return False

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
    
    def accept_eula_if_able(self):
        if self.instance_state == FoundryState.LICENSE_EULA:
            if self.eula_accepted:
                with requests.Session() as session:
                    eula_url = f"{self.server_facing_base_url}/license"
                    session.get(
                        eula_url
                    )
                    form_body = {
                        "accept":"on",
                    }
                    eula_res = session.post(
                        eula_url,
                        data = form_body
                    )
                    if eula_res.ok:
                        print("Accepting EULA automatically, as it has been manually agreed to.")
                        return True
            else:
                print("Cannot accept EULA automatically :(")
        return False
    
    def assign_license_if_able(self):
        try:
            if self.foundry_license:
                return True
        except FoundryLicense.DoesNotExist:
            available_license, to_shutdown = FoundryLicense.find_free_if_available()
            if available_license:
                if to_shutdown:
                    RefractoryServer.get_server().remove_foundry_instance(to_shutdown)
                available_license.instance = self
                available_license.save()
                return True
        return False

    @property
    def worlds(self):
        active_world_id = self.active_world_id
        worlds_path = os.path.join(self.data_path, "Data", "worlds")
        all_worlds = []
        if os.path.exists(worlds_path) and os.path.isdir(worlds_path):
            for file_handle in os.listdir(worlds_path):
                world_path = os.path.join(worlds_path, file_handle)
                is_active_world = str(file_handle) == active_world_id
                if os.path.isdir(world_path):
                    world_json_path = os.path.join(world_path, "world.json")
                    if os.path.exists(world_json_path) and os.path.isfile(world_json_path):
                        with open(world_json_path) as world_json:
                            world_dict = json.load(world_json)
                            world_dict["active"] = is_active_world
                            if not world_dict.get("id"):
                                world_dict["id"] = str(file_handle)
                            all_worlds.append(world_dict)
        return all_worlds
    
    def activate(self):
        return RefractoryServer.get_server().add_foundry_instance(self)
    
    def deactivate(self):
        RefractoryServer.get_server().remove_foundry_instance(self)
    
    @classmethod
    def active_instances(cls):
        return cls.objects.filter(instance_name__in=RefractoryServer.get_server().get_active_instance_names())

    def vtt_login(self, foundry_user):
        with requests.Session() as session:
            return self.vtt_session_login(foundry_user, session)

    def vtt_session_login(self, foundry_user, session):
        login_url = f"{self.server_facing_base_url}/join"
        session.get(
            login_url
        )
        form_body = {
            "userid":foundry_user.user_id,
            "password":foundry_user.user_password,
            "adminPassword":"",
            "action":"join"
        }
        login_res = session.post(
            login_url,
            data = form_body
        )
        if login_res.ok:
            return login_res.json().get("redirect"), dict(session.cookies)
        else:
            return None, None
    
    def admin_login(self):
        with requests.Session() as session:
            return self.admin_session_login(session)

    def admin_session_login(self, session):
        login_url = f"{self.server_facing_base_url}/auth" if self.version_tuple[0] > 8 else f"{self.server_facing_base_url}/setup"
        session.get(login_url)
        admin_pass = self.admin_pass
        form_body = {
            "adminPassword": admin_pass,
            "adminKey": admin_pass,
            "action": "adminAuth"
        }
        login_res = session.post(
            login_url,
            data = form_body
        )
        return self.user_facing_base_url, dict(session.cookies)

    def wait_for_ready(self):
        with requests.Session() as session:
            while True:
                try:
                    base_url = f"{self.server_facing_base_url}/"
                    res = session.get(
                        base_url
                    )
                    break
                except Exception as ex:
                    time.sleep(0.1)

    def activate_license(self):
        with requests.Session() as session:
            license_url = f"{self.server_facing_base_url}/license"
            session.get(
                license_url
            )
            try:
                if self.foundry_license:
                    form_body = {
                        "licenseKey":self.foundry_license.license_key,
                        "action":"enterKey"
                    }
                    license_res = session.post(
                        license_url,
                        data = form_body
                    )
                    if license_res.ok:
                        try:
                            return True
                        except Exception:
                            return False
                    else:
                        return False
            except Exception:
                return False
        return False

    @property
    def active_player_range(self):
        return range(self.active_player_count)

    @property
    def active_player_count(self):
        join_info = self.get_join_info()
        return len(join_info.get("activeUsers", []))

    def has_active_players(self):
        return self.active_player_count > 0

    @property
    def active_world_id(self):
        return self.get_join_info().get("world",{}).get("id")

    @property
    def active_background_url(self):
        join_info = self.get_join_info()
        join_bg = join_info.get("world",{}).get("background")
        if not join_bg:
            join_bg_legacy = join_info.get("world",{}).get("data",{}).get("background")
            join_bg = join_bg_legacy
        if join_bg:
            return f"{self.user_facing_base_url}/{join_bg}"
        else:
            return static_url("refractory/img/ActiveWorld.png")
    
    @property
    def default_background_url(self):
        return static_url("refractory/img/InactiveWorld.png")
    
    @property
    def version_tuple(self):
        return tuple([int(part) for part in self.foundry_version.version_string.split(".")])

    def get_join_info(self):
        if self.instance_state == FoundryState.JOIN:
            try:
                if self.version_tuple[0] > 8:
                    join_info = self.get_ws_response("getJoinData")
                else:
                    join_info = self.get_ws_response("getSetupData")
                world_id = join_info.get("world", {}).get("id", None)
                if world_id and not self.managedfoundryuser_set.filter(world_id=world_id, managed_gm=True).exists():
                    gamemaster_candidate_user = join_info.get("users", [{}])[0]
                    if gamemaster_candidate_user.get("role") == 4:
                        user_id, user_name = gamemaster_candidate_user.get("_id"), gamemaster_candidate_user.get("name")
                        self.register_managed_gm(world_id, user_id, user_name)
                return join_info
            except Exception as ex:
                pass
        return {}
    
    def open_socketio_connection(self, session=None):
        base_url = self.server_facing_base_url
        login_url = f"{base_url}/join"
        if base_url:
            if not session:
                session = requests.Session()
            session.get(login_url)
            session_id = session.cookies.get('session', None)
            if session_id:
                connect_url = f"{base_url.replace('http','ws')}?session={session_id}"
                sio = socketio.SimpleClient()
                sio.connect(
                    connect_url, 
                    socketio_path=self.socketio_path,
                    transports=["websocket"]
                )
                return sio
        return None

    def get_ws_response(self, initial_event_type, initial_event_data=None, session=None):
        sio = self.open_socketio_connection(session=session)
        if sio:
            with sio:
                if initial_event_data == None:
                    event = sio.call(initial_event_type)
                else:
                    event = sio.call(initial_event_type, initial_event_data)
                return event
        return {}

    def get_setup_info(self):
        try:
            join_info = self.get_ws_response("getSetupData")
            world_id = join_info.get("world", {}).get("id", None)
        except Exception as ex:
            pass
        return {}



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
        active_instance_names = RefractoryServer.get_server().get_active_instance_names()
        free_licenses = cls.objects.exclude(instance__instance_name__in=active_instance_names)
        if free_licenses.exists():
            return free_licenses.first(), None
        else:
            available_instances = []
            for instance_name in active_instance_names:
                try:
                    instance = FoundryInstance.objects.get(instance_name=instance_name)
                    if not instance.has_active_players():
                        return instance.foundry_license, instance
                except FoundryInstance.DoesNotExist:
                    pass
        return None, None

    @classmethod
    def load_from_foundry_account(cls, foundry_session, foundry_username):
        with requests.Session() as rsession:
            rsession.cookies.update({"sessionid":foundry_session})
            licenses = foundry_interaction.get_licenses(rsession, foundry_username)
            for license_obj in licenses:
                license_key = license_obj.get("license_key")
                license_name = license_obj.get("license_name", "imported license")
                if not FoundryLicense.objects.filter(license_key=license_key).exists():
                    FoundryLicense(license_key=license_key, license_name=license_name).save()

class ManagedFoundryUser(models.Model):
    user_name = models.CharField(max_length=255, default="")
    user_id = models.CharField(max_length=255, default="")
    user_password = models.CharField(max_length=64, default=generate_default_password)
    world_id = models.CharField(max_length=255, default="")
    instance = models.ForeignKey(FoundryInstance, on_delete=models.CASCADE)
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL)
    managed_gm = models.BooleanField(default=False)

# @receiver(post_save, sender=ManagedFoundryUser)
# def register_user_post_save(sender, instance, created, **kwargs):
#     if created:
#         print(f"New user created: {instance}")
#     else:
#         print(f"User updated: {instance}")
