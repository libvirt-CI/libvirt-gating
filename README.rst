libvirt-gating
**************

The project is for:

1. Setup `Avocado-vt <https://github.com/avocado-framework/avocado-vt>`_ and `tp-libvirt <https://github.com/autotest/tp-libvirt>`_ ready env for libvirt testing.

2. Provide a runner `vtr` for running avocado-vt test cases, a --gating option is supported to run a group of gating cases.

The project include shell, python scripts and Ansible playbooks.

Requirements
============

Packages: git, ansible, pip, libvirt, qemu-kvm, virt-install

Python: Compatible with both Python 2.x and 3.x

Install
=======

1. Clone the repo
   ::

    $ git clone https://github.com/libvirt-CI/libvirt-gating.git

2. Run the setup script to prepare the env
   ::

    $ cd libvirt-gating
    $ sudo /bin/sh setup.sh

Runner command
==============

vtr -- avocado-vt runner

The `vtr` command is avocado command wrapper with support run avocado-vt
tp-libvirt test cases.
As tp-libvirt test cases require privilege user, following cmmands need run
under root or sudo user.

::

    # vtr --help

Run the gating group of tp-libvirt test cases
::

    # vtr run --gating

.. note:: The gating cases is listed in cases/gating.only, and xunit file will
    be generated under current work path.

Run a specific tp-libvirt case
::

    # vtr run virsh.start.status_error_no.normal_start

List test cases
::

    # vtr list --gating    <-- list cases in cases/gating.only

    # vtr list virsh.start    <-- list sub tests under virsh.start

Rerun previous tests
::

    # vtr rerun --xunit $previous_run_result.xml

The rerun command currently only support rerun with given xunit file from
previous run.

Test log and report
===================

The runner have simple console output of the test run progress and result
status of each test case been run.

The runner generates xunit file for report.


Image Builder
=============

The gating cases could be run inside kvm VM, for prepare CentOS and Fedora VM
image with libvirt gating env and install vtr command, check image-builder dir.

The setup script will run ansible playbook to install VM, the kickstart file
include run gating setup script in %post install.