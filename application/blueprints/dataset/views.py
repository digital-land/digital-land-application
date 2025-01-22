from flask import Blueprint, render_template, url_for

from application.database.models import Dataset

ds = Blueprint("dataset", __name__, template_folder="templates", url_prefix="/dataset")


@ds.route("/<string:dataset>")
def dataset(dataset):
    ds = Dataset.query.get_or_404(dataset)

    breadcrumbs = {
        "items": [
            {"text": "Home", "href": url_for("main.index")},
            {
                "text": ds.name.capitalize(),
                "href": url_for("dataset.dataset", dataset=ds.dataset),
            },
            {"text": "Records"},
        ]
    }

    page = {"title": ds.name, "caption": "Dataset"}
    return render_template(
        "dataset/records.html",
        dataset=ds,
        breadcrumbs=breadcrumbs,
        page=page,
        sub_navigation=None,
    )


@ds.route("/<dataset>/record", methods=["GET", "POST"])
def add_record(dataset):

    ds = Dataset.query.get(dataset)

    breadcrumbs = {
        "items": [
            {"text": "Home", "href": url_for("main.index")},
            {
                "text": ds.name.capitalize(),
                "href": url_for("dataset.dataset", dataset=ds.dataset),
            },
            {"text": "Add record"},
        ]
    }

    return render_template(
        "dataset/add-record.html", dataset=ds, breadcrumbs=breadcrumbs
    )
