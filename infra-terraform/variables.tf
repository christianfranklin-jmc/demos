# -----------------------------------------------------------------------------
# Required
# -----------------------------------------------------------------------------

variable "stack_name_base" {
  description = "Base name for all resources (max 35 chars, alphanumeric + hyphens)"
  type        = string

  validation {
    condition     = length(var.stack_name_base) <= 35 && can(regex("^[a-zA-Z0-9-]+$", var.stack_name_base))
    error_message = "stack_name_base must be <= 35 chars and contain only alphanumeric characters and hyphens."
  }
}

# -----------------------------------------------------------------------------
# Optional — Admin
# -----------------------------------------------------------------------------

variable "admin_user_email" {
  description = "Email for optional admin Cognito user (null to skip)"
  type        = string
  default     = null
}

# -----------------------------------------------------------------------------
# Backend Configuration
# -----------------------------------------------------------------------------

variable "backend_pattern" {
  description = "Agent pattern directory name under patterns/"
  type        = string
  default     = "platform-agent"
}

variable "backend_deployment_type" {
  description = "Deployment type: docker or zip"
  type        = string
  default     = "docker"

  validation {
    condition     = contains(["docker", "zip"], var.backend_deployment_type)
    error_message = "backend_deployment_type must be 'docker' or 'zip'."
  }
}

variable "backend_network_mode" {
  description = "Network mode: PUBLIC (internet) or VPC (private)"
  type        = string
  default     = "PUBLIC"

  validation {
    condition     = contains(["PUBLIC", "VPC"], var.backend_network_mode)
    error_message = "backend_network_mode must be 'PUBLIC' or 'VPC'."
  }
}

# -----------------------------------------------------------------------------
# VPC Settings (required if backend_network_mode = "VPC")
# -----------------------------------------------------------------------------

variable "backend_vpc_id" {
  description = "VPC ID for VPC network mode"
  type        = string
  default     = null
}

variable "backend_vpc_subnet_ids" {
  description = "Subnet IDs for VPC network mode"
  type        = list(string)
  default     = []
}

variable "backend_vpc_security_group_ids" {
  description = "Security group IDs for VPC network mode (auto-created if empty)"
  type        = list(string)
  default     = []
}
