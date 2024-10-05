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

from django.core.wsgi import get_wsgi_application
from web_interaction.foundry_resource import INSTANCE_PATH

this = sys.modules[__name__]

this.foundry_instances = {}
this.multifoundry_root = None
this.multifoundry_instances = None

MANAGEMENT_PATH = "manage"

def get_unassigned_port():
    if len(this.foundry_instances) == 0:
        return 30000
    else:
        return max([instance.port for instance in this.foundry_instances.values()])+1

def add_foundry_instance(foundry_instance):
    port = get_unassigned_port()
    instance_slug_bytes = foundry_instance.instance_slug.encode()
    os.makedirs(foundry_instance.data_path, exist_ok=True)
    foundry_instance.inject_config()
    foundry_instance.clear_unmatched_license()
    foundry_instance.assign_license_if_able()
    foundry = web_interaction.foundry_resource.FoundryResource(
        foundry_instance, port=port, log=False
    )
    this.multifoundry_instances.putChild(instance_slug_bytes, foundry)
    this.foundry_instances[foundry_instance.instance_name] = foundry
    foundry_instance.wait_for_ready()
    foundry_instance.activate_license()
    print(f"launched {foundry_instance.instance_name} - version {foundry_instance.foundry_version.version_string}")

def remove_foundry_instance(foundry_instance):
    instance_slug_bytes = foundry_instance.instance_slug.encode()
    if this.multifoundry_instances.getStaticEntity(instance_slug_bytes):
        this.multifoundry_instances.delEntity(instance_slug_bytes)
    if foundry_instance.instance_name in this.foundry_instances:
        res = this.foundry_instances.pop(foundry_instance.instance_name)
        res.end_process()
        print(f"stopped {foundry_instance.instance_name} - version {foundry_instance.foundry_version.version_string}")

def get_foundry_resource(foundry_instance):
    return this.foundry_instances.get(foundry_instance.instance_name, None)

def get_active_instance_names():
    return this.foundry_instances.keys()

class HomeResource(Resource):
    isLeaf = True
    def render(self, request):
        if len(this.foundry_instances) == 1:
            return redirectTo(list(this.foundry_instances.values())[0].path, request)
        else:
            return b"No instance active"

def run():
    this.multifoundry_root = Resource()
    this.multifoundry_instances = Resource()
    site = Site(this.multifoundry_root)

    resource = WSGIResource(reactor, reactor.getThreadPool(), get_wsgi_application())
    this.multifoundry_root.putChild(MANAGEMENT_PATH.encode(), resource)
    this.multifoundry_root.putChild(INSTANCE_PATH.encode(), this.multifoundry_instances)
    this.multifoundry_instances.putChild(b"", HomeResource())
    this.multifoundry_root.putChild(b"", HomeResource())

    reactor.listenTCP(8080, site)
    reactor.run()
