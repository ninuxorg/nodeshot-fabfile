nodeshot-fabfile
================

============================ ===================================================================================
Linux Distribution           Build status
============================ ===================================================================================
Debian 7                      .. image:: https://ci.publicwifi.it/buildStatus/icon?job=nodeshot-fabfile-debian7
Ubuntu 14                     .. image:: https://ci.publicwifi.it/buildStatus/icon?job=nodeshot-fabfile-ubuntu14
============================ ===================================================================================

Nodeshot fabfile deploy script.

Documentation here: http://nodeshot.rtfd.org/en/latest/topics/install_production_automated.html


Quick reference
---------------

install::

    fab install -H <remote_host> -u <user> -p <password>

update::

    fab update:use_defaults=True,project_name=<project_name> -H <remote_host> -u <user> -p <password>
