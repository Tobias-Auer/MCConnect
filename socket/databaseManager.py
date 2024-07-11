import psycopg2

from logger import get_logger
from minecraft import Minecraft

logger = get_logger("databaseManager")
minecraft = Minecraft()

def read_sql_file(filepath):
    with open(filepath, "r") as file:
        return file.read()


class DatabaseManager:
    TABLE_COUNT = 7
    LOWEST_WEB_ACCESS_LEVEL = 2

    def __init__(self):
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
            self.create_tables()

    def create_tables(self):
        """
        WARNING: This function wipes the whole database. Only run on critical errors.

        This function drops the existing database schema and recreates it by executing the SQL query from the initDB.sql file.
        It then commits the changes and prints a success message.

        Returns:
        bool: True if the tables are successfully initiated, False otherwise.

        Raises:
        Exception: If an error occurs while executing the SQL query or committing the changes.
        """
        self.drop_db()
        query = read_sql_file("socket/queries/initDB.sql")
        try:
            self.cursor.execute(query)
            self.conn.commit()
            logger.info("Tables initiated successfully")
        except Exception as e:
            logger.error(f"Error creating tables: {e}")
            return False
        return True

    def get_all_tables(self):
        """
        Retrieves all table names from the connected database.

        Parameters:
        None

        Returns:
        tables (list): A list of tuples, where each tuple contains one table name.
        """
        query = "SELECT tablename FROM pg_catalog.pg_tables WHERE schemaname NOT IN ('pg_catalog', 'information_schema');"
        self.cursor.execute(query)
        tables = self.cursor.fetchall()
        logger.debug(f"Table names retrieved: {tables}")
        return tables

    def drop_db(self):
        """
        WARNING: This function wipes the whole database. Only run on critical errors.

        Drops the public schema and recreates it. This is used to reset the database.

        Parameters:
        None

        Returns:
        None
        """
        query = "DROP SCHEMA public CASCADE;CREATE SCHEMA public;"
        self.cursor.execute(query)
        logger.warn("Database dropped")
        self.conn.commit()

    def check_database_integrity(self):
        """
        Checks the integrity of the database by comparing the number of tables with the expected count.

        Parameters:
        self (DatabaseManager): The instance of the DatabaseManager class.

        Returns:
        bool: True if the database integrity check passes, False otherwise.
        """
        logger.debug("Database integrity check")
        logger.debug(f"Expected table count: {self.TABLE_COUNT}")
        actual_table_count = len(self.get_all_tables())
        if actual_table_count != self.TABLE_COUNT:
            logger.critical("Database integrity check failed.")
            logger.debug(f"Actual table count: {actual_table_count}")
            return False
        else:
            logger.info("Database integrity check passed.")
        return True

    def register_new_server(self, server_id, subdomain, owner_name=None, mc_server_domain=None):
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

        query = """
            INSERT INTO server (server_id, subdomain, owner_name, mc_server_domain)
            VALUES (%s, %s, %s, %s)
                """
        data = (server_id, subdomain, owner_name, mc_server_domain)
        try:
            self.cursor.execute(query, data)
            self.conn.commit()
            logger.info(f'Registered new server: "{subdomain}" with id: "{server_id}"')
        except Exception as e:
            logger.critical(
                f'Failed to register new server: "{subdomain}" with id: "{server_id}". Error: {e}'
            )
            return False
        return True
    
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
        query = "DELETE FROM server WHERE server_id = %s"
        data = (server_id,)

        try:
            self.cursor.execute(query, data)
            self.conn.commit()
            logger.info(f'Deleted server with id: "{server_id}"')
        except Exception as e:
            logger.critical(f'Failed to delete server with id: "{server_id}". Error: {e}')
            return False
        return True


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

        logger.debug(f'Attempting to register new player: "{player_uuid}"')
        query = "INSERT INTO player (uuid, name) VALUES (%s, %s)"
        logger.debug("searching playername for uuid: {player_uuid}")
        player_name = minecraft.get_player_name_from_uuid(player_uuid)
        logger.debug(f'Found playername: "{player_name}" for uuid: {player_uuid}')
        data = (player_uuid, player_name)
        try:
            self.cursor.execute(query, data)
            self.conn.commit()
            logger.info(f'Registered new player: "{player_uuid}" with name: "{player_name}")')
        except Exception as e:
            logger.error(f'Failed to register new player: "{player_uuid}". Error: {e}')
            return False
        return True
    
    def init_player_server_info_table(self, server_id, player_uuid):
        web_access_permissions = self.LOWEST_WEB_ACCESS_LEVEL
        query = "INSERT INTO player_server_info (id, server_id, player_uuid, online, first_seen, last_seen, web_access_permissions) VALUES (uuid_generate_v4(), %s, %s, true, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, %s)"
        data = (server_id, player_uuid, web_access_permissions)
        try:
            self.cursor.execute(query, data)
            self.conn.commit()
            logger.info(f'Initialized player server info for server: "{server_id}" and player: "{player_uuid}"')
        except Exception as e:
            logger.error(f'Failed to initialize player server info for server: "{server_id}" and player: "{player_uuid}". Error: {e}')
            return False
        return True

if __name__ == "__main__":
    db_manager = DatabaseManager()
    db_manager.create_tables()
    db_manager.register_new_server(0, "tobias", "Tobias Auer", "mc.t-auer.com")
    #db_manager.delete_server(9999)
    db_manager.add_new_player("4ebe5f6f-c231-4315-9d60-097c48cc6d30")

    db_manager.init_player_server_info_table(0, "4ebe5f6f-c231-4315-9d60-097c48cc6d30")
    
    logger.info("Database connection closed")
    db_manager.conn.close()
