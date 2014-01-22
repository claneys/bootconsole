%define name bootconsole
%define version 1.1
%define release el5_1

Summary: Boot Ncurses Console configuration
Name: %{name}
Version: %{version}
Release: %{release}
Source0: %{name}-%{version}.tar.gz
License: UNKNOWN
Group: Development/Libraries
BuildRoot: %{_tmppath}/%{name}-%{version}-%{release}-buildroot
Prefix: %{_prefix}
BuildArch: noarch
Vendor: Romain Forlot <romain.forlot@syleps.fr>
Url: http:/github.com/claneys/bootconsole
Requires: dialog

%description
The Configuration Console's objective is to provide the user with basic network configuration information and the ability to perform basic tasks, so as not to force the user to the command line.
The information provided includes: - The binded IP address - The listening services the user may connect to over the network - Version of core appliance software like Oracle database, application server... - Serial Number of appliances matching 3 servers database, application server and SUPrintServer
The basic tasks that the user may perform include: - Setting a static IP address - Requesting DHCP - Set /etc/hosts entries about appliance's servers - Rebooting the appliance - Shutting down the appliance

%prep
%setup

%build
python setup.py build

%install
python setup.py install --root=$RPM_BUILD_ROOT --record=INSTALLED_FILES

%clean
rm -rf $RPM_BUILD_ROOT

%files -f INSTALLED_FILES
%defattr(-,root,root)

%post
# Add Header in bootconsole managed files
sed -i'.rpmsave' "1i# SYLEPS CONFCONSOLE\n# Don't modify this part \!" /etc/sysconfig/network-scripts/ifcfg-eth0
sed -i'.rpmsave' "1i# SYLEPS CONFCONSOLE\n# Don't modify this part \!" /etc/sysconfig/network
sed -i'.rpmsave' "1i# SYLEPS CONFCONSOLE\n# Don't modify this part \!" /etc/resolv.conf
sed -i'.rpmsave' "s/1:2345:respawn:.*mingetty tty1/1:2345:respawn:\/usr\/bin\/startscreen/" /etc/inittab

%postun
# Remove Header in bootconsole managed files
sed -i -e "/# SYLEPS CONFCONSOLE/d" -e "/# Don't modify this part \!/d" /etc/sysconfig/network-scripts/ifcfg-eth0
sed -i -e "/# SYLEPS CONFCONSOLE/d" -e "/# Don't modify this part \!/d" /etc/sysconfig/network
sed -i -e "/# SYLEPS CONFCONSOLE/d" -e "/# Don't modify this part \!/d" /etc/resolv.conf
sed -i "s/1:2345:respawn:.\/usr\/bin\/startscreen/1:2345:respawn:\/sbin\/mingetty tty1/" /etc/inittab
