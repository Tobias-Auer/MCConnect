package org.tobias.mcdatalink;

import com.google.gson.Gson;
import com.google.gson.JsonObject;
import org.bukkit.plugin.java.JavaPlugin;
import org.bukkit.scheduler.BukkitRunnable;

import java.io.FileReader;
import java.io.IOException;
import java.io.InputStream;
import java.io.PrintWriter;
import java.net.Socket;
import java.nio.charset.StandardCharsets;
import java.nio.file.Path;
import java.nio.file.Paths;
import java.util.UUID;
import java.util.concurrent.CompletableFuture;
import java.util.concurrent.Executors;
import java.util.concurrent.ScheduledExecutorService;
import java.util.concurrent.TimeUnit;

public final class MCDataLink extends JavaPlugin {

    private static final int HEADER = 64;
    private static final int PORT = 9991;
    private static final String server = "t-auer.com";
    public static PrintWriter pr;
    private static Socket socket;
    private static boolean keepConnected = true;
    private boolean authComplete = false;
    private final ScheduledExecutorService executorService = Executors.newScheduledThreadPool(1);

    @Override
    public void onEnable() {
        getLogger().info("MCConnect has been enabled");
        saveDefaultConfig();
        try {
            socket = new Socket(server, PORT);
            pr = new PrintWriter(socket.getOutputStream());
        } catch (IOException e) {
            getLogger().severe("ERROR: " + e);
            disablePlugin();
        }

        CompletableFuture<Void> authFuture = startAuth();
        checkConnection();

        authFuture.thenRun(() -> {
            getLogger().info("Authentication complete.");
            startSocketListener();
            getServer().getPluginManager().registerEvents(new JoinListener(this), this);

            // ...

        }).exceptionally(throwable -> {
            getLogger().severe("Authentication failed: " + throwable.getMessage());
            disablePlugin();
            return null;
        });







    }

    private void disablePlugin() {
        keepConnected = false;
        getLogger().severe("MCConnect shuts down! \n\nThis is because of an issue with the server connection.\nPlease ensure that you have a valid license key and that your server can connect to the following server: " + server);
        this.getServer().getPluginManager().disablePlugin(this);
        while (true) {} // waits for the plugin to be completely disabled
    }

    private void checkConnection() {
        String key = getConfig().getString("key", "<enter key here>");
        if (key.equals("<enter key here>")) {
            getLogger().severe("No license key provided to connect to the server. Please update the config.yml file. Or visit https://mc.t-auer.com. Restart the server when you have entered the license key.");
            disablePlugin();
        }
        getLogger().info("Authenticating on the MCConnect server...");
        sendMsg("!AUTH:" + key, pr);
    }

    private void startSocketListener() {
        getLogger().info("Starting socket listener...");
        new BukkitRunnable() {
            @Override
            public void run() {
                try {
                    InputStream input = socket.getInputStream();
                    byte[] headerBuffer = new byte[HEADER];

                    while (keepConnected) {
                        getLogger().info("..");
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
                            sendMsg("!BEAT", pr);
                        } else if (message.contains("|")) {
                            String[] parts = message.split("\\|");
                            String status_code = parts[1];
                            if (status_code.equals("100")) {
                                authComplete = true;
                            }

                            else if (status_code.equals("000")) {
                                getLogger().severe("Critical error... Disconnecting...\nTo reconnect restart the server or the plugin\nStatus Code: 000");
                                keepConnected = false;
                                disablePlugin();
                            } else if (status_code.equals("001") || status_code.equals("002")) {
                                getLogger().severe("License key error: Please check your license key and restart the server or the plugin!\nStatus code:" + status_code);
                                keepConnected = false;
                                disablePlugin();
                            }
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
        }.runTaskAsynchronously(this);
    }

    private CompletableFuture<Void> startAuth() {
        CompletableFuture<Void> future = new CompletableFuture<>();

        // Schedule timeout task to complete the future with an exception if not completed in time
        executorService.schedule(() -> {
            if (!future.isDone()) {
                future.completeExceptionally(new RuntimeException("Authentication timed out"));
            }
        }, 5, TimeUnit.SECONDS);

        new BukkitRunnable() {
            @Override
            public void run() {
                try {
                    InputStream input = socket.getInputStream();
                    byte[] headerBuffer = new byte[HEADER];

                    while (!future.isDone()) {
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
                        if (message.equals("!heartbeat")) {
                            sendMsg("!BEAT", pr);
                        } else if (message.contains("|")) {
                            String[] parts = message.split("\\|");
                            String status_code = parts[1];
                            if (status_code.equals("100")) {
                                future.complete(null); // Successfully authenticated
                                break;
                            } else if (status_code.equals("000") || status_code.equals("001") || status_code.equals("002")) {
                                future.completeExceptionally(new RuntimeException("Authentication failed with status code: " + status_code));
                                break;
                            }
                        }
                    }
                } catch (IOException e) {
                    future.completeExceptionally(new RuntimeException("IOException in socket listener", e));
                }
            }
        }.runTaskAsynchronously(this);

        return future;
    }


    private JsonObject readPlayerStats(UUID playerUUID) {
        // Correct path to the stats file
        Path statsPath = Paths.get(getServer().getWorldContainer().getAbsolutePath(), "world", "stats", playerUUID.toString() + ".json");

        // Log the path being used
        getLogger().info("Reading stats from: " + statsPath);

        try (FileReader reader = new FileReader(statsPath.toFile())) {
            Gson gson = new Gson();
            return gson.fromJson(reader, JsonObject.class);
        } catch (IOException e) {
            getLogger().severe("Could not read stats file for player " + playerUUID);
            e.printStackTrace();
        }
        return null;
    }


    public void sendMsg(String msg, PrintWriter pr) {
        byte[] message = msg.getBytes(StandardCharsets.UTF_8);
        int msgLen = message.length;
        String sendLen = String.format("%-" + HEADER + "s", msgLen);
        pr.print(sendLen);
        pr.flush();

        getLogger().info("Sending message: " + msg);
        pr.print(msg);
        pr.flush();
    }


    @Override
    public void onDisable() {
        getLogger().info("MCConnect has been successfully disabled");
        if (socket != null && !socket.isClosed()) {
            try {
                socket.close();
            } catch (IOException e) {
                getLogger().severe("Error closing socket: " + e.getMessage());
            }
        }
    }
}

