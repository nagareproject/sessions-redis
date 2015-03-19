# (C)opyright Net-ng 2008-2015
try:
    from redis_session_latest import Sessions
except ImportError:
    from redis_session_legacy import Sessions
