import json
import os.path
import subprocess
import urllib.parse

from autobahn.twisted.resource import Resource, WebSocketResource
from autobahn.twisted.websocket import (
    WebSocketClientFactory,
    WebSocketClientProtocol,
    WebSocketServerFactory,
    WebSocketServerProtocol,
)
from socketio.packet import Packet
from twisted.internet import reactor
from twisted.web import error, proxy
from twisted.web.server import Site

from refractory_settings import INSTANCE_PATH
from web_interaction import template_rewrite


def to_socketio_packet(payload):
    if isinstance(payload, bytes):
        str_payload = payload.decode("utf8")
    else:
        str_payload = payload
    pkt = Packet()
    try:
        pkt.decode(str_payload)
        return pkt
    except Exception:
        return None


def mod_id(id, mod=1):
    id = str(id)
    new_id = ""
    if len(id) > 0:
        new_id += str(int(id[0]) + mod)
    if len(id) > 1:
        new_id += id[1:]
    return int(new_id)


class BlackholeResource(Resource):
    isLeaf = True

    def render(self, request):
        request.setResponseCode(403)
        return b"Blocked by Refractory"


def build_websocket_reverse_proxy_client_protocol(
    server_instance, override_client_payload=None
):
    class WebsocketReverseProxyClientProtocol(WebSocketClientProtocol):
        def onOpen(self):
            server_instance.set_client(self)

        def onMessage(self, payload, isBinary):
            pkt = to_socketio_packet(payload)
            orig_pkt = None
            if pkt and pkt.id:
                orig_id = mod_id(pkt.id, mod=-1)
                orig_pkt = server_instance.sent_messages.pop(orig_id, None)
            if override_client_payload:
                payload = (
                    override_client_payload(pkt, response_to=orig_pkt).encode().encode()
                )
            server_instance.sendMessage(payload, isBinary=isBinary)

        def onClose(self, wasClean, code, reason):
            server_instance.sendClose(code=1000, reason=reason)

    return WebsocketReverseProxyClientProtocol


def build_websocket_reverse_proxy_protocol(
    addr, host, port, override_server_payload=None, override_client_payload=None
):
    class WebsocketReverseProxyServerProtocol(WebSocketServerProtocol):
        def onConnect(self, request):
            self.params = request.params
            self.sent_messages = {}

        def onOpen(self):
            url = (
                addr
                + "?"
                + "&".join(
                    [f"{key}={''.join(value)}" for (key, value) in self.params.items()]
                )
            )
            factory = WebSocketClientFactory(url)
            factory.protocol = build_websocket_reverse_proxy_client_protocol(
                self, override_client_payload=override_client_payload
            )
            reactor.connectTCP(host, port, factory)

        def set_client(self, client_instance):
            self.client_instance = client_instance

        def onMessage(self, payload, isBinary):
            if hasattr(self, "client_instance") and self.client_instance:
                pkt = to_socketio_packet(payload)
                if pkt and pkt.id:
                    self.sent_messages[pkt.id] = pkt
                if override_server_payload:
                    payload = override_server_payload(pkt).encode().encode()
                self.client_instance.sendMessage(payload, isBinary=isBinary)

        def onClose(self, wasClean, code, reason):
            if hasattr(self, "client_instance") and self.client_instance:
                self.client_instance.sendClose(code=1000, reason=reason)

    return WebsocketReverseProxyServerProtocol


class OverrideProxyClient(proxy.ProxyClient):
    _finished = False

    def __init__(self, command, rest, version, headers, data, father):
        super().__init__(command, rest, version, headers, data, father)

    def handleResponseEnd(self):
        if not self._finished:
            self._finished = True
            try:
                self.father.finish()
            except RuntimeError:
                pass
            self.transport.loseConnection()


class OverrideProxyClientFactory(proxy.ProxyClientFactory):
    """
    Used by ProxyRequest to implement a simple web proxy.
    """

    def __init__(self, command, rest, version, headers, data, father):
        super().__init__(command, rest, version, headers, data, father)
        self.protocol = OverrideProxyClient


class SocketIOReverseProxy(proxy.ReverseProxyResource):
    def __init__(self, host, port, path):
        proxy.ReverseProxyResource.__init__(self, host, port, path)
        self.proxyClientFactoryClass = OverrideProxyClientFactory
        self.host = host
        self.port = port
        self.path = path
        self.ws_path = "socket.io"
        self.ws_redirect = (
            f"ws://{self.host}:{self.port}/{self.path.decode('utf8')}/{self.ws_path}/"
        )
        factory = WebSocketServerFactory()
        factory.protocol = build_websocket_reverse_proxy_protocol(
            self.ws_redirect,
            self.host,
            self.port,
            override_client_payload=self.rewrite_socketio_response,
        )
        self.ws_proxy = WebSocketResource(factory)
        self.rev_proxy = proxy.ReverseProxyResource(
            self.host, self.port, b"/" + self.path
        )

    def rewrite_socketio_response(self, pkt, response_to=None):
        return pkt

    def render(self, request):
        return self.rev_proxy.render(request)

    def getChild(self, path, request):
        path_string = path.decode()
        if path_string.startswith(self.ws_path):
            return self.ws_proxy
        else:
            return self.rev_proxy.getChild(path, request)


DENY_ACTIONS = {
    "join": ["shutdown", "login", "adminLogin"],
    "auth": ["adminAuth", "auth"],
}


def get_request_param(request, param_name):
    body = request.content.read().decode()
    request.content.seek(0)
    try:
        json_body = json.loads(body)
        return json_body.get(param_name)
    except json.decoder.JSONDecodeError:
        qs_body = urllib.parse.parse_qs(body)
        return qs_body.get(param_name, [None])[0]


class FoundryResource(SocketIOReverseProxy):
    def __init__(self, foundry_instance, host="localhost", port=30000, log=True):
        self.foundry_instance = foundry_instance
        self.port = port
        self.host = host
        self.path = (INSTANCE_PATH + "/" + foundry_instance.instance_slug).encode()
        super().__init__(self.host, self.port, self.path)
        self.blackhole = BlackholeResource()
        data_path = self.foundry_instance.data_path
        if not log:
            kwargs = {
                "stdout": subprocess.DEVNULL,
                "stderr": subprocess.DEVNULL,
            }
        else:
            kwargs = {}
        self.process = subprocess.Popen(
            [
                "node",
                foundry_instance.foundry_version.executable_path,
                f"--dataPath={data_path}",
                "--noupdate",
                f"--adminPassword={foundry_instance.admin_pass}",
                f"--adminKey={foundry_instance.admin_pass}",
            ],
            **kwargs,
        )

    def get_base_url(self):
        return f"http://{self.host}:{self.port}"

    def end_process(self):
        try:
            self.process.terminate()
            self.process.communicate(timeout=1)
        except Exception:
            self.process.kill()
            self.process.communicate(timeout=1)

    def rewrite_socketio_response(self, pkt, response_to=None):
        return template_rewrite.rewrite_template_payload(
            pkt, response_to=response_to, instance=self.foundry_instance
        )

    def check_for_deny(self, request):
        if request.method == b"POST":
            try:
                amended_path = request.path.decode().split("/")[3]
                if amended_path in DENY_ACTIONS:
                    actions_to_deny = DENY_ACTIONS[amended_path]
                    action = get_request_param(request, "action")
                    if action in actions_to_deny:
                        return True
                elif amended_path == "license":
                    action = get_request_param(request, "agree")
                    if action == "on":
                        self.foundry_instance.eula_accepted = True
                        self.foundry_instance.save()
            except Exception:
                pass
        return False

    def getChild(self, path, request):
        if self.check_for_deny(request):
            return self.blackhole
        else:
            return super().getChild(path, request)
