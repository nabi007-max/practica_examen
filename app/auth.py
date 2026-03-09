from decimal import Decimal
﻿from decimal import Decimal
from io import BytesIO

from flask import (
    Blueprint,
    abort,
    current_app,
    redirect,
    render_template,
    request,
    send_file,
    url_for,
)
from flask_login import login_required, login_user, logout_user
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

from .extensions import db, login_manager
from .models import User, Venta

auth_bp = Blueprint("auth", __name__)


def _get_reset_serializer():
    return URLSafeTimedSerializer(current_app.config["SECRET_KEY"])


def _generate_reset_token(email):
    serializer = _get_reset_serializer()
    return serializer.dumps(email, salt="password-reset")


def _read_reset_token(token, max_age=3600):
    serializer = _get_reset_serializer()
    return serializer.loads(token, salt="password-reset", max_age=max_age)

def _fmt_money(value):
    return f"{Decimal(value or 0):.2f}"


def _fmt_money(value):
    return f"{Decimal(value or 0):.2f}"


def _build_venta_pdf(venta):
    from reportlab.lib.pagesizes import letter
    from reportlab.pdfgen import canvas

    buffer = BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=letter)
    width, height = letter

    y = height - 50
    pdf.setFont("Helvetica-Bold", 14)
    pdf.drawString(50, y, "Comprobante de Venta")

    y -= 30
    pdf.setFont("Helvetica", 11)
    pdf.drawString(50, y, f"Venta ID: {venta.id}")
    y -= 18
    pdf.drawString(50, y, f"Fecha: {venta.fecha.strftime('%Y-%m-%d %H:%M:%S')}")
    y -= 18
    pdf.drawString(50, y, f"Cliente: {venta.cliente_nombre}")
    y -= 18
    pdf.drawString(50, y, f"Vendedor: {venta.usuario.nombre if venta.usuario else '-'}")

    y -= 28
    pdf.setFont("Helvetica-Bold", 10)
    pdf.drawString(50, y, "Producto")
    pdf.drawString(300, y, "Cant.")
    pdf.drawString(360, y, "P. Unit.")
    pdf.drawString(460, y, "Subtotal")

    y -= 14
    pdf.line(50, y, 550, y)
    y -= 16

    pdf.setFont("Helvetica", 10)
    detalles = sorted(venta.detalles, key=lambda d: d.id or 0)
    for detalle in detalles:
        if y < 80:
            pdf.showPage()
            y = height - 50
            pdf.setFont("Helvetica-Bold", 10)
            pdf.drawString(50, y, "Producto")
            pdf.drawString(300, y, "Cant.")
            pdf.drawString(360, y, "P. Unit.")
            pdf.drawString(460, y, "Subtotal")
            y -= 14
            pdf.line(50, y, 550, y)
            y -= 16
            pdf.setFont("Helvetica", 10)

        nombre_producto = detalle.producto.nombre if detalle.producto else "Producto"
        pdf.drawString(50, y, nombre_producto[:45])
        pdf.drawRightString(340, y, str(detalle.cantidad))
        pdf.drawRightString(430, y, _fmt_money(detalle.precio_unitario))
        pdf.drawRightString(540, y, _fmt_money(detalle.subtotal))
        y -= 16

    y -= 6
    pdf.line(360, y, 550, y)
    y -= 18
    pdf.setFont("Helvetica-Bold", 11)
    pdf.drawRightString(500, y, "TOTAL:")
    pdf.drawRightString(540, y, _fmt_money(venta.total))

    pdf.showPage()
    pdf.save()
    buffer.seek(0)
    return buffer


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(user_id)


@auth_bp.route("/")
def inicio():
    return redirect(url_for("auth.login"))


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    login_error = None

@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        usuario = User.query.filter_by(nombre=request.form.get("nombreusuario")).first()

        if usuario and usuario.check_password(request.form.get("contrasenia")):
            login_user(usuario)
            return redirect("/admin")

    return render_template("login.html")
        nombreusuario = request.form.get("nombreusuario", "").strip()
        contrasenia = request.form.get("contrasenia", "")
        usuario = User.query.filter_by(
            nombre=nombreusuario
        ).first()
        
        if usuario and usuario.check_password(contrasenia):
            login_user(usuario)
            return redirect("/admin")

    return render_template("login.html")


@auth_bp.route("/registro", methods=["POST"])
def registro():
    nombre = request.form.get("nuevo_nombre", "").strip()
    email = request.form.get("nuevo_email", "").strip()
    password = request.form.get("nuevo_password", "")
    password_confirm = request.form.get("nuevo_password_confirm", "")

    if not nombre or not email or not password or not password_confirm:
        return render_template("login.html", registro_error="Todos los campos son obligatorios.")

    if password != password_confirm:
        return render_template("login.html", registro_error="Las contrasenas no coinciden.")

    if User.query.filter_by(nombre=nombre).first():
        return render_template("login.html", registro_error="El nombre de usuario ya existe.")

    if User.query.filter_by(email=email).first():
        return render_template("login.html", registro_error="El correo ya esta registrado.")

    usuario = User(nombre=nombre, email=email, rol="usuario")
    usuario.set_password(password)
    db.session.add(usuario)
    db.session.commit()

    return render_template("login.html", registro_ok="Cuenta creada correctamente. Ya puedes iniciar sesion.")


@auth_bp.route("/recuperar", methods=["GET", "POST"])
def recuperar_password():
    reset_link = None
    mensaje = None

    if request.method == "POST":
        email = request.form.get("email", "").strip()
        usuario = User.query.filter_by(email=email).first()

        if usuario:
            token = _generate_reset_token(usuario.email)
            reset_link = url_for("auth.restablecer_password", token=token, _external=True)
            mensaje = "Se genero un enlace de recuperacion."
        else:
            mensaje = "No existe un usuario con ese correo."

    return render_template("forgot_password.html", reset_link=reset_link, mensaje=mensaje)


@auth_bp.route("/restablecer/<token>", methods=["GET", "POST"])
def restablecer_password(token):
    error = None

    try:
        email = _read_reset_token(token)
    except SignatureExpired:
        return render_template("reset_password.html", token_valido=False, error="El enlace expiro.")
    except BadSignature:
        return render_template("reset_password.html", token_valido=False, error="El enlace no es valido.")

    usuario = User.query.filter_by(email=email).first()
    if not usuario:
        return render_template("reset_password.html", token_valido=False, error="Usuario no encontrado.")

    if request.method == "POST":
        password = request.form.get("password", "")
        password_confirm = request.form.get("password_confirm", "")

        if not password:
            error = "La contrasena es obligatoria."
        elif password != password_confirm:
            error = "Las contrasenas no coinciden."
        else:
            usuario.set_password(password)
            db.session.commit()
            return redirect(url_for("auth.login"))

    return render_template("reset_password.html", token_valido=True, error=error)


@auth_bp.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("auth.login"))


@auth_bp.route("/ventas/<int:venta_id>/pdf")
@login_required
def venta_pdf(venta_id):
    venta = Venta.query.get_or_404(venta_id)
    try:
        pdf_buffer = _build_venta_pdf(venta)
    except ImportError:
        abort(500, description="Falta instalar reportlab para generar PDF.")

    return send_file(
        pdf_buffer,
        mimetype="application/pdf",
        as_attachment=True,
        download_name=f"comprobante_venta_{venta.id}.pdf",
    )
