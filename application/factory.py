"""The app module, containing the app factory function."""

from flask import Flask, render_template
from govuk_frontend_wtf.main import WTFormsHelpers

from application.database.models import *  # noqa - import all models for alembic


def create_app(config_filename):
    app = Flask(__name__)
    app.config.from_object(config_filename)
    register_errorhandlers(app)
    register_blueprints(app)
    register_extensions(app)
    register_templates(app)
    register_context_processors(app)
    register_filters(app)
    register_commands(app)
    return app


def register_errorhandlers(app):
    def render_error(error):
        error_messages = {
            401: "You are not authorised to see this page",
            404: "Sorry, that page doesn't exist",
            500: "Sorry, something went wrong on our system",
        }
        # If a HTTPException, pull the `code` attribute; default to 500
        error_code = getattr(error, "code", 500)
        error_message = error_messages.get(error_code, "An unknown error has occurred")
        return render_template(
            "error.html", error_code=error_code, error_message=error_message
        )

    for errcode in [401, 404, 500]:
        app.errorhandler(errcode)(render_error)
    return None


def register_blueprints(app):
    from application.blueprints.dataset.views import ds
    from application.blueprints.explore.views import explore
    from application.blueprints.main.views import main

    app.register_blueprint(main)
    app.register_blueprint(ds)
    app.register_blueprint(explore)


def register_templates(app):
    """
    Register templates from packages
    """
    from jinja2 import ChoiceLoader, PackageLoader, PrefixLoader

    multi_loader = ChoiceLoader(
        [
            app.jinja_loader,
            PrefixLoader(
                {
                    "govuk_frontend_jinja": PackageLoader("govuk_frontend_jinja"),
                    "digital-land-frontend": PackageLoader("digital_land_frontend"),
                    "govuk_frontend_wtf": PackageLoader("govuk_frontend_wtf"),
                }
            ),
        ]
    )
    app.jinja_loader = multi_loader
    WTFormsHelpers(app)


def register_context_processors(app):
    """
    Add template context variables and functions
    """

    def base_context_processor():
        from flask import session

        authenticated = not app.config.get("AUTHENTICATION_ON", False) or (
            app.config.get("AUTHENTICATION_ON", False) and session.get("user")
        )
        return {"assetPath": "/static", "AUTHENTICATED": authenticated}

    app.context_processor(base_context_processor)


def register_filters(app):
    from application.filters import value_or_empty_string

    app.jinja_env.filters["value_or_empty_string"] = value_or_empty_string


def register_extensions(app):
    from application.extensions import db, migrate

    db.init_app(app)
    migrate.init_app(app, db)


def register_commands(app):
    from application.commands import specification_cli

    app.cli.add_command(specification_cli)
