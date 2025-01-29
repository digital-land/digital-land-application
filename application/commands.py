import json
import sys

import click
import requests
from flask.cli import AppGroup

from application.database.models import (
    Category,
    CategoryValue,
    Dataset,
    Field,
    Organisation,
    Record,
    Specification,
    dataset_field,
)
from application.extensions import db

DATASETTE_URL = "https://datasette.planning.data.gov.uk"
DIGTAL_LAND_DB_URL = f"{DATASETTE_URL}/digital-land"
SPECIFICATION_URL = f"{DIGTAL_LAND_DB_URL}/specification.json"
SPECIFICATION_QUERY = (
    "?specification__exact={specification}&end_date__isblank&_shape=object"
)
FIELDS_URL = f"{DIGTAL_LAND_DB_URL}/field.json?_shape=array"
CATEGORY_DATASETS_URL = f"{DIGTAL_LAND_DB_URL}/dataset.json?end_date__isblank=1&typology__exact=category&_shape=array"
CATEGORY_VALUES_URL = (
    "https://dluhc-datasets.planning-data.dev/dataset/{category_reference}.json"
)

specification_cli = AppGroup("specification")


# def _get_category_datasets():
#     print("Getting category datasets")
#     return _get(CATEGORY_DATASETS_URL)


def _get_specification(specification):
    print(f"Getting specification for {specification}")
    url = (
        f"{SPECIFICATION_URL}{SPECIFICATION_QUERY.format(specification=specification)}"
    )
    return _get(url)


@specification_cli.command("import")
@click.argument("reference")
@click.option("--parent", default=None, help="Parent dataset")
def import_data(reference, parent):
    spec = Specification.query.all()
    if len(spec) > 0:
        print(
            "A specification has already been imported. Another one can't be imported."
        )
        return sys.exit(1)

    specification = _get_specification(reference)
    if specification is None:
        print(f"Specification {reference} not found")
        return

    try:
        data, name = _get_specification_data(reference, specification)

        # Start transaction
        db.session.begin_nested()

        _import_specification_datasets(reference, data, name)
        _set_entity_minimum_and_maximum()
        _import_dataset_fields(data)
        _set_field_attributes()
        _get_and_import_category_values()
        _set_parent_dataset(parent)
        _check_for_geography_datasets()
        _import_organisations()

        # If we get here, commit the transaction
        db.session.commit()
        print("Successfully imported specification data")

    except Exception as e:
        # If anything fails, rollback the transaction
        db.session.rollback()
        print(f"Error importing specification data: {str(e)}")
        return sys.exit(1)


@specification_cli.command("clear")
def clear_data():
    print("Clearing data")
    db.session.query(dataset_field).delete()
    db.session.query(Record).delete()
    db.session.query(CategoryValue).delete()
    db.session.query(Field).delete()
    db.session.query(Category).delete()
    db.session.query(Dataset).delete()
    db.session.query(Specification).delete()
    db.session.query(Organisation).delete()
    db.session.commit()


@specification_cli.command("category-values")
def get_category_values():
    for field in Field.query.all():
        if field.category_reference is not None:
            print(
                f"Getting category values for {field.field} and sub category {field.category_reference}"
            )
            for v in field.category.values:
                print(v)


def _get(url):
    try:
        response = requests.get(url)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.HTTPError as e:
        print(f"Error getting {url}: {e}")
        return None


def _import_specification_datasets(reference, data, name):
    spec = Specification(specification=reference, name=name)
    db.session.add(spec)
    db.session.commit()
    for item in data:
        dataset = item["dataset"]
        if Dataset.query.get(dataset) is not None:
            print(f"Dataset {dataset} already exists")
        else:
            dataset = Dataset(dataset=dataset)
            db.session.add(dataset)
            spec.datasets.append(dataset)
    db.session.commit()


def _import_dataset_fields(data):
    print("Importing fields")
    for dataset in data:
        d = Dataset.query.get(dataset["dataset"])
        if d is None:
            print(f"Dataset {dataset['dataset']} not found")
            continue
        for field in dataset["fields"]:
            f = Field.query.get(field["field"])
            if f is None:
                f = Field(field=field["field"], description=field["description"])
                print(f"Field {field['field']} added")
                category_reference = field.get("dataset", None)
                if category_reference is not None:
                    c = Category.query.get(category_reference)
                    if c is None:
                        c = Category(reference=category_reference)
                        f.category_reference = category_reference
                        db.session.add(c)
            if f not in d.fields:
                d.fields.append(f)
                db.session.add(d)
                print(f"Added field {field['field']} to dataset {dataset['dataset']}")
        db.session.commit()


def _set_field_attributes():
    for field in Field.query.all():
        field_url = f"{FIELDS_URL}&field__exact={field.field}"
        field_data = _get(field_url)
        if field_data and len(field_data) > 0:
            field.name = field_data[0]["name"]
            field.cardinality = field_data[0]["cardinality"]
            field.datatype = field_data[0]["datatype"]
            typology = field_data[0]["typology"]
            if typology == "category":
                field.parent_field = field_data[0]["parent_field"]
            db.session.add(field)
    db.session.commit()


def _set_entity_minimum_and_maximum():
    for dataset in Dataset.query.all():
        url = f"{DIGTAL_LAND_DB_URL}/dataset.json?dataset__exact={dataset.dataset}&_shape=array"
        data = _get(url)
        if data and len(data) > 0:
            dataset.entity_minimum = data[0]["entity_minimum"]
            dataset.entity_maximum = data[0]["entity_maximum"]
            db.session.add(dataset)
    db.session.commit()


def _get_specification_data(reference, specification):
    data_str = specification[reference]["json"]
    name = specification[reference]["name"]
    data = json.loads(data_str)
    return data, name


def _get_and_import_category_values():
    for category in Category.query.all():
        reference = category.reference
        url = CATEGORY_VALUES_URL.format(category_reference=reference)
        category_values = _get(url)
        if category_values is None or "records" not in category_values:
            print(f"No records found for {reference}")
            continue
        for record in category_values["records"]:
            if record["end-date"] != "":
                continue
            if "prefix" not in record or record["prefix"] == "":
                print(f"No prefix found for {reference}")
                continue
            if "reference" not in record or record["reference"] == "":
                print(f"No reference found for {reference}")
                continue
            prefix = record["prefix"]
            reference = record["reference"]
            name = record["name"] if record["name"] else None
            start_date = record["start-date"] if record["start-date"] else None
            if (
                CategoryValue.query.filter(
                    CategoryValue.prefix == prefix, CategoryValue.reference == reference
                ).one_or_none()
                is None
            ):
                category_value = CategoryValue(
                    prefix=prefix,
                    reference=reference,
                    name=name,
                    category_reference=category.reference,
                    start_date=start_date,
                )
                db.session.add(category_value)
                db.session.commit()
            else:
                print(f"Category value {prefix} {reference} already exists")


def _set_parent_dataset(parent):
    datasets = Dataset.query.all()
    if parent is not None:
        print(f"Overriding parent dataset to {parent}")
        for dataset in datasets:
            if dataset.dataset != parent:
                dataset.parent = parent
                db.session.add(dataset)
    else:
        for dataset in datasets:
            for field in dataset.fields:
                if field.field == dataset.dataset:
                    continue
                parent = Dataset.query.get(field.field)
                if parent is not None:
                    dataset.parent = parent.dataset
                db.session.add(dataset)
    db.session.commit()


def _check_for_geography_datasets():
    url = "{datasette_url}/dataset.json?_shape=array&typology__exact=geography&dataset__exact={dataset}"
    for dataset in Dataset.query.all():
        url = url.format(datasette_url=DIGTAL_LAND_DB_URL, dataset=dataset.dataset)
        resp = _get(url)
        if len(resp) > 0:
            print(f"Setting {dataset.dataset} as geography dataset")
            dataset.is_geography = True
            db.session.add(dataset)
    db.session.commit()


def _import_organisations():
    url = f"{DIGTAL_LAND_DB_URL}/organisation.json?_shape=array&_size=max"
    organisations = _get(url)
    for organisation in organisations:
        la_type = (
            organisation.get("local_authority_type")
            if organisation.get("local_authority_type")
            else None
        )
        org = Organisation(
            organisation=organisation["organisation"],
            name=organisation["name"],
            local_authority_type=la_type,
        )
        db.session.add(org)
    db.session.commit()
