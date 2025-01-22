from pydantic import BaseModel, ConfigDict


class FieldModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    field: str


class RowModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    # id: UUID4
    data: dict[str, str]


class DatesetModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    dataset: str
    fields: list[FieldModel]
    rows: list[RowModel]
