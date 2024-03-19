import requests
#import flask
from websockets.sync.client import connect
import re
import json
from enum import Enum
from bs4 import BeautifulSoup
import bs4.element

from socketio.packet import Packet

class SocketioMessageCode(Enum):
    JOIN_DATA_RESPONSE = 430

from web_interaction.template_rewrite import REWRITE_RULES

def rewrite_template_payload(payload, response_to=None):
    if response_to and response_to.data and isinstance(response_to.data, list) and len(response_to.data)==2:
        verb, subject = response_to.data
        if verb == 'template':
            if payload.data:
                if isinstance(payload.data, list) and len(payload.data) > 0:
                    first_data = payload.data[0]
                    if isinstance(first_data, dict):
                        text_payload = first_data.get('html')
                        success = first_data.get('success')
                        if text_payload:
                            if subject in REWRITE_RULES:
                                rewritten_html = REWRITE_RULES[subject](text_payload)
                                return Packet(
                                    packet_type=payload.packet_type, 
                                    data=[{"html": rewritten_html, "success":success}], 
                                    namespace=payload.namespace, id=payload.id
                                )
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

