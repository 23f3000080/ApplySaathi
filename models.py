from extensions import db, bcrypt
from flask_login import UserMixin
from datetime import datetime
from sqlalchemy.sql import func

# ---------------- USER MODEL ---------------- #
class User(UserMixin, db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.String(36), unique=True, nullable=False)
    name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    phone = db.Column(db.String(15), nullable=False)
    password = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime, default=func.now())

    forms = db.relationship("FormApplication", backref="user", lazy=True)

    def set_password(self, password):
        self.password = bcrypt.generate_password_hash(password).decode("utf-8")

    def check_password(self, password):
        return bcrypt.check_password_hash(self.password, password)

class Admin(UserMixin, db.Model):
    __tablename__ = "admins"

    id = db.Column(db.Integer, primary_key=True)
    admin_id = db.Column(
        db.String(36),
        unique=True,
        nullable=False
    )
    name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(50), nullable=False)  # e.g., 'superadmin', 'admin'
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=func.now())

    # -------------------------
    # Password Methods
    # -------------------------

    def set_password(self, password):
        self.password_hash = bcrypt.generate_password_hash(password).decode("utf-8")

    def check_password(self, password):
        return bcrypt.check_password_hash(self.password_hash, password)


# ---------------- FORM MODEL ---------------- #
class FormApplication(db.Model):
    __tablename__ = "form_applications"

    id = db.Column(db.Integer, primary_key=True)
    form_type = db.Column(db.String(150), nullable=False)
    form_name = db.Column(db.String(150), nullable=False)
    description = db.Column(db.Text, nullable=True)
    status = db.Column(db.String(50), default="Inprocess") #Inprocess, Approved, Rejected, Completed
    message = db.Column(db.Text, nullable=True)
    payment_status = db.Column(db.String(50), default="Unpaid") # Unpaid, Paid, Failed
    created_at = db.Column(db.DateTime, default=func.now())

    filled_by_admin_id = db.Column(db.Integer, db.ForeignKey('admins.id'), nullable=True)

    payment_method = db.Column(db.String(100), nullable=True)
    transaction_id = db.Column(db.String(150), nullable=True)
    payment_screenshot = db.Column(db.String(255), nullable=True)

    # after apply recipt
    recipt = db.Column(db.String(255), nullable=True)

    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)

    documents = db.relationship("Document", backref="form", lazy=True)
    filled_by_admin = db.relationship('Admin', backref='filled_forms', lazy=True)


# ---------------- DOCUMENT MODEL ---------------- #
class Document(db.Model):
    __tablename__ = "documents"

    id = db.Column(db.Integer, primary_key=True)
    document_name = db.Column(db.String(150))
    file_path = db.Column(db.String(255))
    file_type = db.Column(db.String(100))
    document_size = db.Column(db.Integer)
    uploaded_at = db.Column(db.DateTime, default=func.now())

    form_id = db.Column(db.Integer, db.ForeignKey("form_applications.id"), nullable=False)

class Contact(db.Model):
    __tablename__ = "contacts"

    id = db.Column(db.Integer, primary_key=True)

    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), nullable=False)
    subject = db.Column(db.String(200), nullable=False)
    message = db.Column(db.Text, nullable=False)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f"<Contact {self.email}>"
    
