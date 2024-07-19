import ast
from datetime import datetime, timedelta
import json
import re
from tarfile import data_filter
from tkinter import E
import psycopg2

from logger import get_logger
import logging
from minecraft import Minecraft

logger = get_logger("databaseManager",logging.INFO)
minecraft = Minecraft()

def read_sql_file(filepath):
    with open(filepath, "r") as file:
        return file.read()


class DatabaseManager:
    TABLE_COUNT = 7
    LOWEST_WEB_ACCESS_LEVEL = 2

    def __init__(self):
        logger.debug("Initializing database manager")
        self.conn = psycopg2.connect(
            database="mcConnect-TestDB-1",
            host="localhost",
            user="admin",
            password="admin",
            port="5432",
        )
        logger.info("Established connection to the database")
        self.cursor = self.conn.cursor()

        if not self.check_database_integrity():
            self.init_tables()
    ################################ INIT FUNCTIONS ###################################
    def init_tables(self):
        """
        WARNING: This function wipes the whole database.

        This function drops the existing database schema and recreates it by executing the SQL query from the initDB.sql file.
        It then commits the changes and prints a success message.

        Returns:
        bool: True if the tables are successfully initiated, False otherwise.

        Raises:
        Exception: If an error occurs while executing the SQL query or committing the changes.
        """
        logger.debug("create_tables is called")
        logger.debug("dropping existing tables")
        self.drop_db()
        query = read_sql_file("database/queries/initDB.sql")
        logger.debug(f"executing SQL query: {query}")
        try:
            self.cursor.execute(query)
            self.conn.commit()
            logger.info("Tables initiated successfully")
        except Exception as e:
            logger.error(f"Error creating tables: {e}")
            return False
        return True

    def init_new_server(self, subdomain, license_type, owner_name=None, mc_server_domain=None):
            """
            Registers a new server in the database.

            Parameters:
            server_id (str): The unique identifier for the server.
            server_name (str): The name of the server.
            owner_name (str, optional): The name of the server owner. Defaults to None.
            mc_server_domain (str, optional): The domain of the Minecraft server. Defaults to None.

            Returns:
            bool: True if the server is successfully registered, False otherwise.

            Raises:
            Exception: If an error occurs while executing the SQL query or committing the changes.
            """
            logger.debug("register_new_server is called")
            query = """
                INSERT INTO server (subdomain, license_type, owner_name, mc_server_domain)
                VALUES (%s, %s, %s, %s)
                    """
            logger.debug(f"executing SQL query: {query}")
            data = (subdomain, license_type, owner_name, mc_server_domain)
            logger.debug(f"with follwing data: {data}")
            try:
                self.cursor.execute(query, data)
                self.conn.commit()
                logger.info(f'Registered new server: "{subdomain}"')
            except Exception as e:
                logger.critical(
                    f'Failed to register new server: "{subdomain}". Error: {e}'
                )
                return False
            return True

    def init_player_server_info_table(self, server_id, player_uuid):
        logger.debug("init_player_server_info_table is called")
        web_access_permissions = self.LOWEST_WEB_ACCESS_LEVEL
        query = "INSERT INTO player_server_info (id, server_id, player_uuid, online, first_seen, last_seen, web_access_permissions) VALUES (uuid_generate_v4(), %s, %s, true, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, %s)"
        logger.debug(f"executing SQL query: {query}")#
        data = (server_id, player_uuid, web_access_permissions)
        logger.debug(f"with following data: {data}")
        try:
            self.cursor.execute(query, data)
            self.conn.commit()
            logger.info(f'Initialized player server info for server: "{server_id}" and player: "{player_uuid}"')
        except Exception as e:
            logger.error(f'Failed to initialize player server info for server: "{server_id}" and player: "{player_uuid}". Error: {e}')
            return False
        return True
    
    def init_prefix_table(self, player_id):
        logger.debug("init_prefix_table is called")
        query = "INSERT INTO player_prefixes (player_id) VALUES (%s)"
        data = (player_id,)
        try:
            self.cursor.execute(query, data)
            self.conn.commit()
            logger.info(f'Initialized prefix for player: "{player_id}"')
        except Exception as e:
            logger.error(f'Failed to initialize prefix for player: "{player_id}". Error: {e}')
            return False
        return True

    def init_item_blocks_lookup_table(self, block_list_file_path):
        with open(block_list_file_path, 'r') as block_list_file:
            json_data = json.load(block_list_file)
        
        names = [block["name"] for block in json_data]
            
        query = "INSERT INTO block_lookup (blocks) VALUES (%s)"
        try:
            self.cursor.executemany(query, [(element,) for element in names])
            logger.info(f"Inserted {self.cursor.rowcount} rows successfully.")
            self.conn.commit()
        except Exception as e:
            logger.error(f'Failed to insert rows into blocks_lookup table. Error: {e}')
            return False
            
    def init_item_items_lookup_table(self, item_list_file_path):
        with open(item_list_file_path, 'r') as item_list_file:
            json_data = json.load(item_list_file)
        
        names = [item["id"] for item in json_data]
            
        query = """ INSERT INTO item_lookup (items)
                    SELECT %s
                    WHERE NOT EXISTS (
                    SELECT 1 FROM block_lookup WHERE "blocks" = %s
                    );
                """
        try:
            tools_substrings = ["axe", "shovel", "hoe", "sword", "pickaxe", "shield", "flint_and_steel"]
            armor_substrings = ["boots", "leggings", "chestplate", "helmet"]
            self.cursor.executemany(query, [(element, element) for element in names if not any(substring in element for substring in tools_substrings) and not any(substring in element for substring in armor_substrings)])
            logger.info(f"Inserted {self.cursor.rowcount} rows successfully.")
            self.conn.commit()

        except Exception as e:
            logger.error(f'Failed to insert rows into item_lookup table. Error: {e}')
            return False

    ################################ CHECK FUNCTIONS ##################################
    def check_database_integrity(self):
        """
        Checks the integrity of the database by comparing the number of tables with the expected count.

        Parameters:
        self (DatabaseManager): The instance of the DatabaseManager class.

        Returns:
        bool: True if the database integrity check passes, False otherwise.
        """
        logger.debug("check_database_integrity is called")
        logger.debug(f"Expected table count: {self.TABLE_COUNT}")
        actual_table_count = len(self.get_all_tables())
        if actual_table_count != self.TABLE_COUNT:
            logger.critical("Database integrity check failed.")
            logger.debug(f"Actual table count: {actual_table_count}")
            return False
        else:
            logger.info("Database integrity check passed.")
        return True
    
    def check_for_ban_entry(self, player_id):
        logger.debug("check_for_ban_entry is called")
        query = "SELECT * FROM banned_players WHERE player_id = %s"
        data = (player_id,)
        logger.debug(f"executing SQL query: {query}")
        logger.debug(f"with following data: {data}")
        try:
            self.cursor.execute(query, data)
            ban_entry = self.cursor.fetchone()
            if ban_entry:
                logger.info(f'Player: "{player_id}" is currently banned.')
                return True
            else:
                logger.info(f'Player: "{player_id}" is currently not banned.')
                return False
        except Exception as e:
            logger.error(f'Failed to check for ban entry for player: "{player_id}". Error: {e}')
            return False
        
        
    ################################ ADD FUNCTIONS ####################################
    def add_new_player(self, player_uuid):
        """
        Registers a new player in the database.

        Parameters:
        player_uuid (str): The unique identifier for the player.

        Returns:
        bool: True if the player is successfully registered, False otherwise.

        Raises:
        Exception: If an error occurs while executing the SQL query or committing the changes.
        """
        logger.debug("add_new_player is called")
        logger.debug(f'Attempting to register new player: "{player_uuid}"')
        query = "INSERT INTO player (uuid, name) VALUES (%s, %s)"
        logger.debug("searching playername for uuid: {player_uuid}")
        logger.debug(f"executing SQL query: {query}")
        player_name = minecraft.get_player_name_from_uuid(player_uuid)
        data = (player_uuid, player_name)
        logger.debug(f"with following data: {data}")
        logger.debug(f'Found playername: "{player_name}" for uuid: {player_uuid}')
        try:
            self.cursor.execute(query, data)
            self.conn.commit()
            logger.info(f'Registered new player: "{player_uuid}" with name: "{player_name}")')
        except Exception as e:
            logger.error(f'Failed to register new player: "{player_uuid}". Error: {e}')
            return False
        return True
    
    def add_login_entry(self, player_id, pin):
        logger.debug("add_login_entry is called")
        query = """INSERT INTO login (player_id, pin, timestamp) VALUES (%s, %s, CURRENT_TIMESTAMP)"""
        data = (player_id, pin)
        logger.debug(f"executing SQL query: {query}")
        logger.debug(f"with following data: {data}")
        try:
            self.cursor.execute(query, data)
            self.conn.commit()
            logger.info(f'Added login entry for player: "{player_id}" with pin: "{pin}"')
        except Exception as e:
            logger.error(f'Failed to add login entry for player: "{player_id}". Error: {e}')
            return False
        return True
    ################################ UPDATE FUNCTIONS #################################
    def update_prefix(self, player_id, prefix=None, password=None):
        logger.debug("update_prefix is called")
        query = """ UPDATE player_prefixes
                    SET prefix = %s, password = %s
                    WHERE player_id = %s;"""
        data = (prefix, password, player_id)
        logger.debug(f"executing SQL query: {query}")
        logger.debug(f"with following data: {data}")
        try:
            self.cursor.execute(query, data)
            self.conn.commit()
            logger.info(f'Updated prefix for player: "{player_id}" to: "{prefix}" with password: "{password}"')
        except Exception as e:
            logger.error(f'Failed to update prefix for player: "{player_id}". Error: {e}')
            return False
        return True

    def join_prefix(self, player_id, prefix_id):
        logger.debug("join_prefix is called")
        query = """ UPDATE player_prefixes
                    SET members = CASE
                        WHEN array_position(members, %s) IS NULL THEN array_append(members, %s)
                        ELSE members
                    END
                    WHERE id = '%s';"""
        data = (player_id, player_id, prefix_id)
        logger.debug(f"executing SQL query: {query}")
        logger.debug(f"with following data: {data}")
        try:
            self.cursor.execute(query, data)
            self.conn.commit()
            logger.info(f'Joined prefix for player: "{player_id}" with prefix: "{prefix_id}"')
        except Exception as e:
            logger.error(f'Failed to join prefix for player: "{player_id}" with prefix: "{prefix_id}". Error: {e}')
            return False
        return True
        
    def leave_prefix(self, player_id, prefix_id):
        logger.debug("leave_prefix is called")

        query = """ UPDATE player_prefixes
                SET members = array_remove(members, %s)
                WHERE id = %s;"""
        data = (player_id, prefix_id)
        logger.debug(f"executing SQL query: {query}")
        logger.debug(f"with following data: {data}")
        try:
            self.cursor.execute(query, data)
            self.conn.commit()
            logger.info(f'{player_id} left prefix: "{prefix_id}"')
        except Exception as e:
            logger.error(f'{player_id} failed to leave prefix: "{prefix_id}". Error: {e}')
            return False
        return True
        
    def ban_player(self, banned_player_id, admin_player_id, reason, end):
        logger.debug(f"ban_player is called")
        query = """ INSERT INTO banned_players (player_id, admin, ban_reason, ban_start, ban_end)
                    VALUES (%s, %s, %s, CURRENT_TIMESTAMP, TO_TIMESTAMP(%s, 'YYYY-MM-DD HH24:MI:SS'));"""
        data = (banned_player_id, admin_player_id, reason, end)
        logger.debug(f"executing SQL query: {query}")
        logger.debug(f"with following data: {data}")
        try:
            self.cursor.execute(query, data)
            self.conn.commit()
            logger.info(f'Banned player: "{banned_player_id}" by admin: "{admin_player_id}" with reason: "{reason}" until: "{end}"')

        except Exception as e:
            logger.error(f'Failed to ban player: "{banned_player_id}" by admin: "{admin_player_id}" with reason: "{reason}" until: "{end}" Error: {e}')
            return False
        return True
        
    def unban_player(self, banned_player_id, admin_player_id):
        logger.debug(f"unban_player is called")
        query = """ DELETE FROM banned_players WHERE player_id = %s;"""
        data = (banned_player_id,)
        logger.debug(f"executing SQL query: {query}")
        logger.debug(f"with following data: {data}")
        try:
            self.cursor.execute(query, data)
            self.conn.commit()
            logger.info(f'Unbanned player: "{banned_player_id}" by admin: "{admin_player_id}"')
        except Exception as e:
            logger.error(f'Failed to unban player: "{banned_player_id}" by admin: "{admin_player_id}". Error: {e}')
            return False
        return True

    def update_player_stats(self, player_id, stats):
        logger.debug("update_player_stats is called")
        items = self.split_items_from_json(stats)
        query = """ INSERT INTO actions (player_id, object, category, value)
                    VALUES (%s, %s, %s, %s)
                    ON CONFLICT (player_id, object, category)
                    DO UPDATE SET
                    "value" = EXCLUDED.value;"""
        for item in items:
            data = (player_id, *data)
            logger.debug(f"executing SQL query: {query}")
            logger.debug(f"with following data: {data}")
            try:
                self.cursor.execute(query, data)
                self.conn.commit()
                logger.info(f'Updated player: "{player_id}" stats with items: {stats}')
            except Exception as e:
                logger.error(f'Failed to update player: "{player_id}" stats with items: {stats}. Error: {e}')
                return False
            return True
    ################################ DELETE FUNCTIONS #################################
    def drop_db(self):
        """
        WARNING: This function wipes the whole database. Only run on critical errors.

        Drops the public schema and recreates it. This is used to reset the database.

        Parameters:
        None

        Returns:
        None
        """
        logger.debug("drop_db is called")
        query = "DROP SCHEMA public CASCADE;CREATE SCHEMA public;"
        logger.debug(f"executing SQL query: {query}")
        self.cursor.execute(query)
        logger.warning("Database dropped")
        self.conn.commit()

    def delete_server(self, server_id):
        """
        Deletes a server from the database based on the provided server ID.

        Parameters:
        server_id (int): The unique identifier of the server to be deleted.

        Returns:
        None

        Raises:
        Exception: If an error occurs while executing the SQL query or committing the changes.
        """
        logger.debug("delete_server is called")
        query = "DELETE FROM server WHERE server_id = %s"
        logger.debug(f"executing SQL query: {query}")
        data = (server_id,)
        logger.debug(f"with following data: {data}")

        try:
            self.cursor.execute(query, data)
            self.conn.commit()
            logger.info(f'Deleted server with id: "{server_id}"')
        except Exception as e:
            logger.critical(f'Failed to delete server with id: "{server_id}". Error: {e}')
            return False
        return True

    def delete_login_entry(self, player_id):
        logger.debug("delete_login_entry is called")
        query = "DELETE FROM login WHERE player_id = %s"
        data = (player_id,)
        logger.debug(f"executing SQL query: {query}")
        logger.debug(f"with following data: {data}")
        try:
            self.cursor.execute(query, data)
            self.conn.commit()
            logger.info(f'Deleted login entry for player: "{player_id}"')
        except Exception as e:
            logger.critical(f'Failed to delete login entry for player: "{player_id}". Error: {e}')
            return False
        return True

    ################################ GET FUNCTIONS ####################################
    def get_all_tables(self):
        """
        Retrieves all table names from the connected database.

        Parameters:
        None

        Returns:
        tables (list): A list of tuples, where each tuple contains one table name.
        """
        logger.debug("get_all_tables is called")
        query = "SELECT tablename FROM pg_catalog.pg_tables WHERE schemaname NOT IN ('pg_catalog', 'information_schema');"
        logger.debug(f"executing SQL query: {query}")
        self.cursor.execute(query)
        tables = self.cursor.fetchall()
        logger.debug(f"Table names retrieved: {tables}")
        return tables

    def get_player_id_from_player_uuid_and_server_id(self, player_uuid, server_id):
        logger.debug("get_player_id_from_uuid_and_server is called")
        query = "SELECT id FROM player_server_info WHERE player_uuid = %s AND server_id = %s"
        logger.debug(f"executing SQL query: {query}")
        data = (player_uuid, server_id)
        logger.debug(f"with following data: {data}")
        try:
            self.cursor.execute(query, data)
            result = self.cursor.fetchone()
            if result is None:
                logger.warning(f'No player found for uuid: "{player_uuid}" and server: "{server_id}"')
                return None
            player_id = result[0]
            logger.info(f'Found player id: "{player_id}" for uuid: "{player_uuid}" and server: "{server_id}"')
            return player_id
        except Exception as e:
            logger.error(f'Failed to get player id for uuid: "{player_uuid}" and server: "{server_id}". Error: {e}')
            return None
        
    def get_server_id_from_subdomain(self, subdomain):
        logger.debug("get_server_id_from_subdomain is called")
        query = "SELECT server_id FROM server WHERE subdomain = %s"
        logger.debug(f"executing SQL query: {query}")
        data = (subdomain,)
        logger.debug(f"with following data: {data}")
        try:
            self.cursor.execute(query, data)
            result = self.cursor.fetchone()
            if result is None:
                logger.warning(f'No server found for subdomain: "{subdomain}"')
                return None
            server_id = result[0]
            logger.info(f'Found server id: "{server_id}" for subdomain: "{subdomain}"')
            return server_id
        except Exception as e:
            logger.error(f'Failed to get server id for subdomain: "{subdomain}". Error: {e}')
            return None

    def get_prefix_id_from_player_id(self, player_id):
        logger.debug("get_prefix_id_from_player_and_server_id is called")
        query = "SELECT id FROM player_prefixes WHERE player_id = %s ;"
        data = (player_id,)
        logger.debug(f"executing SQL query: {query}")
        logger.debug(f"with following data: {data}")
        try:
            self.cursor.execute(query, data)
            result = self.cursor.fetchone()
            logger.info(f'Found prefix id: "{result[0]}" for player: "{player_id}"')
        except Exception as e:
            logger.error(f'Failed to get prefix id for player: "{player_id}". Error: {e}')
            return None
        return result[0]

    def get_prefix_id_from_player_id(self, player_id):
        logger.debug(f"getting prefix_id_from_player_id is called")
        query = "SELECT id FROM player_prefixes WHERE player_id = %s ;"
        data = (player_id,)
        try:
            self.cursor.execute(query, data)
            result = self.cursor.fetchone()
            logger.info(f'Found prefix id: "{result[0]}" for player: "{player_id}"')
        except Exception as e:
            logger.error(f'Failed to get prefix id for player: "{player_id}". Error: {e}')
            return None
        return result[0]
        
    def get_prefix_name_from_prefix_id(self, prefix_id):
        logger.debug(f"getting prefix_name_from_prefix_id is called")
        query = "SELECT prefix FROM player_prefixes WHERE id = %s ;"
        data = (prefix_id,)
        logger.debug(f"executing SQL query: {query}")
        logger.debug(f"with following data: {data}")
        try:
            self.cursor.execute(query, data)
            result = self.cursor.fetchone()
            logger.info(f'Found prefix name: "{result[0]}" for prefix id: "{prefix_id}"')
        except Exception as e:
            logger.error(f'Failed to get prefix name for prefix id: "{prefix_id}". Error: {e}')
            return None
        return result[0]
    
    def get_members_from_prefix_id(self, prefix_id):
        logger.debug(f"getting members_from_prefix_id is called")
        query = "SELECT members FROM player_prefixes WHERE id = %s;"
        data = (prefix_id,)
        logger.debug(f"executing SQL query: {query}")
        logger.debug(f"with following data: {data}")
        try:
            self.cursor.execute(query, data)
            result = self.cursor.fetchall()
            logger.info(f'Found players for prefix id: "{prefix_id}"')
        except Exception as e:
            logger.error(f'Failed to get players for prefix id: "{prefix_id}". Error: {e}')
            return None
        return re.findall(r'[a-zA-Z0-9-]+', result[0][0])

    def get_ban_info(self, player_id):
        logger.debug(f"getting ban_info is called")
        query = "SELECT * FROM banned_players WHERE player_id = %s;"
        data = (player_id,)
        logger.debug(f"executing SQL query: {query}")
        logger.debug(f"with following data: {data}")
        try:
            self.cursor.execute(query, data)
            result = self.cursor.fetchone()
            logger.info(f'Found ban info for player: "{player_id}"')
        except Exception as e:
            logger.error(f'Failed to get ban info for player: "{player_id}". Error: {e}')
            return None
        logger.info(f"Ban info: {result}")
        return result

    def get_login_attempt_validity(self, player_id, pin):
        logger.debug(f"get_login_attempt_validity called for player_id: {player_id}")
        
        query = "SELECT pin, timestamp FROM login WHERE player_id = %s;"
        data = (player_id,)
        logger.debug(f"Executing SQL query: {query} with data: {data}")
        
        try:
            self.cursor.execute(query, data)
            result = self.cursor.fetchone()
            
            if not result:
                logger.debug(f"No entry found for player_id: {player_id}")

                return [False, "no entry found in the database"]
            
            stored_pin, saved_timestamp = result
            
            # Verify PIN
            if pin != stored_pin:
                logger.debug(f"PIN is wrong for player_id: {player_id}")
                return [False, "wrong pin provided"]
            
            # Verify timestamp validity
            current_timestamp = datetime.now()
            time_difference = current_timestamp - saved_timestamp
            
            # Check if saved timestamp is older than 5 minutes from current timestamp
            if time_difference > timedelta(minutes=5):
                logger.debug(f"Saved timestamp is older than 5 minutes for player_id: {player_id}")
                self.delete_login_entry(player_id)
                return [False, "timeout reached"]
            
            logger.debug(f"Login attempt for player_id: {player_id} is valid")
            return [True,]
        
        except Exception as e:
            logger.error(f'Failed to verify login attempt for player_id: {player_id}. Error: {e}')
            return [False, "database error occurred"]
    
    
    ################################ helper functions################################
    
    def split_items_from_json(self, items):
        '''
        Return: [[object/item, category, value],]
        '''
        return_list = []
        stats_categorys = ["minecraft:broken", "minecraft:mined","minecraft:dropped","minecraft:used","minecraft:killed","minecraft:crafted","minecraft:killed_by","minecraft:custom","minecraft:picked_up"]
        all_data = json.loads(items)["stats"]
        for category in stats_categorys:
            data = all_data[category]
            # if category == "minecraft:broken":
            for item_name, item_data in data.items():
                db_category = self.get_db_category_from_item_and_json_category(item_name, category)
                return_list.append([item_name, db_category, item_data])
        return return_list
                    
    def get_db_category_from_item_and_json_category(self, item, category):
        '''
        categorys = ["minecraft:broken", "minecraft:mined","minecraft:dropped","minecraft:used","minecraft:killed","minecraft:killed_by","minecraft:crafted","minecraft:picked_up","minecraft:custom"]

        0: broken tool
        1: broken armor

        2: mined block

        3: dropped block
        4: dropped items
        5: dropped armor
        6: dropped tools

        7: used blocks
        8: used items
        9: used armor
        10: used tools

        11: killed mobs

        12: killed by

        13: crafted blocks
        14: crafted items
        15: crafted tools
        16: crafted armor

        17: picked up blocks
        18: picked up items
        19: picked up armor
        20: picked up tools

        21: custom
        Return: database category name
        '''
        tools_substrings = ["axe", "shovel", "hoe", "sword", "pickaxe", "shield", "flint_and_steel"]
        armor_substrings = ["boots", "leggings", "chestplate", "helmet"]
        recognized_item_group = ""

        if any(substring in item for substring in tools_substrings):
            recognized_item_group = "tool"
        elif any(substring in item for substring in armor_substrings):
            recognized_item_group = "armor"
        elif self.check_item_for_block(item):
            recognized_item_group = "block"
        elif self.check_item_for_item(item):
            recognized_item_group = "item"
        else:
            recognized_item_group = "unknown"

        if recognized_item_group == "tool":
            if category == "minecraft:broken":
                return 0
            elif category == "minecraft:dropped":
                return 6
            elif category == "minecraft:used":
                return 10
            elif category == "minecraft:crafted":
                return 15
            elif category == "minecraft:picked_up":
                return 20

        elif recognized_item_group == "armor":
            if category == "minecraft:broken":
                return 1
            elif category == "minecraft:dropped":
                return 5
            elif category == "minecraft:used":
                return 9
            elif category == "minecraft:crafted":
                return 16
            elif category == "minecraft:picked_up":
                return 19

        elif recognized_item_group == "block":
            if category == "minecraft:mined":
                return 2
            elif category == "minecraft:dropped":
                return 3
            elif category == "minecraft:used":
                return 7
            elif category == "minecraft:crafted":
                return 13
            elif category == "minecraft:picked_up":
                return 17

        elif recognized_item_group == "item":
            if category == "minecraft:dropped":
                return 4
            elif category == "minecraft:used":
                return 8
            elif category == "minecraft:crafted":
                return 14
            elif category == "minecraft:picked_up":
                return 18

        elif category == "minecraft:killed":
            return 11
        elif category == "minecraft:killed_by":
            return 12
        elif category == "minecraft:custom":
            return 21
        else:
            return -1  # Return an invalid value if no match is found

    def check_item_for_block(self, item):
        item = item.replace("minecraft:", "")
        query = f"SELECT EXISTS (SELECT 1 FROM block_lookup WHERE blocks = %s)"
        self.cursor.execute(query, (item,))
        result = self.cursor.fetchone()[0]
        return result
        
    def check_item_for_item(self, item):
        item = item.replace("minecraft:", "")

        query = f"SELECT EXISTS (SELECT 1 FROM item_lookup WHERE items = %s)"
        self.cursor.execute(query, (item,))
        result = self.cursor.fetchone()[0]
        return result
        
        
if __name__ == "__main__":
    db_manager = DatabaseManager()
    db_manager.init_tables()
    # db_manager.init_new_server("tobias", 2, "Tobias Auer", "mc.t-auer.com")
    # my_server_id = db_manager.get_server_id_from_subdomain("tobias")
    # db_manager.add_new_player("4ebe5f6f-c231-4315-9d60-097c48cc6d30")

    # db_manager.init_player_server_info_table(my_server_id, "4ebe5f6f-c231-4315-9d60-097c48cc6d30")
    
    # my_id = db_manager.get_player_id_from_player_uuid_and_server_id("4ebe5f6f-c231-4315-9d60-097c48cc6d30", my_server_id)
    # db_manager.init_prefix_table(my_id)
    # my_prefix_id = db_manager.get_prefix_id_from_player_id(my_id)
    # db_manager.join_prefix(my_id, my_prefix_id)
    # db_manager.update_prefix(my_id, "NewPrefix", "newpassword")
    # db_manager.get_prefix_id_from_player_id(my_id)
    # db_manager.get_prefix_name_from_prefix_id(my_prefix_id)
    # print(db_manager.get_members_from_prefix_id(my_prefix_id))
    # #db_manager.leave_prefix(my_id, my_prefix_id)
    # db_manager.ban_player(my_id, my_id, "banned for testing", "2024-08-12 19:10:50")
    # db_manager.check_for_ban_entry(my_id)
    # db_manager.get_ban_info(my_id)
    # db_manager.unban_player(my_id, my_id)
    # db_manager.check_for_ban_entry(my_id)
    # db_manager.get_ban_info(my_id)
    # db_manager.add_login_entry(my_id, "1234")
    # print(db_manager.get_login_attempt_validity(my_id, 1234))
    # print(db_manager.get_login_attempt_validity(my_id, 1235))
    # db_manager.delete_login_entry(my_id)
    # print(db_manager.get_login_attempt_validity(my_id, 1234))
    # logger.info("Database connection closed")

    db_manager.init_item_blocks_lookup_table("database/blocks.json")
    db_manager.init_item_items_lookup_table("database/itemlist.json")
    with open("sampleData/4ebe5f6f-c231-4315-9d60-097c48cc6d30.json", "r") as f:
        print(db_manager.split_items_from_json(f.read()))
    #TODO: insert it into the action table
    db_manager.conn.close()

