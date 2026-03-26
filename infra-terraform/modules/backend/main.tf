# -----------------------------------------------------------------------------
# Backend — AgentCore Runtime, Gateway, Memory, OAuth2
# Following FAST template: infra-terraform/modules/backend/
#
# Phase 2b: Gateway + Auth resources
# Phase 3:  Runtime + Memory resources (to be added)
# -----------------------------------------------------------------------------

# --- Core variables ---

variable "stack_name" { type = string }
variable "account_id" { type = string }
variable "region" { type = string }
variable "deployment_type" { type = string }
variable "network_mode" { type = string }
variable "pattern" { type = string }
variable "user_pool_id" { type = string }
variable "oidc_discovery_url" { type = string }
variable "vpc_id" { type = string; default = null }
variable "vpc_subnet_ids" { type = list(string); default = [] }
variable "vpc_security_group_ids" { type = list(string); default = [] }
variable "tags" { type = map(string); default = {} }

# --- Database connection variables (for Gateway Lambda env vars) ---

variable "db_host" {
  description = "Database host for Gateway Lambda tools"
  type        = string
  default     = ""
}

variable "db_port" {
  description = "Database port"
  type        = number
  default     = 5432
}

variable "db_name" {
  description = "Database name"
  type        = string
  default     = ""
}

variable "db_user" {
  description = "Database username"
  type        = string
  default     = ""
}

variable "db_password" {
  description = "Database password"
  type        = string
  default     = ""
  sensitive   = true
}

variable "db_driver_type" {
  description = "Database driver type: postgresql or redshift"
  type        = string
  default     = "postgresql"
}

# --- Outputs ---

output "runtime_id" {
  description = "AgentCore Runtime ID (populated in Phase 3)"
  value       = ""
}

output "gateway_id" {
  description = "AgentCore Gateway ID"
  value       = aws_bedrockagentcore_gateway.main.gateway_id
}

output "gateway_url" {
  description = "AgentCore Gateway URL"
  value       = aws_bedrockagentcore_gateway.main.endpoint
}

output "memory_arn" {
  description = "AgentCore Memory ARN (populated in Phase 3)"
  value       = ""
}

output "machine_client_id" {
  description = "Machine client ID for M2M auth"
  value       = aws_cognito_user_pool_client.machine.id
}

# --- Required provider for time_sleep ---

terraform {
  required_providers {
    time = {
      source  = "hashicorp/time"
      version = ">= 0.9.0"
    }
  }
}
