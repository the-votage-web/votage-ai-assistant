resource "aws_security_group" "votage_ai_assistant_sg" {
  name        = "${var.project_name}-sg"
  description = "Security group for AI Assistant"
  vpc_id      = var.vpc_id

  tags = {
    Name = "${var.project_name}-sg"
  }
}

#
# Inbound Rules
#

resource "aws_vpc_security_group_ingress_rule" "ssh" {
  security_group_id = aws_security_group.votage_ai_assistant_sg.id

  ip_protocol = "tcp"
  from_port   = 22
  to_port     = 22

  cidr_ipv4 = "0.0.0.0/0"

  description = "SSH"
}

resource "aws_vpc_security_group_ingress_rule" "http" {
  security_group_id = aws_security_group.votage_ai_assistant_sg.id

  ip_protocol = "tcp"
  from_port   = 80
  to_port     = 80

  cidr_ipv4 = "0.0.0.0/0"

  description = "HTTP"
}

resource "aws_vpc_security_group_ingress_rule" "https" {
  security_group_id = aws_security_group.votage_ai_assistant_sg.id

  ip_protocol = "tcp"
  from_port   = 443
  to_port     = 443

  cidr_ipv4 = "0.0.0.0/0"

  description = "HTTPS"
}

#
# Optional - FastAPI
#

resource "aws_vpc_security_group_ingress_rule" "fastapi" {
  security_group_id = aws_security_group.votage_ai_assistant_sg.id

  ip_protocol = "tcp"
  from_port   = 8000
  to_port     = 8000

  cidr_ipv4 = "0.0.0.0/0"

  description = "FastAPI (Development Only)"
}

#
# Outbound Rules
#

resource "aws_vpc_security_group_egress_rule" "all" {
  security_group_id = aws_security_group.votage_ai_assistant_sg.id

  ip_protocol = "-1"
  cidr_ipv4   = "0.0.0.0/0"

  description = "Allow all outbound traffic"
}