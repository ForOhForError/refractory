from flask import Flask, render_template, request
from flask_admin import Admin

import web_interaction.foundry_interaction
#import flask
import secrets
import requests

# flask_app = Flask(__name__)
# flask_app.secret_key = secrets.token_urlsafe(32)
# flask_app.debug = True
# # set optional bootswatch theme
# flask_app.config['FLASK_ADMIN_SWATCH'] = 'cerulean'

# admin = Admin(
#     flask_app, 
#     name='Multifoundry Management', 
#     template_mode='bootstrap3',
#     endpoint="manage/admin"
# )
# # Add administrative views here

# links = [
#     {"url":"/manage/login","text":"Login"},
#     {"url":"/manage/versions","text":"Versions"},
#     {"url":"/manage/foundry-login","text":"Foundry Login"}
# ]

# @flask_app.route('/')
# def index():
#     return render_template('index.html', links=links)

# @flask_app.route('/login')
# def do_login():
#     try:
#         return foundry.login_flask()
#     except Exception as ex:
#         raise(ex)

# @flask_app.route('/foundry-login', methods=('GET', 'POST'))
# def foundry_login():
#     canon_username = None
#     if request.method == 'POST':
#         with requests.Session() as rsession:
#             username = request.form['username']
#             password = request.form['password']
#             tok = foundry_interaction.get_token(rsession)
#             canon_username = foundry_interaction.login(rsession, tok, username, password)
#             flask.session['foundry_data'] = {
#                 "cookies":rsession.cookies.get_dict(),
#                 "foundry_user":canon_username
#             }
#     else:
#         canon_username = flask.session.get('foundry_data', {}).get('foundry_user', None)
#     return render_template('foundry_login.html', canon_username=canon_username)

# @flask_app.route('/versions/')
# def versions():
#     cookies = flask.session.get('foundry_data', {}).get('cookies', {})
#     versions = []
#     with requests.Session() as rsession:
#         rsession.cookies.update(cookies)
#         versions = foundry_interaction.get_releases(rsession)
#     return render_template('versions.html', versions=versions)

# @flask_app.route('/versions/<version_number>')
# def launch_version(version_number):
#     cookies = flask.session.get('foundry_data', {}).get('cookies', {})
#     versions = []
#     with requests.Session() as rsession:
#         rsession.cookies.update(cookies)
#         releases = foundry_interaction.get_releases(rsession)
#         if version_number in [release.get('version') for release in releases]:
#             success = foundry_interaction.download_and_write_release(rsession, version_string=version_number)
#             if success:
#                 from web_server import add_foundry_instance
#                 add_foundry_instance('foundry', version_number)
#                 return ':)'
#             else:
#                 return '...'
#     return ':('