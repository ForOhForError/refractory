from twisted.internet import reactor
from twisted.web.resource import Resource
from twisted.web.wsgi import WSGIResource
from twisted.web.server import Site

import web_interaction.foundry_resource
from urllib.parse import quote_plus

import sys
import os
import os.path

from twisted.web.util import redirectTo

from django.core.wsgi import get_wsgi_application as get_django_wsgi_application
from web_interaction.foundry_resource import INSTANCE_PATH

MANAGEMENT_PATH = "manage"
MIN_INTERNAL_PORT = 30000
_MODULE = sys.modules[__name__]

class HomeResource(Resource):
    isLeaf = True
    def render(self, request):
        return redirectTo(b"/manage/panel", request)

class RefractoryServer:
    def __init__(self):
        self.foundry_resources = {}
        self.refractory_root_res = Resource()
        self.refractory_instances_res = Resource()
        self.site = Site(self.refractory_root_res)
        self.django_res= WSGIResource(reactor, reactor.getThreadPool(), get_django_wsgi_application())
        self.refractory_root_res.putChild(MANAGEMENT_PATH.encode(), self.django_res)
        self.refractory_root_res.putChild(INSTANCE_PATH.encode(), self.refractory_instances_res)
        self.refractory_instances_res.putChild(b"", HomeResource())
        self.refractory_root_res.putChild(b"", HomeResource())

    def get_unassigned_port(self):
        if not len(self.foundry_resources):
            return MIN_INTERNAL_PORT
        assigned_ports = [instance.port for instance in self.foundry_resources.values()]
        for port in range(MIN_INTERNAL_PORT, max(assigned_ports)+2):
            if port not in assigned_ports: 
                return port
        print("port assignment failed")

    def run(self, port=8080):
        reactor.listenTCP(port, self.site)
        reactor.run()

    def stop(self):
        reactor.stop()

    def add_foundry_instance(self, foundry_instance):
        port = self.get_unassigned_port()
        instance_slug_bytes = foundry_instance.instance_slug.encode()
        precheck = foundry_instance.pre_activate(port)
        if precheck:
            foundry_res = web_interaction.foundry_resource.FoundryResource(
                foundry_instance, port=port, log=False
            )
            self.refractory_instances_res.putChild(instance_slug_bytes, foundry_res)
            self.foundry_resources[foundry_instance.instance_name] = foundry_res
            foundry_instance.post_activate()
            print(f"launched {foundry_instance.instance_name} - version {foundry_instance.foundry_version.version_string} - on internal port {port}")

    def remove_foundry_instance(self, foundry_instance):
        instance_slug_bytes = foundry_instance.instance_slug.encode()
        if self.refractory_instances_res.getStaticEntity(instance_slug_bytes):
            self.refractory_instances_res.delEntity(instance_slug_bytes)
        if foundry_instance.instance_name in self.foundry_resources:
            res = self.foundry_resources.pop(foundry_instance.instance_name)
            res.end_process()
            print(f"stopped {foundry_instance.instance_name} - version {foundry_instance.foundry_version.version_string}")

    def get_foundry_resource(self, foundry_instance):
        return self.foundry_resources.get(foundry_instance.instance_name, None)

    def get_active_instance_names(self):
        return self.foundry_resources.keys()

    @classmethod
    def get_server(cls):
        if not hasattr(_MODULE, "_server"):
            server = cls()
            _MODULE._server = server
            return server
        else:
            return _MODULE._server