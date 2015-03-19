========================
nng-nagare-redis-session
========================

A nagare session manager for ``Nagare`` using ``Redis`` as storage backend .


Usage
=====

Many Nagare mechanisms can be extended through the use of
`entry points <http://guide.python-distribute.org/creation.html#entry-points>`_.
The `Nagare entry point <http://www.nagare.org/trac/wiki/EntryPoints>`_
``nagare.sessions`` is used here:

.. code-block:: ini

    ...
    [nagare.sessions]
    redis = nagare.contrib.redis_session:Sessions
    ...

``nagare.contrib.redis_session:Sessions`` is the path to the Session manager
implementation class.


To use the newly created session manager, you have to create a publisher
configuration file. The `sessions section <http://www.nagare.org/trac/wiki/PublisherConfiguration#sessions-section>`_
is configured as this:

.. code-block:: ini

    ...
    [sessions]
    type = redis
    ...


As pointed out by `expo on Nagare mailing list <https://groups.google.com/d/msg/nagare-users/B0FYrYNkQZ0/engbx7rrliAJ>`_,
`original version <http://pastebin.com/SMu5UcKu>`_ did not work with Nagare
latest version but a `working version <http://pastebin.com/BWsiUfQZ>`_  was released.

This package automatically uses the version matching your ``Python`` / ``Nagare`` environment.


Requirements
============

* Python 2.6+ with nagare latest
* Stackless Python 2.6+ with Nagare >= 0.4.1
* redis


License
=======

Proprietary


Running Tests
=============

.. code-block:: sh

    $ hg clone http://hg.net-ng.com/nng-nagare-redis-session
    $ cd nng-nagare-redis-session
    $ nosetests -v


Changelog
=========

Dev
    *

v0.0.1
    * Initial release from Nagare blog post http://www.nagare.org/trac/blog/redis-session-backend