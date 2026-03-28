# -----------------------------------------------------------------------------
# Amplify
# -----------------------------------------------------------------------------

output "amplify_app_url" {
  description = "Amplify frontend URL"
  value       = module.amplify_hosting.app_url
}

# -----------------------------------------------------------------------------
# Cognito
# -----------------------------------------------------------------------------

output "cognito_user_pool_id" {
  description = "Cognito User Pool ID"
  value       = module.cognito.user_pool_id
}

output "cognito_web_client_id" {
  description = "Cognito web client ID (for frontend)"
  value       = module.cognito.web_client_id
}

output "cognito_domain_url" {
  description = "Cognito hosted UI domain URL"
  value       = module.cognito.domain_url
}

output "cognito_oidc_issuer_url" {
  description = "OIDC issuer URL for JWT validation"
  value       = module.cognito.oidc_issuer_url
}

# -----------------------------------------------------------------------------
# Backend
# -----------------------------------------------------------------------------

output "runtime_id" {
  description = "AgentCore Runtime ID"
  value       = module.backend.runtime_id
}

output "gateway_id" {
  description = "AgentCore Gateway ID"
  value       = module.backend.gateway_id
}

output "gateway_url" {
  description = "AgentCore Gateway URL"
  value       = module.backend.gateway_url
}

output "machine_client_id" {
  description = "Machine client ID for M2M auth"
  value       = module.backend.machine_client_id
}

output "memory_arn" {
  description = "AgentCore Memory ARN"
  value       = module.backend.memory_arn
}

output "memory_id" {
  description = "AgentCore Memory ID"
  value       = module.backend.memory_id
}

output "runtime_arn" {
  description = "AgentCore Runtime ARN"
  value       = module.backend.runtime_arn
}

output "ecr_repository_url" {
  description = "ECR repository URL for agent Docker image"
  value       = module.backend.ecr_repository_url
}
