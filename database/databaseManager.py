import ast
from datetime import datetime, timedelta
import html
import json
import re
import secrets
import string
import threading
import traceback
import uuid
import argon2
import psycopg2

from logger import get_logger
import logging
from minecraft import Minecraft
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

ph = argon2.PasswordHasher()
logger = get_logger("databaseManager",logging.INFO)
minecraft = Minecraft()

def read_sql_file(filepath):
    with open(filepath, "r") as file:
        return file.read()

def generate_secure_token(length=64):
    characters = string.ascii_letters + string.digits
    return ''.join(secrets.choice(characters) for _ in range(length))



class DatabaseManager:
    TABLE_COUNT = 9
    LOWEST_WEB_ACCESS_LEVEL = 2

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
            self.init_item_blocks_lookup_table("database/blocks.json")
            self.init_item_items_lookup_table("database/itemlist.json")
            logger.info("block and item data initiated successfully")
        except Exception as e:
            logger.error(f"Error creating tables: {e}")
            self.conn.rollback()
            return False
        return True

    def init_new_server(self, subdomain, license_type, server_description_short, server_description_long, server_name, server_key, owner_username, owner_email, owner_password, discord_url=None, owner_name=None, mc_server_domain=None):
            """
            Registers a new server in the database.

            Parameters:
            subdomain (str): The name of the subdomain.
            owner_name (str, optional): The name of the server owner. Defaults to None.
            mc_server_domain (str, optional): The domain of the Minecraft server. Defaults to None.

            Returns:
            bool: True if the server is successfully registered, False otherwise.

            Raises:
            Exception: If an error occurs while executing the SQL query or committing the changes.
            """
            logger.debug("register_new_server is called")
            hashed_password = ph.hash(owner_password)
            query = """
                INSERT INTO server (owner_username, owner_email, owner_password, subdomain, license_type, server_key, server_description_short, server_description_long, discord_url, owner_name, mc_server_domain, server_name)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """
            logger.debug(f"executing SQL query: {query}")
            data = (owner_username, owner_email, hashed_password, subdomain, license_type, server_key, html.escape(server_description_short), html.escape(server_description_long).replace("\n", "<br>"), discord_url, owner_name, mc_server_domain, server_name)
            logger.debug(f"with follwing data: {data}")
            try:
                self.cursor.execute(query, data)
                self.conn.commit()
                logger.info(f'Registered new server: "{subdomain}"')
            except Exception as e:
                logger.critical(
                    f'Failed to register new server: "{subdomain}". Error: {e}'
                )
                self.conn.rollback()

                return False
            return True

    def init_player_server_info_table(self, server_id, player_uuid):
        logger.debug("init_player_server_info_table is called")
        web_access_permissions = self.LOWEST_WEB_ACCESS_LEVEL
        query = "INSERT INTO player_server_info (id, server_id, player_uuid, online, first_seen, last_seen, web_access_permissions) VALUES (uuid_generate_v4(), %s, %s, false, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, %s)"
        logger.debug(f"executing SQL query: {query}")
        data = (server_id, player_uuid, web_access_permissions)
        logger.debug(f"with following data: {data}")
        try:
            self.cursor.execute(query, data)
            self.conn.commit()
            logger.info(f'Initialized player server info for server: "{server_id}" and player: "{player_uuid}"')
        except Exception as e:
            logger.error(f'Failed to initialize player server info for server: "{server_id}" and player: "{player_uuid}". Error: {e}')
            self.conn.rollback()
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
            self.conn.rollback()
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
            self.conn.rollback()
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
            self.conn.rollback()
            return False

    def add_new_empty_manager_account(self, username, password, email, email_verificated=False):
        if not email_verificated:
            verification_code = str(uuid.uuid4())
            link = f"{self.CURRENT_DOMAIN}/verify_email/{username}/{verification_code}"
            email_text = f"Your account has been created. Please verify your email address by clicking <a href='{link}'> here </a> <br>If you didn't create an account, please ignore this email."
            hashed_password = ph.hash(password)
            query = "INSERT INTO unsetUser (username, password, email, email_verified, verification_code) VALUES (%s, %s, %s, %s, %s)"
            data = (username, hashed_password, email, False, verification_code)
            logger.debug(f"executing SQL query: {query} with data: {data}")
            try:
                self.cursor.execute(query, data)
                self.conn.commit()
                logger.info(f'Added new empty manager account: "{username}" with email verification link: {link}')
                threading.Thread(target=self.send_email, args=(email, email_text)).start()
                return True
            except Exception as e:
                logger.error(f'Failed to add new empty manager account: "{username}". Error: {e}')
                self.conn.rollback()
                return False
    
    ################################ EMAIL ################################
    def send_email(self, recipient, text):
        SMTP_SERVER = "smtp.strato.com"  # Ersetze mit deinem SMTP-Server
        SMTP_PORT = 587  
        with open("./database/credentials.txt", "r") as file:
            SMTP_USER = file.readline().strip()
            SMTP_PASS = file.readline().strip()

        # E-Mail Details
        sender_email = SMTP_USER
        receiver_email = recipient
        subject = "Test HTML E-Mail"

        # HTML-Inhalt der E-Mail
        html_content = f"""\
        <html>
        <body>
            {text}
        </body>
        </html>
        """

        # E-Mail Nachricht erstellen
        msg = MIMEMultipart()
        msg["From"] = sender_email
        msg["To"] = receiver_email
        msg["Subject"] = subject
        msg.attach(MIMEText(html_content, "html"))

        # E-Mail senden
        try:
            with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
                server.starttls()  # TLS-Verschlüsselung aktivieren
                server.login(SMTP_USER, SMTP_PASS)
                server.sendmail(sender_email, receiver_email, msg.as_string())
            print("E-Mail erfolgreich gesendet!")
        except Exception as e:
            print(f"Fehler beim Senden: {e}")
        
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
        if actual_table_count < self.TABLE_COUNT:
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
            self.conn.rollback()
            return False

    def check_for_new_login_challenge(self):
        ...
        return True
        
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
            self.conn.rollback()
            return False
        return True
    
    def add_login_entry_from_player_id(self, player_id, pin):
        logger.debug("add_login_entry is called")
        self.delete_login_entry(player_id)
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
            self.conn.rollback()
            return False
        return True
    
    def init_new_player(self, player_uuid, server_id):
        self.add_new_player(player_uuid)
        self.init_player_server_info_table(server_id, player_uuid)
        return self.get_player_id_from_player_uuid_and_server_id(player_uuid, server_id)
        
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
            self.conn.rollback()
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
            self.conn.rollback()
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
            self.conn.rollback()
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
            self.conn.rollback()
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
            self.conn.rollback()
            return False
        return True

    def update_player_stats(self, player_id, stats):
        logger.info("update_player_stats is called")
        items = self.split_items_from_json(stats)
        query = """ INSERT INTO actions (player_id, object, category, value)
                    VALUES (%s, %s, %s, %s)
                    ON CONFLICT (player_id, object, category)
                    DO UPDATE SET
                    "value" = EXCLUDED.value
                    WHERE actions.value IS DISTINCT FROM EXCLUDED.value;"""
        data = [(player_id, item[0], item[1], item[2]) for item in items if item[2] != 0]

        logger.debug(f"Executing SQL query: {query}")
        logger.debug(f"With following data: {data}")
        
        try:
            #start_time = time.time()
            self.cursor.executemany(query, data)
            self.conn.commit()
            #end_time = time.time()
        
            #elapsed_time = end_time - start_time
            logger.info(f'Updated player: "{player_id}" stats with {self.cursor.rowcount} items.')
            self.conn.commit()
            #logger.info(f'Updated player: "{player_id}" stats with {self.cursor.rowcount} items in {elapsed_time} seconds.')

            return True
        except Exception as e:
            logger.error(f'Failed to update player: "{player_id}" stats with items: {items}. Error: {e}')
            self.conn.rollback()
            self.conn.rollback()
            return False
    
    def update_player_status_from_player_uuid_and_server_id(self, player_uuid, server_id, status, exceptionCounter=0):
        logger.info("update_player_status_from_player_uuid_and_server_id is called")
        query = """ UPDATE player_server_info
                    SET online = %s
                    WHERE player_uuid = %s AND server_id = %s;"""
        data = (True if status=="online" else False, player_uuid, server_id)
        logger.debug(f"executing SQL query: {query}")
        logger.debug(f"with following data: {data}")
        try:
            self.cursor.execute(query, data)
            self.conn.commit()
            logger.info(f'Updated player status for player: "{player_uuid}" on server: "{server_id}" to: "{status}"')
            if self.cursor.rowcount == 0:
                self.init_new_player(player_uuid, server_id)
                self.update_player_status_from_player_uuid_and_server_id(player_uuid,server_id, status, exceptionCounter=1)
            query = """UPDATE player_server_info
                SET last_seen = CURRENT_TIMESTAMP
                WHERE player_uuid = %s AND server_id = %s;"""
            data = (player_uuid, server_id)
            self.cursor.execute(query, data)
            self.conn.commit()
        except Exception as e:
            self.conn.rollback()
            logger.error(f'Failed to update player status for player: "{player_uuid}" on server: "{server_id}". Error: {e}')
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
        query = "DELETE FROM server WHERE id = %s"
        logger.debug(f"executing SQL query: {query}")
        data = (server_id,)
        logger.debug(f"with following data: {data}")

        try:
            self.cursor.execute(query, data)
            self.conn.commit()
            logger.info(f'Deleted server with id: "{server_id}"')
        except Exception as e:
            logger.critical(f'Failed to delete server with id: "{server_id}". Error: {e}')
            self.conn.rollback()
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
            self.conn.rollback()
            return False
        return True

    ################################ GET FUNCTIONS ####################################
    def get_all_logins(self):
        logger.debug("get_all_logins is called")
        query = "SELECT pin, player_id FROM login"
        logger.debug(f"executing SQL query: {query}")
        self.cursor.execute(query)
        logins = self.cursor.fetchall()
        logger.debug(f"Logins retrieved: {logins}")
        return logins
    
    def get_server_id_from_player_id(self, player_id):
        logger.debug("get_server_id_from_player_id is called")
        query = "SELECT server_id FROM player_server_info WHERE id = %s"
        logger.debug(f"executing SQL query: {query}")
        data = (player_id,)
        logger.debug(f"with following data: {data}")  
        try:
            self.cursor.execute(query, data)
            result = self.cursor.fetchone()
            if result is None:
                logger.warning(f'No server found for player id: "{player_id}"')
                return None
            server_id = result[0]
            logger.debug(f'Server id for player: "{player_id}" is: "{server_id}"')
            return server_id
        except Exception as e:
            logger.error(f'Failed to get server id for player: "{player_id}". Error: {e}')
            self.conn.rollback()
            return None
        
    def get_player_uuid_from_player_id(self, player_id):
        logger.debug("get_player_uuid_from_player_id is called")
        query = "SELECT player_uuid FROM player_server_info WHERE id = %s"
        logger.debug(f"executing SQL query: {query}")
        data = (player_id,)
        logger.debug(f"with following data: {data}")  
        try:
            self.cursor.execute(query, data)
            result = self.cursor.fetchone()
            if result is None:
                logger.warning(f'No player uuid found for player id: "{player_id}"')
                return None
            server_id = result[0]
            logger.debug(f'Player uuid for player id: "{player_id}" is: "{server_id}"')
            return server_id
        except Exception as e:
            logger.error(f'Failed to get player uuid for player id: "{player_id}". Error: {e}')
            self.conn.rollback()
            return None

    
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
        logger.debug("get_player_id_from_player_uuid_and_server_id is called")
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
            self.conn.rollback()
            return None
        
    def get_player_id_from_player_uuid_and_subdomain(self, player_uuid, subdomain):
        logger.debug("get_player_id_from_player_uuid_and_subdomain is called")
        query = """SELECT psi.id
                FROM player_server_info psi
                JOIN server s ON psi.server_id = s.id
                WHERE psi.player_uuid = %s AND s.subdomain = %s;"""
        logger.debug(f"executing SQL query: {query}")
        data = (player_uuid, subdomain,)
        logger.debug(f"with following data: {data}")
        try:
            self.cursor.execute(query, data)
            result = self.cursor.fetchone()
            if result is None:
                logger.warning(f'No player found for uuid: "{player_uuid}" and subdomain: "{subdomain}"')
                return None
            player_id = result[0]
            logger.info(f'Found player id: "{player_id}" for uuid: "{player_uuid}" and subdomain: "{subdomain}"')
            return player_id
        except Exception as e:
            logger.error('Failed to find player for uuid: "{player_uuid}" and subdomain: "{subdomain}"')
            self.conn.rollback()
            return None
        
    def get_server_id_from_subdomain(self, subdomain):
        logger.debug("get_server_id_from_subdomain is called")
        query = "SELECT id FROM server WHERE subdomain = %s"
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
            self.conn.rollback()
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
            self.conn.rollback()
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
            self.conn.rollback()
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
            self.conn.rollback()
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
            self.conn.rollback()
            return None
        return re.findall(r'[a-zA-Z0-9-]+', result[0][0])

    def get_ban_info_from_player_id(self, player_id):
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
            self.conn.rollback()
            return None
        logger.info(f"Ban info: {result}")
        return result
    
    def get_ban_info_from_player_uuid_and_subdomain(self, player_uuid, subdomain):
        logger.debug(f"getting ban_info is called")
        query = """
            SELECT bp.*
            FROM banned_players bp
            JOIN player_server_info psi ON bp.player_id = psi.id
            JOIN server s ON psi.server_id = s.id
            WHERE psi.player_uuid = %s AND s.subdomain = %s;
            """        
        data = (player_uuid, subdomain)
        logger.debug(f"executing SQL query: {query}")
        logger.debug(f"with following data: {data}")
        try:
            self.cursor.execute(query, data)
            result = self.cursor.fetchone()
            logger.info(f'Found ban info for player: "{player_uuid}" and subdomain: "{subdomain}"')
        except Exception as e:
            logger.error(f'Failed to get ban info for player: "{player_uuid}" and subdomain: "{subdomain}". Error: {e}')
            self.conn.rollback()
            return None
        logger.info(f"Ban info: {result}")
        return result

    def get_login_attempt_validity_from_player_id_and_pin(self, player_id, pin):
        logger.debug(f"get_login_attempt_validity_from_player_id_and_pin is called for player_id: {player_id}")
        
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
            self.delete_login_entry(player_id)

            return [True,]
        
        except Exception as e:
            logger.error(f'Failed to verify login attempt for player_id: {player_id}. Error: {e}')
            self.conn.rollback()
            return [False, "database error occurred"]
    
    def get_web_access_permission_from_uuid_and_subdomain(self, player_uuid, subdomain):
        logger.debug(f"getting web_access_permission_from_uuid_and_subdomain is called")
        query = """
                SELECT psi.web_access_permissions
                FROM player_server_info psi
                JOIN server s ON psi.server_id = s.id
                WHERE psi.player_uuid = %s AND s.subdomain = %s;
                """
        data = (player_uuid, subdomain)
        logger.debug(f"executing SQL query: {query}")
        logger.debug(f"with following data: {data}")
        try:
            self.cursor.execute(query, data)
            result = self.cursor.fetchone()
            logger.info(f'Found web access permission for player_uuid: "{player_uuid}" and subdomain: "{subdomain}": {result[0]}')
        except Exception as e:
            logger.error(f'Failed to get web access permission for player_uuid: "{player_uuid}" and subdomain: "{subdomain}". Error: {e}')
            self.conn.rollback()
            return None
        return result[0] if result else 99
    
    def get_web_access_permission_from_player_id(self, player_id):
        logger.debug(f"getting web_access_permission_from_player_id is called")
        query = "SELECT web_access_permissions FROM player_server_info WHERE id = %s;"
        data = (player_id,)
        logger.debug(f"executing SQL query: {query}")
        logger.debug(f"with following data: {data}")
        try:
            self.cursor.execute(query, data)
            result = self.cursor.fetchone()
            logger.info(f'Found web access permission for player_id: "{player_id}": {result[0]}')
        except Exception as e:
            self.conn.rollback()
            logger.error(f'Failed to get web access permission for player_id: "{player_id}". Error: {e}')
            
            return 99
        return result[0] if result else 99
    
    def get_server_information(self, subdomain):
        logger.debug(f"getting server_information is called")
        query = "SELECT * FROM server WHERE subdomain = %s;"
        data = (subdomain,)
        logger.debug(f"executing SQL query: {query}")
        logger.debug(f"with following data: {data}")
        try:
            self.cursor.execute(query, data)
            result = self.cursor.fetchone()
            logger.info(f'Found server information for subdomain: "{subdomain}"')
        except Exception as e:
            self.conn.rollback()
            logger.error(f'Failed to get server information for subdomain: "{subdomain}". Error: {e}')
            return None
        return result
    
    def get_online_status_by_player_id(self, player_id):
        logger.debug(f"getting online_status_by_player_id is called")
        query = """ SELECT online FROM player_server_info WHERE id=%s"""
        data = (player_id,)
        logger.debug(f"executing SQL query: {query}")
        logger.debug(f"with following data: {data}")
        try:
            self.cursor.execute(query, data)
            result = self.cursor.fetchone()
            logger.debug(f'Found online status for player_id: "{player_id}": {result[0]}')
        except Exception as e:
            self.conn.rollback()
            logger.error(f'Failed to get online status for player_id: "{player_id}". Error: {e}')
            return None
        return result[0] if result else False
    
    def get_online_status_by_player_uuid_and_subdomain(self, player_uuid, subdomain):
        logger.debug(f"getting online_status_by_player_uuid_and_subdomain is called")
        query = """
                SELECT psi.online
                FROM player_server_info psi
                JOIN server s ON psi.server_id = s.id
                WHERE psi.player_uuid = %s AND s.subdomain = %s;
                """
        data = (player_uuid, subdomain)
        logger.debug(f"executing SQL query: {query}")
        logger.debug(f"with following data: {data}")
        try:
            self.cursor.execute(query, data)
            result = self.cursor.fetchone()
            logger.debug(f'Found online status for player_uuid: "{player_uuid}" and subdomain: "{subdomain}": {result[0]}')
            return result[0]
        except Exception as e:
            self.conn.rollback()
            logger.error(f'Failed to get online status for player_uuid: "{player_uuid}" and subdomain "{subdomain}" Error: {e}')
        return None
    
    def get_player_name_from_uuid__offline(self, uuid):
        logger.debug(f'getting_player_name_from_uuid__offline is called with uuid: "{uuid}"')
        """
        Gets the username from the database using the given UUID.

        :param UUID: UUID of the player.
        :return: str: The username of the requested player.
        """
        query = """SELECT name FROM player WHERE uuid = %s"""
        data = (uuid,)
        logger.debug(f"executing query: {query}")
        logger.debug(f"with data: {data}")
        try:
            result = self.cursor.execute(query, data)
            result = self.cursor.fetchone()
            if result:
                logger.debug(f"Found username: {result[0]} for uuid: {uuid}")
                return result[0]
            else:
                logger.warning(f"No player found for uuid: {uuid}")
                return -1
        except Exception as e:
            self.conn.rollback()
            logger.error("Error in get_player_name_from_uuid__offline: " + str(e))
            return -1
    
    def get_player_uuid_from_name__offline(self, name):
        """
        Gets the uuid from the database using the given username.

        :param name: str: The username of the player.
        :return: str: The uuid of the requested player.
        """
        logger.debug(f"get_player_uuid_from_name__offline is called with name: {name}")
        query = """SELECT uuid FROM player WHERE LOWER(name) = LOWER(%s)"""
        data = (name,)
        try:
            self.cursor.execute(query, data)
            result = self.cursor.fetchone()
            if result:
                uuid = result[0]
                logger.debug(f"Found uuid: {uuid} for username: {name}")
                return uuid
            else:
                logger.warning(f"No player found for name: {name}")
                return -1
        except Exception as e:
            self.conn.rollback()
            logger.error("Error in get_player_uuid_from_name__offline: " + str(e))
            return -1

    def get_all_uuids_from_subdomain(self, subdomain):
        logger.debug(f"getting_all_uuids_from_subdomain is called with subdomain: {subdomain}")
        query = """SELECT player_uuid FROM player_server_info WHERE server_id IN (SELECT id FROM server WHERE subdomain = %s)"""
        data = (subdomain,)
        logger.debug(f"executing SQL query: {query}")
        logger.debug(f"with following data: {data}")
        try:
            self.cursor.execute(query, data)
            result = self.cursor.fetchall()
            uuids = [uuid[0] for uuid in result]
            logger.debug(f"Found uuids: {uuids} for subdomain: {subdomain}")
            return uuids
        except Exception as e:
            self.conn.rollback()
            logger.error(f"Error in getting_all_uuids_from_subdomain: {e}")
            return []
        
    def get_online_player_count_from_subdomain(self, subdomain):
        logger.debug(f"getting_online_player_count_from_subdomain is called with subdomain: {subdomain}")
        query = """SELECT COUNT(*) FROM player_server_info WHERE server_id IN (SELECT id FROM server WHERE subdomain = %s) AND online = true"""
        data = (subdomain,)
        logger.debug(f"executing SQL query: {query}")
        logger.debug(f"with following data: {data}")
        try:
            self.cursor.execute(query, data)
            result = self.cursor.fetchone()
            logger.debug(f"Found online player count: {result[0]} for subdomain: {subdomain}")
            return result[0]
        except Exception as e:
            self.conn.rollback()
            logger.error(f"Error in getting_online_player_count_from_subdomain: {e}")
            return 0
    
    def get_banned_status_from_uuid_and_subdomain(self, uuid, subdomain):
        logger.debug(f"getting_banned_status_from_uuid_and_subdomain is called with uuid: {uuid} and subdomain: {subdomain}")
        query = """SELECT * FROM banned_players WHERE player_id = server_id(SELECT id FROM server WHERE subdomain = %s)"""
        data = (uuid, subdomain)
        logger.debug(f"executing SQL query: {query}")
        logger.debug(f"with following data: {data}")
        try:
            self.cursor.execute(query, data)
            result = self.cursor.fetchone()
            logger.debug(f"Found banned status: {result[0]} for uuid: {uuid} and subdomain: {subdomain}")
            return result[0] if result else False
        except Exception as e:
            self.conn.rollback()
            logger.error(f"Error in getting_banned_status_from_uuid_and_subdomain")
    
    def get_first_seen_by_player_id(self, player_id):
        logger.debug(f"getting_first_seen_by_player_id is called with player_id: {player_id}")
        query = """SELECT first_seen FROM player_server_info WHERE id = %s"""
        data = (player_id,)
        logger.debug(f"executing SQL query: {query}")
        logger.debug(f"with following data: {data}")
        try:
            self.cursor.execute(query, data)
            result = self.cursor.fetchone()
            logger.debug(f"Found first seen timestamp: {result[0]} for player_id: {player_id}")
            return result[0]
        except Exception as e:
            self.conn.rollback()
            logger.error(f"Error in getting_first_seen_by_player_id: {e}")
            return None
    
    def get_last_seen_by_player_id(self, player_id):
        logger.debug(f"getting_last_seen_by_player_id is called with player_id: {player_id}")
        query = """SELECT last_seen FROM player_server_info WHERE id = %s"""
        data = (player_id,)
        logger.debug(f"executing SQL query: {query}")
        logger.debug(f"with following data: {data}")
        try:
            self.cursor.execute(query, data)
            result = self.cursor.fetchone()
            logger.debug(f"Found first seen timestamp: {result[0]} for player_id: {player_id}")
            return result[0]
        except Exception as e:
            self.conn.rollback()
            logger.error(f"Error in getting_last_seen_by_player_id: {e}")
            return None
    
    def get_value_from_unique_object_from_action_table_with_player_id(self, object, player_id):
        """
        This function retrieves the value associated with a unique object from the 'actions' table.

        Parameters:
        object (str): The unique object for which the value needs to be retrieved.

        Returns:
        value (str): The value associated with the unique object. If the object is not found, it returns None.
        """
        logger.debug(f"get_value_from_unique_object_from_action_table_with_player_id is called with object: {object}")
        query = """SELECT value FROM actions WHERE object = %s and player_id = %s"""
        data = (object,player_id)
        logger.debug(f"executing SQL query: {query}")
        logger.debug(f"with following data: {data}")
        try:
            self.cursor.execute(query, data)
            result = self.cursor.fetchone()
            result = result[0] if result else None
            logger.debug(f"Found value: {result} for object: {object}")
            return result
        except Exception as e:
            self.conn.rollback()
            logger.error(f"Error in get_value_from_unique_object_from_action_table_with_player_id: {e}\n{traceback.format_exc()}")
            return None
    
    def get_all_armor_stats(self, player_id):
        '''
        ----> Layout.txt
        '''
        logger.debug("getting_all_armor_stats is called")
        query = """ SELECT jsonb_agg(category_objects) AS grouped_objects
                    FROM (
                        SELECT category, jsonb_agg(jsonb_build_object('object', object, 'value', value)) AS category_objects
                        FROM actions
                        WHERE category IN (19, 16, 9, 5, 1) AND player_id = %s
                        GROUP BY category
                        ORDER BY category DESC
                    ) subquery;
                """     
        data = (player_id,)
        logger.debug(f"executing SQL query: {query}")
        logger.debug(f"with following data: {data}")

        try:
            self.cursor.execute(query, data)
            result = self.cursor.fetchone()
            logger.debug(f"Found grouped_objects: {result[0]} for player_id: {player_id}")
            return result[0]
        except Exception as e:
            self.conn.rollback()
            logger.error(f"Error in getting_all_armor_stats: {e}")
            return None
        
    def get_all_tools_stats(self, player_id):
        '''
        ----> Layout.txt
        '''
        logger.debug("getting_all_tools_stats is called")
        query = """ SELECT jsonb_agg(category_objects) AS grouped_objects
                    FROM (
                        SELECT category, jsonb_agg(jsonb_build_object('object', object, 'value', value)) AS category_objects
                        FROM actions
                        WHERE category IN (20, 15, 10, 6, 0) AND player_id = %s
                        GROUP BY category
                        ORDER BY category DESC
                    ) subquery;
                """     
        data = (player_id,)
        logger.debug(f"executing SQL query: {query}")
        logger.debug(f"with following data: {data}")

        try:
            self.cursor.execute(query, data)
            result = self.cursor.fetchone()
            logger.debug(f"Found grouped_objects: {result[0]} for player_id: {player_id}")
            return result[0]
        except Exception as e:
            self.conn.rollback()
            logger.error(f"Error in getting_all_tools_stats: {e}")
            return None
        
    def get_all_items_stats(self, player_id):
        '''        
        ----> Layout.txt
        '''
        logger.debug("getting_all_items_stats is called")
        query = """ SELECT jsonb_agg(category_objects) AS grouped_objects
                    FROM (
                        SELECT category, jsonb_agg(jsonb_build_object('object', object, 'value', value)) AS category_objects
                        FROM actions
                        WHERE category IN (18, 14, 8, 4) AND player_id = %s
                        GROUP BY category
                        ORDER BY category DESC
                    ) subquery;
                """     
        data = (player_id,)
        logger.debug(f"executing SQL query: {query}")
        logger.debug(f"with following data: {data}")

        try:
            self.cursor.execute(query, data)
            result = self.cursor.fetchone()
            logger.debug(f"Found grouped_objects: {result[0]} for player_id: {player_id}")
            return result[0]
        except Exception as e:
            self.conn.rollback()
            logger.error(f"Error in getting_all_items_stats: {e}")
            return None
    
    def get_all_blocks_stats(self, player_id):
        '''
                ----> Layout.txt
        '''
        logger.debug("getting_all_blocks_stats is called")
        query = """ SELECT jsonb_agg(category_objects) AS grouped_objects
                    FROM (
                        SELECT category, jsonb_agg(jsonb_build_object('object', object, 'value', value)) AS category_objects
                        FROM actions
                        WHERE category IN (17, 13, 7, 3, 2) AND player_id = %s
                        GROUP BY category
                        ORDER BY category DESC
                    ) subquery;
                """     
        data = (player_id,)
        logger.debug(f"executing SQL query: {query}")
        logger.debug(f"with following data: {data}")

        try:
            self.cursor.execute(query, data)
            result = self.cursor.fetchone()
            logger.debug(f"Found grouped_objects: {result[0]} for player_id: {player_id}")
            return result[0]
        except Exception as e:
            self.conn.rollback()
            logger.error(f"Error in getting_all_blocks_stats: {e}")
            return None
        
    def get_all_mobs_stats(self, player_id):
        '''
        ----> Layout.txt

        '''
        logger.debug("getting_all_mobs_stats is called")
        query = """ SELECT jsonb_agg(category_objects) AS grouped_objects
                    FROM (
                        SELECT category, jsonb_agg(jsonb_build_object('object', object, 'value', value)) AS category_objects
                        FROM actions
                        WHERE category IN (12, 11) AND player_id = %s
                        GROUP BY category
                        ORDER BY category DESC
                    ) subquery;
                """     
        data = (player_id,)
        logger.debug(f"executing SQL query: {query}")
        logger.debug(f"with following data: {data}")

        try:
            self.cursor.execute(query, data)
            result = self.cursor.fetchone()
            logger.debug(f"Found grouped_objects: {result[0]} for player_id: {player_id}")
            return result[0]
        except Exception as e:
            self.conn.rollback()
            logger.error(f"Error in getting_all_mobs_stats: {e}")
            return None
        
    def get_all_custom_stats(self, player_id):
        '''
        Custom:
            custom: 21
        '''
        logger.debug("getting_all_custom_stats is called")
        query = """ SELECT jsonb_agg(category_objects) AS grouped_objects
                    FROM (
                        SELECT category, jsonb_agg(jsonb_build_object('object', object, 'value', value)) AS category_objects
                        FROM actions
                        WHERE category = 21 AND player_id = %s
                        GROUP BY category
                        ORDER BY category DESC
                    ) subquery;
                """     
        data = (player_id,)
        logger.debug(f"executing SQL query: {query}")
        logger.debug(f"with following data: {data}")

        try:
            self.cursor.execute(query, data)
            result = self.cursor.fetchone()
            logger.debug(f"Found grouped_objects: {result[0]} for player_id: {player_id}")
            return result[0]
        except Exception as e:
            self.conn.rollback()
            logger.error(f"Error in getting_all_custom_stats: {e}")
            return None
    
    def get_server_id_by_auth_key(self, auth_key):
        logger.debug(f"get_server_id_by_auth_key is called with auth_key: {auth_key}")
        query = """ SELECT id FROM server WHERE server_key = %s; """
        data = (auth_key,)
        logger.debug(f"executing SQL query: {query}")
        logger.debug(f"with following data: {data}")

        try:
            self.cursor.execute(query, data)
            result = self.cursor.fetchone()
            result = result[0] if result else None
            logger.debug(f"Found server_id: {result} for auth_key: {auth_key}")
            return result
        except Exception as e:
            self.conn.rollback()
            logger.error(f"Error in get_server_id_by_auth_key: {e}")
            return None
    
    ################################ helper functions ################################
    def split_items_from_json(self, items):
        '''
        Return: [[object/item, category, value],]
        '''
        return_list = []
        stats_categorys = ["minecraft:broken", "minecraft:mined","minecraft:dropped","minecraft:used","minecraft:killed","minecraft:crafted","minecraft:killed_by","minecraft:custom","minecraft:picked_up"]
        all_data = json.loads(items)["stats"]
        for category in stats_categorys:
            try:
                data = all_data[category]
                # if category == "minecraft:broken":
                for item_name, item_data in data.items():
                    db_category = self.get_db_category_from_item_and_json_category(item_name, category)
                    return_list.append([item_name, db_category, item_data])
            except KeyError:
                continue

        return return_list
                    
    def get_db_category_from_item_and_json_category(self, item, category):
        '''
        categorys = ["minecraft:broken", "minecraft:mined","minecraft:dropped","minecraft:used","minecraft:killed","minecraft:killed_by","minecraft:crafted","minecraft:picked_up","minecraft:custom"]

        ----> Layout.txt
        Return: database category name
        '''
        tools_substrings = ["axe", "shovel", "hoe", "sword", "pickaxe", "shield", "flint_and_steel", "bow", "crossbow", "brush", "trident", "shears", "fishing_rod"]
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
                return 15
            elif category == "minecraft:dropped":
                return 10
            elif category == "minecraft:used":
                return 20
            elif category == "minecraft:crafted":
                return 0
            elif category == "minecraft:picked_up":
                return 6

        elif recognized_item_group == "armor":
            if category == "minecraft:broken":
                return 16
            elif category == "minecraft:dropped":
                return 9
            elif category == "minecraft:used":
                return 19
            elif category == "minecraft:crafted":
                return 1
            elif category == "minecraft:picked_up":
                return 5

        elif recognized_item_group == "block":
            if category == "minecraft:mined":
                return 17
            elif category == "minecraft:dropped":
                return 7
            elif category == "minecraft:used":
                return 13
            elif category == "minecraft:crafted":
                return 2
            elif category == "minecraft:picked_up":
                return 3

        elif recognized_item_group == "item":
            if category == "minecraft:dropped":
                return 14
            elif category == "minecraft:used":
                return 18
            elif category == "minecraft:crafted":
                return 4
            elif category == "minecraft:picked_up":
                return 8

        if category == "minecraft:killed":
            return 12
        elif category == "minecraft:killed_by":
            return 11
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
    
    def format_time(self, seconds):
        """
        Formats a given number of seconds into a human-readable time string.

        Args:
            seconds (int): The number of seconds to be formatted.

        Returns:
            str: A formatted time string in the format "X Tage, Y Stunden, Z Minuten, W Sekunden",
                    where the parts are included only if they are non-zero.
        """
        days = int(seconds // 86400)
        seconds %= 86400

        hours = int(seconds // 3600)
        seconds %= 3600

        minutes = int(seconds // 60)
        seconds = int(seconds % 60)

        time_parts = []
        setMinutes, setSeconds = True, True
        if days > 0:
            time_parts.append(f"{days} Tag{'e' if days > 1 else ''}")
            setSeconds, setMinutes = False, False
        if hours > 0:
            time_parts.append(f"{hours} Std.")
            setMinutes = False
        if minutes > 0 and setMinutes:
            time_parts.append(f"{minutes} Min.")
        if seconds > 0 and setSeconds:
            time_parts.append(f"{seconds} Sec.")

        return ' '.join(time_parts)      
    
        
if __name__ == "__main__":
    server_description_long = """
    Dieser Server ist ein Hobby Projekt von mir, welches am 29.01.2023 gestartet wurde.

    Zusätzlich befinden sich auf dem Server verschiedene Plugins. Unter anderem sind custom crafting Recipes, eigene Prefixe und auch eine Spawn Elytra dabei.

    100% der installierten Plugins sind zu 100% von mir gecodet und ich verzichten dabei vollständig auf third party plugins.

    Der Server ist an sich Vanilla Gameplay, aber für Plugin Vorschläge bin ich jederzeit offen. :)
    """
    server_description_short = "Komm auf den Server und spiele mit."
    db_manager = DatabaseManager()
    db_manager.init_tables()
    db_manager.init_new_server(subdomain="tobias", 
                                license_type=2,
                                owner_name="Tobias Auer", 
                               mc_server_domain="mc.t-auer.com", 
                               owner_username="Tobias",
                               owner_email="mc.t-auer.com",
                               owner_password="1234",
                               discord_url="https://www.discord.gg/vJYNnsQwf8", 
                               server_description_short=server_description_short, 
                               server_description_long=server_description_long,
                               server_name="Tobi's Mc-Server",
                               server_key=generate_secure_token())
    
    #my_server_id = db_manager.get_server_id_from_subdomain("tobias")
    # my_other_server_id = db_manager.get_server_id_from_subdomain("tobias2")
    
    
    #db_manager.add_new_player("4ebe5f6f-c231-4315-9d60-097c48cc6d30")
    # db_manager.add_new_player("c96792ac-7aea-4f16-975e-535a20a2791a") #test player
    # db_manager.add_new_player("83f4a8ea-51f1-465d-9274-9a6b2e4ec64c")#test player
    # db_manager.add_new_player("25c6a3b7-94fa-45b4-8d9f-7041a35d97b3")#test player

    #db_manager.init_player_server_info_table(my_server_id, "4ebe5f6f-c231-4315-9d60-097c48cc6d30")
    # db_manager.init_player_server_info_table(my_server_id, "c96792ac-7aea-4f16-975e-535a20a2791a")#test player
    # db_manager.init_player_server_info_table(my_server_id, "83f4a8ea-51f1-465d-9274-9a6b2e4ec64c")#test player
    # db_manager.init_player_server_info_table(my_other_server_id, "4ebe5f6f-c231-4315-9d60-097c48cc6d30")#test player
    # db_manager.init_player_server_info_table(my_other_server_id, "25c6a3b7-94fa-45b4-8d9f-7041a35d97b3")#test player
    
    #my_id = db_manager.get_player_id_from_player_uuid_and_server_id("4ebe5f6f-c231-4315-9d60-097c48cc6d30", my_server_id)
    # db_manager.init_prefix_table(my_id)
    # my_prefix_id = db_manager.get_prefix_id_from_player_id(my_id)
    # db_manager.join_prefix(my_id, my_prefix_id)
    # db_manager.update_prefix(my_id, "NewPrefix", "newpassword")
    # db_manager.get_prefix_id_from_player_id(my_id)
    # db_manager.get_prefix_name_from_prefix_id(my_prefix_id)
    # print(db_manager.get_members_from_prefix_id(my_prefix_id))
    # #db_manager.leave_prefix(my_id, my_prefix_id)
    #db_manager.ban_player(my_id, my_id, "banned for testing", "2024-08-12 19:10:50")
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

    #db_manager.add_login_entry_from_player_uuid_and_subdomain("4ebe5f6f-c231-4315-9d60-097c48cc6d30", "tobias", 1234)
    #print(db_manager.get_login_attempt_validity_from_uuid_subdomain_and_pin("4ebe5f6f-c231-4315-9d60-097c48cc6d30", "tobias", 1234))
    #print(db_manager.get_login_attempt_validity_from_uuid_subdomain_and_pin("4ebe5f6f-c231-4315-9d60-097c48cc6d30", "tobias", 12345))

    #exit(db_manager.get_player_id_from_player_uuid_and_subdomain("4ebe5f6f-c231-4315-9d60-097c48cc6d30", "tobias"))
    #logger.info(db_manager.get_all_uuids_from_subdomain("tobias"))
    #print(db_manager.get_online_player_count_from_subdomain("tobias"))

    #db_manager.get_online_status_by_player_uuid_and_subdomain("4ebe5f6f-c231-4315-9d60-097c48cc6d30", "tobias")
    #with open("sampleData/4ebe5f6f-c231-4315-9d60-097c48cc6d30.json", "r") as f:
        #db_manager.update_player_stats(my_id,f.read())
    
    #db_manager.get_all_armor_stats(my_id)
            
    #db_manager.get_web_access_permission_from_player_id(my_id)
    db_manager.conn.close()


# TODO: Insert player kills from 'other' to 'mobs' -> player