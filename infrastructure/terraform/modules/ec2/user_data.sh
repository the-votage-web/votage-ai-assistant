#!/bin/bash

# Update system
yum update -y

# Install Docker
yum install -y docker git

# Start Docker service
systemctl start docker
systemctl enable docker

# Add ec2-user to docker group
usermod -a -G docker ec2-user

# Log system info
echo "Server initialized at $(date)" > /var/log/init.log
