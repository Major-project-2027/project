import os

from config import DATABASE_PATH
from flask_cors import CORS
print("=" * 50)
print("DATABASE:", DATABASE_PATH)
print("=" * 50)

from flask import Flask

from routes.student import student_bp
from routes.teacher import teacher_bp

app = Flask(__name__)

# CORS_ORIGINS: comma-separated allowed origins (e.g. the deployed Vercel
# URL), or "*" (default, unchanged from before) to allow any origin. No
# cookies/session credentials are used by this API, so a wildcard is
# functionally safe -- this env var exists to let production be locked
# down to just the real frontend origin if desired, without a code change.
_cors_origins_raw = os.getenv("CORS_ORIGINS", "*").strip()
_cors_origins = (
    "*"
    if _cors_origins_raw == "*"
    else [o.strip() for o in _cors_origins_raw.split(",") if o.strip()]
)
CORS(app, resources={r"/*": {"origins": _cors_origins}})

app.register_blueprint(student_bp)
app.register_blueprint(teacher_bp)
@app.route("/")
def home():
    return {
        "message": "Predictive Multimodal Student Engagement Backend",
        "status": "Running Successfully"
    }

print("\n========== ROUTES ==========")
for rule in app.url_map.iter_rules():
    print(rule)
print("============================\n")

if __name__ == "__main__":
    # In production this file is imported by gunicorn ("app" is the WSGI
    # callable), which binds via its own -b flag/$PORT -- this block only
    # runs for `python app.py` local dev, same as before, just now also
    # respecting $PORT/0.0.0.0 if they happen to be set (e.g. testing the
    # production start command locally).
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)