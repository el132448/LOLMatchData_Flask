from flask import Flask
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()
DB_NAME = "database.db"

# create app
def create_app():
    app = Flask(__name__)
    app.config['SECRET_KEY'] = '123'
    app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{DB_NAME}'
    db.init_app(app)

    # import blueprint
    from .match import match_blueprint
    from .panel import panel_blueprint
    app.register_blueprint(match_blueprint)
    app.register_blueprint(panel_blueprint)

    # create database
    with app.app_context():
        db.create_all()

    return app