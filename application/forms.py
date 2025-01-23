import re
import json

from geojson import loads
from shapely import wkt

from flask_wtf import FlaskForm
from flask_wtf.file import FileField, FileRequired
from govuk_frontend_wtf.wtforms_widgets import GovDateInput
from wtforms import DateField, StringField, TextAreaField, URLField, SelectField
from wtforms.validators import URL, DataRequired, ValidationError, Regexp

from application.database.models import CategoryValue




curie_validator = Regexp(
    r'^[^:]+:[^:]+$',
    message="Field must be in the format 'namespace:identifier'"
)

def geometry_check(form, field):
    try:
        # Try parsing as GeoJSON
        geojson_obj = loads(field.data)
        if geojson_obj.get('type') != 'MultiPolygon':
            raise ValidationError('GeoJSON must be a MultiPolygon')
    except (json.JSONDecodeError, AttributeError):
        # If not valid GeoJSON, try as WKT
        try:
            geom = wkt.loads(field.data)
            if geom.geom_type != 'MultiPolygon':
                raise ValidationError('WKT must be a MultiPolygon')
        except Exception:
            raise ValidationError('Must be valid WKT MultiPolygon')


def point_check(form, field):
    try:
        geom = wkt.loads(field.data)
        if geom.geom_type != 'Point':
            raise ValidationError('Must be a valid WKT Point e.g. POINT (-0.813597 51.710921)')
    except Exception:
        raise ValidationError('Must be a valid WKT Point e.g. POINT (-0.813597 51.710921)')




class FormBuilder:
    
    field_types = {
        "curie": StringField,
        "string": StringField,
        "text": TextAreaField,
        "url": URLField,
        "datetime": DateField,
        "multipolygon": TextAreaField,
        "point": StringField,
    }
    
    def __init__(self, fields, require_reference=True, additional_skip_fields=None):
        skip_fields = {"entity", "prefix", "entry-date", "start-date", "end-date"}
        if additional_skip_fields:
            skip_fields.update(additional_skip_fields)
        self.fields = []
        self.require_reference = require_reference
        for field in fields:
            if field.field not in skip_fields:
                self.fields.append(field)

    def build(self):
        
        class TheForm(FlaskForm):
            pass

        for field in self.fields:
            if field.category_reference is not None:
                # Get category values for this category reference
                category_values = CategoryValue.query.filter(
                    CategoryValue.category_reference == field.category_reference
                ).all()
                choices = [(cv.reference, cv.name) for cv in category_values]
                setattr(TheForm, field.name, SelectField(choices=choices))
                continue

            form_field = self.field_types.get(field.datatype)
            if form_field is not None:
                match field.datatype:
                    case "curie":
                        setattr(TheForm, field.name, form_field(validators=[curie_validator]))
                    case "string" | "text":
                        setattr(TheForm, field.name, form_field())
                    case "url":
                        setattr(TheForm, field.name , form_field(validators=[URL()]))
                    case "datetime":
                        setattr(TheForm, field.name, form_field(widget=GovDateInput()))
                    case "multipolygon":
                        setattr(TheForm, field.name, form_field(validators=[geometry_check]))
                    case "point":
                        setattr(TheForm, field.name, form_field(validators=[point_check]))
                    case _:
                        if field.field == "name" or (
                            field.field == "reference" and self.require_reference
                        ):
                            setattr(
                                TheForm, field.name, form_field(validators=[DataRequired()])
                            )
                        else:
                            setattr(TheForm, field.name, form_field())

        return TheForm()

    def sorted_fields(self):
        return sorted(self.fields)




class CsvUploadForm(FlaskForm):
    csv_file = FileField("Upload a file", validators=[FileRequired()])
