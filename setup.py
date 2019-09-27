# Encoding: utf-8

# --
# Copyright (c) 2008-2019 Net-ng.
# All rights reserved.
#
# This software is licensed under the BSD License, as described in
# the file LICENSE.txt, which you should have received as part of
# this distribution.
# --

from os import path

from setuptools import setup, find_packages


here = path.normpath(path.dirname(__file__))

with open(path.join(here, 'VERSION')) as version:
    VERSION = version.readline().rstrip()

with open(path.join(here, 'README.rst')) as long_description:
    LONG_DESCRIPTION = long_description.readline().rstrip()

setup(
    name='nagare-sessions-redis',
    version=VERSION,
    author='Net-ng',
    author_email='alain.poirier@net-ng.com',
    description='Manager for sessions in redis',
    long_description=LONG_DESCRIPTION,
    license='BSD',
    keywords='',
    url='https://github.com/nagareproject/sessions-redis',
    packages=find_packages(),
    include_package_data=True,
    zip_safe=False,
    install_requires=['redis', 'nagare-server-http', 'nagare-services-sessions'],
    entry_points='''
        [nagare.sessions]
        redis = nagare.sessions.redis_sessions:Sessions
    '''
)
