import psycopg2

from logger import get_logger


logger = get_logger('databaseManager')   
def read_sql_file(filepath):
    with open(filepath, 'r') as file:
        return file.read()

class DatabaseManager:
    TABLE_COUNT = 7
    def __init__(self):
        self.conn = psycopg2.connect(database="mcConnect-TestDB-1",
                                host="localhost",
                                user="admin",
                                password="admin",
                                port="5432")
        logger.info("Established connection to the database")
        self.cursor = self.conn.cursor()


    def create_tables(self):
        """
        WARNING: This function wipes the whole database. Only run on critical errors.

        This function drops the existing database schema and recreates it by executing the SQL query from the initDB.sql file.
        It then commits the changes and prints a success message.
        Returns:
        bool: True if the tables are successfully initiated, False otherwise.
        """
        self.drop_db()
        query = read_sql_file('socket/queries/initDB.sql')
        try:     
            self.cursor.execute(query)
            self.conn.commit()
            logger.info("Tables initiated successfully")
            return True
        except Exception as e:
            logger.error(f"Error creating tables: {e}")
            return False
    

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
        print(len(self.get_all_tables()))
        if len(self.get_all_tables()) != self.TABLE_COUNT:
            logger.critical("Database integrity check failed.")
            return False
        else:
            logger.info("Database integrity check passed.")
            return True

if __name__ == "__main__":
    db_manager = DatabaseManager()
    
    db_manager.create_tables()
    db_manager.check_database_integrity()


    db_manager.conn.close()

        