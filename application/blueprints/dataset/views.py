from flask import Blueprint, flash, redirect, render_template, url_for
from pydantic import ValidationError

from application.blueprints.dataset.utils import create_record
from application.database.models import Dataset, Record
from application.extensions import db
from application.forms.builder import FormBuilder
from application.validation.models import RecordModel

ds = Blueprint("dataset", __name__, template_folder="templates", url_prefix="/dataset")


@ds.route("/<string:dataset>")
def dataset(dataset):
    ds = Dataset.query.get_or_404(dataset)
    breadcrumbs = {
        "items": [
            {"text": "Home", "href": url_for("main.index")},
            {
                "text": ds.name.capitalize(),
            },
        ]
    }
    return render_template("dataset/dataset.html", dataset=ds, breadcrumbs=breadcrumbs)


@ds.route("/<string:dataset>/records")
def records(dataset):
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


@ds.route("/<string:dataset>/add", methods=["GET", "POST"])
def add_record(dataset):

    ds = Dataset.query.get_or_404(dataset)

    breadcrumbs = {
        "items": [
            {"text": "Home", "href": url_for("main.index")},
            {
                "text": ds.name.capitalize(),
                "href": url_for("dataset.dataset", dataset=ds.dataset),
            },
            {"text": "Add"},
        ]
    }

    # check if there are additional fields to skip. for example if there are references
    # from another dataset to the parent dataset we should skip them. We can do that by checking
    # if the field name is the same as the reference for another dataset
    additional_skip_fields = []
    if ds.parent is None:
        other_datasets = [
            dataset.dataset
            for dataset in Dataset.query.filter(Dataset.dataset != ds.dataset).all()
        ]
        for field in ds.fields:
            if field.field in other_datasets:
                additional_skip_fields.append(field.field)

    builder = FormBuilder(ds.fields, additional_skip_fields=additional_skip_fields)
    form = builder.build()

    if form.validate_on_submit():
        data = form.data

        try:
            # Remove CSRF token before validation
            if "csrf_token" in data:
                del data["csrf_token"]

            # Bind form data to Pydantic model
            record_model = RecordModel.from_form_data(data, ds.fields)

            # Get last record for its entity ID
            last_record = (
                db.session.query(Record)
                .filter(Record.dataset_id == ds.dataset)
                .order_by(Record.entity.desc())
                .first()
            )
            entity = (
                last_record.entity + 1
                if (last_record is not None and last_record.entity is not None)
                else ds.entity_minimum
            )
            if not (ds.entity_minimum <= entity <= ds.entity_maximum):
                flash(
                    f"entity id {entity} is outside of range {ds.entity_minimum} to {ds.entity_maximum}"
                )
                return redirect(url_for("dataset.dataset", dataset=ds.dataset))

            # Use validated data from Pydantic model
            validated_data = record_model.model_dump(
                by_alias=True, exclude={"fields": True}
            )
            record = create_record(entity, validated_data, ds)
            ds.records.append(record)
            db.session.add(ds)
            db.session.commit()
            flash("Record added")
            return redirect(url_for("dataset.dataset", dataset=ds.dataset))

        except ValidationError as e:
            for error in e.errors():
                field = error["loc"][0]
                message = error["msg"]
                if hasattr(form, field):
                    getattr(form, field).errors = [message]

            return render_template(
                "dataset/add-record.html",
                dataset=ds,
                breadcrumbs=breadcrumbs,
                form=form,
                error_list=[
                    {"text": f"{error['loc'][0]}: {error['msg']}"}
                    for error in e.errors()
                ],
            )

    return render_template(
        "dataset/add-record.html", dataset=ds, breadcrumbs=breadcrumbs, form=form
    )


@ds.route("/<string:dataset>/<string:reference>")
def record(dataset, reference):
    ds = Dataset.query.get_or_404(dataset)
    r = Record.query.get_or_404((reference, ds.dataset))

    breadcrumbs = {
        "items": [
            {"text": "Home", "href": url_for("main.index")},
            {
                "text": ds.name.capitalize(),
                "href": url_for("dataset.dataset", dataset=ds.dataset),
            },
            {"text": r.reference},
        ]
    }
    return render_template("dataset/record.html", record=r, breadcrumbs=breadcrumbs)
