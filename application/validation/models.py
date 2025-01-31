from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, ValidationInfo, model_validator
from sqlalchemy import select

from application.database.models import Dataset, Record
from application.extensions import db


def cross_dataset_reference_validator(dataset_name: str, value: str) -> str:
    # Check if value exists as a reference in the target dataset
    stmt = select(Record).where(
        Record.dataset_id == dataset_name, Record.reference == value
    )
    record = db.session.execute(stmt).scalar_one_or_none()
    if not record:
        raise ValueError(f"Reference '{value}' not found in dataset '{dataset_name}'")
    return value


class FieldModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    field: str
    name: str
    datatype: str


class OrganisationModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    organisation: str


class RecordModel(BaseModel):
    model_config = ConfigDict(
        from_attributes=True,
        alias_generator=lambda x: x.replace("_", "-"),
        populate_by_name=True,
    )
    name: str
    description: Optional[str]
    notes: Optional[str]
    data: dict[str, Any]
    organisation: Optional[OrganisationModel]
    organisations: Optional[list[OrganisationModel]]
    fields: list[FieldModel]

    @model_validator(mode="after")
    @classmethod
    def validate_model(
        cls, model: "RecordModel", info: ValidationInfo
    ) -> "RecordModel":
        # Get fields directly from the model instance
        valid_field_names = {field.field for field in model.fields}

        # Get all dataset names
        stmt = select(Dataset.dataset)
        dataset_names = {d[0] for d in db.session.execute(stmt).fetchall()}

        # Check each key in data exists in the fields list and validate dataset references
        for key, val in model.data.items():
            if key not in valid_field_names:
                raise ValueError(
                    f"Field '{key}' in data is not a valid field for this dataset"
                )

            # If the field name matches a dataset name, validate the reference
            if key in dataset_names and isinstance(val, str):
                try:
                    cross_dataset_reference_validator(key, val)
                except ValueError as e:
                    raise ValueError(f"Invalid dataset reference: {str(e)}")

        return model

    @classmethod
    def from_form_data(
        cls, form_data: dict[str, Any], fields: list[FieldModel]
    ) -> "RecordModel":
        # Extract and map form data to RecordModel
        data = {
            key: value
            for key, value in form_data.items()
            if key
            not in {
                "name",
                "description",
                "notes",
                "organisation",
                "organisations",
            }  # Fields not part of 'data'
        }
        name = form_data.get("name", "")
        description = form_data.get("description", "")
        notes = form_data.get("notes", "")
        organisation = {"organisation": form_data.get("organisation", "")}
        organisations = [
            {"organisation": org}
            for org in form_data.get("organisations", "").split(";")
        ]
        return cls(
            name=name,
            description=description,
            notes=notes,
            data=data,
            organisation=organisation,
            organisations=organisations,
            fields=fields,
        )
