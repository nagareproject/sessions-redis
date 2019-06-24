# (C)opyright Net-ng 2008-2015
# -*- coding:utf-8 -*-
import unittest
import random
from .mock_redis import mock_redis_client
from mock import patch
from nagare import local
from nagare.contrib.redis_session_legacy import Sessions

random.seed(2 ** 8)


@patch("redis.Redis", mock_redis_client)
class RedisSessionTest(unittest.TestCase):
    def setUp(self):

        self.session = Sessions()
        local.worker = local.Thread()

    def tearDown(self):
        self.session = None
        local.worker = None

    def test_create(self):
        """Create a session"""
        self.session._create("0", random.randint(1, 1000000))
