#!/usr/bin/env bash
# Run once as root on a fresh Ubuntu 22.04/24.04 Vultr VPS.
# Usage: DEPLOY_USER=deploy bash vps_bootstrap.sh
# Prerequisite: your SSH public key is already on root (Vultr "SSH Keys").
set -euo pipefail
DEPLOY_USER="${DEPLOY_USER:-deploy}"

apt-get update && apt-get -y upgrade
apt-get install -y ca-certificates curl gnupg ufw fail2ban unattended-upgrades git

# Docker official repo
install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
chmod a+r /etc/apt/keyrings/docker.asc
echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu $(. /etc/os-release && echo $VERSION_CODENAME) stable" > /etc/apt/sources.list.d/docker.list
apt-get update
apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin

# Non-root deploy user with the same SSH key
id "$DEPLOY_USER" &>/dev/null || adduser --disabled-password --gecos "" "$DEPLOY_USER"
usermod -aG docker,sudo "$DEPLOY_USER"
mkdir -p /home/$DEPLOY_USER/.ssh
cp /root/.ssh/authorized_keys /home/$DEPLOY_USER/.ssh/authorized_keys
chown -R $DEPLOY_USER:$DEPLOY_USER /home/$DEPLOY_USER/.ssh
chmod 700 /home/$DEPLOY_USER/.ssh && chmod 600 /home/$DEPLOY_USER/.ssh/authorized_keys

# SSH hardening (verify a second session as $DEPLOY_USER works BEFORE logging out)
sed -i 's/^#\?PermitRootLogin.*/PermitRootLogin no/' /etc/ssh/sshd_config
sed -i 's/^#\?PasswordAuthentication.*/PasswordAuthentication no/' /etc/ssh/sshd_config
systemctl restart ssh

# Firewall: SSH only for now. Open 80/443 later when Nginx + HTTPS are added.
ufw default deny incoming
ufw default allow outgoing
ufw allow OpenSSH
ufw --force enable
systemctl enable --now fail2ban unattended-upgrades
echo "Bootstrap complete. Log in as $DEPLOY_USER."
