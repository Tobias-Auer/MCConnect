import sys
import os

# Get the path to the root directory of your project
root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'database'))

# Add the root directory to sys.path
sys.path.insert(0, root_dir)

# Now you can import databaseManager
from databaseManager import DatabaseManager # type: ignore

