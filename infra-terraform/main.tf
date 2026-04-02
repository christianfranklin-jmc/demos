# -----------------------------------------------------------------------------
# AWS Platform Agent — FAST Infrastructure
#
# Three-module hierarchy following the FAST template:
#   1. amplify-hosting  — S3 + Amplify App (deployed first, provides callback URL)
#   2. cognito          — User Pool + OAuth2 clients (depends on Amplify URL)
#   3. backend          — Runtime, Gateway, Memory, OAuth2 (depends on Cognito)
# -----------------------------------------------------------------------------

module "amplify_hosting" {
  source = "./modules/amplify-hosting"

  stack_name = local.stack_name
  tags       = local.common_tags
}

module "cognito" {
  source = "./modules/cognito"

  stack_name       = local.stack_name
  account_id       = local.account_id
  region           = local.region
  admin_user_email = var.admin_user_email
  amplify_app_url  = module.amplify_hosting.app_url
  tags             = local.common_tags

  depends_on = [module.amplify_hosting]
}

module "backend" {
  source = "./modules/backend"

  stack_name      = local.stack_name
  account_id      = local.account_id
  region          = local.region
  deployment_type = var.backend_deployment_type
  network_mode    = var.backend_network_mode
  pattern         = var.backend_pattern

  # Cognito integration
  user_pool_id       = module.cognito.user_pool_id
  oidc_discovery_url = module.cognito.oidc_discovery_url
  web_client_id      = module.cognito.web_client_id

  # VPC settings (conditional)
  vpc_id                 = var.backend_vpc_id
  vpc_subnet_ids         = var.backend_vpc_subnet_ids
  vpc_security_group_ids = var.backend_vpc_security_group_ids

  # Database connection (for Gateway Lambda env vars)
  db_host        = var.db_host
  db_port        = var.db_port
  db_name        = var.db_name
  db_user        = var.db_user
  db_password    = var.db_password
  db_driver_type = var.db_driver_type

  tags = local.common_tags

  depends_on = [module.cognito]
}
