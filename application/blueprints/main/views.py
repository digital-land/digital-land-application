import zipfile
from csv import DictWriter
from io import BytesIO, StringIO

import requests
from flask import Blueprint, make_response, render_template

from application.database.models import Specification

main = Blueprint("main", __name__, template_folder="templates")

SPECIFICATION_URL = "https://digital-land.github.io/specification/specification"


@main.route("/")
def index():
    specification = Specification.query.one_or_none()
    if specification is not None:
        try:
            diagram_url = (
                f"{SPECIFICATION_URL}/{specification.specification}/diagram.svg"
            )
            resp = requests.get(diagram_url)
            resp.raise_for_status()
        except requests.exceptions.HTTPError:
            print(f"Failed to fetch diagram for {specification.specification}")
            diagram_url = None
    else:
        diagram_url = None
    return render_template(
        "index.html",
        specification=specification,
        diagram_url=diagram_url,
    )


@main.route("/download-all")
def download_all():
    specification = Specification.query.one_or_none()
    if not specification:
        return "No specification found", 404

    # Create a BytesIO object to store the zip file
    memory_file = BytesIO()

    # Create the zip file
    with zipfile.ZipFile(memory_file, "w", zipfile.ZIP_DEFLATED) as zf:
        # Iterate through all datasets in the specification
        for dataset in specification.ordered_datasets:
            # Create CSV content for this dataset
            output = StringIO()
            fieldnames = [field.field for field in dataset.ordered_fields()]
            writer = DictWriter(output, fieldnames)
            writer.writeheader()

            # Write records if they exist
            if dataset.records:
                for record in dataset.records:
                    writer.writerow(record.to_dict())

            # Add the CSV file to the zip inside a directory named after the specification
            csv_content = output.getvalue().encode("utf-8")
            zf.writestr(
                f"{specification.specification}/{dataset.dataset}.csv", csv_content
            )

    # Seek to the beginning of the BytesIO object
    memory_file.seek(0)

    # Create the response
    response = make_response(memory_file.getvalue())
    response.headers["Content-Type"] = "application/zip"
    response.headers["Content-Disposition"] = (
        f"attachment; filename={specification.specification}.zip"
    )
    return response
