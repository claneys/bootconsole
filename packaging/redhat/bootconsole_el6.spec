%define name bootconsole
%define version 1.11
%define release 3.el6

Summary: Boot Ncurses Console configuration
Name: %{name}
Version: %{version}
Release: %{release}
Source0: %{name}-%{version}.tar.gz
License: GPL
Source1: %{name}.conf
Source2: start-ttys.override
Group: Development/Libraries
BuildRoot: %{_tmppath}/%{name}-%{version}-%{release}-buildroot
Prefix: %{_prefix}
BuildArch: noarch
Vendor: Romain Forlot <romain.forlot@syleps.fr>
Url: http:/github.com/claneys/bootconsole
Requires: dialog

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
python setup.py install --root=$RPM_BUILD_ROOT --record=INSTALLED_FILES
%{__install} -D -m0644 %{SOURCE1} %{buildroot}%{_sysconfdir}/init/%{name}.conf
%{__install} -D -m0644 %{SOURCE2} %{buildroot}%{_sysconfdir}/init/start-ttys.override

%clean
rm -rf $RPM_BUILD_ROOT

%files -f INSTALLED_FILES
%defattr(-,root,root)
%config %{_sysconfdir}/%{name}/%{name}.conf
%config %{_sysconfdir}/%{name}/usage.txt
%config %{_sysconfdir}/init/%{name}.conf
%config %{_sysconfdir}/init/start-ttys.override
%{_var}%{_lib}/bootconsole

%post
# Add Header in bootconsole managed files
ifcfg=$(grep 'SYLEPS CONFCONSOLE' %{_sysconfdir}/sysconfig/network-scripts/ifcfg-eth0)
network=$(grep 'SYLEPS CONFCONSOLE' %{_sysconfdir}/sysconfig/network)
inittab=$(grep 'startscreen' %{_sysconfdir}/inittab)
[ -z "$ifcfg" ] && sed -i'.rpmsave' "1i# SYLEPS CONFCONSOLE\n# Don't modify this part \!" %{_sysconfdir}/sysconfig/network-scripts/ifcfg-eth0
[ -z "$network" ] && sed -i'.rpmsave' "1i# SYLEPS CONFCONSOLE\n# Don't modify this part \!" %{_sysconfdir}/sysconfig/network
exit 0

%postun
# $1 = 0 uninstall, $1 = 1 upgrade
if [ "$1" = "0" ]
then
    # Remove Header in bootconsole managed files
    sed -i -e "/# SYLEPS CONFCONSOLE/d" -e "/# Don't modify this part \!/d" %{_sysconfdir}/sysconfig/network-scripts/ifcfg-eth0
    sed -i -e "/# SYLEPS CONFCONSOLE/d" -e "/# Don't modify this part \!/d" %{_sysconfdir}/sysconfig/network
    sed -i -e "/# SYLEPS CONFCONSOLE/d" -e "/# Don't modify this part \!/d" %{_sysconfdir}/resolv.conf
    # And validated file
    if [ -f %{_sysconfdir}/bootconsole/validated ]
    then
        chattr -i %{_sysconfdir}/bootconsole/validated
        rm -f %{_sysconfdir}/bootconsole/validated
    fi
fi
