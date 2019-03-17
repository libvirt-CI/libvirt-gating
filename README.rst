libvirt-gating
**************

The project is for:

1. Setup `Avocado-vt <https://github.com/avocado-framework/avocado-vt>`_ and `tp-libvirt <https://github.com/autotest/tp-libvirt>`_ ready env for libvirt testing.

2. Provide a runner ``vtr`` for running avocado-vt test cases, a --gating option is supported to run a group of gating cases.

The project include shell, python scripts and Ansible playbooks.

Requirements
============

Packages: git, ansible, libvirt, qemu-kvm, virt-manager-common, firewalld

If on CentOS, make sure you have EPEL repo configured
::

  $ sudo yum install epel-release -y

Install rpm packages if on Fedora/RHEL/CentOS
::

  $ sudo yum install git python-pip libvirt qemu-kvm virt-manager-common firewalld -y

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

The setup script will run ansible playbook with install all missing packages
and install Avocado, Avocado-vt with tp-libvirt, then run the boostrap to
make avocado-vt env ready.

Runner command
==============

vtr -- avocado-vt runner

The ``vtr`` command is avocado command wrapper with support run avocado-vt
tp-libvirt test cases.
As tp-libvirt test cases require privilege user, following commands need run
under ``root`` or with ``sudo`` user.

::

    $ sudo vtr --help

Run the gating group of tp-libvirt test cases
::

    $ sudo vtr run --gating

.. note:: The gating cases is listed in cases/gating.only, and xunit file will
    be generated under current work path.

Run a specific tp-libvirt case
::

    $ sudo vtr run virsh.start.status_error_no.normal_start

List test cases
::

    $ sudo vtr list --gating    <-- list cases in cases/gating.only

    $ sudo vtr list virsh.start    <-- list sub tests under virsh.start

Rerun previous tests
::

    $ sudo vtr rerun --ignore-pass --xunit $previous_run_result.xml

The rerun command currently only support rerun with given xunit file from
previous run. If not specify, it will retrieve latest xunit file under
current dir. With --ignore-pass option, only failed cases will be rerun.

.. note:: The native Avocado command is default supported after install
    with the project, so you could run all your familiar avocado command
    also
    e.g. ::

    $ sudo avocado list --vt-type libvirt --machine-type q35

Libvirt gating cases
====================

The cases in cases/gating.only are selected avocado-vt/tp-libvirt test
cases under tier1 functional group, it's for CI gating against libvirt
package.

The test cases could run in::

  - Machines: Bare Metal, KVM Nested VM
  - OS Distro: Fedora, CentOS, RHEL

Time for running the gating cases: within 40 minutes

Test log and report
===================

The runner have simple console output of the test run progress and result
status of each test case been run.

The runner generates xunit file for report.

As the vtr command is Avocado wrapper to simplify runing avocado-vt test cases,
the original avocado-vt test case logs will be generated also.

Test case debug
===============

When test cases failed, failed case log link will be displayed in the console,
e.g.
::

  (58/63) virsh.vol_create.create.positive_test.disk_pool.vol_format_linux.pool_format_none.non_encryption Result: ERROR: 15.07 s
  log file: /root/avocado/job-results/job-2019-03-16T05.05-f11c028/job.log

Also the test log is collected in the xunit file under current working path
::

  $ ls -l
  -rw-r--r--. 1 root   root   96124 Mar 16 05:10 vtr_result_16-Mar-2019_04:41:40_UTC

When the problem is fixed, whether is libvirt bug, test framework, test case
bug or test env issue, the case could be specified with ``vtr rerun`` command
to rerun
::

  $ sudo vtr rerun --ignore-pass --xunit vtr_result_16-Mar-2019_04:41:40_UTC
  There are 1 cases pass in 1 cases

Image Builder
=============

The gating cases could be run inside kvm VM, for prepare CentOS and Fedora VM
image with libvirt gating env and install vtr command, check image-builder dir.

The setup script will run ansible playbook to install VM, the kickstart file
include run gating setup script in %post install.
