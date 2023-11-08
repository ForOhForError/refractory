import requests
import flask
from websockets.sync.client import connect
import re
import json
from enum import Enum
from bs4 import BeautifulSoup


class SocketioMessageCode(Enum):
    JOIN_DATA_RESPONSE = 430
    TEMPLATE_RESPONSE = 432

def rewrite_template_payload(payload, isBinary=False):
    payload = payload.decode()
    code_match = re.search("^\d*", payload)
    code, data = int(payload[code_match.start():code_match.end()]), payload[code_match.end():]
    if code == SocketioMessageCode.TEMPLATE_RESPONSE.value:
        json_data = json.loads(data)[0]
        html_data = json_data.get("html","")
        html_data_parse = BeautifulSoup(
            html_data, 
            features="html.parser"
        )
        join_form = html_data_parse.find(
            'form',
            attrs = {'id':'join-game'}
        )
        # if join_form:
        #     for element in join_form.children:
        #         element.extract()
        template_str = html_data_parse.encode("ascii").decode()
        print(template_str)
        json_res = {"html":template_str}
        json_str = json.dumps(json_res)
        #return f'{code}[{json_str}]'.encode()
    return payload.encode()

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
                res = flask.redirect(login_res.json().get("redirect"))
                res.set_cookie('session', session.cookies.get('session',''))
                return res
            except Exception:
                return login_res.content
        else:
            return flask.redirect("/manage")

def get_join_info(base_url, session_id = None):
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

