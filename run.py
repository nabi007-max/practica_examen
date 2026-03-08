from app import create_app
from app.extensions import db
from app.models import User
from sqlalchemy import inspect, text

app = create_app()


def sync_user_table_schema():
    inspector = inspect(db.engine)

    if not inspector.has_table("user"):
        return

    columns = {column["name"] for column in inspector.get_columns("user")}
    statements = []

    if "id" in columns and "id_usuario" not in columns:
        statements.append(
            "ALTER TABLE `user` CHANGE id id_usuario INT NOT NULL AUTO_INCREMENT"
        )
    if "username" in columns and "nombre" not in columns:
        statements.append(
            "ALTER TABLE `user` CHANGE username nombre VARCHAR(100)"
        )
    if "role" in columns and "rol" not in columns:
        statements.append(
            "ALTER TABLE `user` CHANGE role rol VARCHAR(50)"
        )
    if "email" not in columns:
        statements.append("ALTER TABLE `user` ADD COLUMN email VARCHAR(100)")
    if "fecha_creacion" not in columns:
        statements.append(
            "ALTER TABLE `user` ADD COLUMN fecha_creacion DATETIME DEFAULT CURRENT_TIMESTAMP"
        )

    if statements:
        with db.engine.begin() as conn:
            for statement in statements:
                conn.execute(text(statement))


if __name__ == "__main__":
    with app.app_context():
        # Ensure tables exist before running any auth queries.
        db.create_all()
        sync_user_table_schema()
        if not User.query.filter_by(nombre="admin").first():
            usuario = User(nombre="admin", email="admin@local", rol="admin")
            usuario.set_password('1234')
            db.session.add(usuario)
            db.session.commit()
    app.run(debug=True, port=5001)
