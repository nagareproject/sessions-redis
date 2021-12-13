# --
# Copyright (c) 2008-2021 Net-ng.
# All rights reserved.
#
# This software is licensed under the BSD License, as described in
# the file LICENSE.txt, which you should have received as part of
# this distribution.
# --

from hashlib import md5

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
        reset_on_reload='option(on, off, invalidate, flush, default="invalidate")',
        version='string(default="")',
        serializer='string(default="nagare.sessions.serializer:Pickle")'
    )

    def __init__(
            self,
            name, dist,
            ttl=0, lock_ttl=None, lock_poll_time=0.1, lock_max_wait_time=5,
            reset_on_reload='invalidate', version='',
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
        services_service(
            super(Sessions, self).__init__, name, dist,
            ttl=ttl, lock_ttl=lock_ttl, lock_poll_time=lock_poll_time,
            lock_max_wait_time=lock_max_wait_time,
            reset_on_reload=reset_on_reload, version=version,
            **config
        )

        self.ttl = ttl
        self.lock_ttl = lock_ttl
        self.lock_poll_time = lock_poll_time
        self.lock_max_wait_time = lock_max_wait_time
        self.redis = redis_service

        self.reset_on_reload = 'invalidate' if reset_on_reload == 'on' else reset_on_reload
        self.version = self._version = version.encode('utf-8')

    def generate_version(self):
        return str(self.generate_id()).encode('utf-8')

    def handle_start(self, app):
        info = self.redis.info()
        if (info['maxmemory'] == 0) or (info['maxmemory_policy'] == 'noeviction'):
            self.logger.error(
                'Redis server not configured as a LRU cache '
                '(see configuration parameters `maxmemory` and `maxmemory_policy`)'
            )

    def handle_reload(self):
        if self.reset_on_reload == 'invalidate':
            version = md5((self._version or self.generate_version())).hexdigest()[:16]
            self.version = version.encode('utf-8')
            self.logger.info("Sessions version '{}'".format(version))

        if self.reset_on_reload == 'flush':
            self.redis.flushall()
            self.logger.info('Deleting all the sessions')

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
        if (last_state_id is None) or (sess is None) or (state_data is None):
            raise ExpirationError('invalid session')

        version, secure_token, session_data = sess.split(b':', 2)

        if (session_data is None) or (version != self.version):
            raise ExpirationError('invalid session')

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
                'sess': b':'.join((self.version, secure_token, session_data or '')),
                '%05d' % state_id: state_data
            }
        )

        if self.ttl:
            pipe.expire(KEY_PREFIX % session_id, self.ttl)

        pipe.execute()
