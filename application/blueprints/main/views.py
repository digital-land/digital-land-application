import requests
from flask import Blueprint, render_template

from application.database.models import Specification

main = Blueprint("main", __name__, template_folder="templates")

SPECIFICATION_URL = "https://digital-land.github.io/specification/specification"


@main.route("/")
def index():
    specification = Specification.query.one_or_none()
    diagram_url = f"{SPECIFICATION_URL}/{specification.specification}/diagram.svg"
    try:
        resp = requests.get(diagram_url)
        resp.raise_for_status()
    except requests.exceptions.HTTPError:
        diagram_url = None
        print(f"Failed to fetch diagram for {specification.specification}")
    return render_template(
        "index.html",
        specification=specification,
        diagram_url=diagram_url,
    )
