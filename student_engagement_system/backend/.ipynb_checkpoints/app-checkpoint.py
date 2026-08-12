from config import DATABASE_PATH
from flask_cors import CORS
print("=" * 50)
print("DATABASE:", DATABASE_PATH)
print("=" * 50)

from flask import Flask

from routes.student import student_bp
from routes.teacher import teacher_bp

app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "*"}})

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
    app.run(debug=True)