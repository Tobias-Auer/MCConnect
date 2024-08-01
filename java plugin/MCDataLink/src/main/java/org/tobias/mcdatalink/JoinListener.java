package org.tobias.mcdatalink;

import org.bukkit.event.EventHandler;
import org.bukkit.event.Listener;
import org.bukkit.event.player.PlayerJoinEvent;
import org.bukkit.event.player.PlayerQuitEvent;

import static org.bukkit.Bukkit.getLogger;

public class JoinListener implements Listener {
    private final MCDataLink plugin;

    public JoinListener(MCDataLink plugin) {
        this.plugin = plugin;
    }

    @EventHandler
    public void onPlayerJoin(PlayerJoinEvent event) {
        getLogger().info("onPlayerJoin");
        plugin.sendMsg("!JOIN~" + event.getPlayer().getUniqueId(), MCDataLink.pr);
    }

    @EventHandler
    public void onPlayerQuit(PlayerQuitEvent event) {
        getLogger().info("onPlayerQuit");
        plugin.sendMsg("!QUIT~" + event.getPlayer().getUniqueId(), MCDataLink.pr);
    }
}
