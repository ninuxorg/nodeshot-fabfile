CREATE DATABASE nodeshot;
\connect nodeshot;
CREATE EXTENSION postgis;
CREATE EXTENSION postgis_topology;
CREATE EXTENSION hstore;
CREATE USER <user> WITH PASSWORD '<password>';
GRANT ALL PRIVILEGES ON DATABASE "nodeshot" to <user>;
GRANT ALL PRIVILEGES ON TABLE spatial_ref_sys TO <user>;
