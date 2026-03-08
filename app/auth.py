from flask import Blueprint, redirect, url_for, render_template, request, current_app
from flask_login import login_required, login_user, logout_user
from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired
from .models import User
from .extensions import login_manager, db
auth_bp = Blueprint("auth", __name__)


def _get_reset_serializer():
    return URLSafeTimedSerializer(current_app.config["SECRET_KEY"])


def _generate_reset_token(email):
    serializer = _get_reset_serializer()
    return serializer.dumps(email, salt="password-reset")


def _read_reset_token(token, max_age=3600):
    serializer = _get_reset_serializer()
    return serializer.loads(token, salt="password-reset", max_age=max_age)

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(user_id)

@auth_bp.route('/')
def inicio():
    return redirect(url_for('auth.login'))

@auth_bp.route('/login', methods = ['GET','POST']) 
def login():
    if request.method == "POST":
        usuario = User.query.filter_by(
            nombre = request.form.get("nombreusuario")
        ).first()
        
        if usuario and usuario.check_password(request.form.get("contrasenia")):
            login_user(usuario)
            return redirect("/admin")
    
    return render_template("login.html")


@auth_bp.route('/recuperar', methods=['GET', 'POST'])
def recuperar_password():
    reset_link = None
    mensaje = None

    if request.method == "POST":
        email = request.form.get("email", "").strip()
        usuario = User.query.filter_by(email=email).first()

        if usuario:
            token = _generate_reset_token(usuario.email)
            reset_link = url_for("auth.restablecer_password", token=token, _external=True)
            mensaje = "Se generó un enlace de recuperación."
        else:
            mensaje = "No existe un usuario con ese correo."

    return render_template("forgot_password.html", reset_link=reset_link, mensaje=mensaje)


@auth_bp.route('/restablecer/<token>', methods=['GET', 'POST'])
def restablecer_password(token):
    error = None

    try:
        email = _read_reset_token(token)
    except SignatureExpired:
        return render_template("reset_password.html", token_valido=False, error="El enlace expiró.")
    except BadSignature:
        return render_template("reset_password.html", token_valido=False, error="El enlace no es válido.")

    usuario = User.query.filter_by(email=email).first()
    if not usuario:
        return render_template("reset_password.html", token_valido=False, error="Usuario no encontrado.")

    if request.method == "POST":
        password = request.form.get("password", "")
        password_confirm = request.form.get("password_confirm", "")

        if not password:
            error = "La contraseña es obligatoria."
        elif password != password_confirm:
            error = "Las contraseñas no coinciden."
        else:
            usuario.set_password(password)
            db.session.commit()
            return redirect(url_for("auth.login"))

    return render_template("reset_password.html", token_valido=True, error=error)


@auth_bp.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for("auth.login"))
