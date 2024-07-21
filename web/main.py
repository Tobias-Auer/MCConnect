from re import sub
import secrets
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
    host_parts = request.host.split('.')
    subdomain = host_parts[0] if len(host_parts) > 2 else None
    if subdomain == "mc":
        return dict()  
    server_information = db_manager.get_server_information(subdomain)
    logger.debug("Server information: %s" % str(server_information))
    if server_information is None:
        abort(404)
    
    uuid = session.get('uuid')
    player_id = session.get('id')
    # uuid = "4ebe5f6f-c231-4315-9d60-097c48cc6d30"
    loginVar = "<a href=\"/login\" id=loginLink>Login</a>"
    permission_level = 99
    name = ""
    logger.debug("UUID: %s" % uuid)
    
    if isinstance(uuid, str):
        name = db_manager.get_player_name_from_uuid__offline(uuid)
        loginVar = (f"{name}<br> <a id=logoutLink onclick=\"logout()\" style=\"cursor: "
                    "pointer;font-size:20px;\">Logout</a>")
        
        permission_level = db_manager.get_web_access_permission_from_player_id(player_id)
    
    return dict(loginVar=loginVar, 
                perm=permission_level,
                uuid_profile=uuid, 
                name=name,
                server_description_short=server_information[6], 
                server_description_long=server_information[7], 
                discord_url=server_information[5], 
                license_type=server_information[2],
                mc_server_domain=server_information[4],
                server_name=server_information[8])




@app.route('/')
def main_index_route():
    """
    Display the index page.

    :return: Rendered template for the index page (index.html)
    """
    print(session.get("uuid"), session.get("id"))

    return render_template("index-main.html")

@app.route('/', subdomain='<subdomain>')
def subdomain_index_route(subdomain):
    """
    Display the index page.

    :return: Rendered template for the index page (index.html)
    """
    print(subdomain)
    print(session.get("uuid"), session.get("id"))

    return render_template("index-subpage.html")



@app.route('/login', methods=['GET', 'POST'], subdomain='<subdomain>')
def login(subdomain):
    if request.method == 'POST':
        if request.form['text_input'] != "logout":
            abort(400)
        session.clear()
        return render_template("index.html")

    uuid = session.get('uuid')
    logger.debug(f"uuid: {uuid}")
    if isinstance(uuid, str):
        return render_template("logout_confirmation.html", uuid=uuid)
    uuid = session.get('try_login')
    if isinstance(uuid, str):
        return render_template("login.html", uuid=db_manager.get_player_name_from_uuid__offline(uuid))
    if not request.args.get('next'):
        refer = request.referrer
        path = "/" if not refer else urlparse(refer).path
        return redirect(f'/login?next={path}')
    return render_template("login.html", uuid="")

@app.route('/api/login', methods=['POST'], subdomain='<subdomain>')
def login_api(subdomain):
    if not request.headers.get('Content-Type', '') == 'application/json':
        return {'response': "Invalid content"}
    username = request.get_json()["username"]
    pin = request.get_json()["pin"]

    logger.debug(f"Username: '{username}', Password: '{pin}'")
    
    if pin == "":
        return {'response': "Invalid pin", "status": "error",
                    "info": "Please enter a valid pin!"}
    if not pin:
        uuid = db_manager.get_player_uuid_from_name__offline(username)
        if uuid == -1:
            return {'response': "Invalid username", "status": "error",
                    "info": "Given username not found in the database"}
        player_id = db_manager.get_player_id_from_player_uuid_and_subdomain(uuid, subdomain)
        session["id"] = player_id
        online_status = db_manager.get_online_status_by_player_id(player_id)
        print(f"Player status: {online_status}")
        if not online_status:
            return {'response': "You are offline", "status": "error",
                    "info": "Please log into the server and try again. You must be online to progress"}
        secret_pin = secrets.SystemRandom().randrange(100000, 999999)
        db_manager.add_login_entry_from_player_id(player_id, secret_pin)
        session["login_in_progress_uuid"] = uuid  # set session cookie for the next step in the login process
        return {"response": "success", "status": "success", "info": ""}

    uuid = session.get("login_in_progress_uuid")
    if uuid is None:  # error correction
        session.clear()
        return {"response": "Cookie is wrong", "status": "reset",
                "info": "Something with your cookies went wrong! Did you eat any of them?? Please try again!"}
    # if not db_handler.check_for_login_entry(uuid):  # happens after the 5-minute timeout
    #     session.clear()
    #     return {"response": "Timed out", "status": "reset",
    #             "info": "Your pin has timed out. You have 5 only minutes to enter your pin until it gets devalidated! Please try again!"}
    try:
        secret_pin_from_form = int(pin)
    except ValueError:
        return {"response": "Pin is incorrect", "status": "error",
                "info": "Your pin is incorrect! Please try again!"}
    player_id = session.get("id")
    validate_login = db_manager.get_login_attempt_validity_from_player_id_and_pin(player_id, secret_pin_from_form)
    if validate_login[0]:
        session.clear()
        session["uuid"] = uuid
        session["id"] = player_id
        session.permanent = True
        return {"response": "Pin is correct", "status": "success", "info": ""}
    
    if validate_login[1] == "timeout reached":
        return {"response": "Timed out", "status": "reset",
                "info": "Your pin has timed out. You have 5 only minutes to enter your pin until it gets devalidated! Please try again!"}
    return {"response": "Pin is incorrect", "status": "error",
                "info": "Your pin is incorrect! Please try again!"}

if __name__ == '__main__':
    app.run(debug=True)
