# -----------------------------------------------------------------------------
# Cognito — User Pool + OAuth2 clients
# Following FAST template: infra-terraform/modules/cognito/
# Populated in Phase 1.
# -----------------------------------------------------------------------------

variable "stack_name" { type = string }
variable "account_id" { type = string }
variable "region" { type = string }
variable "admin_user_email" { type = string; default = null }
variable "amplify_app_url" { type = string }
variable "tags" { type = map(string); default = {} }

# Stub outputs — will be populated in Phase 1
output "user_pool_id" { value = "" }
output "web_client_id" { value = "" }
output "domain_url" { value = "" }
output "oidc_discovery_url" { value = "" }
