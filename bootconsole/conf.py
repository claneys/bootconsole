# Copyright (c) 2008 Alon Swartz <alon@turnkeylinux.org> - all rights reserved
# Modified and adapted by Romain Forlot.
# Copyright (c) 2014 Romain Forlot <romain.forlot@syleps.fr> - all rights reserved

import re
import os
from ifutil import NetworkSettings
from ipaddr import IP

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
                
                if IP.is_legal(op):
                    self.param[op] = val.split()
                continue
            self.param[op] = val

    def set_param(self, param_key, new_value):
        # Define description of parameters
        # And assig new value to parameter
        param_desc = { 'default_nic' : '# set default network interface', 'alias' : '# set alias of this VM\n# set alias of this VM', }[param_key]
        self.param[param_key] = new_value

        # Write changes
        fh = open(self.conf_file, 'w')
        for k,v in self.param.items():
            k = k.strip()
            fh.write('%s\n%s %s' % (param_desc, k, v))

        fh.close()

    def set_hosts(self, ip, hostname, peer_hostname, sups_hostname, peer_ip, sups_ip, alias):
        try:
            if alias == "ofm11g":
                peer_alias = "oradb11g"
            else:
                peer_alias = "ofm11g"
            sups_alias = "sups"

            NetworkSettings().set_hostname(hostname)

            original_content = []
            is_custom = False
            fh = open(self.conf_file, 'r')
            for line in fh.readlines():
                if is_custom == True:
                    continue
                if line.startswith('# Syleps hosts'):
                    is_custom = True
                    continue
                elif line.startswith('# End Syleps hosts'):
                    is_custom = False
                    continue
                original_content.append(line)

            fh = open(self.conf_file, 'w')
            fh.writelines(original_content)
            fh.close()

            fh = open(self.conf_file, 'w')
            fh.writelines(original_content)
            fh.write("# Syleps hosts\n")
            fh.write("# Don't modifiy this part !\n")
            fh.write(ip + "\t" + hostname + "\t" + hostname.split('.', 1)[0] + "\t" + alias +"\n")
            fh.write(peer_ip + "\t" + peer_hostname + "\t" + peer_hostname.split('.', 1)[0] + "\t" + peer_alias+"\n")
            fh.write(sups_ip + "\t" + sups_hostname + "\t" + sups_hostname.split('.', 1)[0] + "\t" + sups_alias+"\n")
            fh.write("# End Syleps hosts\n")
            fh.close()
        except Exception, e:
            return str(e)
