#!/bin/bash
# deploy_agent.sh - Install or verify BladeLogic RSCD agent on Linux

if command -v rscd > /dev/null; then
  echo "BladeLogic agent already installed."
  rscd --version
else
  echo "Installing BladeLogic agent..."
  # Replace with your RSCD installer path or repo
  yum install -y bladelogic-rscd || apt-get install -y bladelogic-rscd || zypper install -y bladelogic-rscd
fi

systemctl enable rscd
systemctl start rscd
echo "Agent status:"
systemctl status rscd
