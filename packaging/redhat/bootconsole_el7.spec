%define name bootconsole
%define version 1.31
%define release 10.el7

Summary: Boot Ncurses Console configuration
Name: %{name}
Version: %{version}
Release: %{release}
Source0: %{name}-%{version}.tar.gz
License: GPL
Group: Development/Libraries
BuildRoot: %{_tmppath}/%{name}-%{version}-%{release}-buildroot
Prefix: %{_prefix}
BuildArch: noarch
Vendor: Syleps SA <support-sic@syleps.fr>
Url: http:/github.com/claneys/bootconsole
Requires: dialog, python-iniparse

%description
The Configuration Console's objective is to provide the user with basic network
configuration information and the ability to perform basic tasks,
so as not to force the user to the command line. The information provided includes:
- The binded IP address
- The listening services the user may connect to over the network
- Version of core appliance software like Oracle database, application server...
- Serial Number of appliances matching 3 servers database, application server and SUPrintServer
The basic tasks that the user may perform include:
- Setting a static IP address - Requesting DHCP
- Set NTP servers
- Extend FS
- Set /etc/hosts entries about appliance's servers
- Rebooting the appliance - Shutting down the appliance

%prep
%setup

%build
python setup.py build

%install
python setup.py install --root=$RPM_BUILD_ROOT
install -D packaging/redhat/getty@tty1.service ${RPM_BUILD_ROOT}/etc/systemd/system/getty@tty1.service

%clean
rm -rf $RPM_BUILD_ROOT

%files -n bootconsole
%defattr(-,root,root)
%config %{_sysconfdir}/%{name}/%{name}.conf
%config %{_sysconfdir}/%{name}/usage.txt
%config %{_sysconfdir}/systemd/system/getty@tty1.service
%{_bindir}/sic_seal
%{_bindir}/startscreen
%{python_sitelib}/*
/var/lib/bootconsole

%post
# Grab first ethernet interface
netint=$(ls -1 /sys/class/net/ | grep -v lo | head -n1)
# Add Header in bootconsole managed files
ifcfg=$(grep '# Syleps configuration' %{_sysconfdir}/sysconfig/network-scripts/ifcfg-${netint})
network=$(grep '# Syleps configuration' %{_sysconfdir}/sysconfig/network)
inittab=$(grep 'startscreen' %{_sysconfdir}/inittab)
[ -z "$ifcfg" ] && sed -i'.rpmsave' "1i# Syleps configuration\n# Don't modify this part \!" %{_sysconfdir}/sysconfig/network-scripts/ifcfg-${netint}
[ -z "$network" ] && sed -i'.rpmsave' "1i# Syleps configuration\n# Don't modify this part \!" %{_sysconfdir}/sysconfig/network
exit 0

%postun
# Grab first ethernet interface
netint=$(ls -1 /sys/class/net/ | grep -v lo | head -n1)
# $1 = 0 uninstall, $1 = 1 upgrade
if [ "$1" = "0" ]
then
    # Remove Header in bootconsole managed files
    sed -i -e "/# Syleps configuration/d" -e "/# Don't modify this part \!/d" %{_sysconfdir}/sysconfig/network-scripts/ifcfg-${netint}
    sed -i -e "/# Syleps configuration/d" -e "/# Don't modify this part \!/d" %{_sysconfdir}/sysconfig/network
    sed -i -e "/# Syleps configuration/d" -e "/# Don't modify this part \!/d" %{_sysconfdir}/resolv.conf
    # And validated file
    if [ -f %{_sysconfdir}/bootconsole/validated ]
    then
        chattr -i %{_sysconfdir}/bootconsole/validated
        rm -f %{_sysconfdir}/bootconsole/validated
    fi
    rm -rf %{_var}/lib/bootconsole
fi
