from __future__ import absolute_import

import distutils.spawn
import os,sys,io
import subprocess
import shutil
import traceback
import select
import re
from ansible import errors
from ansible.callbacks import vvv

import lxc as _lxc

class Connection(object):
    """ Local lxc based connections """

    def _root_fs(self):
        rootfs = self.container.get_running_config_item("lxc.rootfs")
        # overlayfs use the scheme:
        #   overlayfs:/var/lib/lxc/LXC-Template-1404/rootfs:/var/lib/lxc/lxc-demo/delta0
        match = re.match(r'^overlayfs:.+?rootfs:(.+)', rootfs)
        if match:
            rootfs = match.group(1)
        if not rootfs:
            raise errors.AnsibleError("rootfs not set in configuration for %s") % self.host
        return rootfs

    def __init__(self, runner, host, port, *args, **kwargs):
        self.has_pipelining = False
        self.host = host
        # port is unused, since this is local
        self.port = port
        self.runner = runner

        self.container = _lxc.Container(host)
        if self.container.state == "STOPPED":
            raise errors.AnsibleError("%s is not running" % host)

        self.rootfs = self._root_fs()

    def connect(self, port=None):
        """ connect to the lxc; nothing to do here """

        vvv("THIS IS A LOCAL LXC DIR", host=self.host)

        return self

    def exec_command(self, cmd, tmp_path, sudo_user=None, become_user=None, sudoable=False, executable="/bin/sh", in_data=None, su=None, su_user=None):
        """ run a command on the chroot """

        local_cmd = [cmd]
        if executable:
            local_cmd = [executable, "-c"] + local_cmd
        if sudo_user:
            local_cmd = ["sudo", "-u", sudo_user, "--"] + local_cmd

        read_stdout, write_stdout = os.pipe()
        read_stderr, write_stderr = os.pipe()

        vvv("EXEC %s" % (local_cmd), host=self.host)

        pid = self.container.attach(_lxc.attach_run_command, local_cmd,
                stdout=write_stdout,
                stderr=write_stderr)
        os.close(write_stdout)
        os.close(write_stderr)
        fds = [read_stdout, read_stderr]

        buf = { read_stdout: [], read_stderr: [] }
        while len(fds) > 0:
            ready_fds, _, _ = select.select(fds, [], [])
            for fd in ready_fds:
              data = os.read(fd, 32768)
              if not data:
                  fds.remove(fd)
                  os.close(fd)
              buf[fd].append(data)

        (pid, returncode) = os.waitpid(pid, 0)

        stdout = b"".join(buf[read_stdout])
        stderr = b"".join(buf[read_stderr])

        return (returncode, "", stdout, stderr)

    def _normalize_path(self, path, prefix):
        if not path.startswith(os.path.sep):
            path = os.path.join(os.path.sep, path)
        normpath = os.path.normpath(path)
        return os.path.join(prefix, normpath[1:])

    def _copy(self, in_path, out_path):
        if not os.path.exists(in_path):
            raise errors.AnsibleFileNotFound("file or module does not exist: %s" % in_path)
        try:
            shutil.copyfile(in_path, out_path)
        except shutil.Error:
            traceback.print_exc()
            raise errors.AnsibleError("failed to copy: %s and %s are the same" % (in_path, out_path))
        except IOError:
            traceback.print_exc()
            raise errors.AnsibleError("failed to transfer file to %s" % out_path)

    def put_file(self, in_path, out_path):
        """ transfer a file from local to lxc """

        out_path = self._normalize_path(out_path, self.rootfs)

        vvv("PUT %s TO %s" % (in_path, out_path), host=self.host)
        self._copy(in_path, out_path)

    def fetch_file(self, in_path, out_path):
        """ fetch a file from lxc to local """

        in_path = self._normalize_path(in_path, self.rootfs)

        vvv("FETCH %s TO %s" % (in_path, out_path), host=self.host)
        self._copy(in_path, out_path)

    def close(self):
        """ terminate the connection; nothing to do here """
        pass
