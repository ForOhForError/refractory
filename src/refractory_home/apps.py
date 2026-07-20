import logging

from django.apps import AppConfig
from refractory_home.common_tasks import load_foundry_releases_immediate


class refractoryHomeConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "refractory_home"

    def ready(self):
        try:
            load_foundry_releases_immediate()
        except Exception:
            logging.exception("Error when loading foundry release list")
