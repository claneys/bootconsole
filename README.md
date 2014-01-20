Syleps Linux Configuration Console
===================================

The Configuration Console's objective is to provide the user with basic
network configuration information and the ability to perform basic
tasks, so as not to force the user to the command line.

The information provided includes:
    - The binded IP address
    - The listening services the user may connect to over the network
    - Version of core appliance software like Oracle database, application server...
    - Serial Number of appliances matching 3 servers database, application server and SUPrintServer

The basic tasks that the user may perform include:
    - Setting a static IP address
    - Requesting DHCP
    - Set /etc/hosts entries about appliance's servers
    - Rebooting the appliance
    - Shutting down the appliance

When setting a static IP address or requesting DHCP, /etc/network/interfaces
will be updated so the changes are perminent (unless the configuration
file has been customized by the user).

The Configuration Console will be invoked automatically on a new vt (by
its init script) unless the boot paramater 'noconfconsole' is present 
on /proc/cmdline. 

The Configuration Console (confconsole) may be executed manually aswell.