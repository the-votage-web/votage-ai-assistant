resource "aws_ecr_repository" "repository" {
  name = var.repository_name

  image_tag_mutability = "MUTABLE"

  image_scanning_configuration {
    scan_on_push = true
  }

  encryption_configuration {
    encryption_type = "AES256"
  }

  tags = {
    Name        = var.repository_name
    Project     = var.project_name
    Environment = var.environment
    ManagedBy   = "Terraform"
  }
}