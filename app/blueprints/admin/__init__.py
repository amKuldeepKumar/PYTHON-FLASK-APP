from flask import Blueprint

bp = Blueprint("admin", __name__, template_folder="../../templates/admin")

from . import routes  # noqa: E402,F401

from . import speaking_routes  # noqa: E402,F401
