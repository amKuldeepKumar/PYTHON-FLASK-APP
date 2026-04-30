"""
Phase Coverage:
- Phase 1: Production entrypoint for Gunicorn / WSGI servers.

Future:
- Phase 15: Deployment hardening (Gunicorn config, Nginx, env separation, logging).
"""

from app import create_app

app = create_app()