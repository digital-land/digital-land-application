from wtforms import Field, SelectField, StringField, TextAreaField, URLField
from wtforms.validators import URL, DataRequired, Optional

from application.database.models import CategoryValue, Organisation
from application.forms.forms import (
    DatePartField,
    DynamicForm,
    curie_validator,
    geometry_check,
    point_check,
)


class FormBuilder:

    def __init__(
        self,
        fields,
        inactive_fields=None,
        additional_skip_fields=None,
        obj=None,
        parent_dataset=None,
        parent_reference=None,  # Only need parent_reference
    ):
        skip_fields = {
            "entity",
            "prefix",
            "entry-date",
            "start-date",
            "end-date",
            "reference",
        }
        if additional_skip_fields:
            skip_fields.update(additional_skip_fields)

        # Create a set of valid field names for strict checking
        self.valid_field_names = {
            field.field for field in fields if field.field not in skip_fields
        }

        # Filter fields to only include valid ones
        self.fields = [
            field for field in fields if field.field in self.valid_field_names
        ]
        self.obj = obj
        self.inactive_fields = inactive_fields or []
        self.parent_dataset = parent_dataset
        self.parent_reference = parent_reference

    def get_field_value(self, field_name):
        """Helper to get value from obj, handling special cases"""

        # If this field matches the dataset name and we have a parent reference
        if field_name == self.parent_dataset and self.parent_reference:
            self.inactive_fields.append(field_name)
            return self.parent_reference

        if not self.obj:
            return None

        # Handle special field types
        if field_name == "organisation":
            return self.obj.organisation.organisation if self.obj.organisation else ""
        elif field_name == "organisations":
            return (
                ";".join(org.organisation for org in self.obj.organisations)
                if self.obj.organisations
                else ""
            )

        # Try to get from data dict first for date fields and other stored data
        if hasattr(self.obj, "data") and field_name in self.obj.data:
            return self.obj.data.get(field_name)

        # Fall back to direct attribute access
        return getattr(self.obj, field_name, None)

    def build(self):
        TheForm = DynamicForm

        # Clear any existing fields from the form class
        class_attrs = list(TheForm.__dict__.keys())
        for attr in class_attrs:
            if isinstance(getattr(TheForm, attr), Field):
                delattr(TheForm, attr)

        for field in self.fields:
            # Double check we're only processing valid fields
            if field.field not in self.valid_field_names:
                continue

            field_value = self.get_field_value(field.field)

            # Set up render_kw with disabled if field is inactive
            render_kw = {}
            if field.field in self.inactive_fields:
                render_kw["disabled"] = True
                render_kw["data-hint"] = (
                    "You can't edit this because it's the link to the parent record"
                )

            if field.category_reference is not None:
                # Get category values for this category reference
                category_values = CategoryValue.query.filter(
                    CategoryValue.category_reference == field.category_reference
                ).all()
                choices = [("", "")]
                choices.extend([(cv.reference, cv.name) for cv in category_values])

                if field.cardinality == "n":
                    field_obj = StringField(
                        label=field.name,
                        default=field_value,
                        validators=[Optional()],
                        render_kw={
                            "data-multi-select": "input",
                            "choices": choices,
                            **render_kw,
                        },
                    )
                    setattr(TheForm, field.field, field_obj)
                else:
                    setattr(
                        TheForm,
                        field.field,
                        SelectField(
                            label=field.name,
                            choices=choices,
                            default=field_value,
                            render_kw=render_kw,
                        ),
                    )
                continue

            # Special case for organization fields
            if field.field in ["organisation", "organisations"]:
                organisations = Organisation.query.order_by(Organisation.name).all()
                choices = [("", "")]
                choices.extend([(org.organisation, org.name) for org in organisations])

                if field.cardinality == "n":
                    # For multi-select, convert organizations to semicolon-separated string
                    initial_value = ""
                    if hasattr(self.obj, "organisations"):
                        initial_value = ";".join(
                            org.organisation for org in self.obj.organisations
                        )

                    field_obj = StringField(
                        field.name,
                        render_kw={
                            "data-multi-select": "input",
                            "data-hint": f"Start typing {field.name.lower()} to see suggestions",
                            "choices": choices,
                            "value": initial_value,  # Set as attribute, not as value
                            **render_kw,
                        },
                    )
                    setattr(TheForm, field.field, field_obj)

                    # Add hidden select for JS component
                    setattr(
                        TheForm,
                        f"{field.field}_select",
                        SelectField(
                            choices=choices, render_kw={"data-multi-select": "select"}
                        ),
                    )
                else:
                    # For single organization, find the display name for the selected value
                    selected_name = ""
                    if field_value:
                        for org_id, org_name in choices:
                            if org_id == field_value:
                                selected_name = org_name
                                break

                    field_obj = SelectField(
                        label=field.name,
                        choices=choices,
                        default=field_value,
                        render_kw={"data-selected-name": selected_name, **render_kw},
                    )
                    setattr(TheForm, field.field, field_obj)
                continue

            if field.field == "name":
                setattr(
                    TheForm,
                    field.field,
                    StringField(
                        label=field.name,
                        default=field_value,
                        validators=[DataRequired()],
                        render_kw=render_kw,
                    ),
                )
                continue

            match field.datatype:
                case "curie":
                    setattr(
                        TheForm,
                        field.field,
                        StringField(
                            label=field.name,
                            default=field_value,
                            validators=[Optional(), curie_validator],
                            render_kw=render_kw,
                        ),
                    )
                case "string":
                    setattr(
                        TheForm,
                        field.field,
                        StringField(
                            label=field.name,
                            default=field_value,
                            validators=[Optional()],
                            render_kw=render_kw,
                        ),
                    )
                case "text":
                    setattr(
                        TheForm,
                        field.field,
                        TextAreaField(
                            label=field.name,
                            default=field_value,
                            validators=[Optional()],
                            render_kw=render_kw,
                        ),
                    )
                case "url":
                    setattr(
                        TheForm,
                        field.field,
                        URLField(
                            label=field.name,
                            default=field_value,
                            validators=[Optional(), URL()],
                            render_kw=render_kw,
                        ),
                    )
                case "datetime":
                    setattr(
                        TheForm,
                        field.field,
                        DatePartField(
                            label=field.name,
                            default=field_value,
                            validators=[Optional()],
                            render_kw=render_kw,
                        ),
                    )
                case "multipolygon":
                    setattr(
                        TheForm,
                        field.field,
                        TextAreaField(
                            label=field.name,
                            default=field_value,
                            validators=[Optional(), geometry_check],
                            render_kw={
                                "data-hint": "Enter a WKT multipolygon",
                                **render_kw,
                            },
                        ),
                    )
                case "point":
                    setattr(
                        TheForm,
                        field.field,
                        StringField(
                            label=field.name,
                            default=field_value,
                            validators=[Optional(), point_check],
                            render_kw={"data-hint": "Enter a WKT point", **render_kw},
                        ),
                    )
                case _:
                    setattr(
                        TheForm,
                        field.field,
                        StringField(
                            label=field.name,
                            default=field_value,
                            validators=[Optional()],
                            render_kw=render_kw,
                        ),
                    )

        form = TheForm(sorted_fields=self.sorted_fields(), obj=self.obj)

        # Verify form fields match expected fields
        assert (
            set(form._fields.keys()) == self.valid_field_names
        ), f"Form fields mismatch. Expected: {self.valid_field_names}, Got: {set(form._fields.keys())}"

        return form

    def sorted_fields(self):
        return sorted(self.fields)
