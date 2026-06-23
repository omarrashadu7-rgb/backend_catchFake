import sys
import os

# Add the project root to Python path so imports work on Vercel
root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

os.chdir(root_dir)

from app.main import app
