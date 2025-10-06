import os

from django.core.management.utils import get_random_secret_key

# Don't use a blank string or none as a secret! default to invalidating sessions every launch over that >:|
DJANGO_SECRET = (
    os.environ.get("DJANGO_SECRET")
    if os.environ.get("DJANGO_SECRET")
    else get_random_secret_key()
)
DJANGO_DEBUG = os.environ.get("DJANGO_DEBUG_DANGEROUS", "False") == "True"
DJANGO_ALLOWED_HOSTS = os.environ.get("DJANGO_ALLOWED_HOSTS", "*").split(";")
DJANGO_CSRF_TRUSTED_ORIGINS = os.environ.get("DJANGO_CSRF_TRUSTED_ORIGINS", "*").split(";")