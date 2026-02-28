import uuid
import os
from datetime import datetime

from flask import Flask, session
from dotenv import load_dotenv

from extensions import db, bcrypt, login_manager
from models import User, Admin

# =====================================
# 🔐 Load Environment Variables
# =====================================

load_dotenv()

app = Flask(__name__)

# =====================================
# 🔐 Basic Config
# =====================================

app.config["SECRET_KEY"] = os.getenv("SECRET_KEY")
app.config["SQLALCHEMY_DATABASE_URI"] = os.getenv("DATABASE_URL")
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["MAX_CONTENT_LENGTH"] = 60 * 1024 * 1024  # 60MB limit

# =====================================
# ☁️ Backblaze B2 Config
# =====================================

app.config["B2_BUCKET_NAME"] = os.getenv("B2_BUCKET_NAME")
app.config["B2_ENDPOINT"] = os.getenv("B2_ENDPOINT")
app.config["B2_ACCESS_KEY"] = os.getenv("B2_ACCESS_KEY")
app.config["B2_SECRET_KEY"] = os.getenv("B2_SECRET_KEY")

# Validate B2 credentials
if not all([
    app.config["B2_BUCKET_NAME"],
    app.config["B2_ENDPOINT"],
    app.config["B2_ACCESS_KEY"],
    app.config["B2_SECRET_KEY"],
]):
    raise ValueError("Backblaze B2 credentials missing in environment variables")

# =====================================
# 🚀 Initialize Extensions
# =====================================

db.init_app(app)
bcrypt.init_app(app)
login_manager.init_app(app)

login_manager.login_view = "main.login"
login_manager.login_message = "Please login to access this page."
login_manager.login_message_category = "warning"

# =====================================
# 👤 User Loader
# =====================================

@login_manager.user_loader
def load_user(user_id):
    role = session.get("role")
    if role == "admin":
        return db.session.get(Admin, int(user_id))
    return db.session.get(User, int(user_id))

# =====================================
# 📅 Inject Year
# =====================================

@app.context_processor
def inject_year():
    return {"current_year": datetime.now().year}

# =====================================
# 🔵 Blueprints
# =====================================

from routes import main
app.register_blueprint(main)

# =====================================
# 👑 Create Default Superadmin
# =====================================

def create_superadmin():
    existing = Admin.query.filter_by(role="superadmin").first()
    if not existing:
        superadmin = Admin(
            admin_id=str(uuid.uuid4())[:6].upper(),
            name="Super Admin",
            email="superadmin@gmail.com",
            role="superadmin",
            is_active=True,
        )
        superadmin.set_password("Admin@123")
        db.session.add(superadmin)
        db.session.commit()
        print("Superadmin created!")

# =====================================
# ▶ Run App
# =====================================

if __name__ == "__main__":
    with app.app_context():
        db.create_all()
        create_superadmin()

    app.run(debug=True)