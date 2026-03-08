from flask_login import current_user
from flask import redirect, url_for 
from flask_admin import AdminIndexView
from flask_admin.contrib.sqla import ModelView
from flask_admin.menu import MenuLink
from .extensions import admin, db
from .models import User, Producto

AdminIndexView.extra_css = ["/static/admin_horizontal_static.css"]

class SecurityModelView(ModelView):
    column_exclude_list = ["password"]
    extra_css = ["/static/admin_horizontal_static.css"]
   
    def is_accessible(self):
        return current_user.is_authenticated

    def inaccessible_callback(self, name, **kwargs):
        return redirect(url_for("auth.login"))
    
    
def configuracion_admin():
    admin.add_view(SecurityModelView(User, db.session))
    admin.add_view(SecurityModelView(Producto, db.session))
    admin.add_link(MenuLink(name="Cerrar sesión", url="/logout"))
