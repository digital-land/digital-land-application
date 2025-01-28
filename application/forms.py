import json
import re

from flask import render_template, request
from flask_wtf import FlaskForm
from flask_wtf.file import FileField, FileRequired
from geojson import loads
from markupsafe import Markup
from shapely import wkt
from wtforms import DateField, SelectField, StringField, TextAreaField, URLField
from wtforms.validators import URL, DataRequired, Optional, Regexp, ValidationError

from application.database.models import CategoryValue, Organisation

curie_validator = Regexp(
    r"^[^:]+:[^:]+$", message="Field must be in the format 'namespace:identifier'"
)


def geometry_check(form, field):
    try:
        # Try parsing as GeoJSON
        geojson_obj = loads(field.data)
        if geojson_obj.get("type") != "MultiPolygon":
            raise ValidationError("GeoJSON must be a MultiPolygon")
    except (json.JSONDecodeError, AttributeError):
        # If not valid GeoJSON, try as WKT
        try:
            geom = wkt.loads(field.data)
            if geom.geom_type != "MultiPolygon":
                raise ValidationError("WKT must be a MultiPolygon")
        except Exception:
            raise ValidationError("Must be valid WKT MultiPolygon")


def point_check(form, field):
    try:
        geom = wkt.loads(field.data)
        if geom.geom_type != "Point":
            raise ValidationError(
                "Must be a valid WKT Point e.g. POINT (-0.813597 51.710921)"
            )
    except Exception:
        raise ValidationError(
            "Must be a valid WKT Point e.g. POINT (-0.813597 51.710921)"
        )


def progressive_date_validator(form, field):
    """Validates that date input follows progressive validation rules:
    - YYYY is valid
    - YYYY MM is valid 
    - YYYY MM DD is valid
    But partial dates must include year first."""
    if not field.raw_data:  # No data submitted
        return
        
    # GovDateInput provides data as [day, month, year]
    day, month, year = field.raw_data
    
    # Year is required
    if not year:
        raise ValidationError('Year is required')
    if not year.isdigit() or len(year) != 4:
        raise ValidationError('Year must be YYYY format')
        
    # If month provided, validate it
    if month:
        if not month.isdigit() or int(month) < 1 or int(month) > 12:
            raise ValidationError('Month must be between 1 and 12')
            
        # If day provided when month is set, validate it
        if day:
            if not day.isdigit() or int(day) < 1 or int(day) > 31:
                raise ValidationError('Day must be between 1 and 31')
    elif day:  # Day provided without month
        raise ValidationError('Cannot provide day without month')


class DatePartsInputWidget:
    def __call__(self, field, **kwargs):
        # Get the errors with parts from the field
        errors_with_parts = field.get_errors_with_parts()
        # Create a dict of which parts have errors
        error_parts = {error["part"]: error["message"] for error in errors_with_parts}

        return Markup(
            render_template(
                "partials/date-parts-form.html",
                field=field,
                error_parts=error_parts,
                **kwargs,
            )
        )


class DynamicForm(FlaskForm):

    def __init__(self, sorted_fields, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.field_order = sorted_fields

    def ordered_fields(self):
        for field in self.field_order:
            yield getattr(self, field.field)


class FormBuilder:

    field_types = {
        "curie": StringField,
        "string": StringField,
        "text": TextAreaField,
        "url": URLField,
        "datetime": ProgressiveDateField,  # Use our custom field
        "multipolygon": TextAreaField,
        "point": StringField,
    }

    def __init__(self, fields, additional_skip_fields=None):
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
        self.fields = []
        for field in fields:
            if field.field not in skip_fields:
                self.fields.append(field)

    def build(self):
        TheForm = DynamicForm
        for field in self.fields:
            if field.category_reference is not None:
                # Get category values for this category reference
                category_values = CategoryValue.query.filter(
                    CategoryValue.category_reference == field.category_reference
                ).all()
                choices = [("", "")]
                choices.extend([(cv.reference, cv.name) for cv in category_values])

                if field.cardinality == "n":
                    # For multi-select, use a StringField that will be enhanced by JS
                    field_obj = StringField(
                        label=field.name,
                        validators=[Optional()],
                        render_kw={"data-multi-select": "input", "choices": choices},
                    )
                    setattr(TheForm, field.field, field_obj)
                else:
                    # Single select uses regular SelectField
                    setattr(
                        TheForm,
                        field.field,
                        SelectField(label=field.name, choices=choices),
                    )
                continue

            # Special case for organization fields
            if field.field in ["organisation", "organisations"]:
                organisations = Organisation.query.order_by(Organisation.name).all()
                choices = [("", "")]
                choices.extend(
                    [
                        (f"{org.prefix}:{org.reference}", org.name)
                        for org in organisations
                    ]
                )

                if field.cardinality == "n":
                    # For multi-select, use a StringField that will be enhanced by JS
                    field_obj = StringField(
                        field.name,
                        render_kw={
                            "data-multi-select": "input",
                            "data-hint": f"Start typing {field.name.lower()} to see suggestions",
                            "choices": choices[1:],
                        },
                    )
                    setattr(TheForm, field.field, field_obj)
                else:
                    # Single select uses regular SelectField
                    setattr(
                        TheForm,
                        field.field,
                        SelectField(label=field.name, choices=choices),
                    )
                continue

            if field.field == "name":
                setattr(
                    TheForm,
                    field.field,
                    StringField(label=field.name, validators=[DataRequired()]),
                )
                continue

            form_field = self.field_types.get(field.datatype)
            if form_field is not None:
                match field.datatype:
                    case "curie":
                        setattr(
                            TheForm,
                            field.field,
                            form_field(
                                label=field.name,
                                validators=[Optional(), (curie_validator)],
                            ),
                        )
                    case "string" | "text":
                        setattr(
                            TheForm,
                            field.field,
                            form_field(label=field.name, validators=[Optional()]),
                        )
                    case "url":
                        setattr(
                            TheForm,
                            field.field,
                            form_field(
                                label=field.name, validators=[Optional(), URL()]
                            ),
                        )
                    case "datetime":
                        setattr(
                            TheForm,
                            field.field,
                            form_field(
                                label=field.name,
                                widget=GovDateInput(),
                                validators=[Optional(), progressive_date_validator],
                            ),
                        )
                    case "multipolygon":
                        setattr(
                            TheForm,
                            field.field,
                            form_field(
                                label=field.name,
                                validators=[Optional(), geometry_check],
                            ),
                        )
                    case "point":
                        setattr(
                            TheForm,
                            field.field,
                            form_field(
                                label=field.name, validators=[Optional(), point_check]
                            ),
                        )
                    case _:
                        setattr(
                            TheForm,
                            field.field,
                            form_field(label=field.name, validators=[Optional()]),
                        )

        form = TheForm(sorted_fields=self.sorted_fields())
        return form

    def sorted_fields(self):
        return sorted(self.fields)


class CsvUploadForm(FlaskForm):
    csv_file = FileField("Upload a file", validators=[FileRequired()])
