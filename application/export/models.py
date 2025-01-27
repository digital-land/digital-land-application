from pydantic import BaseModel, ConfigDict


class FieldModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    field: str


class RecordModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    # id: UUID4
    data: dict[str, str]


class DatasetModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    dataset: str
    fields: list[FieldModel]
    records: list[RecordModel]
