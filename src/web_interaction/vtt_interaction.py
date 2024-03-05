import requests
#import flask
from websockets.sync.client import connect
import re
import json
from enum import Enum
from bs4 import BeautifulSoup
import bs4.element

class SocketioMessageCode(Enum):
    JOIN_DATA_RESPONSE = 430
    TEMPLATE_RESPONSE = 432

from html.parser import HTMLParser
from html.entities import name2codepoint

class MyHTMLParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.count = None
        self.cursor = None
        self.range = None

    def handle_starttag(self, tag, attrs):
        found = False
        if tag == "div":
            for attr in attrs:
                attr_key, attr_values = attr
                if attr_key == "class" and "join-form" in attr_values:
                    found = True
                    print(tag,attrs)
            if found:
                self.count = 0
                self.cursor = self.getpos()
            elif self.count != None:
                self.count += 1

    def handle_endtag(self, tag):
        if tag == "div":
            if self.count != None:
                self.count -= 1
                if self.count == 0:
                    self.range = [self.cursor, self.getpos()]
                    self.count, self.cursor = None, None


def remove_node(html_text, node, replacement_text:str=""):
    print(node)
    if hasattr(node, "sourcepos"):
        start = node.sourcepos
    else:
        start = str(html_text).find(str(node))
    end = start+len(str(node))
    print(html_text)
    return html_text[:start]+replacement_text+html_text[end:]

def find_and_remove_node(html_text, *args, replacement_text:str="", **kwargs):
    html_data_parse = BeautifulSoup(
        html_text, 
        features="html.parser"
    )
    node = html_data_parse.find(
        *args, **kwargs
    )
    if node:
        html_text = remove_node(html_text, node, replacement_text=replacement_text)
        print(html_text)
    return html_text

def rewrite_template_payload(payload, isBinary=False, response_to=None):
    parser = MyHTMLParser()
    text_payload = payload.decode()
    code_match = re.search("^\d*", text_payload)
    print(response_to)
    code, data = int(text_payload[code_match.start():code_match.end()]), text_payload[code_match.end():]
    if code == SocketioMessageCode.TEMPLATE_RESPONSE.value:
        json_data = json.loads(data)[0]
        html_data = json_data.get("html","")
        if html_data:
            parser.feed(html_data)
            if parser.range:
                print("form found!",parser.range)
            json_res = dict(json_data)
            json_res.update({"html":html_data})
            json_str = json.dumps(json_res)
            return f'{code}[{json_str}]'.encode()
    return payload

def login(base_url, user:str="", password:str=""):
    with requests.Session() as session:
        login_url = f"{base_url}/join"
        session.get(
            login_url
        )
        form_body = {
            "userid":user,
            "password":password,
            "adminPassword":"",
            "action":"join"
        }
        join_info = get_join_info(base_url, session.cookies.get('session',None))
        login_res = session.post(
            login_url,
            data = form_body
        )
        if login_res.ok:
            try:
                res = None #flask.redirect(login_res.json().get("redirect"))
                # res.set_cookie('session', session.cookies.get('session',''))
                return res
            except Exception:
                return login_res.content
        else:
            return None #flask.redirect("/manage")

def get_join_info(foundry_instance):
    try:
        if not session_id:
            login_url = f"{base_url}/join"
            session_id = requests.get(login_url).cookies.get('session', None)
        if session_id:
            ws_url = f"{base_url.replace('http','ws')}/socket.io/?session={session_id}&EIO=4&transport=websocket"
            with connect(ws_url) as websocket:
                websocket.send('40')
                websocket.send('420["getJoinData"]')
                for message in websocket:
                    code_match = re.search("^\d*", message)
                    code, data = int(message[code_match.start():code_match.end()]), message[code_match.end():]
                    if code == SocketioMessageCode.JOIN_DATA_RESPONSE.value:
                        return json.loads(data)[0]
    except Exception as ex:
        pass
    return None

