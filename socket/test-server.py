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
DISCONNECT_MESSAGE = "!DISCONNECT"

server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
server.bind(ADDR)

def send_msg(msg, client):
    message = msg.encode('utf-8')
    msg_len = len(message)
    send_len = str(msg_len).encode('utf-8')
    send_len += b' ' * (HEADER - len(send_len))
    client.send(send_len)
    client.send(message)

def handle_client_connection(conn, addr):
    print(f"[NEW CONNECTION] {addr} connected.")
    connected = True
    heartbeat_received_time = time.time() - 5
    heartbeat_send_time = time.time() - 5
    auth = False
    server_id = None
    #next_msg_sort = ""
    
    while connected:
        try:
            # Use select to check if the socket has data to read
            ready_to_read, _, _ = select.select([conn], [], [], 1)
            
            if ready_to_read:
                data_len = conn.recv(HEADER).decode('utf-8').strip()                
                if data_len:
                    data_len = int(data_len)
                    data = conn.recv(data_len).decode('utf-8')
                    
                    if data == "!beat":
                        heartbeat_received_time = time.time()
                        print(f"heartbeat received from {addr}")
                        continue
                    elif auth is False:
                        if "!AUTH:" in data:
                            _, value = data.split(":")
                            server = db_manager.get_server_id_by_auth_key(value)
                            if server:
                                server_id = server
                                print(f"CONNECTED to server {server_id}")
                                auth = True
                                continue
                            send_msg("AUTH KEY NOT VALID!", conn)
                            continue
                        send_msg("NO AUTH PROVIDED!", conn)
                        heartbeat_received_time = time.time()
                        continue
                    
                        
                    elif ":" in data:
                        command, value = data.split(":")
                        if command == "!JOIN":
                            if db_manager.update_player_status_from_player_uuid_and_server_id(value, server_id, "online"):
                                send_msg("STATUS UPDATED!", conn)
                            else:
                                send_msg("ERROR: STATUS UPDATE FAILED", conn)
                        elif command == "!QUIT":
                            if db_manager.update_player_status_from_player_uuid_and_server_id(value, server_id, "offline"):
                                send_msg("STATUS UPDATED!", conn)
                            else:
                                send_msg("ERROR: STATUS UPDATE FAILED", conn)
                        
                    elif data == DISCONNECT_MESSAGE:
                        connected = False
                    else:
                        send_msg("ERROR: COMMAND NOT RECOGNIZED", conn)
                    print(f"[{addr}] {data}")
                    
                    
                    
            if time.time() - heartbeat_send_time > 5:
                send_msg("!heartbeat", conn)
                heartbeat_send_time = time.time()
            if time.time() - heartbeat_received_time > 7:
                print(f"[ERROR] {addr} has not sent heartbeat within 7 seconds.")
                connected = False
        except Exception as e:
            print(f"[ERROR] {e}")
            connected = False
    
    conn.close()
    print(f"[DISCONNECTED] {addr} disconnected.")

def start_server():
    server.listen()
    print(f"[LISTENING] Server is listening on {SERVER}:{PORT}")
    while True:
        conn, addr = server.accept()
        thread = threading.Thread(target=handle_client_connection, args=(conn, addr))
        thread.start()
        print(f"[ACTIVE CONNECTIONS] {threading.active_count() - 1}")

print("[STARTING] Server is starting...")
print(ADDR)
start_server()
