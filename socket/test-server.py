import select
import socket
import threading
import time

HEADER = 64
PORT = 9991
SERVER = "0.0.0.0"
ADDR = (SERVER, PORT)
DISCONNECT_MESSAGE = "!DISCONNECT"

server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
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
    heartbeat_received_time = time.time()
    heartbeat_send_time = time.time()
    while connected:
        try:
            # Use select to check if the socket has data to read
            ready_to_read, _, _ = select.select([conn], [], [], 1)
            
            if ready_to_read:
                data_len = conn.recv(HEADER).decode('utf-8').strip()                
                if data_len:
                    data_len = int(data_len)
                    data = conn.recv(data_len).decode('utf-8')
                    
                    if data == DISCONNECT_MESSAGE:
                        connected = False
                    elif data == "!beat":
                        heartbeat_received_time = time.time()
                        print(f"heartbeat received from {addr}")
                    else:
                        # Echo the message back
                        send_msg(data, conn)
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
