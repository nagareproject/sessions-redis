# (C)opyright Net-ng 2008-2015
VERSION = '0.0.2'

from setuptools import setup, find_packages

setup(
    name='nng-nagare-sessions-redis',
    version=VERSION,
    author='',
    author_email='',
    description='Redis session manager for Nagare',
    long_description=open('README.rst', 'r').read(),
    keywords='nagare redis session',
    url='',
    packages=find_packages(),
    license='LICENSE.txt',
    zip_safe=False,
    install_requires=('nagare>=0.4.1', 'redis', 'mock', 'mockredispy'),
    namespace_packages=('nagare', 'nagare.contrib', ),
    extras_require={'test': ('nose', 'coverage')},
    entry_points='''
      [nagare.sessions]
      redis = nagare.contrib.redis_session:Sessions
      '''
)
