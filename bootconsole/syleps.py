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
from netinfo import NetworkInfo
import ConfigParser
from conf import Conf
import pwd
from conf import Conf

class SylepsError(Exception):
    def __init__(self, msg):
        self.msg = msg
        
    def __str__(self):
        return repr(self.msg)

class Syleps:
    '''
    Syleps object that take care of password change when hostname change
    and configuration files integrity.
    '''

    def __init__(self, bootconsole_conf=Conf('bootconsole.conf')):
        self.bootconsole_conf = bootconsole_conf
        self.var_dir = bootconsole_conf.get_param('var_dir')
        self.as_user = bootconsole_conf.get_param('as_user')
        self.db_user = bootconsole_conf.get_param('db_user')
        self.suux_user = bootconsole_conf.get_param('suux_user')
        self.suas_user = bootconsole_conf.get_param('suas_user')
        
        # Append system configuration files
        self.conf_files = { 'ntp': '/etc/ntp.conf',
                            'hosts' : '/etc/hosts',
                            'resolv' : ifutil.NetworkSettings.RESOLV_FILE,
                            'network' : ifutil.NetworkSettings.NETWORK_FILE,
                            'net_interface' : '%s/ifcfg-%s' % (ifutil.NetworkSettings.IFCFG_DIR, bootconsole_conf.get_param('default_nic')),
        }
        
        self._last_init(bootconsole_conf.get_param('component'))
        
    def _last_init(self, component):
        # Only process first product installed as we install one product by machine
        if 'Database' in component or 'DB' in component:
            component = 'DB'
            peer_component = 'AS'
            if 'as_tnsnames' in self.conf_files:
                del self.conf_files['as_tnsnames']
                del self.conf_files['as_formsweb']
                del self.conf_files['as_dads']
            self.su_user = self.suux_user
            if self.define_conf_file('db_tnsnames'):
                self.conf_files['db_tnsnames'] = Syleps._find_file_in_homedir(self.db_user, 'tnsnames.ora')
            if self.define_conf_file('db_listener'):
                self.conf_files['db_listener'] = Syleps._find_file_in_homedir(self.db_user, 'listener.ora')
            if self.define_conf_file('su_profile'):
                self.conf_files['suux_profile'] = os.path.expanduser('~'+self.su_user+'/.profile')
            if self.define_conf_file('su_profile_spec'):
                self.conf_files['suux_profile_spec'] = os.path.expanduser('~'+self.su_user+'/.profile.spec')
            if self.define_conf_file('su_profile_ora'):
                self.conf_files['suux_profile_ora'] = os.path.expanduser('~'+self.su_user+'/.profile.ora')
            if self.define_conf_file('su_profile_std'):
                self.conf_files['suux_profile_std'] = os.path.expanduser('~'+self.su_user+'/.profile.std')
        else:
            component = 'AS'
            peer_component = 'DB'
            if 'db_tnsnames' in self.conf_files:
                del self.conf_files['db_tnsnames']
                del self.conf_files['db_listener']
            self.su_user = self.suas_user
            if self.define_conf_file('as_tnsnames'):
                self.conf_files['as_tnsnames'] = Syleps._find_file_in_homedir(self.as_user, 'tnsnames.ora')
            if self.define_conf_file('as_formsweb'):
                self.conf_files['as_formsweb'] = Syleps._find_file_in_homedir(self.as_user, 'formsweb.cfg')
            if self.define_conf_file('as_dads'):
                self.conf_files['as_dads'] = Syleps._find_file_in_homedir(self.as_user, 'dads.conf', exclude='FRHome')
            if self.define_conf_file('su_profile'):
                self.conf_files['su_profile'] = os.path.expanduser('~'+self.su_user+'/.profile')
            if self.define_conf_file('su_profile_spec'):
                self.conf_files['su_profile_spec'] = os.path.expanduser('~'+self.su_user+'/.profile.spec')
            if self.define_conf_file('su_profile_ora'):
                self.conf_files['su_profile_ora'] = os.path.expanduser('~'+self.su_user+'/.profile.ora')
            if self.define_conf_file('su_profile_std'):
                self.conf_files['su_profile_std'] = os.path.expanduser('~'+self.su_user+'/.profile.std')
                
        return (component, peer_component)
        
    def define_conf_file(self, conf_file):
        '''
        Return true when file has to be defined and
        False if it is already defined
        '''
        if self.bootconsole_conf.get_param(conf_file) == []:
            return True
        else:
            self.conf_files[conf_file] = self.bootconsole_conf.get_param(conf_file)
            return False
    
    def get_SU_version(self, peer_host, component):
        remote = 'ssh -o StrictHostKeyChecking=no root@%s "' % peer_host
        pre_cmd = 'su - %s -c \'' % self.suux_user
        ending = '"'
        SU_version_cmd = 'sqlplus $ORACLE_USER/$ORACLE_PASSWD << EOF | grep -E "^[0-9]+"\nselect su_bas_get_version_std from dual;\nEOF\n\''
        SU_env_cmd = 'sqlplus $ORACLE_USER/$ORACLE_PASSWD << EOF | grep -E "^Config"\nselect lib_cfg_appli from su_cfg_appli where etat_actif=\'1\';\nEOF\n\''
        
        try:
            if component == 'DB':
                SU = { 'version' : executil.getoutput('%s%s' % (pre_cmd,SU_version_cmd)),
                       'env' : executil.getoutput('%s%s' % (pre_cmd,SU_env_cmd)),
                }
            else:
                SU = { 'version' : executil.getoutput('%s%s%s%s' % (remote,pre_cmd,SU_version_cmd,ending)),
                       'env' : executil.getoutput('%s%s%s%s' % (remote,pre_cmd,SU_env_cmd,ending)),
                }
        except executil.ExecError:
            SU = { 'version' : 'No SU detected',
                   'env' : 'No SU detected',
            }

        return SU
        
    def get_ora_versions(self, peer_host, vfile):
        OracleProductsInstalled = self._getOracleProducts(peer_host)
        # Check there is no errors
        if isinstance(OracleProductsInstalled, str):
            return OracleProductsInstalled
        
        version = re.sub(r'\s+', ' ',OracleProductsInstalled[0][0])
        peer_version = re.sub(r'\s+', ' ', OracleProductsInstalled[1][0])
        
        component, peer_component = self._last_init(OracleProductsInstalled[0][0])
        
        SU = self.get_SU_version(peer_host, component)
        
        # Just store version info into the first flag file
        # So we can retrieve them later without going to ask the peer node.
        fh = open(vfile, 'w')
        fh.write("%s\n%s\n%s\n%s" % (version, peer_version, SU['version'], SU['env']))
        fh.close()
        
        # Rewrite bootconsole configuration
        self.bootconsole_conf.change_param('component', component)
        self.bootconsole_conf.change_param('peer_component', peer_component)
        for label, conf_file in self.conf_files.iteritems():
            # Check if all files found
            if conf_file.startswith('Error'):
                return conf_file
            self.bootconsole_conf.change_param(label, conf_file)
        
        self.bootconsole_conf.write_conf()
            
    def _getOracleProducts(self, peer_host=None):

        opatch_cmd = Syleps._find_file_in_homedir(self.as_user, 'opatch')
        users = [ self.as_user, self.db_user ]
        # Check opatch file retrieved
        if opatch_cmd.startswith('Error'):
            opatch_cmd = Syleps._find_file_in_homedir(self.db_user, 'opatch')
            users = [ self.db_user, self.as_user ]
            # Again
            if opatch_cmd.startswith('Error'):
                return opatch_cmd
        
        # Make awk cmd to extract only products installed, except Examples products.
        begin_pattern = 'Installed Top-level Products'
        end_pattern = 'There are [0-9]+ products installed in this Oracle Home'
        awk_cmd = 'awk \'/%s/{f=1;next} /%s/ {f=0} f && ! /^$/ && ! /Example/ {print}\'' % (begin_pattern, end_pattern)
        
        products = [ executil.getoutput_popen('su - %s -c "%s lsinv" | %s' % (users[0], opatch_cmd, awk_cmd), input='\n\n').split('\n'),
                    executil.getoutput_popen('ssh -o StrictHostKeyChecking=no root@%s "su - %s -c \'opatch lsinv\' | %s"' % (peer_host, users[1], awk_cmd), input='\n\n').split('\n')
                   ]
        return products
        
    @staticmethod
    def _is_syleps_compliant(hostname):   
        # make sure that we act on shortname
        shortname = NetworkInfo.get_shortname(hostname)
        if re.search(r'^[a-zA-Z0-9]{3,6}(db|as)su[ptrmd]$', shortname) :
            return True
        return False
    
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
                
        return "Error: '%s' File not found, or wrong user '%s' selected!\nCheck your bootconsole configuration." % (file2find, user)

    @staticmethod
    def _check_ret(ret):
        if ret == None:
            return True
        pass
    
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
        return 'Error : Can\'t make password from hostname.\nCheck hostname and alias, may be you do not supply a Syleps compliant value(ie: CCCSSSdbsup).'
    
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
            return 'Error: Don\'t find PlsqlDatabasePassword statement in dads.conf file.'

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
            return 'Error: No section "%s" into formsweb.cfg file.' % self.su_user

    def change_password(self, hostname, aliases):
        password = self._make_password(hostname, aliases)
        if password.startswith('Error'):
            return password
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
                err.append('Error: \nAbort changing SU password.\nAnyway, your hosts file was writen.')
                return '\n'.join(err)
        except KeyError:
            pass
        
        try:
            executil.system('/bin/su '+ self.su_user +' - -c "~'+self.su_user+'/run/bin/change_hostname.sh" > /dev/null 2>&1')
        except executil.ExecError:
            return 'Error: When execute change_hostname.sh script.\nMay be user %s doesn\'t exists or wrong component configured or script is missing.\n Execute it manually and see what\'s going wrong.\nSU password has not been changed.' % self.su_user

    def change_system_passwd(self, password):
        cmd_sys = subprocess.Popen(['/usr/bin/passwd', '--stdin', self.su_user], stdin=subprocess.PIPE, stdout=subprocess.PIPE)
        output = cmd_sys.communicate(input=password)
        retcode = cmd_sys.wait()
        if retcode != 0:
            return 'Error: Changing %s password error! Output : %s'% (self.su_user, output)
        cmd_smb = subprocess.Popen(['/usr/bin/smbpasswd', '-s', self.su_user], stdin=subprocess.PIPE, stdout=subprocess.PIPE)
        output = cmd_smb.communicate(input=password+'\n'+password)
        retcode = cmd_smb.wait()
        if retcode != 0:
            return 'Error: Changing %s samba password error! Output : %s'% (self.su_user, output)
        
    def record_checksums(self):
        '''
        Record files checksum about Syleps essentials files that do not have 
        to change over time.
        '''
        csum_file = os.path.join(self.var_dir,'csums')
        
        if os.access(csum_file, os.F_OK):
            content = open(csum_file, 'r').readlines()
            bck_file = '.'.join((csum_file, datetime.now().strftime('%d%m%y%H%M%S')))
            fh = open(bck_file, 'w')
            fh.writelines(content)
            fh.close()

        fh = open(csum_file, 'w')
        for k, v in self.conf_files.iteritems():
            try:
                csum = hashlib.sha256(open(v, 'rb').read()).hexdigest()
            except:
                continue
            line = ' '.join((v, csum, '\n'))
            fh.write(line)

        fh.close()
