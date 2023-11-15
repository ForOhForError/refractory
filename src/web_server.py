from twisted.internet import reactor
from twisted.web.resource import Resource
from twisted.web.wsgi import WSGIResource
from twisted.web.server import Site

import vtt_interaction
import foundry_interaction
import foundry_resource
from management_app import flask_app

import os
import os.path

FOUNDRY_INSTANCES = {}
MULTIFOUNDRY = None

def get_unassigned_port():
    return 30000

def add_foundry_instance(instance_name, version, releases_dir="foundry_releases"):
    global MULTIFOUNDRY
    port = get_unassigned_port()
    instance_name_bytes = instance_name.encode()
    main_path = os.path.join(releases_dir, version, "resources", "app", "main.js")
    data_path = os.path.join("instance-data",instance_name)
    os.makedirs(data_path, exist_ok=True)
    foundry = foundry_resource.FoundryResource(
        "localhost", port, instance_name_bytes,
        main_path, data_path
    )
    MULTIFOUNDRY.putChild(instance_name_bytes, foundry)
    FOUNDRY_INSTANCES[instance_name] = foundry

def run():
    global MULTIFOUNDRY
    MULTIFOUNDRY = Resource()
    site = Site(MULTIFOUNDRY)

    resource = WSGIResource(reactor, reactor.getThreadPool(), flask_app)
    MULTIFOUNDRY.putChild(b"manage",resource)

    reactor.listenTCP(8080, site)
    reactor.run()
