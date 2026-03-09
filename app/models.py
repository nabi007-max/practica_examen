from flask_login import UserMixin
from .extensions import db
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime


class User(db.Model, UserMixin):
    __tablename__ = "user"

    id_usuario = db.Column(db.Integer, primary_key=True, autoincrement=True)
    nombre = db.Column(db.String(100))
    email = db.Column(db.String(100))
    password = db.Column(db.String(255), nullable = False)
    rol = db.Column(db.String(50))
    fecha_creacion = db.Column(db.DateTime, default=datetime.utcnow)

    @property
    def id(self):
        return self.id_usuario
    
    def set_password(self, password):
        self.password = generate_password_hash(password)
        
    def check_password(self, password):
        return check_password_hash(self.password, password)


class Producto(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(120), nullable=False)
    descripcion = db.Column(db.String(255), nullable=True)
    precio = db.Column(db.Numeric(10, 2), nullable=False)
    stock = db.Column(db.Integer, nullable=False, default=0)
