from flask import Blueprint

bp = Blueprint("superadmin", __name__, template_folder="../../templates/superadmin")

from . import routes  # noqa: E402,F401
from . import speaking_routes  # noqa: E402,F401
from . import writing_routes  # noqa: E402,F401

from . import listening_routes  # noqa: E402,F401

from . import publish_review_routes  # noqa: E402,F401
from . import economy_routes  # noqa: E402,F401
