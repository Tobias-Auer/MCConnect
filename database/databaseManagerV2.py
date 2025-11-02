import ast
from datetime import datetime, timedelta
import html
import json
import re
import secrets
import string
import threading
import time
import traceback
import uuid
import argon2
import psycopg2
import functools

from colorlogx import get_logger
import logging
from .minecraft import Minecraft
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

RESET_DATABASE = True
PREFILL_DATABASE = True

TABLE_COUNT = 12
LOWEST_WEB_ACCESS_LEVEL = 0
DEFAULT_WEB_ACCESS_LEVEL = 3
BAN_REASONS = [
    ["breaking the rules", 30],
    ["hacking", 365],
    ["spamming", 1],
    ["other", 7],
]

ph = argon2.PasswordHasher()
logger = get_logger("databaseManager",logging.DEBUG)
minecraft = Minecraft()

def read_sql_file(filepath):
    with open(filepath, "r") as file:
        return file.read()

def generate_secure_token(length=64):
    characters = string.ascii_letters + string.digits
    return ''.join(secrets.choice(characters) for _ in range(length))


def db_error_handler(method):
    @functools.wraps(method)
    def wrapper(self, *args, **kwargs):
        try:
            return method(self, *args, **kwargs)
        except Exception as e:
            logger.error(f"Database error in {method.__name__}: {e}")
            if self.conn:
                self.conn.rollback()
            raise
    return wrapper

def decorate_all_db_methods(cls):
    blacklist = [""]
    for attr_name, attr_value in cls.__dict__.items():
        if callable(attr_value) and not attr_name.startswith("__") and attr_name not in blacklist:
            setattr(cls, attr_name, db_error_handler(attr_value))
    return cls

@decorate_all_db_methods
class DatabaseManager:
    def __init__(self):
        self.CURRENT_DOMAIN = open("DOMAIN.txt", "r").readline().strip()
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

        if not self._check_database_integrity() or RESET_DATABASE:
            self._reset_database()
            self._prefill_database()

    ################################ DB INIT FUNCTIONS ###################################
    def _check_database_integrity(self):
        """
        Checks the integrity of the database by comparing the number of tables with the expected count.

        Parameters:
        self (DatabaseManager): The instance of the DatabaseManager class.

        Returns:
        bool: True if the database integrity check passes, False otherwise.
        """
        logger.debug("check_database_integrity is called")
        logger.debug(f"Expected table count: {TABLE_COUNT}")
        actual_table_count = len(self._get_all_tables())
        if actual_table_count < TABLE_COUNT:
            logger.critical("Database integrity check failed.")
            logger.debug(f"Actual table count: {actual_table_count}")
            return False
        else:
            logger.info("Database integrity check passed.")
    def _get_all_tables(self):
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

    def _reset_database(self):
        """
        WARNING: This function wipes the whole database.

        This function drops the existing database schema and recreates it by executing the SQL query from the initDB.sql file.
        It then commits the changes and prints a success message.

        Returns:
        bool: True if the tables are successfully initiated, False otherwise.

        Raises:
        Exception: If an error occurs while executing the SQL query or committing the changes.
        """
        logger.debug("drop_db is called")
        logger.warning("\nDropping database in 5 Seconds!!!\n\n!!!! To cancel press CTRL+C !!!!\n")
        for i in range(5, 0, -1):
            print(f"Reset in {i}...")
            time.sleep(0)
        query = "DROP SCHEMA public CASCADE;CREATE SCHEMA public;"
        logger.debug(f"executing SQL query: {query}")
        self.cursor.execute(query)
        logger.warning("Database dropped")
        self.conn.commit()
        self._init_tables()

    def _init_tables(self):
        logger.debug("init_tables is called")
        query = read_sql_file("database/queries/initDBv2.sql")
        logger.debug(f"executing SQL query: {query}")
        self.cursor.execute(query)
        self.conn.commit()
        logger.info(f"Tables initiated successfully")

    ################################ PREFILL FUNCTIONS ###################################
    def _prefill_database(self):
        logger.debug("prefill_database is called")
        self.fill_item_blocks_lookup_table("database/blocks.json")
        self.fill_item_items_lookup_table("database/itemlist.json")
        for ban_reason in BAN_REASONS:
            self.add_ban_reason(*ban_reason)


        if PREFILL_DATABASE:
            logger.info("Prefilling database")
            self.add_player("4ebe5f6f-c231-4315-9d60-097c48cc6d30")
            server_id = self.add_server_admin(
                "tobi",
                "testPassword",
                "tobi@t-auer.com",
                True
            )

            self.add_server(
                server_id,
                "testDomain",
                "mc.t-auer.com",
                "Test Server",
                generate_secure_token(64)
            )

            self.add_player_server_info(
                1,
                "4ebe5f6f-c231-4315-9d60-097c48cc6d30"
            )
            player_id = self.get_player_id_from_mojang_uuid_and_server_id("4ebe5f6f-c231-4315-9d60-097c48cc6d30", 1)
            self.add_prefix(player_id, "TEST PREFIX")



        logger.info("Prefill completed")

    def fill_item_blocks_lookup_table(self, block_list_file_path):
        with open(block_list_file_path, 'r') as block_list_file:
            json_data = json.load(block_list_file)
        
        names = [block["name"] for block in json_data]
            
        query = "INSERT INTO block_lookup (blocks) VALUES (%s)"
        self.cursor.executemany(query, [(element,) for element in names])
        logger.info(f"Inserted {self.cursor.rowcount} rows successfully.")
        self.conn.commit()
        return True

    def fill_item_items_lookup_table(self, item_list_file_path):
        with open(item_list_file_path, 'r') as item_list_file:
            json_data = json.load(item_list_file)
        
        names = [item["id"] for item in json_data]
            
        query = """ INSERT INTO item_lookup (items)
                    SELECT %s
                    WHERE NOT EXISTS (
                    SELECT 1 FROM block_lookup WHERE "blocks" = %s
                    );
                """
        tools_substrings = ["axe", "shovel", "hoe", "sword", "pickaxe", "shield", "flint_and_steel"]
        armor_substrings = ["boots", "leggings", "chestplate", "helmet"]
        self.cursor.executemany(query, [(element, element) for element in names if not any(substring in element for substring in tools_substrings) and not any(substring in element for substring in armor_substrings)])
        logger.info(f"Inserted {self.cursor.rowcount} rows successfully.")
        self.conn.commit()


    ################################ ADD FUNCTIONS ####################################
    def add_player_server_info(self, server_id, minecraft_uuid, web_access_permissions=DEFAULT_WEB_ACCESS_LEVEL):
        """
        Adds the player's server information to the database.
    
        Parameters:
        server_id (int): The ID of the server.
        minecraft_uuid (str): The UUID of the player.
        web_access_permissions (int, optional): The web access permissions of the player. Defaults to DEFAULT_WEB_ACCESS_LEVEL.

        Returns:
        String: The ID of the added player server info.
        """
        query = "INSERT INTO player_server_info (mojang_uuid, server_id, web_access_permissions) VALUES (%s, %s, %s)"
        data = (minecraft_uuid, server_id, web_access_permissions)
        self.cursor.execute(query, data)
        self.conn.commit()
    
    def add_player(self, minecraft_uuid):
        """
        Adds minecraft_uuid and minecraft_username to the database.
        
        Parameters:
        minecraft_uuid (str): The UUID of the player.

        Returns:
        None
        """
        logger.debug("add_player is called")
        player_name = minecraft.get_player_name_from_uuid(minecraft_uuid)
        data = (minecraft_uuid, player_name)
        query = """INSERT INTO player (uuid, name)
                    VALUES (%s, %s)
                    ON CONFLICT (uuid) DO NOTHING;
                """
        logger.debug(f"with following data: {data}")
        logger.debug(f'Found playername: "{player_name}" for uuid: {minecraft_uuid}')
        self.cursor.execute(query, data)
        self.conn.commit()
        

    def add_server(self, owner_id, subdomain, mc_server_domain, server_name, server_key, server_description_short="SHORT DESCR", server_description_long="LONG DESCR",  discord_url=None):
        """
        Adds the specified server to the database.
        
        Parameters:
        owner_username (str): The username of the server owner.
        subdomain (str): The subdomain of the server.
        mc_server_domain (str): The domain of the server.
        server_name (str): The name of the server.
        server_key (str): The key of the server.
        server_description_short (str, optional): The short description of the server. Defaults to "SHORT DESCR".
        server_description_long (str, optional): The long description of the server. Defaults to "LONG DESCR".
        discord_url (str, optional): The discord url of the server. Defaults to None.

        Returns:
        int: The ID of the added server.
        """
        query = "INSERT INTO servers (owner_id, subdomain, mc_server_domain, server_name, server_key, server_description_short, server_description_long, discord_url) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)"
        data = (owner_id, subdomain, mc_server_domain, server_name, server_key, server_description_short, server_description_long, discord_url)
        self.cursor.execute(query, data)
        self.conn.commit() 
        return self.cursor.lastrowid
    
    def add_prefix(self, player_id, prefix_text, password=None):
        """
        adds the specified prefix to the database
        
        Parameters:
        player_id (int): The ID of the player.
        prefix_text (str): The prefix to add.
        password (str, optional): The password for the prefix. Defaults to None.

        Returns:
        int: The ID of the added prefix.
        """
        query = "INSERT INTO prefixes (prefix_owner_id, prefix_text, password) VALUES (%s, %s, %s)"
        data = (player_id, prefix_text, password)
        logger.debug(f"executing SQL query: {query}")
        logger.debug(f"with following data: {data}")
        self.cursor.execute(query, data)
        self.conn.commit()
        return self.cursor.lastrowid
    
    def add_server_admin(self, username, password, email, email_verified=False):
        """
        Adds the specified server admin to the database.
        
        Parameters:
        username (str): The username of the server admin.
        password (str): The password of the server admin.
        email (str): The email of the server admin. 
        email_verified (bool, optional): Whether the email has been verified. Defaults to False.
    
        Returns:
        int: The ID of the added server admin.
        """
        query = "INSERT INTO server_admins (username, password, email, email_verified) VALUES (%s, %s, %s, %s) RETURNING id"
        data = (username, password, email, email_verified)
        logger.debug(f"executing SQL query: {query}")
        logger.debug(f"with following data: {data}")
        self.cursor.execute(query, data)
        self.conn.commit()
        id = self.cursor.fetchone()[0]
        return id

    def add_ban_reason(self, reason, durarion_in_days):
        """
        Adds a ban reason to the database.
        
        Parameters:
        reason (str): The reason for the ban.
        durarion_in_days (int): The duration of the ban in days.

        Returns:
        int: The ID of the added ban reason.
        """
        query = "INSERT INTO ban_reasons (reason, ban_duration_in_days) VALUES (%s, %s)"
        data = (reason, durarion_in_days)
        self.cursor.execute(query, data)
        self.conn.commit()
        return self.cursor.lastrowid

    ################################ GET FUNCTIONS ####################################
    def get_player_id_from_mojang_uuid_and_server_id(self, mojang_uuid, server_id):
        logger.debug("get_player_id_from_mojang_uuid_and_server_id is called")
        query = "SELECT player_id FROM player_server_info WHERE mojang_uuid = %s AND server_id = %s"
        logger.debug(f"executing SQL query: {query}")
        data = (mojang_uuid, server_id)
        logger.debug(f"with following data: {data}")
        self.cursor.execute(query, data)
        result = self.cursor.fetchone()
        if result is None:
            logger.warning(f'No player found for uuid: "{mojang_uuid}" and server: "{server_id}"')
            return None
        player_id = result[0]
        logger.info(f'Found player id: "{player_id}" for uuid: "{mojang_uuid}" and server: "{server_id}"')
        return player_id
if __name__ == "__main__":
    db = DatabaseManager()
