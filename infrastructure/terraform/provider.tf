provider "aws" {
  region = var.aws_region

  default_tags {
    tags = {
      Project     = "votage-ai-assistant"
      Environment = "dev"
      ManagedBy   = "Terraform"
    }
  }
}