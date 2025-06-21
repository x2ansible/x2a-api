#!/bin/bash
# linux_patch.sh - Apply security updates on Linux

echo "Updating package repository..."
if command -v yum > /dev/null; then
  yum clean all
  yum -y update --security
elif command -v apt-get > /dev/null; then
  apt-get update
  apt-get -y upgrade
elif command -v zypper > /dev/null; then
  zypper refresh
  zypper patch --with-interactive
else
  echo "ERROR: Unsupported package manager!"
  exit 1
fi

echo "Patching complete. Reboot if necessary."
