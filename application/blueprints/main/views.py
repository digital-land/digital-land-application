from flask import Blueprint, render_template

from application.database.models import Specification

main = Blueprint("main", __name__, template_folder="templates")


@main.route("/")
def index():
    specification = Specification.query.one_or_none()
    return render_template(
        "index.html",
        specification=specification,
    )
