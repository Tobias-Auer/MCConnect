package socket;

import java.io.*;
import java.net.*;
import java.nio.charset.StandardCharsets;
import java.util.Scanner;


public class Client extends Thread {
    private static final int HEADER = 64;
    private static final int PORT = 9991;
    private static final String server = "127.0.1.1";
    private static Socket socket;
    private static PrintWriter pr;

    public static void main(String[] args) {
        try {
            socket = new Socket(server, PORT);
            pr = new PrintWriter(socket.getOutputStream());
            Client receiver = new Client(); // USE BUKKIT ASYNC LATER
                        receiver.start();
            sendMsg("hello world", pr);

            

            Scanner scanner = new Scanner(System.in);
            while (true) {
                System.out.println("Message: ");
                String message = scanner.nextLine();
                sendMsg(message, pr);
            }

        } catch (IOException e) {
            System.err.println("Socket Error: " + e.getMessage());
        }
    }

    // String utf8EncodedString = new String(bytes, StandardCharsets.UTF_8);
    public static void sendMsg(String msg, PrintWriter pr) {
        int msgLen = msg.length();
        System.out.println("Sending message: " + msg);
        pr.print(msgLen); 
        pr.flush();
        pr.print(msg);
        pr.flush();
    }

    @Override
        public void run() {
            try {
                InputStream input = socket.getInputStream();
                byte[] headerBuffer = new byte[HEADER];

                while (true) {
                    // Read the message length header
                    int bytesRead = input.read(headerBuffer);
                    if (bytesRead == -1) {
                        break; // End of stream
                    }

                    String headerStr = new String(headerBuffer, 0, bytesRead, StandardCharsets.UTF_8).trim();
                    int messageLength = Integer.parseInt(headerStr);
                    byte[] messageBuffer = new byte[messageLength];
                    bytesRead = input.read(messageBuffer);
                    if (bytesRead == -1) {
                        break;
                    }

                    String message = new String(messageBuffer, 0, bytesRead, StandardCharsets.UTF_8);
                    System.out.println("Received message: " + message);
                    if (message.equals("!heartbeat")) {
                        sendMsg("!beat", pr);
                    }
                }
            } catch (IOException e) {
                e.printStackTrace();
            } finally {
                try {
                    socket.close();
                } catch (IOException e) {
                    e.printStackTrace();
                }
            }
        }
}
