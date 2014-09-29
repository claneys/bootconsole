# Copyright (c) 2008 Alon Swartz <alon@turnkeylinux.org> - all rights reserved
# Modified and adapted by Romain Forlot.
# Copyright (c) 2014 Romain Forlot <romain.forlot@syleps.fr> - all rights reserved

import os
import executil
import netinfo

class Error(Exception):
    pass

class NetworkSettings:
    """class for controlling /etc/sysconfig/network-scripts/ifcfg-ethX

    An error will be raised if the interfaces file does not include the
    header: # SYLEPS INTERFACES (in other words, we will not override
    any customizations)
    """

    # IFCFG_FILE not complete, you have to add a suffix (eth0, br0,...)
    IFCFG_DIR='/etc/sysconfig/network-scripts/'
    NETWORK_FILE='/etc/sysconfig/network'
    RESOLV_FILE='/etc/resolv.conf'
    HEADER_SYLEPS = "# SYLEPS CONFCONSOLE"
    WARN_SYLEPS = "# Don't modify this part !"

    def __init__(self):
        self.read_conf()

    def read_conf(self):
        self.conf = {}
        self.conf_files = []
        for _file in os.listdir(self.IFCFG_DIR):
            if _file.startswith('ifcfg-') and not _file.endswith('lo'):
                self.conf_files.append(_file)
        self.unconfigured = False

        ifname = None
        for ifcfg_file in self.conf_files:
            fname = self.IFCFG_DIR + ifcfg_file
            for line in file(fname).readlines():
                line = line.rstrip()

                if line == self.HEADER_SYLEPS:
                    self.unconfigured = True

                if not line or line.startswith("#"):
                    continue

                if line.startswith("DEVICE"):
                    ifname = line.split('=')[1]
                    ifname = ifname.strip('"')
                    self.conf[ifname] = line + "\n"
                elif ifname:
                    self.conf[ifname] += line + "\n"

    def _get_iface_opts(self, ifname):
        iface_opts = ('pre-up', 'up', 'post-up', 'pre-down', 'down', 'post-down')
        if ifname not in self.conf:
            return []

        ifconf = self.conf[ifname]
        return [ line.strip()
                 for line in ifconf.splitlines()
                 if line.strip().split()[0] in iface_opts ]

    def write_conf(self, filename, conf):
        self.read_conf()

        if not self.unconfigured:
            raise Error("refusing to write to %s\nheader not found: %s in ifcfg file.\nBootconsole not installed properly." %
                        (filename, self.HEADER_SYLEPS))

        fh = file(filename, "w")
        fh.write(self.HEADER_SYLEPS+'\n')
        fh.write(self.WARN_SYLEPS+'\n')
        fh.write("\n")
        fh.write(conf+'\n')

        fh.close()
    
    def _filepath_assembler(self, ifname):
        return self.IFCFG_DIR+"ifcfg-"+ifname

    def set_dhcp(self, ifname):
        filepath = self._filepath_assembler(ifname)
        ifconf = "DEVICE=%s\nBOOTPROTO=dhcp\nONBOOT=yes" % (ifname)
        self.write_conf(filepath, ifconf)

    def set_static(self, ifname, addr, netmask, gateway=None, nameservers=[], hostname=None):
        filepath = self._filepath_assembler(ifname)
        ifconf = "DEVICE=%s\nBOOTPROTO=none\nONBOOT=yes" % (ifname)
        ifconf = ["DEVICE=%s" % ifname,
                  "BOOTPROTO=none",
                  "IPADDR=%s" % addr,
                  "NETMASK=%s" % netmask,
                  "ONBOOT=yes"]

        networkconf = ["NETWORKING=yes"]
        if gateway:
            networkconf.append("GATEWAY=%s" % gateway)

        resolvconf = []
        if nameservers:
            for nameserver in nameservers:
                resolvconf.append("nameserver %s" % nameserver)

        ifconf = "\n".join(ifconf)
        networkconf = "\n".join(networkconf)
        resolvconf = "\n".join(resolvconf)
        self.write_conf(filepath, ifconf)
        self.write_conf(self.NETWORK_FILE, networkconf)
        self.write_conf(self.RESOLV_FILE, resolvconf)

    def set_hostname(self, hostname):
        fh = file(self.NETWORK_FILE, 'r')
        networkconf = []
        for line in fh.readlines():
            if line.startswith('HOSTNAME'):
                continue
            networkconf.append(line)
        networkconf.append("HOSTNAME=%s" % hostname)
        networkconf = "\n".join(networkconf)

        self.write_conf(self.NETWORK_FILE, networkconf)
        executil.system("hostname %s" % hostname)


class NetworkInterface:
    """enumerate interface information from /etc/network/interfaces"""

    def __init__(self, ifname):
        self.ifname = ifname

        self.networksettings = NetworkSettings()

        self.conflines = []
        if ifname in self.networksettings.conf:
            self.conflines = self.networksettings.conf[ifname].splitlines()

    def _parse_attr(self, attr):
        for line in self.conflines:

            vals = line.strip().split('=')
            if not vals:
                continue

            if vals[0] == attr:
                return vals

        return []

    def __getattr__(self, attrname):
        #attributes with multiple values will be returned in an array
        #exception: dns-nameservers always returns in array (expected)

        attrname = attrname.replace('_', '-')
        values = self._parse_attr(attrname)
        if len(values) > 2:
            return values[1:]
        elif len(values) > 1:
            return values[1]

        return

    def set_dhcp(self):
        try:
            self.ifdown()
            self.networksettings.set_dhcp(self.ifname)
            output = self.ifup()

            addr = netinfo.SysInterfaceInfo(self.ifname).address
            if not addr:
                raise Error('Error obtaining IP address\n\n%s' % output)

        except Exception, e:
            return str(e)

    def set_static(self, addr, netmask, gateway, nameservers, hostname):
        try:
            self.ifdown()
            self.networksettings.set_static(self.ifname, addr, netmask, gateway, nameservers, hostname)
            output = self.ifup()

            addr = netinfo.SysInterfaceInfo(self.ifname).address
            if not addr:
                raise Error('Error obtaining IP address\n\n%s' % output)

        except Exception, e:
            return str(e)

    def unconfigure_if(self):
        try:
            self.ifdown()
            self.networksettings.set_manual(self.ifname)
            executil.system("ifconfig %s 0.0.0.0" % self.ifname)
            self.ifup()
        except Exception, e:
            return str(e)

    def ifup(self):
        return executil.getoutput("ifup %s"% self.ifname)

    def ifdown(self):
        return executil.getoutput("ifdown %s"% self.ifname)

    @property
    def method(self):
        try:
            return self._parse_attr('BOOTPROTO')[1]
        except IndexError:
            return

    @property
    def macaddr(self):
        return self._parse_attr('HWADDR')[1]

    @property
    def dns_nameservers(self):
        return self._parse_attr('dns-nameservers')[1:]

    def __getattr__(self, attrname):
        #attributes with multiple values will be returned in an array
        #exception: dns-nameservers always returns in array (expected)

        attrname = attrname.replace('_', '-')
        values = self._parse_attr(attrname)
        if len(values) > 2:
            return values[1:]
        elif len(values) > 1:
            return values[1]

        return

def get_nameservers(ifname):
    #/etc/network/interfaces (static)
    #interface = NetworkInterface(ifname)
    #if interface.dns_nameservers:
    #    return interface.dns_nameservers

    def parse_resolv(path):
        nameservers = []
        for line in file(path).readlines():
            if line.startswith('nameserver'):
                nameservers.append(line.strip().split()[1])
        return nameservers

    #Debian relative
    #resolvconf (dhcp)
    #path = '/etc/resolvconf/run/interface'
    #if os.path.exists(path):
    #    for f in os.listdir(path):
    #        if not f.startswith(ifname) or f.endswith('.inet'):
    #            continue

    #        nameservers = parse_resolv(os.path.join(path, f))
    #        if nameservers:
    #            return nameservers

    #/etc/resolv.conf
    nameservers = parse_resolv('/etc/resolv.conf')
    if nameservers:
        return nameservers

    return []

def ifup(ifname):
    return executil.getoutput("ifup %s"% ifname)

def ifdown(ifname):
    return executil.getoutput("ifdown %s"% ifname)

def unconfigure_if(ifname):
    try:
        ifdown(ifname)
        interfaces = NetworkSettings()
        interfaces.set_manual(ifname)
        executil.system("ifconfig %s 0.0.0.0" % ifname)
        ifup(ifname)
    except Exception, e:
        return str(e)

def set_static(ifname, addr, netmask, gateway, nameservers, hostname):
    try:
        ifdown(ifname)
        interfaces = NetworkSettings()
        interfaces.set_static(ifname, addr, netmask, gateway, nameservers, hostname)
        output = ifup(ifname)

        net = netinfo.SysInterfaceInfo(ifname)
        if not net.addr:
            raise Error('Error obtaining IP address\n\n%s' % output)

    except Exception, e:
        return str(e)

def set_dhcp(ifname):
    try:
        ifdown(ifname)
        interfaces = NetworkSettings()
        interfaces.set_dhcp(ifname)
        output = ifup(ifname)

        net = netinfo.SysInterfaceInfo(ifname)
        if not net.addr:
            raise Error('Error obtaining IP address\n\n%s' % output)

    except Exception, e:
        return str(e)

def get_ipconf(ifname):
    net = netinfo.SysInterfaceInfo(ifname)
    return net.address, net.netmask, net.gateway, get_nameservers(ifname)

def get_ifmethod(ifname):
    interface = NetworkInterface(ifname)
    return interface.method

def get_ifmacaddr(ifname):
    interface = NetworkInterface(ifname)
    return interface.macaddr

def get_shortname(hostname):
    return hostname.split(".", 1)[0]

def get_filtered_ifnames():
    '''
    Return net interface name without useless or pseudo interface
    '''
    ifnames = []
    for ifname in netinfo.NetworkInfo().get_ifnames():
        is_ok = True
        for elt in ('lo', 'sit', 'tap', 'br', 'tun', 'vmnet', 'wmaster'):
            if ifname.startswith(elt):
                is_ok = False
        if is_ok == True:
            ifnames.append(ifname)

    ifnames.sort()
    return ifnames