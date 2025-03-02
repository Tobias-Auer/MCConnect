import requests

from logger import get_logger

logger = get_logger("minecraftApi")


class Minecraft:
    def __init__(self):
        pass

    def get_player_name_from_uuid(self, uuid):
        """
        Get the username from the Mojang API using the given UUID.

        :param UUID: UUID of the player.
        :return: str: The username of the requested player.
        """
        URL = f"https://playerdb.co/api/player/minecraft/{uuid}"
        try:
            response = requests.get(URL)
            if response.status_code == 200:
                data = response.json()
                user_name = data['data']['player']['username']
                logger.debug("Found username: " + user_name + " for uuid: " + uuid)
            else:
                logger.error(f"Failed to retrieve username for uuid: {uuid}. Status code: {response.status_code}")
                user_name = -1
        except Exception as e:
            logger.error("Error in get_player_name_from_uuid: " + str(e))
            user_name = -1
        return user_name
    
    