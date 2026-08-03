import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from app.main import app
from mangum import Mangum

handler = Mangum(app, lifespan="off")
