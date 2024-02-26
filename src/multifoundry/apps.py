from django.contrib.admin.apps import AdminConfig


class MultifoundryAdminConfig(AdminConfig):
    default_site = "multifoundry_home.admin.MultifoundryAdminSite"