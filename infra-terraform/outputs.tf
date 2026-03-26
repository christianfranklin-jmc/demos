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

# -----------------------------------------------------------------------------
# Backend
# -----------------------------------------------------------------------------

output "runtime_id" {
  description = "AgentCore Runtime ID"
  value       = module.backend.runtime_id
}

output "gateway_url" {
  description = "AgentCore Gateway URL"
  value       = module.backend.gateway_url
}

output "memory_arn" {
  description = "AgentCore Memory ARN"
  value       = module.backend.memory_arn
}
