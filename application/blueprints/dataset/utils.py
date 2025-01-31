from application.database.models import Organisation, Record
from application.extensions import db


def make_reference(dataset, entity):
    dataset_prefix = "".join([word[0] for word in dataset.split("-")])
    return f"{dataset_prefix}-{entity}"


def create_record(entity, validated_data, ds):
    record = Record(
        entity=entity,
        dataset_id=ds.dataset,
        reference=make_reference(ds.dataset, entity),
    )
    return set_record_data(validated_data, record)


def update_record(validated_data, record):
    return set_record_data(validated_data, record)


def set_record_data(validated_data, record):
    if "organisation" in validated_data:
        org = validated_data.pop("organisation")
        org_obj = Organisation.query.get(org)
        if org_obj is not None:
            record.organisation = org_obj

    if "organisations" in validated_data:
        orgs = validated_data.pop("organisations")
        org_list = []
        for org in orgs:
            org_obj = Organisation.query.get(org["organisation"])
            if org_obj is not None:
                org_list.append(org_obj)
        if org_list:
            record.organisations = org_list

    for key, value in validated_data.items():
        setattr(record, key, value)

    # Collect any date fields in data into single date fields
    data = {}
    for key, value in validated_data["data"].items():
        if "date" in key:
            v = _collect_date_fields(value)
            if v is not None:
                data[key] = v
        else:
            data[key] = value
    record.data = data
    return record


def _collect_date_fields(data):
    year = data.get("year")
    month = data.get("month")
    day = data.get("day")
    if year and month and day:
        return f"{year}-{str(month).zfill(2)}-{str(day).zfill(2)}"
    elif year and month:
        return f"{year}-{str(month).zfill(2)}"
    elif year:
        return year
    return None


def next_entity(ds):
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

    return entity
