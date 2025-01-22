from flask import Blueprint, render_template, url_for, abort, redirect, flash
from application.forms import FormBuilder

from application.database.models import Dataset, Record, Field
from application.extensions import db

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
    if ds is None:
        return abort(404)
    
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

    # check if there are additional fields to skip. if they are references 
    # rom another dataset to the parent dataset. We can do that by checking 
    # if the field name is the same as the reference for the other dataset
    additional_skip_fields = []
    if ds.parent is None:
        other_datasets = [dataset.dataset for dataset in Dataset.query.filter(Dataset.dataset != ds.dataset).all()]
        for field in ds.fields:
            if field.field in other_datasets:
                additional_skip_fields.append(field.field)

    builder = FormBuilder(ds.fields, additional_skip_fields=additional_skip_fields)
    form = builder.build()
    sorted_fields = builder.sorted_fields()

    if form.validate_on_submit():
        data = form.data
        last_record = (
            db.session.query(Record)
            .filter_by(dataset_id=dataset.dataset)
            .order_by(Record.row_id.desc())
            .first()
        )
        next_id = last_record.row_id + 1 if last_record else 0
        entity = (
            last_record.entity + 1
            if (last_record is not None and last_record.entity is not None)
            else dataset.entity_minimum
        )
        if not (dataset.entity_minimum <= entity <= dataset.entity_maximum):
            flash(
                f"entity id {entity} is outside of range {dataset.entity_minimum} to {dataset.entity_maximum}"
            )
            return redirect(url_for("main.dataset", id=dataset.dataset))

        if "csrf_token" in data:
            del data["csrf_token"]

        record = Record(row_id=next_id, entity=entity)
        extra_data = {}
        for key, val in data.items():
            if hasattr(record, key):
                setattr(record, key, val)
            else:
                extra_data[key] = val
        if extra_data:
            record.data = extra_data

        dataset.records.append(record)
        db.session.add(dataset)
        db.session.commit()
        flash("Record added")
        return redirect(url_for("dataset.dataset", dataset=ds.dataset))

    return render_template(
        "dataset/add-record.html", dataset=ds, breadcrumbs=breadcrumbs, form=form, sorted_fields=sorted_fields
    )
