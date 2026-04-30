import sys
import os

# Add current directory to path
sys.path.insert(0, os.path.dirname(__file__))

from app import create_app

application = create_app()