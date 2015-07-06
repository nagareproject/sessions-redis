# (C)opyright Net-ng 2008-2015
# -*- coding: utf-8 -*-

import redis

from nagare import local
from nagare.sessions import ExpirationError, common

KEY_PREFIX = 'nagare_'


class Sessions(common.Sessions):
    """Sessions manager for sessions kept in an external redis server
    """
    spec = dict(
        host='string(default="127.0.0.1")',
        port='integer(default=6379)',
        db='integer(default=0)',
        ttl='integer(default=0)',
        lock_ttl='integer(default=0)',
        lock_poll_time='float(default=0.1)',
        lock_max_wait_time='float(default=5.)',
        reset='boolean(default=True)',
    )
    spec.update(common.Sessions.spec)

    def __init__(
            self,
            host='127.0.0.1',
            port=6379,
            db=0,
            ttl=0,
            lock_ttl=5,
            lock_poll_time=0.1,
            lock_max_wait_time=5,
            reset=False,
            **kw
    ):
        """Initialization

        In:
          - ``host`` -- address of the redis server
          - ``port`` -- port of the redis server
          - ``db`` -- id of the redis database
          - ``ttl`` -- sessions and continuations timeout, in seconds (0 = no timeout)
          - ``lock_ttl`` -- session locks timeout, in seconds (0 = no timeout)
          - ``lock_poll_time`` -- wait time between two lock acquisition tries, in seconds
          - ``lock_max_wait_time`` -- maximum time to wait to acquire the lock, in seconds
          - ``reset`` -- do a reset of all the sessions on startup ?
        """
        super(Sessions, self).__init__(**kw)

        self.host = host
        self.port = port
        self.db = db
        self.ttl = ttl
        self.lock_ttl = lock_ttl
        self.lock_poll_time = lock_poll_time
        self.lock_max_wait_time = lock_max_wait_time

        if reset:
            self.flush_all()

    def set_config(self, filename, conf, error):
        """Read the configuration parameters

        In:
          - ``filename`` -- the path to the configuration file
          - ``conf`` -- the ``ConfigObj`` object, created from the
                        configuration file
          - ``error`` -- the function to call in case of configuration errors
        """
        # Let's the super class validate the configuration file
        conf = super(Sessions, self).set_config(filename, conf, error)

        for arg_name in ('host', 'port', 'db', 'ttl', 'lock_ttl', 'lock_poll_time'):
            setattr(self, arg_name, conf[arg_name])

        if conf['reset']:
            self.flush_all()

    def _get_connection(self):
        """Get the connection to the redis server

        Return:
          - the connection
        """
        # The connection objects are local to the workers
        connection = getattr(local.worker, 'redis_connection', None)

        if connection is None:
            connection = redis.Redis(
                host=self.host, port=self.port, db=self.db)
            local.worker.redis_connection = connection

        return connection

    def flush_all(self):
        """Delete all the contents in the redis server
        """
        connection = self._get_connection()
        connection.flushdb()

    def _create(self, session_id, secure_id):
        """Create a new session

        In:
          - ``session_id`` -- id of the session
          - ``secure_id`` -- the secure number associated to the session

        Return:
          - the tuple:
            - id of this state,
            - session lock
        """
        connection = self._get_connection()

        lock = connection.lock('%slock_%s' % (KEY_PREFIX, session_id),
                               self.lock_ttl,
                               self.lock_poll_time,
                               self.lock_max_wait_time)
        lock.acquire()

        connection = connection.pipeline()

        connection.hmset(KEY_PREFIX + session_id, {
            '_sess_id': secure_id,
            '_sess_data': None,
            '_state': '0',
            '00000': {}
        })
        if self.ttl:
            connection.expire(KEY_PREFIX + session_id, self.ttl)

        connection.execute()

        return (0, lock)

    def _get(self, session_id, state_id, use_same_state):
        """Retrieve the state

        In:
          - ``session_id`` -- session id of this state
          - ``state_id`` -- id of this state
          - ``use_same_state`` -- is a copy of this state to create ?

        Return:
          - the tuple:
            - id of this state,
            - session lock,
            - secure number associated to the session,
            - data kept into the session
            - data kept into the state
        """
        connection = self._get_connection()

        lock = connection.lock('%slock_%s' % (KEY_PREFIX, session_id),
                               self.lock_ttl,
                               self.lock_poll_time,
                               self.lock_max_wait_time)
        lock.acquire()

        state_id = state_id.zfill(5)

        secure_id, session_data, last_state_id, state_data = connection.hmget(
            KEY_PREFIX + session_id,
            ('_sess_id', '_sess_data', '_state', state_id)
        )

        if not (secure_id and session_data and last_state_id and state_data):
            raise ExpirationError()

        if not use_same_state:
            state_id = last_state_id

        return (int(state_id), lock, secure_id, session_data, state_data)

    def _set(self, session_id, state_id, secure_id, use_same_state,
             session_data, state_data):
        """Store the state

        In:
          - ``session_id`` -- session id of this state
          - ``state_id`` -- id of this state
          - ``secure_id`` -- the secure number associated to the session
          - ``use_same_state`` -- is this state to be stored in the
                                  previous snapshot ?
          - ``session_data`` -- data keept into the session
          - ``state_data`` -- data keept into the state
        """
        connection = self._get_connection()

        connection = connection.pipeline(True)

        if not use_same_state:
            connection.hincrby(KEY_PREFIX + session_id, '_state', 1)

        connection.hmset(KEY_PREFIX + session_id, {
            '_sess_id': secure_id,
            '_sess_data': session_data,
            '%05d' % state_id: state_data
        })

        if self.ttl:
            connection.expire(KEY_PREFIX + session_id, self.ttl)

        connection.execute()

    def _delete(self, session_id):
        """Delete the session

        In:
          - ``session_id`` -- id of the session to delete
        """
        self._get_connection().delete(KEY_PREFIX + session_id)

    def serialize(self, data):
        """Pickle an objects graph

        In:
          - ``data`` -- the objects graphs

        Return:
          - the tuple:
            - data to keep into the session
            - data to keep into the state
        """
        return self.pickle(data)

    def deserialize(self, session_data, state_data):
        """Unpickle an objects graph

        In:
          - ``session_data`` -- data from the session
          - ``state_data`` -- data from the state

        Out:
          - the objects graph
        """
        return self.unpickle(session_data, state_data)
