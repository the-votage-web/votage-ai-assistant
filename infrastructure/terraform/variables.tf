variable "aws_region" {
  type    = string
  default = "eu-north-1"
}

variable "project_name" {
  type    = string
  default = "votage-ai-assistant"
}

variable "instance_type" {
  type    = string
  default = "t3.micro"
}

variable "environment" {
  type    = string
  default = "dev"
}