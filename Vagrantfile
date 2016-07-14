# -*- mode: ruby -*-
# vi: set ft=ruby :

# This is enough to get you a VM capable of running the unit tests. This should be expanded to install the app as well.
$script = <<SCRIPT
    dnf -y install python
    dnf -y install pyOpenSSL
    dnf -y install python-krbV
    dnf -y install python-urlgrabber
    dnf -y install rpm-python
    dnf -y install pygpgme
    dnf -y install pyliblzma
    dnf -y install python-iniparse
    dnf -y install pyxattr
    dnf -y install yum
    dnf -y install yum-metadata-parser
    dnf -y install python-simplejson
    dnf -y install python-mock
    dnf -y install python-nose
    dnf -y install PyGreSQL.x86_64
    dnf -y install python-coverage
SCRIPT

Vagrant.configure("2") do |config|
  config.vm.box = "box-cutter/fedora23"
  config.vm.provision "shell", inline: $script
end
