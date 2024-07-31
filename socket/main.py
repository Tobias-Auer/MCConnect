import os
import select
import socket
import sys
import threading
import time
root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'database'))

sys.path.insert(0, root_dir)

from databaseManager import DatabaseManager # type: ignore
from logger import get_logger # type: ignore
from minecraft import Minecraft # type: ignore
logger = get_logger("socket")

db_manager = DatabaseManager()


HEADER = 64
PORT = 9991
SERVER = "0.0.0.0"
ADDR = (SERVER, PORT)

"""
Reserved characters:
!
:
|


Error codes:
000: disconnected
001: The license key is invalid
002: No license key is provided
003: Update player status failed
004: Invalid command
005: Invalid request

Success codes:
100: Auth successful
101: updated player status successfully
"""

def send_msg(msg, client):
    message = msg.encode('utf-8')
    msg_len = len(message)
    send_len = str(msg_len).encode('utf-8')
    send_len += b' ' * (HEADER - len(send_len))
    logger.debug(f"Sending message: '{msg}' to client: {client}")
    client.send(send_len)
    client.send(message)

def execute_command(data, conn, addr, server_id):
    try:
        command, value = data.split(":")
    except ValueError:
        send_msg("error|005", conn)
        return
    if command == "!JOIN":
        if db_manager.update_player_status_from_player_uuid_and_server_id(value, server_id, "online"):
            send_msg("success|101", conn)
        else:
            send_msg("error|003", conn)
    elif command == "!QUIT":
        if db_manager.update_player_status_from_player_uuid_and_server_id(value, server_id, "offline"):
            send_msg("success|101", conn)
        else:
            send_msg("error|003", conn)
    elif command == "!STATS":
        try:
            uuid, stats = value.split("|")
        except ValueError:
            send_msg("error|005", conn)
            return
        print(f"Following stats are provided for uuid: {uuid}:\n\n{stats}\n\n")
    else:
        send_msg("error|004", conn)


def retrieve_all_stats(server_id, conn):
    send_msg("!sendAllPlayerStats", conn)
    

def handle_client_connection(conn, addr):
    logger.info(f"{addr} connected to the socket.")
    connected = True
    heartbeat_received_time = time.time() - 5
    heartbeat_send_time = time.time() - 5
    server_id = None
    unauthorized_beat_count = 0
        
    while connected and unauthorized_beat_count < 5:
        try:
            ready_to_read, _, _ = select.select([conn], [], [], 1)
            
            if ready_to_read:
                data_len = conn.recv(HEADER).decode('utf-8').strip()                
                if data_len:
                    data_len = int(data_len)
                    data = conn.recv(data_len).decode('utf-8')
                    
                    if data == "!BEAT":
                        heartbeat_received_time = time.time()
                        unauthorized_beat_count += 1 if not server_id else 0
                        continue
                    elif not server_id:
                        if "!AUTH:" in data:
                            _, value = data.split(":")
                            server = db_manager.get_server_id_by_auth_key(value)
                            if server:
                                server_id = server
                                logger.info(f"{addr} connected to server {server_id}")
                                send_msg("success|100", conn)
                                retrieve_all_stats(server_id, conn)
                                continue
                            send_msg("error|001", conn)
                            continue
                        send_msg("error|002", conn)
                        heartbeat_received_time = time.time()
                        continue  
                    elif data == "!DISCONNECT":
                        connected = False
                        continue
                    elif ":" in data:
                        execute_command(data, conn, addr, server_id)
                    else:
                        send_msg("error|005", conn)
                    logger.debug(f"[{addr}] {data}")
                    
            current_time = time.time()
            if current_time - heartbeat_send_time > 5:
                send_msg("!heartbeat", conn)
                heartbeat_send_time = current_time
            if current_time - heartbeat_received_time > 7:
                logger.info(f"{addr} has not sent heartbeat within 7 seconds. Disconnecting...")
                connected = False
        except BrokenPipeError:
            logger.error(f"{addr} got a broken pipe error! Disconnecting...")
            connected = False
        except Exception as e:
            logger.error(f"Error occured with client {addr}. Error: {e}")

    conn.close()
    logger.info(f"{addr} disconnected.")

def start_server():
    server.listen()
    logger.debug(f"[LISTENING] Server is listening on {SERVER}:{PORT}")
    while True:
        conn, addr = server.accept()
        thread = threading.Thread(target=handle_client_connection, args=(conn, addr))
        thread.start()
        logger.debug(f"Active connections: {threading.active_count() - 1}")

if __name__ == "__main__":
    logger.info(f"Socket is starting...\nADDR:{ADDR}")
    try:
        server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server.bind(ADDR)
    except Exception as e:
        logger.error(f"Error starting server: {e}")
        sys.exit(1)
    logger.info("Socket established successfully")

    start_server()
