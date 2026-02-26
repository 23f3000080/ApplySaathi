import uuid

from flask import Flask, session
from extensions import db, bcrypt, login_manager
from models import User, Admin
from datetime import datetime
import os
from dotenv import load_dotenv

load_dotenv()


app = Flask(__name__)

app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY")
app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get("DATABASE_URL")
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db.init_app(app)
bcrypt.init_app(app)
login_manager.init_app(app)
login_manager.login_view = "main.login"
login_manager.login_message = "Please login to access this page."
login_manager.login_message_category = "warning"

@login_manager.user_loader
def load_user(user_id):

    role = session.get("role")

    if role == "admin":
        return Admin.query.get(int(user_id))
    else:
        return User.query.get(int(user_id))

@app.context_processor
def inject_year():
    return {"current_year": datetime.now().year}

# 🔥 Import blueprint
from routes import main
app.register_blueprint(main)

def create_superadmin():
    existing_superadmin = Admin.query.filter_by(role="superadmin").first()

    if not existing_superadmin:
        print("Creating default superadmin...")

        superadmin = Admin(
            # 6 char UUID for admin_id capital characters only
            admin_id=str(uuid.uuid4())[:6].upper(),
            name="Super Admin",
            email="superadmin@gmail.com",
            role="superadmin",
            is_active=True
        )

        superadmin.set_password("Admin@123")  # 🔥 Change later in production

        db.session.add(superadmin)
        db.session.commit()

        print("Superadmin created successfully!")
    else:
        print("Superadmin already exists.")

if __name__ == "__main__":
    with app.app_context():
        db.create_all()
        create_superadmin()
    app.run(debug=True)