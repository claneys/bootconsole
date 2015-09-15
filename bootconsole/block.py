# Copyright (c) 2014 Romain Forlot <romain.forlot@syleps.fr> - all rights reserved

import re
import os
import executil
from datetime import datetime
import netinfo
import ipaddr
import hashlib
import ConfigParser
from bootconsole.conf import Conf

class Error(Exception):
    pass

class BlockDevices:

    def __init__(self):
        self.disks = self.get_disks()
        # Corresponding expand command associated with the partition type
        # trailing space is important, do not strip it.
        self.resize_cmd_choice = { '8e' : 'pvresize ',
                              '83' : 'resize2fs ',
                              '82' : '',
                              '5'  : 'echo "Do not support extended resize. Please call your Syleps SIC."'}

        self.code_type = { 'LVM2' : '8e',
                     'ext3' : '83',
                     'ext4' : '83',
                     'swap' : '82',
                     'extended' : '5' }

    def detect_part_type(self, part):
                try:
                    type = executil.getoutput('/usr/bin/file -s '+part+' | grep -Eo "LVM2|ext[2-4]|XFS|swap|extended"')
                    return self.code_type[type]
                except:
                    raise Error('Error: FS not compatible')

    @staticmethod
    def get_disks():
        disks = []
        for line in file('/proc/partitions').readlines():
            line = line.strip()
            if not line or line.startswith('major'):
                continue

            # size in MB
            size = int(line.split()[2])
            size = size / 1024

            elt = line.split()[3]
            if not re.search(r'\d+$', elt) and not elt.startswith('dm'):
                disks.append((elt, "%d MB" % size))

        return disks

    def get_lastpart(self, disk):

        device = '/dev/'+disk
        ret = {}

        for line in file('/proc/partitions').readlines():
            try:
                part = int(re.search(disk+r'(\d+)$', line).group(1))
            except AttributeError:
                 continue

            if part > 4:
                raise Error("Error: Bootconsole doesn't manage yet logical partitions.")

            lastpart_indice = str(part)
            parttype = self.detect_part_type(device+lastpart_indice)
            resize_cmd = self.resize_cmd_choice[parttype]+device+lastpart_indice
            max_size = self.get_max_size(device, lastpart_indice)
            ret = {'num': lastpart_indice, 'type': parttype, 'cmd': resize_cmd, 'max_size': max_size}
        return ret

    def rescan_disks(self):
        for disk in self.disks:
            device = '/dev/' + disk[0]
            executil.system('/bin/echo "1" > /sys/block/'+disk[0]+'/device/rescan')

        rescanned_disks = self.get_disks()
        ret_disks = []
        i = 0
        for rescanned_disk in rescanned_disks:
            disk = self.disks[i]
            if rescanned_disk[1] != disk[1]:
                ret_disks.append((rescanned_disk[0], '* Old: '+disk[1]+' New: '+rescanned_disk[1]))
            else:
                ret_disks.append((rescanned_disk[0], rescanned_disk[1]))
            i += 1
        return ret_disks

    def get_max_size(self, device, lastpart):
        # It is important to use sector as unit and not cylinder by default 'cause cylinder
        # doesn't have the necessary granulirity to correctly address partition.
        cmd = 'sfdisk --no-reread -uS -L -N'+lastpart+' '+device+' -L -uS << EOF 2>&1\n,999999999999,'+'\nEOF\n'

        output = executil.getoutput_popen(cmd, careabouterrors=False).split('\n')
        for line in output:
            if 'Warning' in line:
                maximum = re.search(r'\((\d+)\)$', line).group(1)
                return maximum

        raise Error('Error, contact Syleps support about that please: %s' % str(output))