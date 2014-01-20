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

    IFCFG_FILE='/etc/sysconfig/network-scripts/ifcfg-eth0'
    NETWORK_FILE='/etc/sysconfig/network'
    RESOLV_FILE='/etc/resolv.conf'
    HEADER_SYLEPS = "# SYLEPS CONFCONSOLE\n"
    WARN_SYLEPS = "# Don't modify this part !\n"
    def __init__(self):
        self.read_conf()

    def read_conf(self):
        self.conf = {}
        self.unconfigured = False

        ifname = None
        for line in file(self.IFCFG_FILE).readlines():
            line = line.rstrip()

            if line == self.HEADER_SYLEPS:
                self.unconfigured = True

            if not line or line.startswith("#"):
                continue

            if line.startswith("DEVICE"):
                ifname = line.split('=')[1]
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

    def write_conf(self, ifname, ifconf):
        self.read_conf()
        if not self.unconfigured:
            raise Error("refusing to write to %s\nheader not found: %s" %
                        (self.IFCFG_FILE, self.HEADER_SYLEPS))

        FILE = { "eth0" : self.IFCFG_FILE, "net" : self.NETWORK_FILE, "resolv" : self.RESOLV_FILE}[ifname]
        fh = file(FILE, "w")
        fh.write(self.HEADER_SYLEPS)
        fh.write(self.WARN_SYLEPS)
        fh.write("\n")
        fh.write(ifconf)

        fh.close()

    def set_dhcp(self, ifname):
        ifconf = "DEVICE=%s\nBOOTPROTO=dhcp\nONBOOT=yes" % (ifname)
        self.write_conf(ifname, ifconf)

    def set_manual(self, ifname):
        ifconf = "auto %s\niface %s inet manual" % (ifname, ifname)
        self.write_conf(ifname, ifconf)

    def set_static(self, ifname, addr, netmask, gateway=None, nameservers=[], hostname=None):
        ifconf = ["DEVICE=%s" % ifname,
                  "BOOTPROTO=none",
                  "IPADDR=%s" % addr,
                  "NETMASK=%s" % netmask,
                  "ONBOOT=yes"]

        networkconf = ["NETWORKING=yes"]
        if gateway:
            networkconf.append("GATEWAY=%s" % gateway)

        if hostname:
            networkconf.append("HOSTNAME=%s" % hostname)

        resolvconf = []
        if nameservers:
            for nameserver in nameservers:
                resolvconf.append("nameserver %s" % nameserver)

        ifconf = "\n".join(ifconf)
        networkconf = "\n".join(networkconf)
        resolvconf = "\n".join(resolvconf)
        self.write_conf(ifname, ifconf)
        self.write_conf('net', networkconf)
        self.write_conf('resolv', resolvconf)

class NetworkInterface:
    """enumerate interface information from /etc/network/interfaces"""

    def __init__(self, ifname):
        self.ifname = ifname

        interfaces = NetworkSettings()

        self.conflines = []
        if ifname in interfaces.conf:
            self.conflines = interfaces.conf[ifname].splitlines()

    def _parse_attr(self, attr):
        for line in self.conflines:

            vals = line.strip().split('=')
            if not vals:
                continue

            if vals[0] == attr:
                return vals

        return []

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
    return executil.getoutput("ifup", ifname)

def ifdown(ifname):
    return executil.getoutput("ifdown", ifname)

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

        net = netinfo.InterfaceInfo(ifname)
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

        net = netinfo.InterfaceInfo(ifname)
        if not net.addr:
            raise Error('Error obtaining IP address\n\n%s' % output)

    except Exception, e:
        return str(e)

def get_ipconf(ifname):
    net = netinfo.InterfaceInfo(ifname)
    return net.addr, net.netmask, net.gateway, get_nameservers(ifname)

def get_ifmethod(ifname):
    interface = NetworkInterface(ifname)
    return interface.method

def get_ifmacaddr(ifname):
    interface = NetworkInterface(ifname)
    return interface.macaddr

def get_shortname(hostname):
    return hostname.split(".", 1)[0]
