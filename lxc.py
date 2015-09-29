from __future__ import absolute_import

import os, sys
import subprocess
import shutil
import traceback
import select
from ansible import errors, utils
from ansible.callbacks import vvv

import lxc as _lxc

class Connection(object):
    """ Local lxc based connections """

    def __init__(self, runner, host, port, *args, **kwargs):
        self.has_pipelining = False
        self.host = host
        self.runner = runner

        self.container = _lxc.Container(host)
        if self.container.state == "STOPPED":
            raise errors.AnsibleError("%s is not running" % host)

    def connect(self, port=None):
        """ connect to the lxc; nothing to do here """

        vvv("THIS IS A LOCAL LXC DIR", host=self.host)

        return self

    def exec_command(self, cmd, tmp_path, sudo_user=None, become_user=None, sudoable=False, executable="/bin/sh", in_data=None, su=None, su_user=None):
        """ run a command on the chroot """

        if self.runner.become and sudoable:
            cmd, prompt, success_key = utils.make_become_cmd(cmd, become_user, executable, self.runner.become_method, "", self.runner.become_exe)

        local_cmd = [cmd]
        if executable:
            local_cmd = [executable, "-c"] + local_cmd

        read_stdout, write_stdout = os.pipe()
        read_stderr, write_stderr = os.pipe()

        vvv("EXEC %s" % (local_cmd), host=self.host)

        pid = self.container.attach(_lxc.attach_run_command, local_cmd,
                stdout=write_stdout,
                stderr=write_stderr)

        if pid == -1:
            raise errors.AnsibleError("failed to attach to container %s", self.host)

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

    def put_file(self, in_path, out_path):
        """ transfer a file from local to lxc """

        vvv("PUT %s TO %s" % (in_path, out_path), host=self.host)
        if not os.path.exists(in_path):
            raise errors.AnsibleFileNotFound("file or module does not exist: %s" % in_path)
        try:
            src_file = open(in_path, "rb")
        except IOError:
            traceback.print_exc()
            raise errors.AnsibleError("failed to open file to %s" % in_path)

        def write_file(args):
            dst_file = open(out_path, 'wb')
            shutil.copyfileobj(src_file, dst_file)
        try:
            self.container.attach_wait(write_file, None)
        except IOError:
            traceback.print_exc()
            raise errors.AnsibleError("failed to transfer file to %s" % out_path)

    def fetch_file(self, in_path, out_path):
        """ fetch a file from lxc to local """

        vvv("FETCH %s TO %s" % (in_path, out_path), host=self.host)
        if not os.path.exists(in_path):
            raise errors.AnsibleFileNotFound("file or module does not exist: %s" % in_path)

        try:
            dst_file = open(out_path, "wb")
        except IOError:
            traceback.print_exc()
            raise errors.AnsibleError("failed to write to file %s" % out_path)

        def write_file(args):
            src_file = open(in_path, 'rb')
            shutil.copyfileobj(src_file, dst_file)
        try:
            self.container.attach_wait(write_file, None)
        except IOError:
            traceback.print_exc()
            raise errors.AnsibleError("failed to transfer file from %s to %s" % (in_path, out_path))

    def close(self):
        """ terminate the connection; nothing to do here """
        pass
