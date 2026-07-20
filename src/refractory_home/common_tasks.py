from django.utils import timezone
from datetime import timedelta
from functools import wraps
import requests
from django.db import transaction
from web_interaction import foundry_interaction


def limit_refresh(limit_refresh_seconds=0, default=None):
    def limit_refresh_decorator(func):
        @wraps(func)
        def wrapped_func(*args, **kwargs):
            if limit_refresh_seconds > 0:
                now = timezone.now()
                if hasattr(wrapped_func, "refresh_timestamp"):
                    old = getattr(wrapped_func, "refresh_timestamp")
                    if now - old <= timedelta(seconds=limit_refresh_seconds):
                        return default
                setattr(wrapped_func, "refresh_timestamp", now)
                return func(*args, **kwargs)

        return wrapped_func

    return limit_refresh_decorator


def load_foundry_releases_immediate():
    from refractory_home.models import FoundryVersion

    with requests.Session() as rsession:
        versions = foundry_interaction.get_releases(rsession)
        with transaction.atomic():
            for release in versions:
                version_string = release.get("version")
                build = release.get("build")
                update_type, update_category = (
                    FoundryVersion.UpdateType.FULL,
                    FoundryVersion.UpdateCategory.STABLE,
                )
                for tag in release.get("tags"):
                    if tag in FoundryVersion.UpdateType:
                        update_type = tag
                    elif tag in FoundryVersion.UpdateCategory:
                        update_category = tag
                FoundryVersion.objects.update_or_create(
                    version_string=version_string,
                    defaults=dict(
                        update_type=update_type,
                        update_category=update_category,
                        build=build,
                    ),
                )
            for version in FoundryVersion.objects.all():
                if version.download_status == FoundryVersion.DownloadStatus.DOWNLOADED:
                    if not foundry_interaction.release_artifact_exists(version):
                        version.download_status = (
                            FoundryVersion.DownloadStatus.NOT_DOWNLOADED
                        )
                        version.save()


@limit_refresh(limit_refresh_seconds=60)
def load_foundry_releases():
    load_foundry_releases_immediate()
