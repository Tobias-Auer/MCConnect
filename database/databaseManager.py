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
    

    ################################ UPDATE FUNCTIONS #################################
    def update_prefix(self, player_id, prefix=None, password=None):
        ...

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
        
    def leave_prefix():
       ...

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

    
    def get_prefix_id_from_server_id_and_prefix_name(self, server_id, prefix_name):
        ...
    
    def get_prefix_name_from_prefix_id(self, prefix_id):
        ...
    

if __name__ == "__main__":
    db_manager = DatabaseManager()
    db_manager.init_tables()
    db_manager.init_new_server("tobias", 2, "Tobias Auer", "mc.t-auer.com")
    my_server_id = db_manager.get_server_id_from_subdomain("tobias")
    db_manager.add_new_player("4ebe5f6f-c231-4315-9d60-097c48cc6d30")

    db_manager.init_player_server_info_table(my_server_id, "4ebe5f6f-c231-4315-9d60-097c48cc6d30")
    
    my_id = db_manager.get_player_id_from_player_uuid_and_server_id("4ebe5f6f-c231-4315-9d60-097c48cc6d30", my_server_id)
    db_manager.init_prefix_table(my_id)
    my_prefix_id = db_manager.get_prefix_id_from_player_id(my_id)
    db_manager.join_prefix(my_id, my_prefix_id)
    
    logger.info("Database connection closed")
    db_manager.conn.close()
