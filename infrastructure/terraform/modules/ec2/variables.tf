variable "project_name" {
  type    = string
  default = "votage-ai-assistant"
}

variable "instance_type" {
  type    = string
  default = "t3.micro"
}

variable "subnet_id" {
  type = string
}

variable "security_group_id" {
  type = string
}

variable "iam_instance_profile_name" {
  type = string
}
