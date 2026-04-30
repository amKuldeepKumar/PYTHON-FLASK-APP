from flask import Blueprint

bp = Blueprint("account", __name__, template_folder="../../templates/account")

from . import routes  # noqa: E402,F401
