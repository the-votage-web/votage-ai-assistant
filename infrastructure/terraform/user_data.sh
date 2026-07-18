#!/bin/bash

dnf update -y

dnf install docker git -y

systemctl enable docker
systemctl start docker

usermod -aG docker ec2-user

curl "https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip" \
-o "awscliv2.zip"

dnf install unzip -y

unzip awscliv2.zip

./aws/install

dnf install amazon-cloudwatch-agent -y