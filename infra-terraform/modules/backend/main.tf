# -----------------------------------------------------------------------------
# Backend — AgentCore Runtime, Gateway, Memory, OAuth2
# Following FAST template: infra-terraform/modules/backend/
# Populated in Phases 2b and 3.
# -----------------------------------------------------------------------------

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

# Stub outputs — will be populated in Phases 2b and 3
output "runtime_id" { value = "" }
output "gateway_url" { value = "" }
output "memory_arn" { value = "" }
