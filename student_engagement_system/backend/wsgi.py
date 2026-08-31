"""Gunicorn entry point for the Flask API.

`backend/app.py` (the Flask entry point) and `backend/app/` (the FastAPI
package) share the name "app" in the same directory. `python app.py`
works today because the interpreter loads that file directly by path
when it's the script being run, never through `import app`. gunicorn is
different: `gunicorn app:app` does an actual `import app`, and Python
resolves that to the `app/` PACKAGE (found before same-named modules),
not app.py -- so it would import an empty package with no Flask `app`
object and fail immediately.

This file sidesteps the collision by loading app.py directly from its
file path (bypassing normal package/module name resolution) rather than
importing the ambiguous bare name "app". Nothing about app.py or the
local `python app.py` dev workflow changes -- this file exists solely to
give gunicorn (production only) an unambiguous entry point.

Start command: gunicorn wsgi:app --bind 0.0.0.0:$PORT
"""

import importlib.util
from pathlib import Path

_spec = importlib.util.spec_from_file_location(
    "flask_app_entrypoint", Path(__file__).resolve().parent / "app.py"
)
_module = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_module)

app = _module.app
