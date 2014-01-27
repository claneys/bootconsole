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
    for dir in ("/etc", "conf", "/etc/bootconsole"):
        path = os.path.join(dir, filename)
        if os.path.exists(path):
            return path

    raise Error('could not find configuration file: %s' % path)

class Conf:
    def __init__(self, conf_file):
        self.param = {}
        self.conf_file = path(conf_file)
        self._load_conf()
        
    def _load_conf(self):
        if not os.path.exists(self.conf_file):
            return

        for line in file(self.conf_file).readlines():
            line = line.strip()

            if not line or line.startswith("#"):
                continue

            try:
                op, val = re.split(r'\s+', line, 1)
            except ValueError:
                op = line
                val = ''
            if ipaddr.is_legal_ip(op):
                self.param[op] = val.split()
                continue
            self.param[op] = val

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

    def set_hosts(self, ip, hostname, peer_hostname, peer_ip, alias):
        try:
            if alias == "ofm11g":
                peer_alias = "oradb11g"
            else:
                peer_alias = "ofm11g"

            ifutil.NetworkSettings().set_hostname(hostname)

            original_content = []
            is_custom = False
            fh = open(self.conf_file, 'r')
            for line in fh.readlines():
                if re.search(alias, line) is not None or re.search(peer_alias, line) is not None:
                    continue
                if line.startswith('# End Syleps hosts'):
                    is_custom = False
                    continue
                if is_custom == True:
                    continue
                if line.startswith('# Syleps hosts'):
                    is_custom = True
                    continue
                original_content.append(line)

            fh.close()

            fh = open(self.conf_file, 'w')
            fh.writelines(original_content)
            fh.close()

            fh = open(self.conf_file, 'w')
            fh.writelines(original_content)
            fh.write("# Syleps hosts\n")
            fh.write("# Don't modifiy this part !\n")
            fh.write(ip + "\t" + hostname + "\t" + hostname.split('.', 1)[0] + "\t" + alias +"\n")
            fh.write(peer_ip + "\t" + peer_hostname + "\t" + peer_hostname.split('.', 1)[0] + "\t" + peer_alias+"\n")
            fh.write("# End Syleps hosts\n")
            fh.close()
        except Exception, e:
            return str(e)
