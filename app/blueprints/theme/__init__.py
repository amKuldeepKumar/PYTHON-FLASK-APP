from flask import Blueprint

bp = Blueprint("theme", __name__, url_prefix="/theme")

from . import routes  # noqa
