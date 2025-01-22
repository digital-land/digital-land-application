===============================
digital-land-app-template
===============================


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
