#!/bin/sh
# The dest os type
os_type=Fedora

path=$0
dir=.
if [[ $path == */* ]]; then
    dir=${path%/*}
fi
which yum
if [ $? == 0 ]; then
    user_software_manager=`which yum`
fi

py3_dependency=' wget gcc python3-devel python3-policycoreutils policycoreutils-python-utils python3-pip python3-libselinux'
py2_dependency=' wget gcc python-devel python-pip libselinux-python policycoreutils-python'
which python
if [ $? == 0 ]; then
    user_python=`which python`
    version=`python --version | grep -o [23].[0-9].[0-9]`
    if [[ $version = 3* ]]; then
        $user_software_manager install $py3_dependency -y
    else
        $user_software_manager install $py2_dependency -y
    fi
else
    which python3
        if [ $? == 0 ]; then
            user_python=`which python3`
            $user_software_manager install $py3_dependency -y
        else
            which /usr/libexec/platform-python
            if [ $? == 0 ]; then
                user_python=/usr/libexec/platform-python
                $user_software_manager install $py3_dependency -y
            fi
        fi
fi
if [ $? != 0 ]; then
    echo 'The packages installation failed, exiting'
    exit 1
fi

which /usr/bin/pip
if [ $? == 0 ]; then
    $user_python /usr/bin/pip install pip==9.0.3 ansible==2.6.14
else
    which /usr/bin/pip3
    if [ $? == 0 ]; then
        ln -s /usr/bin/pip3 /usr/bin/pip
        $user_python /usr/bin/pip install pip==9.0.3 ansible==2.6.14
    fi
fi

thepwd=`pwd`
export PATH=/usr/local/sbin:/usr/local/bin:$PATH
ansible-playbook $dir/guest_image_builder.yaml -e "pwd=$thepwd os_type=$os_type"
if [ $? != 0 ]; then
    echo 'The ansible prepare failed, exiting'
    exit 1
fi