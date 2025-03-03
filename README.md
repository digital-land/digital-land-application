## Digital land application

Intended to be used for basic data entry for datasets used in a given specification.

For most specifications a dataset which has no foreign keys from other datasets in the specification is assumed to the 'parent' dataset
and will normally be the main entry point for entering data. This behaviour can be over ridden during appilication setup.


#### Prerequisites

1. python 3

Create a virtualenv and activate it, and then:

    make init

2. Add a PostgreSQL database

Create a database:

    createdb digital-land-application

Add this to .flaskenv file in the root directory and add the following:

    DATABASE_URL=postgresql://localhost:5432/digital-land-application

Initialise Alembic for database migrations:

    flask db init

If/when model classes are added, create database migrations:

    flask db migrate

    flask db upgrade

3. Run the application

Use flask run to start the application.

    flask run


#### Initialise application for a given specification

Setup the intial data for running this application.

    flask specification init [specification name]

If you need to specify which dataset should be the parent dataset and entry point for adding data use the --parent flag.

    flask specification import [specification name] --parent [dataset]



#### Importing data from digital land datasette

Assuming that there's a specification in the database, you can import data from the digital land datasette using the following command.

     flask specification seed-data

By default this command loads 100 records of the main (parent) dataset and any dependent datasets records that are
found in Digital land datasette.

That number of parent records can be modified using the --size flag


     flask specification seed-data --size [up to a maximum of 500]

In addition you can restrict the load of seed data to records from a specific organisation using the organisation
curie. For example to load records from Camden:

    flask specification seed-data --organisation local-authority:LBH
