from application.database.models import CategoryValue, Organisation
from application.forms.forms import DynamicForm, curie_validator, geometry_check, point_check, DatePartField


from wtforms import SelectField, StringField, TextAreaField, URLField
from wtforms.validators import URL, DataRequired, Optional


class FormBuilder:

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

            match field.datatype:
                case "curie":
                    setattr(
                        TheForm,
                        field.field,
                        StringField(
                            label=field.name,
                            validators=[Optional(), (curie_validator)],
                        ),
                    )
                case "string":
                    setattr(
                        TheForm,
                        field.field,
                        StringField(label=field.name, validators=[Optional()]),
                    )
                case "text":
                    setattr(
                        TheForm,
                        field.field,
                        TextAreaField(label=field.name, validators=[Optional()]),
                    )
                case "url":
                    setattr(
                        TheForm,
                        field.field,
                        URLField(
                            label=field.name, validators=[Optional(), URL()]
                        ),
                    )
                case "datetime":
                    setattr(
                        TheForm,
                        field.field,
                        DatePartField(
                            label=field.name,
                            validators=[Optional()],
                        ),
                    )
                case "multipolygon":
                    setattr(
                        TheForm,
                        field.field,
                        TextAreaField(
                            label=field.name,
                            validators=[Optional(), geometry_check],
                        ),
                    )
                case "point":
                    setattr(
                        TheForm,
                        field.field,
                        StringField(
                            label=field.name, validators=[Optional(), point_check]
                        ),
                    )
                case _:
                    setattr(
                        TheForm,
                        field.field,
                        StringField(label=field.name, validators=[Optional()]),
                    )

        form = TheForm(sorted_fields=self.sorted_fields())
        return form

    def sorted_fields(self):
        return sorted(self.fields)
