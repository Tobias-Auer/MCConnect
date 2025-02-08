package org.tobias.mcdatalink;

import com.google.gson.Gson;
import com.google.gson.JsonObject;
import org.bukkit.Bukkit;
import org.bukkit.OfflinePlayer;
import org.bukkit.entity.Player;
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
import java.util.Arrays;
import java.util.HashSet;
import java.util.Set;
import java.util.UUID;
import java.util.concurrent.CompletableFuture;
import java.util.concurrent.Executors;
import java.util.concurrent.ScheduledExecutorService;
import java.util.concurrent.TimeUnit;

public final class MCDataLink extends JavaPlugin {

    private static final int HEADER = 10;
    private static final int PORT = 9991;
    private static final String server = "localhost";
    public static PrintWriter pr;
    private static Socket socket;
    private static boolean keepConnected = true;
    private final ScheduledExecutorService executorService = Executors.newScheduledThreadPool(1);
    private boolean authComplete = false;
    private Gson gson;

    @Override
    public void onEnable() {
        getLogger().info("MCConnect has been enabled");
        saveDefaultConfig();

        // Versucht asynchron, sich mit dem Server zu verbinden
        CompletableFuture<Void> connectFuture = CompletableFuture.runAsync(this::connectToServer);

        connectFuture.thenRun(() -> {
            // Nach erfolgreicher Verbindung
            CompletableFuture<Void> authFuture = startAuth();
            String key = getConfig().getString("key", "<enter key here>");
            if (key.contains("<")) {
                getLogger().severe("No license key provided to connect to the server. Please update the config.yml file.");
                disablePlugin();
            }

            authFuture.thenRun(() -> {
                getLogger().info("Authentication complete.");
                startSocketListener();
                getServer().getPluginManager().registerEvents(new JoinListener(this), this);

            }).exceptionally(throwable -> {
                getLogger().severe("Authentication failed: " + throwable.getMessage());
                disablePlugin();
                return null;
            });
        }).exceptionally(throwable -> {
            getLogger().severe("Failed to connect to the server: " + throwable.getMessage());
            disablePlugin();
            return null;
        });
    }


    private void connectToServer() {
        try {
            socket = new Socket(server, PORT);
            socket.setReuseAddress(true);
            pr = new PrintWriter(socket.getOutputStream());
            getLogger().info("Connected to the server.");
        } catch (IOException e) {
            getLogger().severe("Connection failed: " + e.getMessage());
            // Wenn die Verbindung nicht funktioniert, versuch in 5 Sekunden erneut
            try {
                Thread.sleep(5000);
            } catch (InterruptedException ignored) {
            }
            connectToServer(); // Rekursiver Versuch, sich erneut zu verbinden
        }
    }





    private void disablePlugin() {
        keepConnected = false;
        Bukkit.getScheduler().runTask(this, () -> {
            // Actual code to disable the plugin
            Bukkit.getPluginManager().disablePlugin(this);
            getLogger().severe("MCConnect shuts down! \n\nThis is because of an issue with the server connection.\nRead the logs above to find out what went wrong. Ensure that your server can connect to: " + server);

        });

         // waits for the plugin to be completely disabled
    }

    private void startSocketListener() {
        getLogger().info("Starting socket listener...");
        new BukkitRunnable() {
            @Override
            public void run() {
                try {
                    InputStream input = socket.getInputStream();
                    byte[] headerBuffer = new byte[HEADER];
                    long lastHeartbeat = System.currentTimeMillis();
                    while (keepConnected) {
                        if ((System.currentTimeMillis() - lastHeartbeat) >= 7000) {
                            getLogger().info("HOST IS DOWN!! Attempting to reconnect...");
                            reconnect();
                            return;
                        }


                        if (input.available() > 0) {
                            int bytesRead = input.read(headerBuffer);
                            if (bytesRead == -1) {
                                throw new IOException("Connection closed by server");
                            }

                            String headerStr = new String(headerBuffer, 0, bytesRead, StandardCharsets.UTF_8).trim();
                            int messageLength = Integer.parseInt(headerStr);
                            byte[] messageBuffer = new byte[messageLength];
                            bytesRead = input.read(messageBuffer);
                            if (bytesRead == -1) {
                                throw new IOException("Connection closed by server");
                            }

                            String message = new String(messageBuffer, 0, bytesRead, StandardCharsets.UTF_8);
                            if (message.equals("!heartbeat")) {
                                sendMsg("!BEAT", pr);
                                lastHeartbeat = System.currentTimeMillis();
                            } else if (message.contains("|")) {
                                String[] parts = message.split("\\|");
                                String status_code = parts[1];
                                switch (status_code) {
                                    case "100":
                                        authComplete = true;
                                        break;
                                    case "000":
                                        getLogger().severe("Critical error... Disconnecting...");
                                        keepConnected = false;
                                        disablePlugin();
                                        return;
                                    case "001":
                                    case "002":
                                        getLogger().severe("License key error: Please check your license key and restart the server or the plugin!");
                                        keepConnected = false;
                                        disablePlugin();
                                        return;
                                }
                            } else if (message.contains("!")) {
                                String[] parts = message.split("~");
                                String command = parts[0];
                                switch (command) {
                                    case "!sendAllPlayerStats":
                                        sendAllPlayerStats();
                                        break;
                                    case "!sendPlayerStats":
                                        String value = parts[1];
                                        sendPlayerStats(UUID.fromString(value));
                                    break;
                                }
                            }
                        }

                    }
                } catch (IOException e) {
                    getLogger().severe("Connection lost: " + e.getMessage());
                    reconnect();
                }
            }
        }.runTaskAsynchronously(this);
    }

    private void sendAllPlayerStats() {
        Set<UUID> allUUIDs = new HashSet<>();

        // Get UUIDs of online players
        for (Player player : Bukkit.getOnlinePlayers()) {
            allUUIDs.add(player.getUniqueId());
        }

        // Get UUIDs of offline players
        for (OfflinePlayer offlinePlayer : Bukkit.getOfflinePlayers()) {
            allUUIDs.add(offlinePlayer.getUniqueId());
        }

        // Process each UUID
        for (UUID uuid : allUUIDs) sendPlayerStats(uuid);
    }

    public void sendPlayerStats(UUID uuid) {
        gson = new Gson();
        // Read player stats
        JsonObject playerStats = readPlayerStats(uuid);
        if (playerStats != null) {
            getLogger().info(playerStats.toString());
            String jsonData = gson.toJson(playerStats);
            String msg = "!STATS~" + uuid + "|" + jsonData;
            getLogger().info("Sending stats from " + uuid + " to the server");
            sendMsg(msg,pr);
        }

    }

    private void reconnect() {
        keepConnected = true; // Attempt to keep reconnecting
        connectToServer();
        CompletableFuture<Void> authFuture = startAuth();
        authFuture.thenRun(this::startSocketListener).exceptionally(throwable -> {
            getLogger().severe("Re-authentication failed: " + throwable.getMessage());
            disablePlugin();
            return null;
        });
    }
    private CompletableFuture<Void> startAuth() {
        getLogger().info("Authenticating on the MCConnect server...");
        String key = getConfig().getString("key");
        sendMsg("!AUTH~" + key, pr);
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
                    Arrays.asList(Thread.currentThread().getStackTrace()).forEach(System.out::println);
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
        getLogger().info("SENDLEN: '" + sendLen + "'");
        pr.print(sendLen);
        pr.flush();

        getLogger().info("Sending message: " + msg);
        pr.print(msg);
        pr.flush();
    }


    @Override
    public void onDisable() {
        keepConnected = false; // Stop any reconnection attempts
        executorService.shutdownNow(); // Stop the executor service
        if (socket != null && !socket.isClosed()) {
            try {
                socket.close();
            } catch (IOException e) {
                getLogger().severe("Error closing socket: " + e.getMessage());
            }
        }
        getLogger().info("MCConnect has been successfully disabled");
    }
}


// TODO: https://chatgpt.com/c/679a7e3e-4474-8010-898f-35892f9eee25