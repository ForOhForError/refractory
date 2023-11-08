import subprocess


from twisted.internet import reactor
from twisted.web import proxy, server
from twisted.web.resource import Resource
from twisted.web.util import Redirect
from twisted.web.wsgi import WSGIResource

import asyncio
import re

import sys

from twisted.internet import reactor
from twisted.python import log
from twisted.web.server import Site
from twisted.web.static import File

from autobahn.twisted.websocket import WebSocketServerFactory, WebSocketClientFactory,\
    WebSocketServerProtocol, WebSocketClientProtocol

from autobahn.twisted.resource import WebSocketResource

import vtt_interaction
import foundry_interaction
import asyncio

import flask
from flask import Flask, request, redirect, render_template
from flask_admin import Admin
import requests
import secrets


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
            return proxy.ReverseProxyResource(self.host, self.port, b"/"+self.path+b"/"+path)

class FoundryResource(SocketIOReverseProxy):
    def __init__(self,host,port,path,foundry_main,foundry_data_path):
        super().__init__(host, port, path)
        subprocess.Popen(["node", foundry_main, f"--dataPath={foundry_data_path}", "--noupdate"], stdout=subprocess.DEVNULL)

    def login_flask(self):
        return vtt_interaction.login(f"http://{self.host}:{self.port}/{self.path.decode()}")

FOUNDRY_INSTANCE = None

def main():
    app = Flask(__name__)
    app.secret_key = secrets.token_urlsafe(32)
    app.debug = True
    multifoundry = Resource()
    site = server.Site(multifoundry)
    foundry = FoundryResource(
        "localhost",30000,b"foundry",
        "output/resources/app/main.js",
        "data/foundryvtt"
    )
    multifoundry.putChild(b"foundry",foundry)

    links = [
        {"url":"/manage/login","text":"Login"},
        {"url":"/manage/versions","text":"Versions"},
        {"url":"/manage/foundry-login","text":"Foundry Login"}
    ]

    @app.route('/')
    def index():
        return render_template('index.html', links=links)
    
    @app.route('/login')
    def do_login():
        try:
            return foundry.login_flask()
        except Exception as ex:
            raise(ex)

    @app.route('/foundry-login', methods=('GET', 'POST'))
    def foundry_login():
        canon_username = None
        if request.method == 'POST':
            with requests.Session() as rsession:
                username = request.form['username']
                password = request.form['password']
                tok = foundry_interaction.get_token(rsession)
                canon_username = foundry_interaction.login(rsession, tok, username, password)
                flask.session['foundry_data'] = {
                    "cookies":rsession.cookies.get_dict(),
                    "foundry_user":canon_username
                }
        else:
            canon_username = flask.session.get('foundry_data', {}).get('foundry_user', None)
        return render_template('foundry_login.html', canon_username=canon_username)

    @app.route('/versions/')
    def versions():
        cookies = flask.session.get('foundry_data', {}).get('cookies', {})
        versions = []
        with requests.Session() as rsession:
            rsession.cookies.update(cookies)
            versions = foundry_interaction.get_releases(rsession)
        return render_template('versions.html', versions=versions)

    #@app.route('/versions/', methods=('GET', ))
    def launch_version():
        cookies = flask.session.get('foundry_data', {}).get('cookies', {})
        versions = []
        with requests.Session() as rsession:
            rsession.cookies.update(cookies)
            versions = foundry_interaction.get_releases(rsession)
        return render_template('versions.html', versions=versions)

    resource = WSGIResource(reactor, reactor.getThreadPool(), app)
    multifoundry.putChild(b"manage",resource)

    reactor.listenTCP(8080, site)
    reactor.run()


if __name__ == "__main__":
    main()