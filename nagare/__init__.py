# (C)opyright Net-ng 2008-2015
"""
Declare package namespace for setuptools
"""
try:
    __import__('pkg_resources').declare_namespace(__name__)
except ImportError:
    from pkgutil import extend_path
    __path__ = extend_path(__path__, __name__)
