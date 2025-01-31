from flask import Blueprint, flash, redirect, render_template, url_for
from pydantic import ValidationError

from application.blueprints.dataset.utils import (
    create_record,
    next_entity,
    update_record,
)
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
            entity = next_entity(ds)
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
                "dataset/add-edit-record.html",
                dataset=ds,
                breadcrumbs=breadcrumbs,
                form=form,
                action="add",
                form_action=url_for("dataset.add_record", dataset=ds.dataset),
                error_list=[
                    {"text": f"{error['loc'][0]}: {error['msg']}"}
                    for error in e.errors()
                ],
            )

    return render_template(
        "dataset/add-edit-record.html",
        dataset=ds,
        breadcrumbs=breadcrumbs,
        form=form,
        action="add",
        form_action=url_for("dataset.add_record", dataset=ds.dataset),
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


@ds.route("/<string:dataset>/<string:reference>/edit", methods=["GET", "POST"])
def edit_record(dataset, reference):
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
            {"text": "Edit"},
        ]
    }

    inactive_fields = []
    if r.owning_record is not None:
        inactive_fields.append(r.owning_record.dataset_id)

    builder = FormBuilder(ds.fields, inactive_fields=inactive_fields, obj=r)
    form = builder.build()

    if form.validate_on_submit():
        data = form.data
        # Remove CSRF token before validation
        if "csrf_token" in data:
            del data["csrf_token"]

        # Bind form data to Pydantic model
        record_model = RecordModel.from_form_data(data, ds.fields)
        validated_data = record_model.model_dump(
            by_alias=True, exclude={"fields": True}
        )
        record = update_record(validated_data, r)
        db.session.add(record)
        db.session.commit()
        flash("Record updated")
        return redirect(
            url_for("dataset.record", dataset=ds.dataset, reference=r.reference)
        )

    return render_template(
        "dataset/add-edit-record.html",
        dataset=ds,
        record=r,
        breadcrumbs=breadcrumbs,
        form=form,
        action="edit",
        form_action=url_for(
            "dataset.edit_record", dataset=ds.dataset, reference=r.reference
        ),
    )


@ds.route(
    "/<string:dataset>/<string:reference>/<string:related_dataset>/add",
    methods=["GET", "POST"],
)
def add_related(dataset, reference, related_dataset):
    ds = Dataset.query.get_or_404(dataset)
    related_ds = Dataset.query.get_or_404(related_dataset)
    r = Record.query.get_or_404((reference, ds.dataset))

    builder = FormBuilder(
        related_ds.fields,
        parent_dataset=related_ds.parent,
        parent_reference=r.reference,
    )
    form = builder.build()

    breadcrumbs = {
        "items": [
            {"text": "Home", "href": url_for("main.index")},
            {
                "text": ds.name.capitalize(),
                "href": url_for("dataset.dataset", dataset=ds.dataset),
            },
            {
                "text": r.reference,
                "href": url_for(
                    "dataset.record", dataset=ds.dataset, reference=r.reference
                ),
            },
            {"text": related_ds.name.capitalize()},
            {"text": "Add"},
        ]
    }

    if form.validate_on_submit():
        data = form.data
        if "csrf_token" in data:
            del data["csrf_token"]

        record_model = RecordModel.from_form_data(data, related_ds.fields)
        entity = next_entity(related_ds)

        try:
            validated_data = record_model.model_dump(
                by_alias=True, exclude={"fields": True}
            )
            record = create_record(entity, validated_data, related_ds)
            r.related_records.append(record)
            db.session.add(r)
            db.session.commit()
            flash("Record added")
            return redirect(
                url_for(
                    "dataset.record",
                    dataset=related_ds.dataset,
                    reference=record.reference,
                )
            )
        except ValidationError as e:
            for error in e.errors():
                field = error["loc"][0]
                message = error["msg"]
                if hasattr(form, field):
                    getattr(form, field).errors = [message]

    return render_template(
        "dataset/add-edit-record.html",
        dataset=related_ds,
        breadcrumbs=breadcrumbs,
        form=form,
        action="add",
        form_action=url_for(
            "dataset.add_related",
            dataset=ds.dataset,
            reference=r.reference,
            related_dataset=related_ds.dataset,
        ),
    )
