from re import sub
import sys
import os
from urllib.parse import urlparse

# Get the path to the root directory of your project
root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'database'))

# Add the root directory to sys.path
sys.path.insert(0, root_dir)

# Now you can import databaseManager
from databaseManager import DatabaseManager # type: ignore
from logger import get_logger # type: ignore
from minecraft import Minecraft # type: ignore

from flask import Flask, render_template, render_template_string, request, Response, redirect, session, flash, jsonify, abort
logger = get_logger("webServer")
db_manager = DatabaseManager()
minecraft = Minecraft()


# Flask Setup
app = Flask(__name__)
logger.info('Application started')
app.config.from_pyfile("config.py")
app.config.from_pyfile("instance/config.py")


@app.context_processor
def inject_loginVar():
    uuid = session.get('uuid')
    #uuid = "4ebe5f6f-c231-4315-9d60-097c48cc6d30"
    loginVar = "<a href=\"/login\" id=loginLink>Login</a>"
    permission_level = 99
    name = ""
    if isinstance(uuid, str):
        name = minecraft.get_player_name_from_uuid__offline(uuid)
        loginVar = (f"{name}<br> <a id=logoutLink onclick=\"logout()\" style=\"cursor: "
                    "pointer;font-size:20px;\">Logout</a>")
        host_parts = request.host.split('.')
        subdomain = host_parts[0] if len(host_parts) > 2 else None
        permission_level = db_manager.get_web_access_permission_from_uuid_and_subdomain(uuid, subdomain)
    

    return dict(loginVar=loginVar, perm=permission_level, uuid_profile=uuid, name=name)




@app.route('/')
def main_index_route():
    """
    Display the index page.

    :return: Rendered template for the index page (index.html)
    """
    return render_template("index-main.html")

@app.route('/', subdomain='<subdomain>')
def subdomain_index_route(subdomain):
    """
    Display the index page.

    :return: Rendered template for the index page (index.html)
    """
    return render_template("index-subpage.html")

if __name__ == '__main__':
    app.run(debug=True)
