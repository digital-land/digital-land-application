from csv import DictWriter
from io import StringIO

from flask import (
    Blueprint,
    abort,
    flash,
    make_response,
    redirect,
    render_template,
    url_for,
)
from pydantic import ValidationError
from sqlalchemy.exc import SQLAlchemyError

from application.blueprints.dataset.utils import (
    create_record,
    get_next_entity,
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


@ds.route("/<string:dataset>.csv")
def csv(dataset):
    ds = Dataset.query.get_or_404(dataset)
    if ds.records:
        output = StringIO()
        fieldnames = [field.field for field in ds.ordered_fields()]
        writer = DictWriter(output, fieldnames)
        writer.writeheader()

        for record in ds.records:
            writer.writerow(record.to_dict())

        csv_output = output.getvalue().encode("utf-8")
        response = make_response(csv_output)
        response.headers["Content-Disposition"] = (
            f"attachment; filename={ds.dataset}.csv"
        )
        response.headers["Content-Type"] = "text/csv; charset=utf-8"
        return response
    else:
        abort(404)


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
            record_model = RecordModel.from_data(data, ds.fields)

            try:
                entity = get_next_entity(ds)
            except SQLAlchemyError as e:
                if "exceeds sequence" in str(e):
                    flash(f"No more entity IDs available for {ds.dataset}")
                db.session.rollback()
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


@ds.route("/<string:dataset>/<string:entity>")
def record(dataset, entity):
    ds = Dataset.query.get_or_404(dataset)
    r = Record.query.get_or_404((entity, ds.dataset))

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


@ds.route("/<string:dataset>/<string:entity>/edit", methods=["GET", "POST"])
def edit_record(dataset, entity):
    ds = Dataset.query.get_or_404(dataset)
    r = Record.query.get_or_404((entity, ds.dataset))

    breadcrumbs = {
        "items": [
            {"text": "Home", "href": url_for("main.index")},
            {
                "text": ds.name.capitalize(),
                "href": url_for("dataset.dataset", dataset=ds.dataset),
            },
            {"text": r.entity},
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
        record_model = RecordModel.from_data(data, ds.fields)
        validated_data = record_model.model_dump(
            by_alias=True, exclude={"fields": True}
        )
        record = update_record(validated_data, r)
        db.session.add(record)
        db.session.commit()
        flash("Record updated")
        return redirect(url_for("dataset.record", dataset=ds.dataset, entity=r.entity))

    return render_template(
        "dataset/add-edit-record.html",
        dataset=ds,
        record=r,
        breadcrumbs=breadcrumbs,
        form=form,
        action="edit",
        form_action=url_for("dataset.edit_record", dataset=ds.dataset, entity=r.entity),
    )


@ds.route(
    "/<string:dataset>/<string:entity>/<string:related_dataset>/add",
    methods=["GET", "POST"],
)
def add_related(dataset, entity, related_dataset):
    ds = Dataset.query.get_or_404(dataset)
    related_ds = Dataset.query.get_or_404(related_dataset)
    r = Record.query.get_or_404((entity, ds.dataset))

    # Get organization data from parent record if it exists
    parent_org_data = {}
    if hasattr(r, "organisation") and r.organisation:
        parent_org_data["organisation"] = r.organisation.organisation
    if hasattr(r, "organisations") and r.organisations:
        parent_org_data["organisations"] = r.organisations

    builder = FormBuilder(
        related_ds.fields,
        parent_dataset=related_ds.parent,
        parent_reference=r.reference,
        parent_org_data=parent_org_data,
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
                "text": r.entity,
                "href": url_for("dataset.record", dataset=ds.dataset, entity=r.entity),
            },
            {"text": f"Add {related_ds.name.capitalize()}"},
        ]
    }

    if form.validate_on_submit():
        data = form.data
        if "csrf_token" in data:
            del data["csrf_token"]

        record_model = RecordModel.from_data(data, related_ds.fields)
        entity = get_next_entity(related_ds)

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
                    entity=record.entity,
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
            entity=r.entity,
            related_dataset=related_ds.dataset,
        ),
    )
