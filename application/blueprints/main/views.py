import requests
from flask import Blueprint, render_template

from application.database.models import Specification

main = Blueprint("main", __name__, template_folder="templates")

SPECIFICATION_URL = "https://digital-land.github.io/specification/specification"


@main.route("/")
def index():
    specification = Specification.query.one_or_none()
    if specification is not None:
        try:
            diagram_url = (
                f"{SPECIFICATION_URL}/{specification.specification}/diagram.svg"
            )
            resp = requests.get(diagram_url)
            resp.raise_for_status()
        except requests.exceptions.HTTPError:
            print(f"Failed to fetch diagram for {specification.specification}")
            diagram_url = None
    else:
        diagram_url = None
    return render_template(
        "index.html",
        specification=specification,
        diagram_url=diagram_url,
    )
