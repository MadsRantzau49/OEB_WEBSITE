import warnings
warnings.filterwarnings("ignore", category=DeprecationWarning)

import sys
import os
from app import app
import pytest
from Database.database_setup import initialize_database

# Add the root directory to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))


@pytest.fixture(scope='module')
def test_client():
    # Set up the test client
    flask_app = app
    flask_app.config['TESTING'] = True
    flask_app.config['WTF_CSRF_ENABLED'] = False
    flask_app.config['DEBUG'] = False
    
    # Initialize the test database
    initialize_database("test.db")
    
    testing_client = flask_app.test_client()
    
    # Establish an application context before running the tests
    with flask_app.app_context():
        yield testing_client  # This is where the testing happens