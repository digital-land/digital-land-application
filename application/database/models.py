import datetime
from functools import total_ordering
from typing import List, Optional

from sqlalchemy import Date, ForeignKey, ForeignKeyConstraint, Text
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.ext.mutable import MutableDict
from sqlalchemy.orm import Mapped, mapped_column, relationship

from application.extensions import db

dataset_field = db.Table(
    "dataset_field",
    db.Column(
        "dataset",
        Text,
        ForeignKey("dataset.dataset", name="fk_dataset_dataset_field"),
        primary_key=True,
    ),
    db.Column(
        "field",
        Text,
        ForeignKey("field.field", name="fk_field_dataset_field"),
        primary_key=True,
    ),
    db.PrimaryKeyConstraint("dataset", "field", name="pk_dataset_field"),
)


class DateModel(db.Model):
    __abstract__ = True

    entry_date: Mapped[datetime.date] = mapped_column(
        Date, default=datetime.datetime.today
    )
    start_date: Mapped[Optional[datetime.date]] = mapped_column(
        Date, onupdate=datetime.datetime.today
    )
    end_date: Mapped[Optional[datetime.date]] = mapped_column(Date)


class Organisation(DateModel):
    __tablename__ = "organisation"

    organisation: Mapped[str] = mapped_column(Text, primary_key=True)
    name: Mapped[str] = mapped_column(Text)
    local_authority_type: Mapped[Optional[str]] = mapped_column(Text)
    entity: Mapped[int] = mapped_column(db.BigInteger)
    __table_args__ = (db.PrimaryKeyConstraint("organisation", name="pk_organisation"),)


class Specification(DateModel):
    __tablename__ = "specification"

    specification: Mapped[str] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(Text)
    datasets: Mapped[List["Dataset"]] = relationship(
        "Dataset",
        back_populates="specification",
    )

    __table_args__ = (
        db.PrimaryKeyConstraint("specification", name="pk_specification"),
    )

    @property
    def parent_dataset(self):
        return self.ordered_datasets[0]

    @property
    def ordered_datasets(self):
        ds = []
        for dataset in sorted(
            self.datasets, key=lambda d: (d.parent is not None, d.dataset)
        ):
            ds.append(dataset)
        return ds


class Dataset(DateModel):
    __tablename__ = "dataset"

    dataset: Mapped[str] = mapped_column(primary_key=True)
    parent: Mapped[Optional[str]] = mapped_column(
        ForeignKey("dataset.dataset", name="fk_dataset_self_parent"), nullable=True
    )
    specification_id: Mapped[Optional[str]] = mapped_column(
        ForeignKey("specification.specification", name="fk_specification_dataset"),
        nullable=True,
    )
    is_geography: Mapped[bool] = mapped_column(default=False)
    entity_minimum: Mapped[int] = mapped_column(db.BigInteger, nullable=True)
    entity_maximum: Mapped[int] = mapped_column(db.BigInteger, nullable=True)
    specification: Mapped[Optional["Specification"]] = relationship(
        "Specification",
        back_populates="datasets",
    )
    fields: Mapped[List["Field"]] = relationship(
        "Field",
        secondary=dataset_field,
        back_populates="datasets",
    )
    records: Mapped[List["Record"]] = relationship(
        "Record",
        back_populates="dataset",
    )
    # Self-referential relationships
    children: Mapped[List["Dataset"]] = relationship(
        "Dataset", back_populates="parent_dataset", cascade="all, delete-orphan"
    )

    parent_dataset: Mapped[Optional["Dataset"]] = relationship(
        "Dataset", remote_side="Dataset.dataset", back_populates="children"
    )

    __table_args__ = (db.PrimaryKeyConstraint("dataset", name="pk_dataset"),)

    @property
    def name(self):
        return self.dataset.replace("-", " ")

    def get(self, field):
        return self.data.get(field)

    def ordered_fields(self):
        return sorted(self.fields)


@total_ordering
class Field(DateModel):
    __tablename__ = "field"

    field: Mapped[str] = mapped_column(primary_key=True)
    name: Mapped[Optional[str]] = mapped_column(Text)
    description: Mapped[Optional[str]] = mapped_column(Text)
    cardinality: Mapped[Optional[str]] = mapped_column(Text)
    parent_field: Mapped[Optional[str]] = mapped_column(Text)
    category_reference: Mapped[Optional[str]] = mapped_column(
        Text, ForeignKey("category.reference", name="fk_categoryـfield"), nullable=True
    )
    datatype: Mapped[Optional[str]] = mapped_column(Text)
    datasets: Mapped[List["Dataset"]] = relationship(
        "Dataset",
        secondary=dataset_field,
        back_populates="fields",
    )
    category: Mapped[Optional["Category"]] = relationship(
        "Category",
    )

    __table_args__ = (db.PrimaryKeyConstraint("field", name="pk_field"),)

    def __eq__(self, other):
        return self.field == other.field

    def __lt__(self, other):
        if self.field == "entity":
            return True
        if self.field == "name" and other.field != "entity":
            return True
        if self.field == "prefix" and other.field not in ["entity", "name"]:
            return True
        if self.field == "reference" and other.field not in [
            "entity",
            "name",
            "prefix",
        ]:
            return True

        if self.field not in [
            "entity",
            "name",
            "prefix",
            "reference",
        ] and other.field not in ["entity", "name", "prefix", "reference"]:
            if self.datatype == "datetime" and other.datatype != "datetime":
                return False

            if self.datatype == "datetime" and other.datatype == "datetime":
                prefix = self.field.split("-")[0]
                other_prefix = other.field.split("-")[0]
                if prefix == "entry" and other_prefix != "entry":
                    return True
                if prefix == "start" and other_prefix != "entry":
                    return True
                if prefix == "end" and other_prefix not in ["entry", "start"]:
                    return False
                else:
                    return prefix < other_prefix

            if self.datatype != "datetime" and other.datatype != "datetime":
                return self.field < other.field

            if self.datatype != "datetime" and other.datatype == "datetime":
                return True

        return False


class Record(DateModel):
    __tablename__ = "record"

    entity: Mapped[int] = mapped_column(db.BigInteger, primary_key=True)
    dataset_id: Mapped[str] = mapped_column(
        ForeignKey("dataset.dataset"), primary_key=True
    )
    name: Mapped[str] = mapped_column(Text)
    reference: Mapped[str] = mapped_column(Text)
    description: Mapped[Optional[str]] = mapped_column(Text)
    notes: Mapped[Optional[str]] = mapped_column(Text)
    data: Mapped[dict] = mapped_column(MutableDict.as_mutable(JSONB))
    organisation_id: Mapped[Optional[Organisation]] = mapped_column(
        ForeignKey("organisation.organisation", name="fk_organisation_record"),
        nullable=True,
    )
    organisation: Mapped[Optional["Organisation"]] = relationship(
        "Organisation",
    )
    organisation_ids: Mapped[Optional[List[str]]] = mapped_column(
        ARRAY(Text), nullable=True
    )
    dataset: Mapped["Dataset"] = relationship("Dataset", back_populates="records")

    owning_record_entity: Mapped[Optional[int]] = mapped_column(
        db.BigInteger, nullable=True
    )
    owning_record_dataset: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    owning_record: Mapped[Optional["Record"]] = relationship(
        "Record",
        remote_side=lambda: [Record.entity, Record.dataset_id],
        back_populates="related_records",
    )

    related_records: Mapped[List["Record"]] = relationship(
        "Record",
        back_populates="owning_record",
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        db.PrimaryKeyConstraint("entity", "dataset_id", name="pk_record"),
        ForeignKeyConstraint(
            ["owning_record_entity", "owning_record_dataset"],
            ["record.entity", "record.dataset_id"],
            ondelete="CASCADE",
            name="fk_record_self_owning_record",
        ),
    )

    def to_dict(self):
        data = {}
        special_handling = ["organisation", "organisations"]
        for field in [
            f for f in self.dataset.fields if f.field not in special_handling
        ]:
            attr = field.field.replace("-", "_")
            if hasattr(self, attr):
                data[field.field] = getattr(self, attr)
            elif field.field in self.data:
                data[field.field] = self.data.get(field.field)
            else:
                data[field.field] = None
        if self.organisation:
            data["organisation"] = self.organisation.organisation
        if self.organisations:
            data["organisations"] = ";".join(
                [org.organisation for org in self.organisations]
            )

        # check for related records from a dataset with a field with same
        # name as the dataset as these will be references of the related record
        related_data_fields = [field.field for field in self.dataset.fields]
        for r in self.related_records:
            if r.dataset_id in related_data_fields:
                data[r.dataset_id] = r.reference

        return data

    def get(self, field):
        if hasattr(self, field):
            return getattr(self, field)

        # Get the field value from data
        value = self.data.get(field)

        # If no value, return None
        if value is None:
            return None

        # Get the field definition from the dataset
        field_def = next((f for f in self.dataset.fields if f.field == field), None)

        # If field has cardinality "n" and a category reference, look up the category values
        if field_def and field_def.cardinality == "n" and field_def.category_reference:
            # Split the semicolon-separated values
            refs = value.split(";") if isinstance(value, str) else value
            # Look up each reference in CategoryValue
            names = []
            for ref in refs:
                if ref:  # Only process non-empty values
                    category_value = CategoryValue.query.filter_by(
                        reference=ref, category_reference=field_def.category_reference
                    ).first()
                    if category_value:
                        names.append(category_value.name)
            return names if names else value

        return value

    def get_related_by_dataset(self, dataset):
        return [r for r in self.related_records if r.dataset_id == dataset]

    @property
    def organisations(self):
        orgs = []
        if self.organisation_ids is None:
            return orgs
        for org in self.organisation_ids:
            org = Organisation.query.get(org)
            if org:
                orgs.append(org)
        return orgs

    @organisations.setter
    def organisations(self, value):
        self.organisation_ids = [org.organisation for org in value]


class Category(DateModel):
    __tablename__ = "category"
    reference: Mapped[str] = mapped_column(primary_key=True)
    name: Mapped[Optional[str]] = mapped_column(Text)
    values: Mapped[List["CategoryValue"]] = relationship(
        "CategoryValue",
        back_populates="category",
    )

    __table_args__ = (db.PrimaryKeyConstraint("reference", name="pk_category"),)


class CategoryValue(DateModel):
    __tablename__ = "category_value"

    prefix: Mapped[str] = mapped_column(Text, primary_key=True)
    reference: Mapped[str] = mapped_column(Text, primary_key=True)
    name: Mapped[str] = mapped_column(Text)
    category_reference: Mapped[str] = mapped_column(
        ForeignKey("category.reference", name="fk_category_category_value")
    )
    category: Mapped["Category"] = relationship("Category", back_populates="values")

    __table_args__ = (
        db.PrimaryKeyConstraint("prefix", "reference", name="pk_category_value"),
    )
