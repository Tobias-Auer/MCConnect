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

public final class MCDataLink extends JavaPlugin {

    private static final int HEADER = 64;
    private static final int PORT = 9991;
    private static final String server = "t-auer.com";
    public static PrintWriter pr;
    private static Socket socket;
    private static boolean keepConnected = true;
    private Gson gson;

    @Override
    public void onEnable() {
        getLogger().info("MCConnect has been enabled");
        saveDefaultConfig();
        getServer().getPluginManager().registerEvents(new JoinListener(this), this);
        gson = new Gson();
        try {
            socket = new Socket(server, PORT);
            pr = new PrintWriter(socket.getOutputStream()); //removed ,true
        } catch (IOException e) {
            throw new RuntimeException(e);
        }


        new BukkitRunnable() {
            @Override
            public void run() {
                try {
                    InputStream input = socket.getInputStream();
                    byte[] headerBuffer = new byte[HEADER];

                    while (keepConnected) {
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
        new BukkitRunnable() {
            @Override
            public void run() {
                String key = getConfig().getString("key");
                assert key != null;
                if (key.equals("<enter key here>")) {
                    getLogger().severe("No license key provided to connect to the server. Please update the config.yml file. Or visit https://mc.t-auer.com. Restart the server when you have entered the license key.");
                    keepConnected = false;
                    return;
                }
                sendMsg("!AUTH:"+key, pr);
            }
        }.runTaskAsynchronously(this);
        // Example UUID for demonstration
//            UUID playerUUID = UUID.fromString("4ebe5f6f-c231-4315-9d60-097c48cc6d30");
//
//            // Read player stats
//            JsonObject playerStats = readPlayerStats(playerUUID);
//            if (playerStats != null) {
//                getLogger().info(playerStats.toString());
//
//
//                String jsonData = gson.toJson(playerStats);
//                try {
//                    // Send data to server
//                    sendPostRequest(jsonData);
//                } catch (IOException e) {
//                    getLogger().severe("Failed to send data to server: " + e.getMessage());
//                    e.printStackTrace();
//                }
//            }


//        OperatingSystemMXBean osBean = ManagementFactory.getPlatformMXBean(OperatingSystemMXBean.class);
//
//        Bukkit.getScheduler().runTaskTimerAsynchronously(this, () -> {
//            double cpuLoad = osBean.getSystemCpuLoad() * 100;
//            long freeMemory = osBean.getFreePhysicalMemorySize() / (1024 * 1024);
//            long totalMemory = osBean.getTotalPhysicalMemorySize() / (1024 * 1024);
//            long usedMemory = totalMemory - freeMemory;
//
//            getLogger().info("CPU Usage: " + cpuLoad + "%");
//            getLogger().info("RAM Usage: " + usedMemory + "MB / " + totalMemory + "MB");
//        }, 0L, 20L * 5); // Run every 5 seconds (20 ticks * 5)


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

        getLogger().info("Message length: " + msgLen);
        getLogger().info("Sending length header: " + sendLen);
        pr.print(sendLen);
        pr.flush();

        getLogger().info("Sending message: " + msg);
        pr.print(msg);
        pr.flush();
    }


    @Override
    public void onDisable() {
        getLogger().info("MCConnect has been disabled");
        if (socket != null && !socket.isClosed()) {
            try {
                socket.close();
            } catch (IOException e) {
                getLogger().severe("Error closing socket: " + e.getMessage());
            }
        }
    }
}

