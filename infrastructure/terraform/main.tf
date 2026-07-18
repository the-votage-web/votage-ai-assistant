module "network" {
  source = "./modules/network"

  project_name = var.project_name
  aws_region   = var.aws_region
}

module "security" {
  source = "./modules/security"

  project_name = var.project_name
  vpc_id       = module.network.vpc_id
}

module "iam" {
  source = "./modules/iam"

  project_name = var.project_name
}

module "ec2" {
  source = "./modules/ec2"

  project_name              = var.project_name
  instance_type             = var.instance_type
  subnet_id                 = module.network.public_subnet_id
  security_group_id         = module.security.security_group_id
  iam_instance_profile_name = module.iam.instance_profile_name
}

module "ecr" {
  source = "./modules/ecr"

  repository_name = "votage-ai-assistant"
  project_name    = var.project_name
  environment     = var.environment
}