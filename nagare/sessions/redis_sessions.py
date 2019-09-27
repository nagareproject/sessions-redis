# --
# Copyright (c) 2008-2019 Net-ng.
# All rights reserved.
#
# This software is licensed under the BSD License, as described in
# the file LICENSE.txt, which you should have received as part of
# this distribution.
# --

from nagare.sessions import common
from nagare.sessions.exceptions import ExpirationError

KEY_PREFIX = 'nagare_%d_'


class Sessions(common.Sessions):
    """Sessions manager for sessions kept in an external redis server
    """
    CONFIG_SPEC = dict(
        common.Sessions.CONFIG_SPEC,
        ttl='integer(default=None)',
        lock_ttl='float(default=0.)',
        lock_poll_time='float(default=0.1)',
        lock_max_wait_time='float(default=5.)',
        serializer='string(default="nagare.sessions.serializer:Pickle")',
        reset='boolean(default=True)'
    )

    def __init__(
            self,
            name, dist,
            ttl=0, lock_ttl=None, lock_poll_time=0.1, lock_max_wait_time=5,
            reset=False,
            redis_service=None, services_service=None,
            **config
    ):
        """Initialization

        In:
          - ``ttl`` -- sessions and continuations timeout, in seconds (0 = no timeout)
          - ``lock_ttl`` -- session locks timeout, in seconds (0 = no timeout)
          - ``lock_poll_time`` -- wait time between two lock acquisition tries, in seconds
          - ``lock_max_wait_time`` -- maximum time to wait to acquire the lock, in seconds
          - ``reset`` -- do a reset of all the sessions on startup ?
        """
        services_service(super(Sessions, self).__init__, name, dist, **config)

        self.ttl = ttl
        self.lock_ttl = lock_ttl
        self.lock_poll_time = lock_poll_time
        self.lock_max_wait_time = lock_max_wait_time
        self.redis = redis_service

    def handle_start(self, app):
        self.redis.client_setname("nagare-sessions-manager")

        info = self.redis.info()
        if (info['maxmemory'] == 0) or (info['maxmemory_policy'] == 'noeviction'):
            self.logger.error(
                'Redis server not configured as a LRU cache '
                '(see configuration parameters `maxmemory` and `maxmemory_policy`)'
            )

        self.reload()

    def generate_version_id(self):
        return self.generate_id()

    def reload(self):
        self.version = self.generate_version_id()

    def check_concurrence(self, multi_processes, multi_threads):
        return

    def check_session_id(self, session_id):
        return False

    def get_lock(self, session_id):
        return self.redis.lock(
            (KEY_PREFIX + 'lock') % session_id,
            self.lock_ttl, self.lock_poll_time, self.lock_max_wait_time
        )

    def _create(self, session_id, secure_token):
        """Create a new session

        Return:
          - id of the session
          - id of the state
          - secure token associated to the session
          - session lock
        """
        self.redis.hmset(
            KEY_PREFIX % session_id,
            {
                'state': 0,
                'sess': secure_token,
                '00000': ''
            }
        )

        if self.ttl:
            self.redis.expire(KEY_PREFIX % session_id, self.ttl)

        return session_id, 0, secure_token, self.get_lock(session_id)

    def delete(self, session_id):
        """Delete a session

        In:
          - ``session_id`` -- id of the session to delete
        """
        self.redis.delete(KEY_PREFIX % session_id)

    def _fetch(self, session_id, state_id):
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
        last_state_id, sess, state_data = self.redis.hmget(KEY_PREFIX % session_id, ('state', 'sess', state_id))
        version, secure_token, session_data = sess.split(b':', 2)

        if (last_state_id is None) or (session_data is None) or (state_data is None) or (int(version) != self.version):
            raise ExpirationError()

        return int(last_state_id), secure_token, session_data, state_data

    def _store(self, session_id, state_id, secure_token, use_same_state, session_data, state_data):
        """Store a state and its associated objects graph

        In:
          - ``session_id`` -- session id of this state
          - ``state_id`` -- id of this state
          - ``secure_id`` -- the secure number associated to the session
          - ``use_same_state`` -- is this state to be stored in the previous snapshot?
          - ``session_data`` -- data to keep into the session
          - ``state_data`` -- data to keep into the state
        """
        pipe = self.redis.pipeline()

        if not use_same_state:
            pipe.hincrby(KEY_PREFIX % session_id, 'state', 1)

        pipe.hmset(
            KEY_PREFIX % session_id,
            {
                'sess': b':'.join((b'%d' % self.version, secure_token, session_data or '')),
                '%05d' % state_id: state_data
            }
        )

        if self.ttl:
            pipe.expire(KEY_PREFIX % session_id, self.ttl)

        pipe.execute()
