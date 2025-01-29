from re import sub
import secrets
import sys
import os
import time
from urllib.parse import urlparse

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'database')))

from database.databaseManager import DatabaseManager
from database.logger import get_logger
from database.minecraft import Minecraft

from flask import Flask, render_template, render_template_string, request, Response, redirect, session, flash, jsonify, abort
logger = get_logger("webServer")
db_manager = DatabaseManager()
minecraft = Minecraft()



app = Flask(__name__, subdomain_matching=True)
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
        logger.warning("Server not found, aborting with 404...")
        abort(404)
    
    uuid = session.get('uuid')
    player_id = session.get('id')
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



@app.route('/', subdomain='<subdomain>')
def subdomain_index_route(subdomain):
    """
    Display the index page.

    :return: Rendered template for the index page (index.html)
    """
    print("RETURN INDEX FOR: " + subdomain)
    print(session.get("uuid"), session.get("id"))
    return render_template("index-subpage.html")
@app.route('/')
def main_index_route():
    """
    Display the index page.

    :return: Rendered template for the index page (index.html)
    """
    print("NO SUBDOMAIN RECOGNIZED")
    print(session.get("uuid"), session.get("id"))
    logger.debug(f"Full host: {request.host}")

    return render_template("index-main.html")





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


@app.route('/spieler', subdomain="<subdomain>")
def player_overview_route(subdomain):
    """
    Display the player overview or specific player information.

    If a player is specified using the "?player=<username>" query parameter,
    the information for that specific player is displayed. Otherwise, the
    general player overview is shown.

    :return: Rendered template for player list or specific player info
             (spieler.html|spieler-info.html)
    """
    user_name = request.args.get('player')

    if user_name:
        uuid = db_manager.get_player_uuid_from_name__offline(user_name)
        player_id = db_manager.get_player_id_from_player_uuid_and_subdomain(uuid, subdomain)
        status = db_manager.get_online_status_by_player_uuid_and_subdomain(uuid, subdomain)
        
        armor_stats = db_manager.get_all_armor_stats(player_id)
        tool_stats = db_manager.get_all_tools_stats(player_id)
        item_stats = db_manager.get_all_items_stats(player_id)
        block_stats = db_manager.get_all_blocks_stats(player_id)
        mob_stats = db_manager.get_all_mobs_stats(player_id)
        custom_stats = db_manager.get_all_custom_stats(player_id)
        
        enddate, startdate = "", ""
        banned = db_manager.get_ban_info_from_player_uuid_and_subdomain(uuid, subdomain)
        if banned:
            startdate, enddate = banned[4].strftime("%d.%m.%Y %H:%M"), banned[5].strftime(("%d.%m.%Y %H:%M"))
            print(startdate, enddate)
        return render_template("spieler-info.html", uuid=uuid, user_name=user_name, status=status, banned=bool(banned), enddate=enddate,
                               startdate=startdate, armor_stats=armor_stats, tool_stats=tool_stats, item_stats=item_stats, block_stats=block_stats, mob_stats=mob_stats, custom_stats=custom_stats)

    all_users = []
    all_status = []
    combined_users_data = []
    all_uuids = db_manager.get_all_uuids_from_subdomain(subdomain)

    for uuid in all_uuids:
        user_name = db_manager.get_player_name_from_uuid__offline(uuid)
        if user_name is None:
            print(f"No username found for UUID: {uuid}")
            continue  # Skip processing if no username found

        all_users.append(user_name)
        status = "online" if db_manager.get_online_status_by_player_uuid_and_subdomain(uuid, subdomain) else "offline"
        print(f"Status from user: {user_name} with UUID: {uuid} is: {status}")
        all_status.append(status)
        combined_users_data.append([user_name, uuid])

    return render_template("spieler.html", results=combined_users_data, status=all_status)



################################ API #################################
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

@app.route('/api/player_count', subdomain='<subdomain>')
def stream_player_count(subdomain):
    def generate():
        while True:
            online_count = db_manager.get_online_player_count_from_subdomain(subdomain)
            yield f"data: {online_count}\n\n"
            time.sleep(1)

    return Response(generate(), mimetype='text/event-stream')

@app.route('/api/status', subdomain='<subdomain>')
def stream_status(subdomain):
    # could be more efficient witth only one db call and return the whole list instead of just uuids
    def generate():
        while True:
            all_uuids = db_manager.get_all_uuids_from_subdomain(subdomain)
            data = []
            for uuid in all_uuids:
                data.append("online" if db_manager.get_online_status_by_player_uuid_and_subdomain(uuid, subdomain) else "offline")
            yield f"data: {data}\n\n"
            time.sleep(1)

    return Response(generate(), mimetype='text/event-stream')

@app.route('/api/player_info/<path:path>', subdomain='<subdomain>')
def stream_player_info(path,subdomain):
    player_name = path
    uuid = db_manager.get_player_uuid_from_name__offline(player_name)
    player_id = db_manager.get_player_id_from_player_uuid_and_subdomain(uuid, subdomain)
    first_seen = db_manager.get_first_seen_by_player_id(player_id).strftime("%d.%m.%Y")

    def generate():
        last_update = 99
        
        while True:
            status = "online" if db_manager.get_online_status_by_player_id(player_id) else "offline"
            
            if 10 - last_update <= 0:
                last_update = 0
                death_count = db_manager.get_value_from_unique_object_from_action_table_with_player_id("minecraft:deaths", player_id)
                death_count = death_count if death_count else 0
                last_seen = db_manager.get_last_seen_by_player_id(player_id).strftime("%d.%m.%Y")
                death_time = db_manager.get_value_from_unique_object_from_action_table_with_player_id("minecraft:time_since_death", player_id)
                play_time = db_manager.get_value_from_unique_object_from_action_table_with_player_id("minecraft:play_time", player_id)
                death_time = db_manager.format_time(death_time / 20)
                play_time = db_manager.format_time(play_time / 20)
                
            last_update += 1
            
            data = [uuid, status, death_count, first_seen, last_seen, death_time, play_time]
            yield f"data: {data}\n\n"
            time.sleep(1)  

    return Response(generate(), mimetype='text/event-stream')











if __name__ == '__main__':
    app.run(debug=True)
