"""
WSGI config for refractory project.

It exposes the WSGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/5.0/howto/deployment/wsgi/
"""

import os
import logging

from django.core.wsgi import get_wsgi_application
from refractory_home.common_tasks import load_foundry_releases_immediate

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "refractory.settings")

application = get_wsgi_application()

try:
    logging.info("Syncing Foundry Releases...")
    load_foundry_releases_immediate()
except Exception:
    logging.exception("Error when loading foundry release list")
