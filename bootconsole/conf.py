# Copyright (c) 2008 Alon Swartz <alon@turnkeylinux.org> - all rights reserved
# Modified and adapted by Romain Forlot.
# Copyright (c) 2014 Romain Forlot <romain.forlot@syleps.fr> - all rights reserved

import re
import os
import executil
import ifutil
import ipaddr

class Error(Exception):
    pass

def path(filename):
    '''
    Try to find file in some default dir
    Return abs path it finds.
    '''
    for dir in ("/etc", "conf", "/etc/bootconsole"):
        path = os.path.join(dir, filename)
        if os.path.exists(path):
            return path

    raise Error('could not find configuration file: %s' % path)

class Conf:
    def __init__(self, conf_file, sep=None, merge=False):
        self.param = []
        self.sep = sep
        self.merge = merge
        self.conf_file = path(conf_file)
        self._load_conf()

    def _load_conf(self):
        if not os.path.exists(self.conf_file):
            return

        for line in file(self.conf_file).readlines():
            line = line.strip()

            if not line or line.startswith("#"):
                continue

            self.param.append(line)

    def del_param(self, key):
        for elt in self.param:
            if elt.startswith(key):
                self.param.remove(elt)
        for elt in self.param:
            if elt.startswith(key):
                self.param.remove(elt)

    def get_param(self, key, bare=False):
        ret = []
        for elt in self.param:
            if elt.startswith(key):
                if bare == False:
                    try:
                        ret.append(elt.split(self.sep, 1)[1])
                    except IndexError:
                        ret.append('')
                else:
                    ret.append(elt)

        if len(ret) == 1:
            ret = ret[0]
        elif ret == []:
            return('Could not find parameter %s in %s file' % (key, self.conf_file))
        
        return ret

    # Set a parameter at a given position or a the end by default.
    # That does not replace an existing parameter but add a new one.
    def set_param(self, key, val, index=None):
        if index == None :
            try:
                line = key + self.sep + val
            except TypeError:
                line = key + ' ' + val
            self.param.append(line)
        else:
            try:
                self.param.insert(index, key + self.sep + val)
            except TypeError:
                self.param.insert(index, key + ' ' + val)

    def write_conf(self):
        try:
            fh = open(self.conf_file, 'w')
            fh.write("# Syleps configuration\n")
            fh.write("# Don't modifiy this part !\n")
            for elt in self.param:
                fh.write(elt + "\n")
            fh.write("# End Syleps\n")
            fh.close()
        except:
            return "Something goes wrong when attempting to write file."

    def set_default_nic(self, ifname):
        self.param['default_nic'] = ifname

        fh = open(self.conf_file, 'r')
        content = fh.readlines()
        fh.close

        if not "default_nic" in content:
            content.insert(1, 'default_nic')

        fh = open(self.conf_file, 'w')
        for line in content:
            if line.startswith('default_nic'):
                fh.write("default_nic %s\n" % ifname)
                continue
            fh.write(line)
        fh.close()

    def set_hosts(self, ip, hostname, alias, peer_hostname, peer_alias, peer_ip):
        try:
            if alias.count("ofm11g") == 1:
                peer_alias.append("oradb11g")
            elif alias.count("oradb11g") == 1:
                peer_alias.append("ofm11g")
        except:
            raise Exception('Alias ('+' '.join(alias)+') configured in bootconsole.conf file isn\'t correct. Please fix it.')

        # Set domain name if not provided
        if not '.' in hostname:
            hostname = hostname + ".sydel.univers"
        if not '.' in peer_hostname:
            peer_hostname = peer_hostname + ".sydel.univers"

        ifutil.NetworkSettings().set_hostname(hostname)

        all_alias = alias+peer_alias
        original_content = []
        is_custom = False
        fh = open(self.conf_file, 'r')
        for line in fh.readlines():
            for pattern in all_alias:
                    if re.search(pattern, line) is not None:
                        continue
            if line.startswith('# End Syleps'):
                is_custom = False
                continue
            if is_custom == True:
                continue
            if line.startswith('# Syleps configuration'):
                is_custom = True
                continue
            original_content.append(line)

        fh.close()

        fh = open(self.conf_file, 'w')
        fh.writelines(original_content)
        fh.close()

        shortname = ''
        peer_shortname = ''
        if not hostname.split('.',1)[0] == hostname:
            shortname = hostname.split('.', 1)[0] + '\t'
        if not peer_hostname.split('.', 1)[0] == peer_hostname:
            peer_shortname = peer_hostname.split('.', 1)[0] + '\t'

        fh = open(self.conf_file, 'w')
        fh.writelines(original_content)
        fh.write("# Syleps configuration\n")
        fh.write("# Don't modify this part !\n")
        fh.write(ip + "\t" + hostname + "\t" + shortname + '\t'.join(alias) +"\n")
        fh.write(peer_ip + "\t" + peer_hostname + "\t" + peer_shortname + '\t'.join(peer_alias)+"\n")
        fh.write("# End Syleps hosts\n")
        fh.close()

    def get_host(self, alias, get_peer=False):
        # Define alias mapping to display correct label into dialog form
        # { alias_in_conf: [peer_label, peer_alias] }
        label_mapping = { 'ofm11g': {'label': 'DB', 'alias': 'oradb11g'},
                          'oradb11g': { 'label': 'AS', 'alias': 'ofm11g'} }

        # Inverse search to get peer host
        if get_peer:
            ret_alias = label_mapping[alias]['alias']
            ret_label = label_mapping[alias]['label']
        else:
            ret_alias = alias
            ret_label = label_mapping[label_mapping[alias]['alias']]['label']

        for elt in self.param:
            if ret_alias in elt:
                v = elt.split()[1:]
                other_alias = v[2:-1]
                return { 'hostname': v[0],
                        'ip' : elt.split()[0],
                        'others_alias': ','.join(other_alias),
                        'alias': ret_alias,
                        'label': ret_label }
        return { 'hostname': '',
                 'ip': '',
                 'others_alias': '',
                 'alias': '',
                 'label': '' }