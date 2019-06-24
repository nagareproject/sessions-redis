# (C)opyright Net-ng 2008-2015
# -*- coding: utf-8 -*-

import redis
import rediscluster

from io import BytesIO

from nagare import local
from nagare.sessions import ExpirationError, common
from nagare.sessions.serializer import Pickle

KEY_PREFIX = 'nagare_%d_'


class Sessions(common.Sessions):

    """Sessions manager for sessions kept in an external redis server
    """
    spec = common.Sessions.spec.copy()
    spec.update(dict(
        host='string(default="127.0.0.1")',
        port='integer(default=6379)',
        db='integer(default=0)',
        ttl='integer(default=0)',
        lock_ttl='integer(default=0)',
        lock_poll_time='float(default=0.1)',
        lock_max_wait_time='float(default=5.)',
        reset='boolean(default=True)',
        serializer='string(default="nagare.sessions.serializer:Pickle")',
        cluster='boolean(default=False)'
    ))

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
        serializer=None,
        cluster=False,
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
          - ``serializer`` -- serializer / deserializer of the states
        """
        super(Sessions, self).__init__(serializer=serializer or Pickle, **kw)

        self.host = host
        self.port = port
        self.db = db
        self.ttl = ttl
        self.lock_ttl = lock_ttl
        self.lock_poll_time = lock_poll_time
        self.lock_max_wait_time = lock_max_wait_time
        self.cluster = cluster

        if reset:
            self.flush_all()

    def set_config(self, filename, conf, error):
        """Read the configuration parameters

        In:
          - ``filename`` -- the path to the configuration file
          - ``conf`` -- the ``ConfigObj`` object, created from the configuration file
          - ``error`` -- the function to call in case of configuration errors
        """
        # Let's the super class validate the configuration file
        conf = super(Sessions, self).set_config(filename, conf, error)

        for arg_name in (
            'host', 'port', 'db', 'ttl', 'lock_ttl',
                            'lock_poll_time',
                            'lock_max_wait_time',
                            #'min_compress_len', 'debug'
        ):
            setattr(self, arg_name, conf[arg_name])

        if conf['reset']:
            self.flush_all()

        return conf

    def _get_connection(self):
        """Get the connection to the redis server

        Return:
          - the connection
        """
        # The connection objects are local to the workers
        connection = getattr(local.worker, 'redis_connection', None)

        if connection is None:
            if self.cluster:
                connection = rediscluster.StrictRedisCluster(
                startup_nodes=[{"host": self.host, "port": self.port}],
                decode_responses=True,
                skip_full_coverage_check=True)
            else:
                connection = redis.Redis(
                    host=self.host, port=self.port, db=self.db)
                local.worker.redis_connection = connection

        return connection

    def _convert_val_to_store(self, val):
        """Returns the given value as a Redis storable representation
        Mimics what memcache:Client._val_to_store_info does for objects with Memcache

        In:
          - ``val`` -- Value to store

        Return:
          - The value as a Redis storable representation
        """
        file_ = BytesIO()
        pickler = self.serializer.pickler(file_, protocol=-1)
        pickler.dump(val)
        return file_.getvalue()

    def _convert_stored_val(self, val):
        """Returns the value from a stored representation in Redis
        Mimics what memcache:Client._recv_value does for objects with Memcache

        In:
          - ``val`` -- Value stored in Redis

        Return:
          - The value
        """
        return self.serializer.unpickler(BytesIO(val)).load()

    def flush_all(self):
        """Delete all the contents in the redis server
        """
        connection = self._get_connection()
        connection.flushdb()

    def get_lock(self, session_id):
        """Retrieve the lock of a session

        In:
          - ``session_id`` -- session id

        Return:
          - the lock
        """
        connection = self._get_connection()
        lock = connection.lock(
            (KEY_PREFIX + 'lock') % session_id,
            self.lock_ttl,
            self.lock_poll_time,
            self.lock_max_wait_time)
        return lock

    def create(self, session_id, secure_id, lock):
        """Create a new session

        In:
          - ``session_id`` -- id of the session
          - ``secure_id`` -- the secure number associated to the session
          - ``lock`` -- the lock of the session
        """
        connection = self._get_connection()
        connection = connection.pipeline()

        connection.hmset(
            KEY_PREFIX % session_id, {
                'state': 0,
                'sess_id': self._convert_val_to_store(secure_id),
                'sess_data': self._convert_val_to_store(None),
                '00000': self._convert_val_to_store({})
            })

        if self.ttl:
            connection.expire(KEY_PREFIX % session_id, self.ttl)

        connection.execute()

    def delete(self, session_id):
        """Delete the session

        In:
          - ``session_id`` -- id of the session to delete
        """
        self._get_connection().delete(KEY_PREFIX % session_id)

    def fetch_state(self, session_id, state_id):
        """Retrieve a state with its associated objects graph

        In:
          - ``session_id`` -- session id of this state
          - ``state_id`` -- id of this state

        Return:
          - id of the latest state
          - secure number associated to the session
          - data kept into the session
          - data kept into the state
        """
        state_id = '%05d' % state_id

        connection = self._get_connection()

        last_state_id, secure_id, session_data, state_data = connection.hmget(
            KEY_PREFIX % session_id,
            ('state', 'sess_id', 'sess_data', state_id)
        )

        # ``None`` means key was not found
        if secure_id is None or session_data is None or last_state_id is None or state_data is None:
            raise ExpirationError()

        session_data = self._convert_stored_val(session_data)
        secure_id = self._convert_stored_val(secure_id)

        return int(last_state_id), secure_id, session_data, state_data

    def store_state(self, session_id, state_id, secure_id, use_same_state, session_data, state_data):
        """Store a state and its associated objects graph

        In:
          - ``session_id`` -- session id of this state
          - ``state_id`` -- id of this state
          - ``secure_id`` -- the secure number associated to the session
          - ``use_same_state`` -- is this state to be stored in the previous snapshot?
          - ``session_data`` -- data to keep into the session
          - ``state_data`` -- data to keep into the state
        """
        connection = self._get_connection()
        connection = connection.pipeline(True)

        if not use_same_state:
            connection.hincrby(KEY_PREFIX % session_id, 'state', 1)

        connection.hmset(KEY_PREFIX % session_id, {
            'sess_id': self._convert_val_to_store(secure_id),
            'sess_data': self._convert_val_to_store(session_data),
            '%05d' % state_id: state_data
        })

        if self.ttl:
            connection.expire(KEY_PREFIX % session_id, self.ttl)

        connection.execute()
