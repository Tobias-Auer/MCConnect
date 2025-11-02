package org.tobias.mcdatalink;

import org.bukkit.World;
import org.bukkit.entity.Player;
import org.bukkit.event.EventHandler;
import org.bukkit.event.Listener;
import org.bukkit.event.player.PlayerJoinEvent;
import org.bukkit.event.player.PlayerQuitEvent;
import org.bukkit.event.world.WorldSaveEvent;

import java.io.IOException;

import static org.bukkit.Bukkit.getLogger;

public class JoinListener implements Listener {
    private final MCDataLink plugin;

    public JoinListener(MCDataLink plugin) {
        this.plugin = plugin;
    }

    @EventHandler
    public void onPlayerJoin(PlayerJoinEvent event) {
        getLogger().info("onPlayerJoin");
        try {
            plugin.sendMsg("!JOIN~" + event.getPlayer().getUniqueId());
        } catch (IOException e) {
            throw new RuntimeException(e);
        }
    }

    @EventHandler
    public void onPlayerQuit(PlayerQuitEvent event) {
        getLogger().info("onPlayerQuit");
        try {
            plugin.sendMsg("!QUIT~" + event.getPlayer().getUniqueId());
        } catch (IOException e) {
            throw new RuntimeException(e);
        }
    }
    @EventHandler
    public void onWorldSave(WorldSaveEvent event) {
        // Construct the message
        String message = "World " + event.getWorld().getName() + " is being saved.";

        // Send message to players in the specific world
        World world = event.getWorld();
        for (Player player : world.getPlayers()) {
            plugin.sendPlayerStats(player.getUniqueId());
        }
    }
}
