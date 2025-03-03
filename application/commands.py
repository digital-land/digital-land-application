import json
import sys

import click
import requests
from flask.cli import AppGroup
from sqlalchemy import text

from application.blueprints.dataset.utils import create_record
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
from application.validation.models import RecordModel

DATASETTE_URL = "https://datasette.planning.data.gov.uk"
DIGTAL_LAND_DB_URL = f"{DATASETTE_URL}/digital-land"
SPECIFICATION_URL = f"{DIGTAL_LAND_DB_URL}/specification.json"
SPECIFICATION_QUERY = (
    "?specification__exact={specification}&end_date__isblank&_shape=object"
)
FIELDS_URL = f"{DIGTAL_LAND_DB_URL}/field.json?_shape=array"
CATEGORY_DATASETS_URL = f"{DIGTAL_LAND_DB_URL}/dataset.json?end_date__isblank=1&typology__exact=category&_shape=array"
CATEGORY_VALUES_URL = "https://dataset-editor.development.planning.data.gov.uk/dataset/{category_reference}.json"

DATASETTE_SQL_QUERY = """
SELECT * FROM entity
WHERE json_extract(json, '$.{property}') = '{reference}'
AND organisation_entity = {organisation_entity}
"""


specification_cli = AppGroup("specification")


def _get_specification(specification):
    print(f"Getting specification for {specification}")
    url = (
        f"{SPECIFICATION_URL}{SPECIFICATION_QUERY.format(specification=specification)}"
    )
    return _get(url)


@specification_cli.command("seed-data")
@click.option(
    "--size",
    default=100,
    type=click.IntRange(1, 500),
    help="Number of parent dataset records to load (max 500)",
)
@click.option(
    "--organisation", default=None, help="Only records from the given organisation"
)
def get_seed_data(size, organisation):
    print(f"Getting seed data for {size} records")
    # There's only one specification in db at a time for now
    spec = Specification.query.first()
    if spec is None:
        print("No specification found")
        return sys.exit(1)
    print(f"Getting seed data for {spec.specification}")

    if organisation is not None:
        org = Organisation.query.filter(
            Organisation.organisation == organisation
        ).one_or_none()
        if org is None:
            print(f"Organisation {organisation} not found")
            return sys.exit(1)
        organisation_entity = org.entity
    else:
        organisation_entity = None

    url = f"{DATASETTE_URL}/{spec.parent_dataset.dataset}/entity.json?_shape=array&_size={size}"
    if spec.specification == "tree-preservation-order":
        if organisation_entity is not None and organisation_entity != "67":
            print(
                f"Organisation {organisation} is not a tree preservation order authority"
            )
            return sys.exit(1)
        url = f"{url}&organisation_entity__not=67"  # exclude the Buckinghamshire Council - no tree data!

    if organisation_entity is not None:
        url = f"{url}&organisation_entity__exact={organisation_entity}"

    data = _get(url)
    fields = [field.field for field in spec.parent_dataset.fields]

    if len(data) == 0:
        print(f"No data found for {spec.parent_dataset.dataset}")
        return sys.exit(1)

    for d in data:
        load_data = extract_load_data(d, fields)
        try:
            model = RecordModel.from_data(load_data, spec.parent_dataset.fields)
            validated_data = model.model_dump(by_alias=True, exclude={"fields": True})
            reference = d.get("reference", None)
            record = create_record(
                d["entity"], validated_data, spec.parent_dataset, reference=reference
            )
            organisation_entity = d.get("organisation_entity", None)
            if organisation_entity is not None:
                org = Organisation.query.filter(
                    Organisation.entity == organisation_entity
                ).one_or_none()
                if org is not None:
                    record.organisation_id = org.organisation
                db.session.add(record)
        except Exception as e:
            print(f"Error creating record: {e}")
    db.session.commit()

    references = [
        {"dataset": d["dataset"], "reference": d["reference"], "entity": d["entity"]}
        for d in data
    ]

    for dataset in spec.parent_dataset.children:
        print(f"Getting seed data for dependent dataset {dataset.dataset}")
        fields = [field.field for field in dataset.fields]
        for reference in references:
            owning_record = Record.query.get(
                (reference["entity"], reference["dataset"])
            )
            if owning_record is None:
                print(
                    f"No owning record found for {reference['dataset']} record {reference['reference']}"
                )
                continue
            sql = DATASETTE_SQL_QUERY.format(
                property=spec.parent_dataset.dataset,
                reference=reference["reference"],
                organisation_entity=owning_record.organisation.entity,
            )
            query = f"{DATASETTE_URL}/{dataset.dataset}.json?sql={sql}&_shape=array"
            dependent_data = _get(query)
            for dd in dependent_data:
                load_data = extract_load_data(dd, fields)
                model = RecordModel.from_data(load_data, dataset.fields)
                validated_data = model.model_dump(
                    by_alias=True, exclude={"fields": True}
                )
                reference = dd.get("reference", None)
                dependent_record = create_record(
                    dd["entity"], validated_data, dataset, reference=reference
                )
                dependent_record.owning_record = owning_record
                db.session.add(dependent_record)
                print(
                    f"Added dependent {dataset.dataset} record {dependent_record.reference}"
                )
        db.session.commit()


@specification_cli.command("init")
@click.argument("reference")
@click.option("--parent", default=None, help="Parent dataset")
def init_specification(reference, parent):
    spec = Specification.query.all()
    if len(spec) > 0:
        print(
            "A specification has already been imported\n\n"
            "If you want to import a new specification, you need to clear the existing one first.\n\n"
            "You can do this with the 'specification clear-all' command.\n\n"
            "** Download any exising data first as you won't be able to recover it once the data is deleted. **"
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
        print(f"Successfully initialised specification {reference}")

    except Exception as e:
        # If anything fails, rollback the transaction
        db.session.rollback()
        print(f"Error importing specification {reference}: {str(e)}")
        return sys.exit(1)


@specification_cli.command("clear-all")
def clear_all_data():
    print("Clearing all data")

    # Drop sequences for each dataset
    for dataset in Dataset.query.all():
        sequence_name = f"{dataset.dataset.replace('-', '_')}_entity_seq"
        db.session.execute(text(f"DROP SEQUENCE IF EXISTS {sequence_name}"))

    # Clear all data
    db.session.query(dataset_field).delete()
    db.session.query(Record).delete()
    db.session.query(CategoryValue).delete()
    db.session.query(Field).delete()
    db.session.query(Category).delete()
    db.session.query(Dataset).delete()
    db.session.query(Specification).delete()
    db.session.query(Organisation).delete()
    db.session.commit()


@specification_cli.command("clear-seed-data")
def clear_seed_data():
    print("Clearing seed data")

    db.session.query(Record).delete()
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
        return []


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
            min_entity = data[0]["entity_minimum"]
            max_entity = data[0]["entity_maximum"]
            dataset.entity_minimum = min_entity
            dataset.entity_maximum = max_entity

            # Create sequence for this dataset
            sequence_name = f"{dataset.dataset.replace('-', '_')}_entity_seq"
            db.session.execute(
                text(
                    f"""
                CREATE SEQUENCE IF NOT EXISTS {sequence_name}
                START WITH {min_entity}
                MINVALUE {min_entity}
                MAXVALUE {max_entity}
                NO CYCLE
            """
                )
            )

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
            if (
                record.get("end-date", None) is not None
                and record.get("end_date") != ""
            ):
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
            entity=organisation["entity"],
        )
        db.session.add(org)
    db.session.commit()


def extract_load_data(data, fields):
    load_data = {}
    for key, value in data.items():
        k = key.replace("_", "-")
        if k in fields:
            load_data[k] = value
    if "json" in data and data.get("json", None) is not None:
        try:
            json_data = json.loads(data["json"])
            for key, value in json_data.items():
                k = key.replace("_", "-")
                if k in fields:
                    load_data[k] = value
        except json.JSONDecodeError:
            print("Warning: Failed to parse JSON data for record")
    return load_data
