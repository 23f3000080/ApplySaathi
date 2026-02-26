from flask import Blueprint, render_template, redirect, url_for, request, flash, current_app, session
from flask_login import login_user, logout_user, login_required, current_user
from extensions import db
from models import User, FormApplication, Document, Contact, Admin
import os
from werkzeug.utils import secure_filename
from functools import wraps
import uuid

main = Blueprint("main", __name__)

UPLOAD_FOLDER = "static/uploads"

# generate 6char capital random user id
import uuid
def generate_user_id():
    return str(uuid.uuid4())[:6].upper()

# ---------------- HOME ---------------- #
@main.route("/")
def home():
    return render_template("home.html")


# ---------------- REGISTER ROUTE ---------------- #
@main.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        name = request.form.get("name")
        email = request.form.get("email")
        phone = request.form.get("phone")
        password = request.form.get("password")

        # --- Check if email already exists ---
        if User.query.filter_by(email=email).first():
            flash("Email already registered. Please login or use another email.", "warning")
            return redirect(url_for("main.register"))

        # --- Check if phone number already exists (optional) ---
        if User.query.filter_by(phone=phone).first():
            flash("Phone number already registered.", "warning")
            return redirect(url_for("main.register"))

        # --- Generate unique user_id ---
        user_id = generate_user_id()
        while User.query.filter_by(user_id=user_id).first():
            user_id = generate_user_id()

        # --- Create user instance ---
        user = User(name=name, email=email, phone=phone, user_id=user_id)
        user.set_password(password)  # Hash password

        # --- Add to database safely ---
        try:
            db.session.add(user)
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            flash("Something went wrong! Please try again.", "danger")
            print(e)
            return redirect(url_for("main.register"))

        flash("Account created successfully! Please login.", "success")
        return redirect(url_for("main.login"))

    return render_template("register.html")


# ---------------- LOGIN ---------------- #
@main.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form["email"]
        password = request.form["password"]

        if not email or not password:
            flash("Please enter both email and password", "warning")
            return redirect(url_for("main.login"))
        
        user = User.query.filter_by(email=email).first()
        admin = Admin.query.filter_by(email=email).first()

        if user and user.check_password(password):
            login_user(user)
            session["role"] = "user"
            flash("Logged in successfully!", "success")
            return redirect(url_for("main.dashboard"))

        elif admin and admin.check_password(password) and admin.is_active:
            login_user(admin)
            session["role"] = "admin"
            flash("Admin logged in successfully!", "success")
            return redirect(url_for("main.admin_dashboard"))

        else:
            flash("Invalid credentials", "danger")

    return render_template("login.html")

# ---------------- DASHBOARD ---------------- #
@main.route("/dashboard")
@login_required
def dashboard():
    forms = FormApplication.query.filter_by(user_id=current_user.id).all()
    return render_template("user_side/dashboard.html", forms=forms)

# contact us page
@main.route("/contact", methods=["GET", "POST"])
def contact():

    if request.method == "POST":

        name = request.form.get("name")
        email = request.form.get("email")
        subject = request.form.get("subject")
        message = request.form.get("message")

        # Save to database
        new_contact = Contact(
            name=name,
            email=email,
            subject=subject,
            message=message
        )

        db.session.add(new_contact)
        db.session.commit()

        flash("Your message has been sent successfully!", "success")

        return redirect(url_for("main.contact"))

    return render_template("contact.html")

# ---------------- LOGOUT ---------------- #
@main.route("/logout")
@login_required
def logout():
    session.pop("role", None)
    logout_user()
    flash("Logged out successfully", "success")
    return redirect(url_for("main.login"))

@main.route("/terms")
def terms():
    return render_template("terms.html")

@main.route("/privacy")
def privacy():
    return render_template("privacy_policy.html")

@main.route("/forgot-password", methods=["GET", "POST"])
def forgot_password():

    if request.method == "POST":
        email = request.form.get("email")

        user = User.query.filter_by(email=email).first()

        if user:
            # Redirect to reset page with email in session
            return redirect(url_for("main.reset_password_simple", email=email))
        else:
            flash("Email not found!", "danger")
            return redirect(url_for("main.forgot_password"))

    return render_template("forgot_password.html")

@main.route("/reset-password-simple/<email>", methods=["GET", "POST"])
def reset_password_simple(email):

    user = User.query.filter_by(email=email).first()

    if not user:
        flash("Invalid request.", "danger")
        return redirect(url_for("main.forgot_password"))

    if request.method == "POST":
        password = request.form.get("password")
        confirm = request.form.get("confirm_password")

        if password != confirm:
            flash("Passwords do not match!", "danger")
            return redirect(request.url)

        user.set_password(password)

        db.session.commit()

        flash("Password reset successfully. Please login.", "success")
        return redirect(url_for("main.login"))

    return render_template("reset_password.html", email=email)

# help page
@main.route("/help")
def help():
    return 'Help page'

@main.route("/apply-form", methods=["GET", "POST"])
@login_required
def apply_form():
    if request.method == "POST":
        try:
            # Get form data
            form_type = request.form.get("form_type")
            form_name = request.form.get("form_name")
            description = request.form.get("description", "").strip()

            # Validate required fields
            if not form_type or not form_name:
                flash("Please fill in all required fields.", "danger")
                return redirect(url_for("main.apply_form"))

            # Create form entry
            new_form = FormApplication(
                form_type=form_type,
                form_name=form_name,
                description=description,
                user_id=current_user.id,
                status="Inprocess",
            )

            db.session.add(new_form)
            db.session.flush()  # Get ID before commit

            # ✅ FIXED HERE
            files = request.files.getlist("documents")

            if not files or all(file.filename == "" for file in files):
                db.session.rollback()
                flash("Please upload at least one document.", "warning")
                return redirect(url_for("main.apply_form"))

            # Allowed types
            ALLOWED_TYPES = {"application/pdf", "image/jpeg", "image/png"}
            MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB

            upload_folder = os.path.join(
                current_app.root_path,
                "static",
                "uploads",
                "applications"
            )
            os.makedirs(upload_folder, exist_ok=True)

            uploaded_count = 0

            for file in files:
                if file and file.filename:

                    # Validate file type
                    if file.content_type not in ALLOWED_TYPES:
                        db.session.rollback()
                        flash("Invalid file type uploaded.", "danger")
                        return redirect(url_for("main.apply_form"))

                    # Validate file size
                    file.seek(0, os.SEEK_END)
                    file_size = file.tell()
                    file.seek(0)

                    if file_size > MAX_FILE_SIZE:
                        db.session.rollback()
                        flash("File exceeds maximum size of 10MB.", "danger")
                        return redirect(url_for("main.apply_form"))

                    original_filename = secure_filename(file.filename)
                    extension = os.path.splitext(original_filename)[1]
                    unique_filename = f"{uuid.uuid4().hex}{extension}"

                    file_path = os.path.join(upload_folder, unique_filename)
                    file.save(file_path)

                    document = Document(
                        document_name=original_filename,
                        file_path=f"uploads/applications/{unique_filename}",
                        document_size=file_size,
                        file_type=file.content_type,
                        form_id=new_form.id,
                    )

                    db.session.add(document)
                    uploaded_count += 1

            db.session.commit()

            flash(
                f"Application submitted successfully! {uploaded_count} document(s) uploaded.",
                "success",
            )

            return redirect(url_for("main.dashboard"))

        except Exception as e:
            db.session.rollback()

            # Log error instead of exposing
            current_app.logger.error(f"Application Error: {e}")

            flash("Something went wrong. Please try again.", "danger")
            return redirect(url_for("main.apply_form"))

    return render_template("user_side/formApply.html")

# cancel application route
@main.route("/cancel-application/<int:form_id>", methods=["POST"])
@login_required
def cancel_application(form_id):
    form = FormApplication.query.filter_by(id=form_id, user_id=current_user.id).first()

    if not form:
        flash("Application not found.", "danger")
        return redirect(url_for("main.dashboard"))

    if form.status in ["Approved", "Rejected", "Completed"]:
        flash("Cannot cancel an application that is already processed.", "warning")
        return redirect(url_for("main.dashboard"))

    form.status = "Cancelled"
    form.payment_status = "Refund will be processed" if form.payment_status == "Paid" or form.payment_status == 'Pending Verification' else form.payment_status
    db.session.commit()
    flash("Application cancelled successfully.", "success")
    return redirect(url_for("main.dashboard"))

# view application details route
@main.route("/application/<int:form_id>")
@login_required
def view_application(form_id):
    form = FormApplication.query.filter_by(id=form_id, user_id=current_user.id).first()

    if not form:
        flash("Application not found.", "danger")
        return redirect(url_for("main.dashboard"))

    documents = Document.query.filter_by(form_id=form.id).all()
    return render_template("user_side/application_details.html", form=form, documents=documents)

@main.route("/mark-payment/<int:form_id>")
@login_required
def mark_payment_done(form_id):

    form = FormApplication.query.filter_by(
        id=form_id,
        user_id=current_user.id
    ).first()

    if not form:
        flash("Application not found.", "danger")
        return redirect(url_for("main.dashboard"))

    form.payment_status = "Paid"
    db.session.commit()

    flash("Payment marked as completed. We will verify shortly.", "success")
    return redirect(url_for("main.view_application", form_id=form.id))

@main.route("/submit-payment/<int:form_id>", methods=["POST"])
@login_required
def submit_payment(form_id):

    form = FormApplication.query.filter_by(
        id=form_id,
        user_id=current_user.id
    ).first()

    if not form:
        flash("Application not found.", "danger")
        return redirect(url_for("main.dashboard"))

    payment_method = request.form.get("payment_method")
    transaction_id = request.form.get("transaction_id")
    screenshot = request.files.get("payment_screenshot")

    screenshot_path = None

    if screenshot and screenshot.filename:
        filename = secure_filename(screenshot.filename)
        unique_name = f"{uuid.uuid4().hex}_{filename}"

        upload_folder = os.path.join(
            current_app.root_path,
            "static",
            "uploads",
            "payments"
        )
        os.makedirs(upload_folder, exist_ok=True)

        file_path = os.path.join(upload_folder, unique_name)
        screenshot.save(file_path)

        screenshot_path = f"uploads/payments/{unique_name}"

    # Save payment details (add columns if not exists)
    form.payment_status = "Pending Verification"
    form.payment_method = payment_method
    form.transaction_id = transaction_id
    form.payment_screenshot = screenshot_path

    db.session.commit()

    flash("Payment submitted successfully. Awaiting verification.", "success")
    return redirect(url_for("main.view_application", form_id=form.id))

@main.route("/profile")
@login_required
def profile():
    return render_template("user_side/profile.html")


@main.route("/update-profile", methods=["POST"])
@login_required
def update_profile():

    name = request.form.get("name")
    email = request.form.get("email")
    phone = request.form.get("phone")

    current_password = request.form.get("current_password")
    new_password = request.form.get("new_password")
    confirm_password = request.form.get("confirm_password")

    # -------- Basic Validation --------
    if not name or not email or not phone:
        flash("All basic fields are required.", "danger")
        return redirect(url_for("main.profile"))

    # -------- Email Uniqueness Check --------
    existing_user = User.query.filter(
        User.email == email,
        User.id != current_user.id
    ).first()

    if existing_user:
        flash("Email already exists. Please use another email.", "danger")
        return redirect(url_for("main.profile"))

    # -------- Update Basic Info --------
    current_user.name = name
    current_user.email = email
    current_user.phone = phone

    # -------- Password Change Logic --------
    if new_password or confirm_password:

        # Require current password
        if not current_password:
            flash("Current password is required to change password.", "danger")
            return redirect(url_for("main.profile"))

        # Check current password correctness
        if not current_user.check_password(current_password):
            flash("Current password is incorrect.", "danger")
            return redirect(url_for("main.profile"))

        # Check new password match
        if new_password != confirm_password:
            flash("New passwords do not match.", "danger")
            return redirect(url_for("main.profile"))

        # Optional: minimum password length
        if len(new_password) < 6:
            flash("Password must be at least 6 characters long.", "danger")
            return redirect(url_for("main.profile"))

        # Set new password using bcrypt
        current_user.set_password(new_password)

    db.session.commit()

    flash("Profile updated successfully!", "success")
    return redirect(url_for("main.profile"))

# ---------------- ADMIN DECORATOR ---------------- #
def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):

        # Not logged in
        if not current_user.is_authenticated:
            return redirect(url_for('main.login'))

        # Check if this user is Admin model
        if current_user.__class__.__name__ != "Admin":
            flash("Unauthorized access", "danger")
            return redirect(url_for('main.home'))

        # Admin is inactive
        if not current_user.is_active:
            flash("Admin account disabled", "danger")
            return redirect(url_for('main.home'))

        return f(*args, **kwargs)

    return decorated_function

# ---------------- ADMIN DASHBOARD ---------------- #
@main.route("/admin/dashboard")
@login_required
@admin_required
def admin_dashboard():

    total_users = User.query.count()
    total_applications = FormApplication.query.count()
    total_admins = Admin.query.count()

    filled_by_me = FormApplication.query.filter_by(
        filled_by_admin_id=current_user.id
    ).count()

    recent_applications = FormApplication.query.order_by(
        FormApplication.created_at.desc()
    ).limit(10).all()

    # pending forms
    pending_applications = FormApplication.query.filter_by(status="Inprocess").count()

    return render_template(
        "admin_side/admin_dashboard.html",
        total_users=total_users,
        total_applications=total_applications,
        total_admins=total_admins,
        filled_by_me=filled_by_me,
        recent_applications=recent_applications,
        pending_applications=pending_applications
    )

# manage_applications route
from sqlalchemy import or_

@main.route("/admin/manage-applications")
@login_required
@admin_required
def manage_applications():

    status = request.args.get("status", "All")
    search = request.args.get("search", "")
    page = request.args.get("page", 1, type=int)

    query = FormApplication.query.join(FormApplication.user)

    # 🔎 Filter by Status
    if status != "All":
        query = query.filter(FormApplication.status == status)

    # 🔍 Search by User Name or Form Name
    if search:
        query = query.filter(
            or_(
                FormApplication.form_name.ilike(f"%{search}%"),
                User.name.ilike(f"%{search}%")
            )
        )

    # 📄 Pagination (10 per page)
    forms = query.order_by(FormApplication.created_at.desc()) \
                 .paginate(page=page, per_page=10)

    return render_template(
        "admin_side/manage_applications.html",
        forms=forms,
        selected_status=status,
        search=search
    )

# manage_users route
@main.route("/admin/manage-users")
@login_required
@admin_required
def manage_users():

    search = request.args.get("search", "")
    page = request.args.get("page", 1, type=int)

    query = User.query

    # 🔍 Search by name or email
    if search:
        query = query.filter(
            or_(
                User.name.ilike(f"%{search}%"),
                User.email.ilike(f"%{search}%")
            )
        )

    users = query.order_by(User.created_at.desc()) \
                 .paginate(page=page, per_page=10)

    return render_template(
        "admin_side/manage_users.html",
        users=users,
        search=search
    )

#manage_admins
@main.route("/manage-admins")
@login_required
@admin_required
def manage_admins():
    admins = Admin.query.order_by(Admin.created_at.desc()).all()
    return render_template("admin_side/manage_admins.html", admins=admins)

@main.route("/toggle-admin/<int:admin_id>")
@login_required
@admin_required
def toggle_admin_status(admin_id):
    admin = Admin.query.get_or_404(admin_id)

    if admin.role == "superadmin":
        flash("Superadmin cannot be deactivated.", "danger")
        return redirect(url_for("main.manage_admins"))

    admin.is_active = not admin.is_active
    db.session.commit()

    flash("Admin status updated.", "success")
    return redirect(url_for("main.manage_admins"))


@main.route("/delete-admin/<int:admin_id>")
@login_required
@admin_required
def delete_admin(admin_id):
    admin = Admin.query.get_or_404(admin_id)

    if admin.role == "superadmin":
        flash("Superadmin cannot be deleted.", "danger")
        return redirect(url_for("main.manage_admins"))

    db.session.delete(admin)
    db.session.commit()

    flash("Admin deleted successfully.", "success")
    return redirect(url_for("main.manage_admins"))

# generate 6 char capital random admin id
def generate_admin_id():
    return str(uuid.uuid4())[:6].upper()

# add admin route
@main.route("/admin/add-admin", methods=["GET", "POST"])
@login_required
@admin_required
def add_admin():
    if request.method == "POST":
        name = request.form.get("name")
        email = request.form.get("email")
        password = request.form.get("password")
        role = request.form.get("role")

        if not name or not email or not password or not role:
            flash("All fields are required.", "danger")
            return redirect(url_for("main.add_admin"))

        if Admin.query.filter_by(email=email).first():
            flash("Email already registered for another admin.", "danger")
            return redirect(url_for("main.add_admin"))

        admin_id = generate_admin_id()
        while Admin.query.filter_by(admin_id=admin_id).first():
            admin_id = generate_admin_id()

        new_admin = Admin(name=name, email=email, role=role, admin_id=admin_id)
        new_admin.set_password(password)

        db.session.add(new_admin)
        db.session.commit()

        flash("Admin added successfully!", "success")
        return redirect(url_for("main.manage_admins"))

    return render_template("admin_side/add_admin.html")

# admin_profile
@main.route("/admin/profile", methods=["GET", "POST"])
@login_required
@admin_required
def admin_profile():

    admin = current_user  # since admin is logged in

    if request.method == "POST":

        name = request.form.get("name")
        email = request.form.get("email")

        admin.name = name
        admin.email = email

        db.session.commit()
        flash("Profile updated successfully!", "success")

        return redirect(url_for("main.admin_profile"))

    return render_template("admin_side/admin_profile.html", admin=admin)

# admin appearance settings
@main.route("/admin/appearance-settings")
@login_required
@admin_required
def appearance_settings():
    return render_template("admin_side/ui_settings.html")

# admin change password
@main.route("/admin/change-password", methods=["POST"])
@login_required
@admin_required
def admin_change_password():

    admin = current_user

    current_password = request.form.get("current_password")
    new_password = request.form.get("new_password")
    confirm_password = request.form.get("confirm_password")

    if not admin.check_password(current_password):
        flash("Current password is incorrect!", "danger")
        return redirect(url_for("main.admin_profile"))

    if new_password != confirm_password:
        flash("New passwords do not match!", "danger")
        return redirect(url_for("main.admin_profile"))

    admin.set_password(new_password)
    db.session.commit()

    flash("Password changed successfully!", "success")
    return redirect(url_for("main.admin_profile"))

# admin_view_application
@main.route("/admin/application/<int:app_id>")
@login_required
@admin_required
def admin_view_application(app_id):
    app = FormApplication.query.get_or_404(app_id)
    return render_template("admin_side/view_application.html", application=app)

@main.route("/admin/application/<int:id>/update", methods=["POST"])
@login_required
@admin_required
def update_application_status(id):

    message = request.form.get("message", "").strip()
    application = FormApplication.query.get_or_404(id)

    action = request.form.get("action")

    if action in ["Approved", "Rejected"]:
        application.status = action
        application.message = message
        db.session.commit()
        flash(f"Application {action} successfully!", "success")

    return redirect(url_for("main.admin_view_application", app_id=id))

ALLOWED_EXTENSIONS = {"pdf", "jpg", "jpeg", "png"}

def allowed_file(filename):
    return "." in filename and \
           filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


@main.route("/admin/application/<int:id>/upload-receipt", methods=["POST"])
@login_required
@admin_required
def upload_receipt(id):

    application = FormApplication.query.get_or_404(id)

    file = request.files.get("receipt")

    if not file or file.filename == "":
        flash("No file selected", "danger")
        return redirect(url_for("main.admin_view_application", app_id=id))

    if not allowed_file(file.filename):
        flash("Invalid file type. Only PDF, JPG, PNG allowed.", "danger")
        return redirect(url_for("main.admin_view_application", app_id=id))

    # Secure original filename
    original_filename = secure_filename(file.filename)

    # Generate unique filename (prevents overwrite)
    unique_name = f"{uuid.uuid4().hex}_{original_filename}"

    # Absolute folder path (for saving)
    upload_folder = os.path.join(current_app.static_folder, "receipts")
    os.makedirs(upload_folder, exist_ok=True)

    absolute_path = os.path.join(upload_folder, unique_name)

    # Save file
    file.save(absolute_path)

    # 🔥 IMPORTANT: Store URL-safe relative path (forward slash only)
    relative_path = f"receipts/{unique_name}"

    # Update database
    application.recipt = relative_path
    application.status = "Completed"
    application.filled_by_admin_id = current_user.id

    db.session.commit()

    flash("Receipt uploaded successfully!", "success")

    return redirect(url_for("main.admin_view_application", app_id=id))

@main.route("/admin/application/<int:id>/toggle-payment", methods=["POST"])
@login_required
@admin_required
def toggle_payment_status(id):

    application = FormApplication.query.get_or_404(id)

    if application.payment_status == "Paid":
        application.payment_status = "Unpaid"
        flash("Payment marked as Unpaid.", "warning")
    else:
        application.payment_status = "Paid"
        flash("Payment marked as Paid.", "success")

    db.session.commit()

    return redirect(url_for("main.admin_view_application", app_id=id))

@main.route("/admin/user/<int:user_id>")
@login_required
@admin_required
def admin_view_user(user_id):

    user = User.query.get_or_404(user_id)

    forms = FormApplication.query \
        .filter_by(user_id=user.id) \
        .order_by(FormApplication.created_at.desc()) \
        .all()

    # Stats
    total_forms = len(forms)
    approved = len([f for f in forms if f.status == "Approved"])
    rejected = len([f for f in forms if f.status == "Rejected"])
    inprocess = len([f for f in forms if f.status == "Inprocess"])
    completed = len([f for f in forms if f.status == "Completed"])

    return render_template(
        "admin_side/view_user.html",
        user=user,
        forms=forms,
        total_forms=total_forms,
        approved=approved,
        rejected=rejected,
        inprocess=inprocess,
        completed=completed
    )