ansible-lxc
===========

Ansible Connection Plugin for lxc containers (https://linuxcontainers.org/)
The plugin will use lxc-attach under the hood to connect to containers

INSTALL
=======

* Install python2 version of lxc bindings:

   - https://github.com/lxc/python2-lxc

* Clone the plugin in your ansible directory

```
$ mkdir -p /etc/ansible/connection_plugins/
$ git clone git@github.com:Mic92/ansible-lxc.git /etc/ansible/connection_plugins/lxc
```

If your ansible code is already managed by git, you might want to add a submodule instead:

```
$ mkdir -p /etc/ansible/connection_plugins/
$ git submodule add git@github.com:Mic92/ansible-lxc.git /etc/ansible/connection_plugins/lxc
```

* Then add lxc directory to plugin search path in `ansible.cfg`:

```
connection_plugins = /usr/share/ansible_plugins/connection_plugins:/etc/ansible/connection_plugins/lxc
```

USAGE
=====

In your hosts file use container name (`examplecontainer` in this case) as hostname and `ansible_connection` to lxc:

    examplecontainer ansible_connection=lxc
