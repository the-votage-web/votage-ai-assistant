########################################
# Get Latest Amazon Linux 2023 AMI
########################################

data "aws_ami" "amazon_linux_2023" {
  most_recent = true

  owners = ["137112412989"] # Amazon

  filter {
    name   = "name"
    values = ["al2023-ami-2023*-x86_64"]
  }

  filter {
    name   = "architecture"
    values = ["x86_64"]
  }

  filter {
    name   = "root-device-type"
    values = ["ebs"]
  }

  filter {
    name   = "virtualization-type"
    values = ["hvm"]
  }
}

resource "aws_instance" "votage_ai_assistant" {

  ami           = data.aws_ami.amazon_linux_2023.id
  instance_type = var.instance_type

  subnet_id = var.subnet_id

  vpc_security_group_ids = [
    var.security_group_id
  ]

  iam_instance_profile = var.iam_instance_profile_name

  key_name = aws_key_pair.main.key_name

  associate_public_ip_address = true

  user_data = file("${path.module}/user_data.sh")

  tags = {
    Name = "${var.project_name}-server"
  }
}

resource "aws_key_pair" "main" {
  key_name   = "${var.project_name}-key"
  public_key = file("~/.ssh/id_ed25519.pub")
}