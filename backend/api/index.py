import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

# Exported directly as an ASGI app rather than wrapped in a Lambda adapter.
# Mangum buffers the whole response body before returning it (Lambda hands back
# a single response object), which defeated the token-by-token streaming in
# /chat. Vercel's Python runtime serves a module-level `app` as ASGI.
from app.main import app

__all__ = ["app"]
