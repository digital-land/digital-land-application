## Digital land application

Intended to be used for basic data entry for datasets used in a given specification. 

For most specifications a dataset which has no foreign keys from other datasets in the specification is assumed to the 'parent' dataset 
and will normally be the main entry point for entering data. This behaviour can be over ridden during appilication setup.


#### Prerequisites

1. python 3

Create a virtualenv and activate it, and then:

    make init

Run the app

    flask run

and have a look at http://localhost:5000


2. Add a PostgreSQL database

Create a database:

    createdb [db name]

Add this to .flaskenv file in the root directory and add the following:

    DATABASE_URL=postgresql://localhost:5432/[db name]

Initialise Alembic for database migrations:

    flask db init

If/when model classes are added, create database migrations:

    flask db migrate

    flask db upgrade



#### Initial application for a given specification

Setup the intial data for running this application.

    flask specification import [specification name]

If you need to specify which dataset should be the parent dataset and entry point for adding data use the --parent flag.

    flask specification import [specification name] --parent [dataset]
  
