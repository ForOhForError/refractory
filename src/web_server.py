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

this = sys.modules[__name__]

this.foundry_instances = {}
this.multifoundry = None

def get_unassigned_port():
    if len(this.foundry_instances) == 0:
        return 30000
    else:
        return max([instance.port for instance in this.foundry_instances.values()])

def add_foundry_instance(foundry_instance):
    port = get_unassigned_port()
    instance_slug_bytes = foundry_instance.instance_slug.encode()
    os.makedirs(foundry_instance.data_path, exist_ok=True)
    foundry = web_interaction.foundry_resource.FoundryResource(
        foundry_instance, port=port
    )
    this.multifoundry.putChild(instance_slug_bytes, foundry)
    this.foundry_instances[foundry_instance.instance_name] = foundry
    print(f"launched {foundry_instance.instance_name} - version {foundry_instance.foundry_version.version_string}")
    
def get_foundry_resource(foundry_instance):
    return this.foundry_instances.get(foundry_instance.instance_name, None)

class HomeResource(Resource):
    isLeaf = True
    def render(self, request):
        if len(this.foundry_instances) == 1:
            return redirectTo(list(this.foundry_instances.values())[0].path, request)
        else:
            return b"No instance active"

def run():
    this.multifoundry = Resource()
    site = Site(this.multifoundry)

    resource = WSGIResource(reactor, reactor.getThreadPool(), get_wsgi_application())
    this.multifoundry.putChild(b"manage",resource)
    this.multifoundry.putChild(b"", HomeResource())

    reactor.listenTCP(8080, site)
    reactor.run()
