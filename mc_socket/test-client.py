import socket
import threading
import time

HEADER = 64
PORT = 9991
SERVER = "t-auer.com"
ADDR = (SERVER, PORT)

client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

def send_msg(msg):
    message = msg.encode('utf-8')
    msg_len = len(message)
    send_len = str(msg_len).encode('utf-8')
    send_len += b' ' * (HEADER - len(send_len))
    #print(send_len)
    client.send(send_len)
    client.send(message)

def receive_msg():
    while True:
        try:
            data_len = client.recv(HEADER).decode('utf-8').strip()
            if data_len:
                data_len = int(data_len)
                data = client.recv(data_len).decode('utf-8')
                print(f"[RECEIVED] {data}")

                if data == "!heartbeat":
                    send_msg("!beat")
                    #print("sent heartbeat")
        except Exception as e:
            print(f"[ERROR] {e}")
            break

def start_client():
    try:
        client.connect(ADDR)
        
        # Start a thread for receiving messages
        recv_thread = threading.Thread(target=receive_msg)
        recv_thread.daemon = True
        recv_thread.start()
        
        while True:
            # Take user input and send messages
            msg = input("Enter message to send: ")
            if msg.lower() == 'exit':
                send_msg("!DISCONNECT")
                break
            send_msg(msg)

    except Exception as e:
        print(f"[ERROR] {e}")
    finally:
        client.close()

if __name__ == "__main__":
    start_client()