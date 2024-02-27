
import subprocess
from twisted.internet import reactor
from twisted.web import proxy

from autobahn.twisted.websocket import WebSocketServerFactory, WebSocketClientFactory,\
    WebSocketServerProtocol, WebSocketClientProtocol

from autobahn.twisted.resource import WebSocketResource

from web_interaction import vtt_interaction, foundry_interaction

import os.path
import json

def build_websocket_reverse_proxy_client_protocol(server_instance, override_client_payload=None):
    class WebsocketReverseProxyClientProtocol(WebSocketClientProtocol):
        def onOpen(self):
            server_instance.set_client(self)
        def onMessage(self, payload, isBinary):
            if override_client_payload:
                payload = override_client_payload(payload, isBinary=isBinary)
            server_instance.sendMessage(payload, isBinary=isBinary)
        def onClose(self, wasClean, code, reason):
            server_instance.sendClose(code=1000,reason=reason)
    return WebsocketReverseProxyClientProtocol

def build_websocket_reverse_proxy_protocol(addr, host, port, override_server_payload=None, override_client_payload=None):
    class WebsocketReverseProxyServerProtocol(WebSocketServerProtocol):
        def onConnect(self, request):
            self.params = request.params

        def onOpen(self):
            url = addr+"?"+"&".join([f"{key}={''.join(value)}" for (key, value) in self.params.items()])
            factory = WebSocketClientFactory(url)
            factory.protocol = build_websocket_reverse_proxy_client_protocol(self, override_client_payload=override_client_payload)
            reactor.connectTCP(host, port, factory)

        def set_client(self, client_instance):
            self.client_instance = client_instance

        def onMessage(self, payload, isBinary):
            if hasattr(self, "client_instance") and self.client_instance:
                if override_server_payload:
                    payload = override_server_payload(payload, isBinary=isBinary)
                self.client_instance.sendMessage(payload, isBinary=isBinary)

        def onClose(self, wasClean, code, reason):
            if hasattr(self, "client_instance") and self.client_instance:
                self.client_instance.sendClose(code=1000,reason=reason)
    return WebsocketReverseProxyServerProtocol

class SocketIOReverseProxy(proxy.ReverseProxyResource):
    def __init__(self, host, port, path):
        proxy.ReverseProxyResource.__init__(self, host, port, path)
        self.host = host
        self.port = port
        self.path = path
        self.ws_path = "socket.io"
        self.ws_redirect = f"ws://{self.host}:{self.port}/{self.path.decode('utf8')}/{self.ws_path}/"
        factory = WebSocketServerFactory()
        factory.protocol = build_websocket_reverse_proxy_protocol(self.ws_redirect, self.host, self.port, override_client_payload=self.rewrite_socketio_response)
        self.ws_proxy = WebSocketResource(factory)
        self.rev_proxy = proxy.ReverseProxyResource(self.host, self.port, b"/"+self.path)

    def rewrite_socketio_response(self, payload, isBinary=False):
        return vtt_interaction.rewrite_template_payload(payload, isBinary=isBinary)

    def render(self, request):
        return self.rev_proxy.render(request)

    def getChild(self, path, request):
        if path.decode().startswith(self.ws_path):
            return self.ws_proxy
        else:
            return self.rev_proxy.getChild(path, request)

class FoundryResource(SocketIOReverseProxy):
    def __init__(
        self, host, port, path, foundry_main, foundry_data_path
    ):
        super().__init__(host, port, path)
        self.path_bytes = path
        self.data_path = foundry_data_path
        self.port = port
        self.inject_config()
        self.process = subprocess.Popen(
            ["node", foundry_main, f"--dataPath={self.data_path}", "--noupdate"], 
            #stdout=subprocess.DEVNULL
        )

    def inject_config(self):
        config_path = os.path.join(self.data_path, "Config")
        os.makedirs(config_path, exist_ok=True)
        config_file_path = os.path.join(config_path, "options.json")
        if os.path.exists(config_file_path):
            with open(config_file_path) as config_file:
                config_obj = json.load(config_file)
        else:
            config_obj = {}
        config_obj.update({
            "port": self.port,
            "routePrefix": self.path.decode()
        })
        with open(config_file_path, "w") as config_file:
            config_file.write(json.dumps(config_obj))

    def login_flask(self):
        return vtt_interaction.login(f"http://{self.host}:{self.port}/{self.path.decode()}")