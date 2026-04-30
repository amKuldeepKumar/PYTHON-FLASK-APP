from flask import Blueprint

# Phase 1: Auth blueprint initialization
bp = Blueprint("auth", __name__)

from . import routes  # noqa