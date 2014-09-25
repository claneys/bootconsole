# Copyright (c) 2014 Romain Forlot <romain.forlot@syleps.fr> - all rights reserved

import re
import os
import executil
from datetime import datetime
import netinfo
import ipaddr
import hashlib
import ConfigParser
import bootconsole.conf as conf

class Error(Exception):
    pass

class Syleps:
    '''
    Syleps object that take care of password change when hostname change
    and configuration files integrity.
    '''

    def __init__(self, bootconsole_conf=conf.Conf('bootconsole.conf')):
        self.db_user = bootconsole_conf.get_param('db_user')
        self.as_user = bootconsole_conf.get_param('as_user')
        self.suux_user = bootconsole_conf.get_param('suux_user')
        self.suas_user = bootconsole_conf.get_param('suas_user')
        self.csum_file = conf.path('csums')
        self.conf_files = { 'db_tnsnames': self._find_file_in_homedir(self.db_user, 'tnsnames.ora'),
            'db_listener' : self._find_file_in_homedir(self.db_user, 'listener.ora'),
            'as_tnsnames' : self._find_file_in_homedir(self.as_user, 'tnsnames.ora'),
            'as_formsweb' : self._find_file_in_homedir(self.as_user, 'formsweb.cfg'),
            'as_dads' : self._find_file_in_homedir(self.as_user, 'dads.conf', exclude='FRHome'),
            'suas_profile' : os.path.expanduser('~'+self.suas_user+'/.profile'),
            'suas_profile_spec' : os.path.expanduser('~'+self.suas_user+'/.profile.spec'),
            'suas_profile_ora' : os.path.expanduser('~'+self.suas_user+'/.profile.ora'),
            'suas_profile_std' : os.path.expanduser('~'+self.suas_user+'/.profile.std'),
            'suux_profile' : os.path.expanduser('~'+self.suux_user+'/.profile'),
            'suux_profile_spec' : os.path.expanduser('~'+self.suux_user+'/.profile.spec'),
            'suux_profile_ora' : os.path.expanduser('~'+self.suux_user+'/.profile.ora'),
            'suux_profile_std' : os.path.expanduser('~'+self.suux_user+'/.profile.std')
        }

    def _make_password(self):
        '''
        Determine su ux user password based on hostname
        '''
        hostname = netinfo.NetworkInfo().hostname.split('.')[0]
        password = re.sub(r'(db|as)(su)', r'pw\2', hostname)
        return password
        
    def _find_file_in_homedir(self, user, file2find, exclude=None):
        '''
        Use to find a file into a home directory.
        Param : user, file2find and exclude regex pattern
        Return : os path object of file if found else None
        '''
        homedir = os.path.expanduser('~'+user)
        if exclude:
            excludepattern = r'sample|tmp|backup|'+exclude
        else:
            excludepattern = r'sample|tmp|backup'

        for root, dirs, files in os.walk(homedir):
            for filee in files:
                if filee == file2find and not re.search(excludepattern, root):
                    return os.path.join(root, file2find)

    def _change_dads(self, conf, password):
        '''
        Change su ux password in dads.conf file
        Param: bootconsole conf object, password
        Return: None
        '''
        try:
            pos = conf.param.index(conf.get_param('PlsqlDatabasePassword', bare=True))        
            conf.del_param('PlsqlDatabasePassword')
            conf.set_param('PlsqlDatabasePassword', password, pos)
            conf.write_conf()
        except ValueError:
            return 'Don\'t find PlsqlDatabasePassword statement in dads.conf file.'

    def _change_formsweb(self, conf, password):
        '''
        Change su ux password in formsweb.conf file
        Param: bootconsole conf object, password
        Return: None
        '''
        pattern_replacement = r'\1' + password + r'\2'

        try:
            userid_val = conf.get(self.suas_user, 'userid')
            userid_val = re.sub(r'(/).*(@)', pattern_replacement, userid_val)

            conf.set(self.suas_user, 'userid', userid_val)
            conf.write(open(self.conf_files['as_formsweb'],'w'))
        except ConfigParser.NoSectionError:
            return 'No section "%s" into formsweb.cfg file.' % self.suas_user

    def change_su_password(self):
        '''
        Process su ux password change and launch tcho
        change_hostname.sh script that change password in
        oracle database.
        Param: None
        Return:  if error on change_hostname.sh
        '''
        password = self._make_password()
        err = []
        if self.conf_files['as_formsweb'] != None:
            formsweb_conf = ConfigParser.ConfigParser()
            formsweb_conf.readfp(open(self.conf_files['as_formsweb']))
            err.append(self._change_formsweb(formsweb_conf, password))
        if self.conf_files['as_dads'] != None:
            dads_conf = conf.Conf(self.conf_files['as_dads'])
            err.append(self._change_dads(dads_conf, password))

        if err != []:
            err.append('\nAbort changing SU password.\nAnyway, your hosts file was writen.')
            return '\n'.join(err)
        
        try:
            executil.system('/bin/su '+ self.suas_user +' - -c "~'+self.suas_user+'/run/bin/change_hostname.sh" > /dev/null 2>&1')
        except executil.ExecError:
            executil.system('/bin/su '+ self.suux_user +' - -c "~'+self.suux_user+'/run/bin/change_hostname.sh" > /dev/null 2>&1')
        else:
            return 'Can\'t execute change_hostname.sh script.'

    def record_checksums(self):
        '''
        Record files checksum about Syleps essentials files that do not have 
        to change over time.
        '''
        
        if os.access(self.csum_file, os.F_OK):
            content = open(self.csum_file, 'r').readlines()
            bck_file = '.'.join((self.csum_file, datetime.now().strftime('%d%m%y%H%M%S')))
            fh = open(bck_file, 'w')
            fh.writelines(content)
            fh.close()

        fh = open(self.csum_file, 'w')
        for k, v in self.conf_files.iteritems():
            try:
                csum = hashlib.sha256(open(v, 'rb').read()).hexdigest()
            except:
                continue
            line = ' '.join((v, csum, '\n'))
            fh.write(line)

        fh.close()
