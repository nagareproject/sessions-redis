# Encoding: utf-8

# --
# Copyright (c) 2008-2020 Net-ng.
# All rights reserved.
#
# This software is licensed under the BSD License, as described in
# the file LICENSE.txt, which you should have received as part of
# this distribution.
# --

import os

from setuptools import setup, find_packages


with open(os.path.join(os.path.dirname(__file__), 'README.rst')) as long_description:
    LONG_DESCRIPTION = long_description.readline()

setup(
    name='nagare-sessions-redis',
    author='Net-ng',
    author_email='alain.poirier@net-ng.com',
    description='Manager for sessions in redis',
    long_description=LONG_DESCRIPTION,
    license='BSD',
    keywords='',
    url='https://github.com/nagareproject/sessions-redis',
    packages=find_packages(),
    zip_safe=False,
    setup_requires=['setuptools_scm'],
    use_scm_version=True,
    install_requires=['redis', 'nagare-services-redis', 'nagare-server-http', 'nagare-services-sessions'],
    entry_points='''
        [nagare.sessions]
        redis = nagare.sessions.redis_sessions:Sessions
    '''
)
