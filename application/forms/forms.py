import json
import re
from datetime import datetime
from flask import render_template, request
from flask_wtf import FlaskForm
from flask_wtf.file import FileField, FileRequired
from geojson import loads
from markupsafe import Markup
from shapely import wkt
from wtforms import Field
from wtforms.validators import Regexp, ValidationError


def curie_validator(form, field):
    pattern = r"^[^:]+:[^:]+$"
    if not re.match(pattern, field.data):
        raise ValidationError("Field must be in the format 'namespace:identifier'")


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


class DatePartValidationError(ValidationError):
    def __init__(self, message, part=None):
        super().__init__(message)
        self.part = part  # 'day', 'month', or 'year'


class DynamicForm(FlaskForm):

    def __init__(self, sorted_fields, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.field_order = sorted_fields

    def ordered_fields(self):
        for field in self.field_order:
            yield getattr(self, field.field)


class DatePartField(Field):
    widget = DatePartsInputWidget()

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.errors = []
        self._part_errors = []

    def process_data(self, value):
        """Process the Python data applied to this field.
        This will be called during form construction by the form's `kwargs` or
        `obj` argument.
        """
        if value:
            # Handle string date from database
            if isinstance(value, str):
                try:
                    parts = value.split("-")
                    if len(parts) == 3:
                        self.data = {
                            "year": parts[0],
                            "month": str(int(parts[1])),  # Remove leading zeros
                            "day": str(int(parts[2])),  # Remove leading zeros
                        }
                    elif len(parts) == 2:
                        self.data = {
                            "year": parts[0],
                            "month": str(int(parts[1])),
                            "day": "",
                        }
                    else:
                        self.data = {"year": parts[0], "month": "", "day": ""}
                except (ValueError, IndexError):
                    self.data = {"day": "", "month": "", "year": ""}
            else:
                self.data = {"day": "", "month": "", "year": ""}
        else:
            self.data = {"day": "", "month": "", "year": ""}

    def _value(self):
        if self.data:
            return {
                "day": self.data.get("day", ""),
                "month": self.data.get("month", ""),
                "year": self.data.get("year", ""),
            }
        return {"day": "", "month": "", "year": ""}

    def process_formdata(self, valuelist):
        """Process data received over the wire from a form."""
        self.data = {
            "day": request.form.get(f"{self.name}_day", "").strip(),
            "month": request.form.get(f"{self.name}_month", "").strip(),
            "year": request.form.get(f"{self.name}_year", "").strip(),
        }

    def pre_validate(self, form):
        day = self.data.get("day", "").strip()
        month = self.data.get("month", "").strip()
        year = self.data.get("year", "").strip()

        # Reset errors
        self._part_errors = []
        self.errors = []

        # If no data provided at all, field is considered optional
        if not any([day, month, year]):
            return True

        # If day is provided, need month and year
        if day:
            if not month:
                self._add_error("Month is required when day is provided", "month")
                return False
            if not year:
                self._add_error("Year is required when day is provided", "year")
                return False

        # If month is provided, need year
        if month and not year:
            self._add_error("Year is required when month is provided", "year")
            return False

        # Validate year format if provided
        if year:
            if not year.isdigit() or len(year) != 4:
                self._add_error("Year must be in YYYY format", "year")
                return False

        # Validate month if provided
        if month:
            try:
                month_int = int(month)
                if not 1 <= month_int <= 12:
                    self._add_error("Month must be between 1 and 12", "month")
                    return False
            except ValueError:
                self._add_error("Month must be a number", "month")
                return False

        # Validate day if provided
        if day:
            try:
                day_int = int(day)
                if not 1 <= day_int <= 31:
                    self._add_error("Day must be between 1 and 31", "day")
                    return False

                # Validate complete date if we have all parts
                if year and month:
                    try:
                        datetime(int(year), int(month), day_int)
                    except ValueError:
                        self._add_error(f"Invalid day for {month}/{year}", "day")
                        return False
            except ValueError:
                self._add_error("Day must be a number", "day")
                return False

        return True

    def _add_error(self, message, part):
        error = DatePartValidationError(message, part=part)
        self._part_errors.append(error)
        self.errors.append(str(error))

    def get_errors_with_parts(self):
        """Return list of errors with their associated parts"""
        return [
            {"message": str(error), "part": error.part} for error in self._part_errors
        ]

    def validate(self, form, extra_validators=None):
        self._part_errors = []  # Reset errors
        self.errors = []  # Reset errors
        success = self.pre_validate(form)
        if not success:
            # Ensure errors are propagated to the form level
            self.errors = [str(error) for error in self._part_errors]
        return success
    

class CsvUploadForm(FlaskForm):
    csv_file = FileField("Upload a file", validators=[FileRequired()])
