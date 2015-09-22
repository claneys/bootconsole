# Copyright (c) 2014 Romain Forlot <romain.forlot@syleps.fr> - all rights reserved

import re
import os
import subprocess
import executil
from datetime import datetime
import bootconsole.ifutil as ifutil
import netinfo
import ipaddr
import hashlib
import ConfigParser
import bootconsole.conf as conf
import pwd

class Error(Exception):
    pass

class Syleps:
    '''
    Syleps object that take care of password change when hostname change
    and configuration files integrity.
    '''

    def __init__(self, bootconsole_conf=conf.Conf('bootconsole.conf')):
        
        self.var_dir = bootconsole_conf.get_param('var_dir')
        self.as_user = bootconsole_conf.get_param('as_user')
        self.db_user = bootconsole_conf.get_param('db_user')
        
        OracleProductsInstalled = Syleps._getOracleProducts()
        # Only process first product installed as we install one product by machine
        if 'Database' in OracleProductsInstalled[0]:
            self.component = 'db'
            self.peer_component = 'as'
            self.su_user = bootconsole_conf.get_param('suux_user')
            self.conf_files = { 'db_tnsnames': Syleps._find_file_in_homedir(self.db_user, 'tnsnames.ora'),
                                'db_listener' : Syleps._find_file_in_homedir(self.db_user, 'listener.ora'),
                                'suux_profile' : os.path.expanduser('~'+self.su_user+'/.profile'),
                                'suux_profile_spec' : os.path.expanduser('~'+self.su_user+'/.profile.spec'),
                                'suux_profile_ora' : os.path.expanduser('~'+self.su_user+'/.profile.ora'),
                                'suux_profile_std' : os.path.expanduser('~'+self.su_user+'/.profile.std')
            }
        else:
            self.component = 'as'
            self.peer_component = 'db'
            self.su_user = bootconsole_conf.get_param('suas_user')
            self.conf_files = { 'as_tnsnames' : Syleps._find_file_in_homedir(self.as_user, 'tnsnames.ora'),
                                'as_formsweb' : Syleps._find_file_in_homedir(self.as_user, 'formsweb.cfg'),
                                'as_dads' : Syleps._find_file_in_homedir(self.as_user, 'dads.conf', exclude='FRHome'),
                                'suas_profile' : os.path.expanduser('~'+self.su_user+'/.profile'),
                                'suas_profile_spec' : os.path.expanduser('~'+self.su_user+'/.profile.spec'),
                                'suas_profile_ora' : os.path.expanduser('~'+self.su_user+'/.profile.ora'),
                                'suas_profile_std' : os.path.expanduser('~'+self.su_user+'/.profile.std'),
            }
        
        # Append system configuration files
        self.conf_files['ntp'] = '/etc/ntp.conf'
        self.conf_files['hosts'] = '/etc/hosts'
        self.conf_files['resolv'] = ifutil.NetworkSettings.RESOLV_FILE
        self.conf_files['network'] = ifutil.NetworkSettings.NETWORK_FILE
        self.conf_files['net_interface'] = '%s/ifcfg-%s' % (ifutil.NetworkSettings.IFCFG_DIR, bootconsole_conf.get_param('default_nic'))
    
    @staticmethod
    def _getOracleProducts(self, peer_host):
        try:
            opatch_cmd = Syleps._find_file_in_homedir(self.as_user, 'opatch')
            users = [ self.as_user, self.db_user ]
        except:
            opatch_cmd = Syleps._find_file_in_homedir(self.db_user, 'opatch')
            users = [ self.db_user, self.as_user ]
        
        # Make awk cmd to extract only products installed, except Examples products.
        begin_pattern = 'Installed Top-level Products'
        end_pattern = 'There are [0-9]+ products installed in this Oracle Home'
        awk_cmd = 'awk \'/%s/{f=1;next} /%s/ {f=0} f && ! /^$/ && ! /Example/ {print}\'' % (begin_pattern, end_pattern)
        
        products = [ executil.getoutput('su - %s -c "%s lsinv" | %s' % (users[0], opatch_cmd, awk_cmd)).split('\n'),
                    executil.getoutput('ssh -o StrictHostKeyChecking=no root@%s "su - %s -c \'opatch lsinv\' | %s' % (peer_host, users[1], awk_cmd).split('\n'))
                   ]
        return products
        
    @staticmethod
    def _is_syleps_compliant(hostname):   
        # make sure that we act on shortname
        shortname = NetworkInfo.get_shortname(hostname)
        if re.search(r'^[a-zA-Z0-9]{3,6}(db|as)su[ptrmd]$', shortname) :
            return True
        return False
    
    def _make_password(self, hostname, aliases):
        '''
        Determine su ux user password based on hostname
        '''
        if Syleps._is_syleps_compliant(hostname):
            password = re.sub(r'(db|as)(su)', r'pw\2', NetworkInfo.get_shortname(hostname))
            return password
        for elt in aliases:
            if Syleps._is_syleps_compliant(elt):
                elt = NetworkInfo.get_shortname(elt)
                password = re.sub(r'(db|as)(su)', r'pw\2', elt)
                return password
        raise Exception('Can\'t make password. Check hostname and alias.')
    
    @staticmethod
    def _find_file_in_homedir(user, file2find, exclude=None):
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
                
        raise(Exception("File not found, or wrong user selected!"))

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
            userid_val = conf.get(self.su_user, 'userid')
            userid_val = re.sub(r'(/).*(@)', pattern_replacement, userid_val)

            conf.set(self.su_user, 'userid', userid_val)
            conf.write(open(self.conf_files['as_formsweb'],'w'))
        except ConfigParser.NoSectionError:
            return 'No section "%s" into formsweb.cfg file.' % self.su_user

    def change_password(self, hostname, aliases):
        password = self._make_password(hostname, aliases)
        ret = []
        ret.append(self.change_su_password(password))
        ret.append(self.change_system_passwd(password))
        
        ret = filter(None, ret)
        return '\n'.join(ret)

    def change_su_password(self, password):
        '''
        Process su ux password change and launch tcho
        change_hostname.sh script that change password in
        oracle database.
        Param: None
        Return:  if error on change_hostname.sh
        '''
        err = []

        try:
            if self.conf_files['as_formsweb'] != None:
                formsweb_conf = ConfigParser.ConfigParser()
                formsweb_conf.readfp(open(self.conf_files['as_formsweb']))
                err.append(self._change_formsweb(formsweb_conf, password))
            if self.conf_files['as_dads'] != None:
                dads_conf = conf.Conf(self.conf_files['as_dads'])
                err.append(self._change_dads(dads_conf, password))



            # Dirty workaroud to Empty err element
            err = filter(None, err)       
            
            if err != []:
                err.append('\nAbort changing SU password.\nAnyway, your hosts file was writen.')
                return '\n'.join(err)
        except KeyError:
            pass
        
        try:
            executil.system('/bin/su '+ self.su_user +' - -c "~'+self.su_user+'/run/bin/change_hostname.sh" > /dev/null 2>&1')
        except executil.ExecError:
            return 'Can\'t execute change_hostname.sh script.\nMay be user %s doesn\'t exists or script is missing.\nSU password has not been changed.' % user

    def change_system_passwd(self, password):
        cmd_sys = subprocess.Popen(['/usr/bin/passwd', '--stdin', self.su_user], stdin=subprocess.PIPE, stdout=subprocess.PIPE)
        output = cmd_sys.communicate(input=password)
        retcode = cmd_sys.wait()
        if retcode != 0:
            return 'Changing %s password error! Output : %s'% (self.su_user, output)
        cmd_smb = subprocess.Popen(['/usr/bin/smbpasswd', '-s', self.su_user], stdin=subprocess.PIPE, stdout=subprocess.PIPE)
        output = cmd_smb.communicate(input=password+'\n'+password)
        retcode = cmd_smb.wait()
        if retcode != 0:
            return 'Changing %s samba password error! Output : %s'% (self.su_user, output)
        
    def record_checksums(self):
        '''
        Record files checksum about Syleps essentials files that do not have 
        to change over time.
        '''
        self.csum_file = os.path.join(self.var_dir,'csums')
        
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
