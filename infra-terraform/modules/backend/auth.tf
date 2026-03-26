# -----------------------------------------------------------------------------
# M2M Authentication — Resource Server + Machine Client
# Following FAST template: infra-terraform/modules/backend/auth.tf
#
# Creates a Cognito Resource Server with gateway scopes and a machine
# client using client_credentials grant for agent → gateway auth.
# -----------------------------------------------------------------------------

# --- Resource Server (defines gateway scopes) ---

resource "aws_cognito_resource_server" "gateway" {
  identifier   = "${var.stack_name}-gateway"
  name         = "${var.stack_name}-gateway"
  user_pool_id = var.user_pool_id

  scope {
    scope_name        = "read"
    scope_description = "Read access to gateway tools"
  }

  scope {
    scope_name        = "write"
    scope_description = "Write access to gateway tools"
  }
}

# --- Machine Client (client_credentials grant) ---

resource "aws_cognito_user_pool_client" "machine" {
  name         = "${var.stack_name}-machine-client"
  user_pool_id = var.user_pool_id

  generate_secret = true

  allowed_oauth_flows                  = ["client_credentials"]
  allowed_oauth_flows_user_pool_client = true
  allowed_oauth_scopes = [
    "${aws_cognito_resource_server.gateway.identifier}/read",
    "${aws_cognito_resource_server.gateway.identifier}/write",
  ]

  supported_identity_providers = ["COGNITO"]

  access_token_validity = 1 # hours
  token_validity_units {
    access_token = "hours"
  }

  depends_on = [aws_cognito_resource_server.gateway]
}

# --- Store machine client credentials ---

resource "aws_ssm_parameter" "machine_client_id" {
  name  = "/${var.stack_name}/machine_client_id"
  type  = "String"
  value = aws_cognito_user_pool_client.machine.id
  tags  = var.tags
}

resource "aws_secretsmanager_secret" "machine_client_secret" {
  name                    = "${var.stack_name}/machine_client_secret"
  recovery_window_in_days = 0 # Immediate deletion on destroy
  tags                    = var.tags
}

resource "aws_secretsmanager_secret_version" "machine_client_secret" {
  secret_id = aws_secretsmanager_secret.machine_client_secret.id
  secret_string = jsonencode({
    client_id     = aws_cognito_user_pool_client.machine.id
    client_secret = aws_cognito_user_pool_client.machine.client_secret
  })
}
