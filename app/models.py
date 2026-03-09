from datetime import datetime
﻿from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP

from flask_login import UserMixin
from sqlalchemy import event, func, inspect, select, update
from sqlalchemy.orm import Session

from .extensions import db
from werkzeug.security import generate_password_hash, check_password_hash


class User(db.Model, UserMixin):
    __tablename__ = "user"

    id_usuario = db.Column(db.Integer, primary_key=True, autoincrement=True)
    nombre = db.Column(db.String(100))
    email = db.Column(db.String(100))
    password = db.Column(db.String(255), nullable=False)
    rol = db.Column(db.String(50))
    fecha_creacion = db.Column(db.DateTime, default=datetime.utcnow)

    @property
    def id(self):
        return self.id_usuario

    def set_password(self, password):
        self.password = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password, password)

    def __str__(self):
        return self.nombre or f"Usuario {self.id_usuario}"

        return self.nombre

class Producto(db.Model):
    __tablename__ = "producto"

    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(120), nullable=False)
    descripcion = db.Column(db.String(255), nullable=True)
    precio = db.Column(db.Numeric(10, 2), nullable=False)
    stock = db.Column(db.Integer, nullable=False, default=0)

    def __str__(self):
        return f"{self.nombre} (Precio: {self.precio})"


class Venta(db.Model):
    __tablename__ = "venta"

    id = db.Column(db.Integer, primary_key=True)
    fecha = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    cliente_nombre = db.Column(db.String(120), nullable=False)
    usuario_id = db.Column(db.Integer, db.ForeignKey("user.id_usuario"), nullable=False)
    estado = db.Column(db.String(20), nullable=False, default="borrador")
    fecha_confirmacion = db.Column(db.DateTime, nullable=True)
    total = db.Column(db.Numeric(10, 2), nullable=False, default=0)

    usuario = db.relationship("User", backref=db.backref("ventas", lazy=True))
    detalles = db.relationship(
        "DetalleVenta",
        back_populates="venta",
        cascade="all, delete-orphan",
        lazy=True,
    )

    def __str__(self):
        return f"Venta #{self.id} - {self.cliente_nombre} [{self.estado}]"


class DetalleVenta(db.Model):
    __tablename__ = "detalle_venta"

    id = db.Column(db.Integer, primary_key=True)
    venta_id = db.Column(db.Integer, db.ForeignKey("venta.id"), nullable=False)
    producto_id = db.Column(db.Integer, db.ForeignKey("producto.id"), nullable=False)
    cantidad = db.Column(db.Integer, nullable=False, default=1)
    precio_unitario = db.Column(db.Numeric(10, 2), nullable=False)
    subtotal = db.Column(db.Numeric(10, 2), nullable=False)

    venta = db.relationship("Venta", back_populates="detalles")
    producto = db.relationship("Producto", backref=db.backref("detalles_venta", lazy=True))

    def __str__(self):
        return f"Detalle #{self.id} (Venta #{self.venta_id})"


def _to_decimal(value):
    return Decimal(value or 0).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def _get_venta_id(detalle):
    if detalle.venta_id is not None:
        return int(detalle.venta_id)
    if detalle.venta is not None and detalle.venta.id is not None:
        return int(detalle.venta.id)
    return None


def _history_id(history, fallback=None):
    if history is None:
        return fallback

    values = history if isinstance(history, list) else [history]
    for value in values:
        if value is None:
            continue
        if hasattr(value, "id"):
            if value.id is not None:
                return int(value.id)
            continue
        return int(value)
    return fallback


@event.listens_for(Session, "before_flush")
def _calcular_detalles_y_marcar_ventas(session, flush_context, instances):
    venta_ids = session.info.setdefault("recalcular_venta_ids", set())

    for obj in session.new:
        if isinstance(obj, DetalleVenta):
            if obj.producto is not None:
                obj.precio_unitario = _to_decimal(obj.producto.precio)
            obj.subtotal = _to_decimal(obj.cantidad) * _to_decimal(obj.precio_unitario)
            venta_id = _get_venta_id(obj)
            if venta_id is not None:
                venta_ids.add(venta_id)

    for obj in session.dirty:
        if isinstance(obj, DetalleVenta):
            if obj.producto is not None:
                obj.precio_unitario = _to_decimal(obj.producto.precio)
            obj.subtotal = _to_decimal(obj.cantidad) * _to_decimal(obj.precio_unitario)

            state = inspect(obj)
            venta_hist = state.attrs.venta_id.history
            venta_rel_hist = state.attrs.venta.history
            current_venta_id = _get_venta_id(obj)

            if venta_hist.has_changes():
                for old_id in venta_hist.deleted:
                    if old_id is not None:
                        venta_ids.add(old_id)
                for new_id in venta_hist.added:
                    if new_id is not None:
                        venta_ids.add(new_id)
            elif venta_rel_hist.has_changes():
                old_rel_id = _history_id(venta_rel_hist.deleted)
                new_rel_id = _history_id(venta_rel_hist.added)
                if old_rel_id is not None:
                    venta_ids.add(old_rel_id)
                if new_rel_id is not None:
                    venta_ids.add(new_rel_id)
            elif current_venta_id is not None:
                venta_ids.add(current_venta_id)

    for obj in session.deleted:
        if isinstance(obj, DetalleVenta):
            venta_id = _get_venta_id(obj)
            if venta_id is not None:
                venta_ids.add(venta_id)


@event.listens_for(Session, "after_flush_postexec")
def _recalcular_total_venta(session, flush_context):
    venta_ids = session.info.pop("recalcular_venta_ids", set())
    if not venta_ids:
        return

    for venta_id in venta_ids:
        total_query = (
            select(func.coalesce(func.sum(DetalleVenta.subtotal), 0))
            .where(DetalleVenta.venta_id == venta_id)
            .scalar_subquery()
        )
        session.execute(
            update(Venta)
            .where(Venta.id == venta_id)
            .values(total=total_query)
        )
# Relación con la tabla de ventas
class Venta(db.Model):
    __tablename__ = "venta"

    id = db.Column(db.Integer, primary_key=True)
    fecha = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    cliente_nombre = db.Column(db.String(120), nullable=False)
    usuario_id = db.Column(db.Integer, db.ForeignKey("user.id_usuario"), nullable=False)
    estado = db.Column(db.String(20), nullable=False, default="borrador")
    fecha_confirmacion = db.Column(db.DateTime, nullable=True)
    total = db.Column(db.Numeric(10, 2), nullable=False, default=0)

    usuario = db.relationship("User", backref=db.backref("ventas", lazy=True))
    detalles = db.relationship(
        "DetalleVenta",
        back_populates="venta",
        cascade="all, delete-orphan",
        lazy=True,
    )

    def __str__(self):
        return f"Venta #{self.id} - {self.cliente_nombre} [{self.estado}]"

class DetalleVenta(db.Model):
    __tablename__ = "detalle_venta"

    id = db.Column(db.Integer, primary_key=True)
    venta_id = db.Column(db.Integer, db.ForeignKey("venta.id"), nullable=False)
    producto_id = db.Column(db.Integer, db.ForeignKey("producto.id"), nullable=False)
    cantidad = db.Column(db.Integer, nullable=False, default=1)
    precio_unitario = db.Column(db.Numeric(10, 2), nullable=False)
    subtotal = db.Column(db.Numeric(10, 2), nullable=False)

    venta = db.relationship("Venta", back_populates="detalles")
    producto = db.relationship("Producto", backref=db.backref("detalles_venta", lazy=True))

    def __str__(self):
        return f"Detalle #{self.id} (Venta #{self.venta_id})"


def _to_decimal(value):
    return Decimal(value or 0).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def _get_venta_id(detalle):
    if detalle.venta_id is not None:
        return int(detalle.venta_id)
    if detalle.venta is not None and detalle.venta.id is not None:
        return int(detalle.venta.id)
    return None


def _history_id(history, fallback=None):
    if history is None:
        return fallback

    values = history if isinstance(history, list) else [history]
    for value in values:
        if value is None:
            continue
        if hasattr(value, "id"):
            if value.id is not None:
                return int(value.id)
            continue
        return int(value)
    return fallback


@event.listens_for(Session, "before_flush")
def _calcular_detalles_y_marcar_ventas(session, flush_context, instances):
    venta_ids = session.info.setdefault("recalcular_venta_ids", set())

    for obj in session.new:
        if isinstance(obj, DetalleVenta):
            if obj.producto is not None:
                obj.precio_unitario = _to_decimal(obj.producto.precio)
            obj.subtotal = _to_decimal(obj.cantidad) * _to_decimal(obj.precio_unitario)
            venta_id = _get_venta_id(obj)
            if venta_id is not None:
                venta_ids.add(venta_id)

    for obj in session.dirty:
        if isinstance(obj, DetalleVenta):
            if obj.producto is not None:
                obj.precio_unitario = _to_decimal(obj.producto.precio)
            obj.subtotal = _to_decimal(obj.cantidad) * _to_decimal(obj.precio_unitario)

            state = inspect(obj)
            venta_hist = state.attrs.venta_id.history
            venta_rel_hist = state.attrs.venta.history
            current_venta_id = _get_venta_id(obj)

            if venta_hist.has_changes():
                for old_id in venta_hist.deleted:
                    if old_id is not None:
                        venta_ids.add(old_id)
                for new_id in venta_hist.added:
                    if new_id is not None:
                        venta_ids.add(new_id)
            elif venta_rel_hist.has_changes():
                old_rel_id = _history_id(venta_rel_hist.deleted)
                new_rel_id = _history_id(venta_rel_hist.added)
                if old_rel_id is not None:
                    venta_ids.add(old_rel_id)
                if new_rel_id is not None:
                    venta_ids.add(new_rel_id)
            elif current_venta_id is not None:
                venta_ids.add(current_venta_id)

    for obj in session.deleted:
        if isinstance(obj, DetalleVenta):
            venta_id = _get_venta_id(obj)
            if venta_id is not None:
                venta_ids.add(venta_id)


@event.listens_for(Session, "after_flush_postexec")
def _recalcular_total_venta(session, flush_context):
    venta_ids = session.info.pop("recalcular_venta_ids", set())
    if not venta_ids:
        return

    for venta_id in venta_ids:
        total_query = (
            select(func.coalesce(func.sum(DetalleVenta.subtotal), 0))
            .where(DetalleVenta.venta_id == venta_id)
            .scalar_subquery()
        )
        session.execute(
            update(Venta)
            .where(Venta.id == venta_id)
            .values(total=total_query)
        )