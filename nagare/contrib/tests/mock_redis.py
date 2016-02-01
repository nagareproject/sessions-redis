from mockredis import MockRedis
from mockredis.lock import MockRedisLock


class MockRedisLock(MockRedisLock):

    def __init__(self, redis, name, timeout=None, sleep=0.1, blocking_timeout=None):
        super(MockRedisLock, self).__init__(redis, name, timeout=timeout, sleep=sleep)
        self.blocking_timeout = blocking_timeout

class MockRedis(MockRedis):

    def lock(self, key, timeout=0, sleep=0, blocking_timeout=None):
        """Emulate lock."""
        return MockRedisLock(self, key, timeout, sleep, blocking_timeout)

def mock_redis_client(**kwargs):
    return MockRedis()
