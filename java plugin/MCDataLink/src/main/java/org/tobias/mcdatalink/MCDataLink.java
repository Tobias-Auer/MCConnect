package org.tobias.mcdatalink;

import com.google.gson.Gson;
import com.google.gson.JsonObject;
import org.bukkit.Bukkit;
import org.bukkit.OfflinePlayer;
import org.bukkit.entity.Player;
import org.bukkit.plugin.java.JavaPlugin;
import org.bukkit.scheduler.BukkitRunnable;

import java.io.BufferedInputStream;
import java.io.FileReader;
import java.io.IOException;
import java.io.InputStream;
import java.io.OutputStream;
import java.net.Socket;
import java.nio.charset.StandardCharsets;
import java.nio.file.Path;
import java.nio.file.Paths;
import java.util.HashSet;
import java.util.Set;
import java.util.UUID;
import java.util.concurrent.CompletableFuture;
import java.util.concurrent.CountDownLatch;
import java.util.concurrent.Executors;
import java.util.concurrent.ScheduledExecutorService;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.atomic.AtomicBoolean;

public final class MCDataLink extends JavaPlugin {

    private static final int HEADER = 10;
    private static final int PORT = 9991;
    private static final String SERVER_HOST = "10.69.10.232";
    private static final int CONNECT_RETRY_SECONDS = 5;
    private static final int AUTH_TIMEOUT_SECONDS = 5;
    private static final int HEARTBEAT_SEND_INTERVAL_SECONDS = 7;
    private static final int HEARTBEAT_TIMEOUT_SECONDS = 20;

    private volatile Socket socket;
    private volatile OutputStream out;
    private volatile BufferedInputStream in;
    private final ScheduledExecutorService scheduler = Executors.newScheduledThreadPool(2);
    private final AtomicBoolean running = new AtomicBoolean(false);
    private final AtomicBoolean keepPluginEnabled = new AtomicBoolean(true);
    private final Gson gson = new Gson();
    private String key;
    private volatile long lastReceived = 0L;

    @Override
    public void onEnable() {
        saveDefaultConfig();
        key = getConfig().getString("key", "<enter key here>");
        if (key.contains("<")) {
            getLogger().severe("No license key provided to connect to the server. Please update the config.yml file.");
            disablePlugin();
            return;
        }
        running.set(true);
        CompletableFuture.runAsync(this::connectionSupervisor);
        getServer().getPluginManager().registerEvents(new JoinListener(this), this);
        getLogger().info("MCConnect enabled and supervisor started");
    }

    private void connectionSupervisor() {
        while (running.get() && keepPluginEnabled.get()) {
            try {
                establishConnectionWithRetry();
                boolean authed = performAuthHandshake();
                if (!authed) {
                    getLogger().severe("Authentication failed; disabling plugin");
                    disablePlugin();
                    return;
                }
                lastReceived = System.currentTimeMillis();
                startHeartbeatSender();
                startReaderLoop();
                waitForDisconnect();
            } catch (Throwable t) {
                getLogger().severe("Connection supervisor encountered an error: " + t.getMessage());
                safeCloseSocket();
            }

            if (!keepPluginEnabled.get()) break;

            sleepSeconds(CONNECT_RETRY_SECONDS);
            getLogger().info("Attempting reconnect...");
        }
    }

    private void establishConnectionWithRetry() throws InterruptedException {
        while (running.get() && keepPluginEnabled.get()) {
            try {
                socket = new Socket(SERVER_HOST, PORT);
                socket.setReuseAddress(true);
                socket.setSoTimeout(0);
                out = socket.getOutputStream();
                in = new BufferedInputStream(socket.getInputStream());
                getLogger().info("Connected to the server at " + SERVER_HOST + ":" + PORT);
                return;
            } catch (IOException e) {
                getLogger().severe("Connection failed: " + e.getMessage());
                safeCloseSocket();
                sleepSeconds(CONNECT_RETRY_SECONDS);
            }
        }
    }

    private boolean performAuthHandshake() {
        CountDownLatch latch = new CountDownLatch(1);
        final boolean[] authResult = {false};

        CompletableFuture.runAsync(() -> {
            try {
                sendMsg("!AUTH~" + key);
            } catch (IOException e) {
                getLogger().severe("Failed to send AUTH: " + e.getMessage());
                latch.countDown();
                return;
            }

            long deadline = System.currentTimeMillis() + AUTH_TIMEOUT_SECONDS * 1000L;
            while (System.currentTimeMillis() < deadline && socket != null && !socket.isClosed()) {
                try {
                    String msg = readNextMessageNonBlocking(50);
                    if (msg == null) continue;
                    lastReceived = System.currentTimeMillis();
                    if (msg.equals("!heartbeat")) {
                        try {
                            sendMsg("!BEAT");
                        } catch (IOException ignored) {}
                        continue;
                    }
                    if (msg.contains("|")) {
                        String[] parts = msg.split("\\|", 2);
                        String status = parts.length > 1 ? parts[1] : "";
                        if ("100".equals(status)) {
                            authResult[0] = true;
                            latch.countDown();
                            return;
                        } else if ("000".equals(status) || "001".equals(status) || "002".equals(status)) {
                            authResult[0] = false;
                            latch.countDown();
                            return;
                        }
                    }
                } catch (IOException e) {
                    getLogger().severe("IOException during auth handshake: " + e.getMessage());
                    break;
                }
            }
            latch.countDown();
        });

        try {
            boolean completed = latch.await(AUTH_TIMEOUT_SECONDS + 1, TimeUnit.SECONDS);
            if (!completed) {
                getLogger().severe("Authentication timed out");
            }
        } catch (InterruptedException e) {
            Thread.currentThread().interrupt();
        }

        return authResult[0];
    }

    private void startHeartbeatSender() {
        scheduler.scheduleAtFixedRate(() -> {
            try {
                if (socket == null || socket.isClosed()) return;
                sendMsg("!BEAT");
            } catch (IOException e) {
                getLogger().severe("Heartbeat send failed: " + e.getMessage());
            }
        }, HEARTBEAT_SEND_INTERVAL_SECONDS, HEARTBEAT_SEND_INTERVAL_SECONDS, TimeUnit.SECONDS);
    }

    private void startReaderLoop() {
        CompletableFuture.runAsync(() -> {
            try {
                while (running.get() && keepPluginEnabled.get() && socket != null && !socket.isClosed()) {
                    String message = readNextMessageBlocking();
                    if (message == null) {
                        getLogger().severe("Read returned null, assuming disconnect");
                        break;
                    }
                    lastReceived = System.currentTimeMillis();
                    if (message.equals("!heartbeat")) {
                        try {
                            sendMsg("!BEAT");
                        } catch (IOException ignored) {}
                        continue;
                    }
                    if (message.contains("|")) {
                        String[] parts = message.split("\\|", 2);
                        String code = parts.length > 1 ? parts[1] : "";
                        switch (code) {
                            case "100":
                                getLogger().info("Auth confirmed by server");
                                break;
                            case "000":
                                getLogger().severe("Critical error from server. Disconnecting.");
                                keepPluginEnabled.set(false);
                                disablePlugin();
                                return;
                            case "001":
                            case "002":
                                getLogger().severe("License key error: Please check your license key and restart.");
                                keepPluginEnabled.set(false);
                                disablePlugin();
                                return;
                        }
                        continue;
                    }
                    if (message.startsWith("!")) {
                        String[] parts = message.split("~");
                        String command = parts[0];
                        switch (command) {
                            case "!sendAllPlayerStats":
                                sendAllPlayerStats();
                                break;
                            case "!sendPlayerStats":
                                if (parts.length > 1) {
                                    try {
                                        UUID uuid = UUID.fromString(parts[1]);
                                        sendPlayerStats(uuid);
                                    } catch (IllegalArgumentException ignored) {}
                                }
                                break;
                            case "!loginPin":
                                if (parts.length > 2) {
                                    try {
                                        UUID uuid = UUID.fromString(parts[1]);
                                        String pin = parts[2];
                                        Player player = Bukkit.getPlayer(uuid);
                                        if (player != null) {
                                            player.sendMessage("Deine Pin ist: " + pin + "\nGebe sie niemals weiter!");
                                        }
                                    } catch (IllegalArgumentException ignored) {}
                                }
                                break;
                            default:
                                getLogger().info("Unknown command received: " + message);
                        }
                        continue;
                    }
                    getLogger().info("Unhandled message: " + message);
                    if (System.currentTimeMillis() - lastReceived > HEARTBEAT_TIMEOUT_SECONDS * 1000L) {
                        getLogger().severe("No data received for " + HEARTBEAT_TIMEOUT_SECONDS + " seconds; reconnecting");
                        break;
                    }
                }
            } catch (IOException e) {
                getLogger().severe("Reader loop IOException: " + e.getMessage());
            } finally {
                safeCloseSocket();
            }
        });
    }

    private void waitForDisconnect() {
        while (running.get() && keepPluginEnabled.get() && socket != null && !socket.isClosed()) {
            if (System.currentTimeMillis() - lastReceived > HEARTBEAT_TIMEOUT_SECONDS * 1000L) {
                getLogger().severe("Heartbeat timeout detected in supervisor; will reconnect");
                safeCloseSocket();
                return;
            }
            sleepSeconds(1);
        }
    }

    public void sendAllPlayerStats() {
        Set<UUID> allUUIDs = new HashSet<>();
        for (Player player : Bukkit.getOnlinePlayers()) allUUIDs.add(player.getUniqueId());
        for (OfflinePlayer offlinePlayer : Bukkit.getOfflinePlayers()) allUUIDs.add(offlinePlayer.getUniqueId());
        for (UUID uuid : allUUIDs) sendPlayerStats(uuid);
    }

    public void sendPlayerStats(UUID uuid) {
        JsonObject playerStats = readPlayerStats(uuid);
        if (playerStats != null) {
            String jsonData = gson.toJson(playerStats);
            String msg = "!STATS~" + uuid + "|" + jsonData;
            try {
                sendMsg(msg);
                getLogger().info("Sent stats for " + uuid);
            } catch (IOException e) {
                getLogger().severe("Failed to send player stats for " + uuid + ": " + e.getMessage());
                safeCloseSocket();
            }
        } else {
            getLogger().info("No stats for " + uuid);
        }
    }

    private JsonObject readPlayerStats(UUID playerUUID) {
        Path statsPath = Paths.get(getServer().getWorldContainer().getAbsolutePath(), "world", "stats", playerUUID.toString() + ".json");
        getLogger().info("Reading stats from: " + statsPath);
        try (FileReader reader = new FileReader(statsPath.toFile())) {
            return gson.fromJson(reader, JsonObject.class);
        } catch (IOException e) {
            getLogger().severe("Could not read stats file for player " + playerUUID + ": " + e.getMessage());
        }
        return null;
    }

    public synchronized void sendMsg(String msg) throws IOException {
        if (socket == null || socket.isClosed() || out == null) throw new IOException("Socket not connected");
        byte[] payload = msg.getBytes(StandardCharsets.UTF_8);
        String header = String.format("%-" + HEADER + "s", payload.length);
        out.write(header.getBytes(StandardCharsets.UTF_8));
        out.write(payload);
        out.flush();
    }

    private String readNextMessageBlocking() throws IOException {
        byte[] headerBuf = readExactly(HEADER);
        if (headerBuf == null) return null;
        String headerStr = new String(headerBuf, StandardCharsets.UTF_8).trim();
        int length;
        try {
            length = Integer.parseInt(headerStr);
        } catch (NumberFormatException e) {
            throw new IOException("Invalid header length: '" + headerStr + "'");
        }
        if (length <= 0) return "";
        byte[] payload = readExactly(length);
        if (payload == null) return null;
        return new String(payload, StandardCharsets.UTF_8);
    }

    private String readNextMessageNonBlocking(int waitMillis) throws IOException {
        long start = System.currentTimeMillis();
        while (System.currentTimeMillis() - start < waitMillis) {
            if (in == null) return null;
            if (in.available() >= HEADER) {
                return readNextMessageBlocking();
            }
            sleepMillis(10);
        }
        return null;
    }

    private byte[] readExactly(int len) throws IOException {
        byte[] buf = new byte[len];
        int read = 0;
        while (read < len) {
            int r = in.read(buf, read, len - read);
            if (r == -1) {
                return null;
            }
            read += r;
        }
        return buf;
    }

    private void safeCloseSocket() {
        try {
            if (socket != null && !socket.isClosed()) socket.close();
        } catch (IOException ignored) {}
        socket = null;
        out = null;
        in = null;
    }

    private void sleepSeconds(int s) {
        try {
            TimeUnit.SECONDS.sleep(s);
        } catch (InterruptedException e) {
            Thread.currentThread().interrupt();
        }
    }

    private void sleepMillis(long ms) {
        try {
            TimeUnit.MILLISECONDS.sleep(ms);
        } catch (InterruptedException e) {
            Thread.currentThread().interrupt();
        }
    }

    private void disablePlugin() {
        keepPluginEnabled.set(false);
        Bukkit.getScheduler().runTask(this, () -> {
            getLogger().severe("MCConnect shuts down! Read the logs to find out what went wrong. Ensure your server can connect to: " + SERVER_HOST);
            Bukkit.getPluginManager().disablePlugin(this);
        });
    }

    @Override
    public void onDisable() {
        running.set(false);
        keepPluginEnabled.set(false);
        scheduler.shutdownNow();
        safeCloseSocket();
        getLogger().info("MCConnect has been successfully disabled");
    }
}
