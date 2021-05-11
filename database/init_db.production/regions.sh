#!/bin/bash

# Import OQT regions for which indicators will be precomputed into the database.

wget https://downloads.ohsome.org/OQT/regions.geojson

psql --command \
    "DROP TABLE IF EXISTS regions"

# nln: Assign an alternate name to the new layer
# nlt: Define the geometry type for the created layer
# lco: Layer creation option (format specific)
ogr2ogr \
    -f PostgreSQL PG:"
        host=$POSTGRES_HOST
        port=$POSTGRES_PORT
        dbname=$POSTGRES_DB
        user=$POSTGRES_USER
        password=$POSTGRES_PASSWORD
        "\
    "regions.geojson" \
    -nln regions\
    -nlt MULTIPOLYGON\
    -lco GEOMETRY_NAME=geom
