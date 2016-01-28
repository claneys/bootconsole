#!/usr/bin/env python

from distutils.core import setup
#from setuptools import setup

import bootconsole

setup (name = "bootconsole",
       version = "1.29",
       description = "Boot Ncurses Console configuration",
       include_package_data=True,
       author = "Romain Forlot",
       author_email = "romain.forlot@syleps.fr",
       url = "http:/github.com/claneys/bootconsole",
       packages = ['bootconsole', ''],
       data_files = [('/etc/bootconsole', ['conf/usage.txt',
           'conf/bootconsole.conf']), ('/var/lib/bootconsole', [])],
       scripts = ['startscreen', 'sic_seal']
      )
