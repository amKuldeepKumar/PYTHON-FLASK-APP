from flask import Blueprint

bp = Blueprint("student", __name__, url_prefix="/student")

from . import routes  # noqa: E402,F401
from . import speaking_routes  # noqa: E402,F401
from . import reading_routes  # noqa: E402,F401
from . import writing_routes  # noqa: E402,F401
from . import listening_routes  # noqa: E402,F401
from . import interview_routes  # noqa: E402,F401  # keep only for pause-check API
from . import economy_routes  # noqa: E402,F401
