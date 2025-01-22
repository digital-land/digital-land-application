from flask import Blueprint, render_template

explore = Blueprint(
    "explore", __name__, template_folder="templates", url_prefix="/explore"
)


@explore.route("/")
def index():
    return render_template("explore/index.html")
