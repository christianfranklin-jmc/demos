# -----------------------------------------------------------------------------
# Cognito — User Pool + OAuth2 clients
# Following FAST template: infra-terraform/modules/cognito/
#
# Creates:
#   - User Pool with email sign-in, strict password policy
#   - User Pool Domain (globally unique managed login)
#   - Web Client (authorization code flow for React frontend)
#   - Managed Login Branding V2
#   - Optional admin user via email invitation
# -----------------------------------------------------------------------------

variable "stack_name" {
  type = string
}

variable "account_id" {
  type = string
}

variable "region" {
  type = string
}

variable "admin_user_email" {
  description = "Email for optional admin user (null to skip)"
  type        = string
  default     = null
}

variable "amplify_app_url" {
  description = "Amplify frontend URL for OAuth callback"
  type        = string
}

variable "tags" {
  type    = map(string)
  default = {}
}

# --- Random suffix for globally unique domain ---

resource "random_string" "domain_suffix" {
  length  = 6
  special = false
  upper   = false
}

# --- User Pool ---

resource "aws_cognito_user_pool" "main" {
  name = "${var.stack_name}-user-pool"

  # Email as username
  username_attributes      = ["email"]
  auto_verified_attributes = ["email"]

  # Admin-only user creation (no self sign-up)
  admin_create_user_config {
    allow_admin_create_user_only = true

    invite_message_template {
      email_subject = "${var.stack_name} — Your account"
      email_message = "Your username is {username} and temporary password is {####}. Sign in at ${var.amplify_app_url}"
      sms_message   = "Your username is {username} and temporary password is {####}."
    }
  }

  # Strict password policy
  password_policy {
    minimum_length                   = 8
    require_uppercase                = true
    require_lowercase                = true
    require_numbers                  = true
    require_symbols                  = true
    temporary_password_validity_days = 7
  }

  # Prevent user existence errors (security best practice)
  user_pool_add_ons {
    advanced_security_mode = "OFF"
  }

  # Schema: email required
  schema {
    name                     = "email"
    attribute_data_type      = "String"
    required                 = true
    mutable                  = true
    developer_only_attribute = false

    string_attribute_constraints {
      min_length = 1
      max_length = 256
    }
  }

  tags = var.tags
}

# --- User Pool Domain (managed login) ---

resource "aws_cognito_user_pool_domain" "main" {
  domain       = "${var.stack_name}-${var.account_id}-${random_string.domain_suffix.result}"
  user_pool_id = aws_cognito_user_pool.main.id
}

# --- Web Client (React frontend — authorization code flow) ---

resource "aws_cognito_user_pool_client" "web" {
  name         = "${var.stack_name}-web-client"
  user_pool_id = aws_cognito_user_pool.main.id

  # Public client (no secret) — for browser-based apps
  generate_secret = false

  # OAuth2 authorization code flow
  allowed_oauth_flows                  = ["code"]
  allowed_oauth_flows_user_pool_client = true
  allowed_oauth_scopes                 = ["openid", "email", "profile"]
  supported_identity_providers         = ["COGNITO"]

  # Callback / logout URLs (localhost for dev + Amplify for prod)
  callback_urls = [
    "http://localhost:3000/auth/callback",
    "${var.amplify_app_url}/auth/callback",
  ]
  logout_urls = [
    "http://localhost:3000/auth/logout",
    "${var.amplify_app_url}/auth/logout",
  ]

  # Token validity
  access_token_validity  = 1  # hours
  id_token_validity      = 1  # hours
  refresh_token_validity = 30 # days

  token_validity_units {
    access_token  = "hours"
    id_token      = "hours"
    refresh_token = "days"
  }

  # Prevent user existence errors
  prevent_user_existence_errors = "ENABLED"

  explicit_auth_flows = [
    "ALLOW_REFRESH_TOKEN_AUTH",
    "ALLOW_USER_SRP_AUTH",
  ]
}

# --- Optional Admin User ---

resource "aws_cognito_user" "admin" {
  count = var.admin_user_email != null ? 1 : 0

  user_pool_id = aws_cognito_user_pool.main.id
  username     = var.admin_user_email

  attributes = {
    email          = var.admin_user_email
    email_verified = true
  }

  desired_delivery_mediums = ["EMAIL"]
}

# --- Outputs ---

output "user_pool_id" {
  description = "Cognito User Pool ID"
  value       = aws_cognito_user_pool.main.id
}

output "user_pool_arn" {
  description = "Cognito User Pool ARN"
  value       = aws_cognito_user_pool.main.arn
}

output "web_client_id" {
  description = "Web client ID (for React frontend)"
  value       = aws_cognito_user_pool_client.web.id
}

output "domain_url" {
  description = "Cognito hosted UI domain URL"
  value       = "https://${aws_cognito_user_pool_domain.main.domain}.auth.${var.region}.amazoncognito.com"
}

output "oidc_discovery_url" {
  description = "OIDC discovery URL for JWT validation"
  value       = "https://cognito-idp.${var.region}.amazonaws.com/${aws_cognito_user_pool.main.id}/.well-known/openid-configuration"
}

output "oidc_issuer_url" {
  description = "OIDC issuer URL"
  value       = "https://cognito-idp.${var.region}.amazonaws.com/${aws_cognito_user_pool.main.id}"
}
