from app import create_app
from app.utils.runtime_schema import ensure_runtime_schema
from app.schema_bootstrap import ensure_dev_sqlite_schema


app = create_app()

with app.app_context():
    ensure_dev_sqlite_schema()
    ensure_runtime_schema()
    print('Interview Prep schema columns ensured successfully.')
