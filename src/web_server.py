from twisted.internet import reactor
from twisted.web.resource import Resource
from twisted.web.wsgi import WSGIResource
from twisted.web.server import Site

import vtt_interaction
import foundry_interaction
import foundry_resource
from management_app import flask_app

FOUNDRY_INSTANCES = {}
MULTIFOUNDRY = None

def get_unassigned_port():
    return 30000

def add_foundry_instance(instance_name, version, foundry_resource):
    port = get_unassigned_port()
    instance_name_bytes = instance_name.encode()
    foundry = foundry_resource.FoundryResource(
        "localhost",port,instance_name_bytes,
        f"foundry_releases/{version}/resources/app/main.js",
        "data/foundryvtt"
    )
    multifoundry.putChild(instance_name_bytes, foundry)
    FOUNDRY_INSTANCES[instance_name] = foundry

def main():
    multifoundry = Resource()
    MULTIFOUNDRY = multifoundry
    site = Site(multifoundry)

    resource = WSGIResource(reactor, reactor.getThreadPool(), flask_app)
    multifoundry.putChild(b"manage",resource)

    reactor.listenTCP(8080, site)
    reactor.run()


if __name__ == "__main__":
    main()