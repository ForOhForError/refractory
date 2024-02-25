from twisted.internet import reactor
from twisted.web.resource import Resource
from twisted.web.wsgi import WSGIResource
from twisted.web.server import Site
from twisted.python import log as twlog

import web_interaction.vtt_interaction
import web_interaction.foundry_interaction
import web_interaction.foundry_resource
from urllib.parse import quote_plus

import sys
import os
import os.path

twlog.startLogging(sys.stdout)
from django.core.wsgi import get_wsgi_application

FOUNDRY_INSTANCES = {}
MULTIFOUNDRY = None

def get_unassigned_port():
    if len(FOUNDRY_INSTANCES) == 0:
        return 30000
    else:
        return max([instance.port for instance in FOUNDRY_INSTANCES.values()])

def add_foundry_instance(instance_name, version, releases_dir="foundry_releases"):
    global MULTIFOUNDRY
    port = get_unassigned_port()
    instance_name_bytes = f"instances/{quote_plus(instance_name)}".encode()
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

    resource = WSGIResource(reactor, reactor.getThreadPool(), get_wsgi_application())
    MULTIFOUNDRY.putChild(b"manage",resource)

    reactor.listenTCP(8080, site)
    reactor.run()
