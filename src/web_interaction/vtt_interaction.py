import requests
from websockets.sync.client import connect
import re
import json
from enum import Enum
from bs4 import BeautifulSoup
import bs4.element
from web_server import RefractoryServer

class SocketioMessageCode(Enum):
    JOIN_DATA_RESPONSE = 430

from web_interaction.template_rewrite import REWRITE_RULES

def vtt_login(foundry_instance, foundry_user):
    with requests.Session() as session:
        return vtt_session_login(foundry_instance, foundry_user, session)

def vtt_session_login(foundry_instance, foundry_user, session):
    login_url = f"{foundry_instance.server_facing_base_url}/join"
    session.get(
        login_url
    )
    form_body = {
        "userid":foundry_user.user_id,
        "password":foundry_user.user_password,
        "adminPassword":"",
        "action":"join"
    }
    login_res = session.post(
        login_url,
        data = form_body
    )
    if login_res.ok:
        return login_res.json().get("redirect"), dict(session.cookies)
    else:
        return None, None
    
def admin_login(foundry_instance):
    with requests.Session() as session:
        return admin_session_login(foundry_instance, session)

def admin_session_login(foundry_instance, session):
    login_url = f"{foundry_instance.server_facing_base_url}/auth"
    session.get(login_url)
    admin_pass = foundry_instance.admin_pass
    form_body = {
        "adminPassword": admin_pass,
        "adminKey": admin_pass,
        "action": "adminAuth"
    }
    login_url = f"{foundry_instance.server_facing_base_url}/auth"
    login_res = session.post(
        login_url,
        data = form_body
    )
    return foundry_instance.user_facing_base_url, dict(session.cookies)

def wait_for_ready(foundry_instance):
    with requests.Session() as session:
        while True:
            try:
                base_url = f"{foundry_instance.server_facing_base_url}"
                res = session.get(
                    base_url
                )
                break
            except Exception:
                pass

def activate_license(foundry_instance):
    with requests.Session() as session:
        license_url = f"{foundry_instance.server_facing_base_url}/license"
        session.get(
            license_url
        )
        try:
            if foundry_instance.foundry_license:
                form_body = {
                    "licenseKey":foundry_instance.foundry_license.license_key,
                    "action":"enterKey"
                }
                license_res = session.post(
                    license_url,
                    data = form_body
                )
                if license_res.ok:
                    try:
                        return True
                    except Exception:
                        return False
                else:
                    return False
        except Exception:
            return False
    return False

def get_join_info(foundry_instance):
    try:
        if RefractoryServer.get_server().get_foundry_resource(foundry_instance):
            base_url = foundry_instance.server_facing_base_url
            login_url = f"{base_url}/join"
            session_id = requests.get(login_url).cookies.get('session', None)
            if session_id:
                ws_url = f"{base_url.replace('http','ws')}/socket.io/?session={session_id}&EIO=4&transport=websocket"
                with connect(ws_url) as websocket:
                    websocket.send('40')
                    websocket.send('420["getJoinData"]')
                    while True:
                        message = websocket.recv(timeout=1)
                        code_match = re.search("^\d*", message)
                        code, data = int(message[code_match.start():code_match.end()]), message[code_match.end():]
                        if code == SocketioMessageCode.JOIN_DATA_RESPONSE.value:
                            join_info = json.loads(data)[0]
                            world_id = join_info.get("world", {}).get("id", None)
                            if world_id and not foundry_instance.managedfoundryuser_set.filter(world_id=world_id, managed_gm=True).exists():
                                gamemaster_candidate_user = join_info.get("users", [{}])[0]
                                print(gamemaster_candidate_user)
                                if gamemaster_candidate_user.get("role") == 4:
                                    user_id, user_name = gamemaster_candidate_user.get("_id"), gamemaster_candidate_user.get("name")
                                    foundry_instance.register_managed_gm(world_id, user_id, user_name)
                            return join_info
    except Exception as ex:
        pass
    return {}

def get_setup_info(foundry_instance):
    try:
        if RefractoryServer.get_server().get_foundry_resource(foundry_instance):
            base_url = foundry_instance.server_facing_base_url
            login_url = f"{base_url}/join"
            session_id = requests.get(login_url).cookies.get('session', None)
            if session_id:
                ws_url = f"{base_url.replace('http','ws')}/socket.io/?session={session_id}&EIO=4&transport=websocket"
                with connect(ws_url) as websocket:
                    websocket.send('40')
                    websocket.send('420["getSetupData"]')
                    while True:
                        message = websocket.recv(timeout=1)
                        code_match = re.search("^\d*", message)
                        code, data = int(message[code_match.start():code_match.end()]), message[code_match.end():]
                        if code == SocketioMessageCode.JOIN_DATA_RESPONSE.value:
                            return json.loads(data)[0]
    except Exception as ex:
        pass
    return {}

