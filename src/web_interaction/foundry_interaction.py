import requests
from bs4 import BeautifulSoup
from datetime import datetime
import cgi
import zipfile
import os
import os.path

from twisted.python import log

from twisted.internet import reactor
from twisted.web import proxy, server

BASE_URL = "https://foundryvtt.com"
LOGIN_URL = f"{BASE_URL}/auth/login/"
RELEASES_URL = f"{BASE_URL}/releases"

POST_HEADERS = {
    "DNT": "1",
    "Referer": BASE_URL,
    "Upgrade-Insecure-Requests": "1",
    "User-Agent": "python-requests",
}

def get_releases(session):
    releases_page = session.get(RELEASES_URL)
    releases_page_parse = BeautifulSoup(
        releases_page.text, 
        features="html.parser"
    )
    releases = releases_page_parse.find_all(
        'li',
        attrs = {'class':'release'}
    )
    parsed_releases = []
    for release in releases:
        release_link = release.find('a')
        version = release_link.getText().replace("Release ","")
        tags = [
            tag.getText() for tag in 
            release.find_all(
                'span',
                attrs = {'class':'release-tag'}
            )
        ]
        date = release.find('span',attrs={'class':'release-time'}).getText()
        date = datetime.strptime(date, '%B %d, %Y')
        parsed_releases.append(
            {
                "version": version,
                "tags": tags,
                "date": date
            }
        )
    return parsed_releases

def get_token(session):
    foundry_home_res = session.get(BASE_URL)
    foundry_home_parse = BeautifulSoup(
        foundry_home_res.text, 
        features="html.parser"
    )
    csrf_token_element = foundry_home_parse.find(
        'input',
        attrs = {'name':'csrfmiddlewaretoken'}
    )
    if csrf_token_element:
        return csrf_token_element['value']
    else:
        return None

def login(session, csrf_token, username, password):
    form_body = {
        "csrfmiddlewaretoken": csrf_token,
        "password": password,
        "next": "/",
        "username": username,
        "login": "",
    }
    login_res = session.post(
        LOGIN_URL,
        data = form_body,
        headers = POST_HEADERS
    )
    login_res_parse = BeautifulSoup(
        login_res.text, 
        features="html.parser"
    )
    profile_element = login_res_parse.find(
        'span',
        attrs = {'id':'login-welcome'}
    )
    if profile_element:
        canon_username = profile_element.find('a')['href'].split('/')[-1]
        return canon_username
    return None


def download_linux_zip(session, version_string, download_dir="foundry_releases_zip", platform="linux"):
    download_url = f"{RELEASES_URL}/download"
    try:
        with session.get(
            download_url, params = {
                "version": version_string,
                "platform": platform
            },
            stream = True
        ) as download_res:
            download_res.raise_for_status()
            filename = f"{version_string}.zip"
            zip_file = os.path.join(download_dir, filename)
            os.makedirs(download_dir, exist_ok=True)
            with open(zip_file, 'wb') as f:
                for chunk in download_res.iter_content(chunk_size=8192): 
                    f.write(chunk)
            return True
    except Exception as ex:
        raise ex
        return False

def get_licenses(session, canon_username):
    licenses_url = f"{BASE_URL}/community/{canon_username}/licenses/"
    licenses_res = session.get(
        licenses_url,
    )
    licenses_res_parse = BeautifulSoup(
        licenses_res.text, 
        features="html.parser"
    )
    licenses = licenses_res_parse.find_all(
        'div',
        attrs = {'class':'license'}
    )
    parsed_licenses = []
    for license_div in licenses:
        license_obj = {}
        license_key = license_div.find('input', attrs={'readonly':''})['value']
        license_obj['license_key'] = license_key
        license_name_element = license_div.find('span', attrs={'class':'license-name'})
        if license_name_element:
            license_name = license_name_element.getText()
            license_obj['license_name'] = license_name
        else:
            license_obj['license_name'] = ""
        parsed_licenses.append(license_obj)
    return parsed_licenses

def download_and_write_release(session, version_string=None, output_path="foundry_releases", download_dir="foundry_releases_zip"):
    tok = get_token(session)
    if not version_string:
        releases = get_releases(session)
        version_string = releases[0].version
    try:
        filename = f"{version_string}.zip"
        zip_file = os.path.join(download_dir, filename)
        output_dir = os.path.join(output_path,version_string)
        test_for_file = os.path.join(output_path,version_string,"refractory")
        if not os.path.exists(zip_file):
            #raise Exception("doesn't exist")
            success = download_linux_zip(session, version_string)
            if not success:
                raise Exception("didn't download")
                return False
        if not os.path.exists(test_for_file):
            log.msg("extracting")
            with zipfile.ZipFile(zip_file, 'r') as zip_ref:
                zip_ref.extractall(output_dir)
            with open(test_for_file, "w") as testfile:
                testfile.write("refractory")
        return True
    except Exception as ex:
        raise ex
        return False
    return False
