# Vercel entry point — thin shim for the Python WSGI runtime.
# Vercel's `functions` config key only applies to files inside `api/`.
# This file imports the Flask app from root app.py so `vercel.json` can
# target `api/index.py` for maxDuration / memory configuration.
from app import app
