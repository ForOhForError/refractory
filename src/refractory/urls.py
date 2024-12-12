from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path, re_path
from django.views.static import serve as static_serve

from refractory_home.admin import adminsite

urlpatterns = [
    path("", include("refractory_home.urls")),
    path("admin/", adminsite.urls, name="admin"),
    re_path(
        r"^static/(?P<path>.*)$", static_serve, {"document_root": settings.STATIC_ROOT}
    ),
]
