# Secrets Manager — stores Snowflake and database credentials.
# Agents access secrets via IAM roles, never in LLM context.

variable "stack_name" {
  type = string
}

variable "sf_account" {
  type    = string
  default = ""
}

variable "sf_user" {
  type    = string
  default = ""
}

variable "sf_password" {
  type      = string
  default   = ""
  sensitive = true
}

variable "sf_warehouse" {
  type    = string
  default = ""
}

variable "sf_database" {
  type    = string
  default = ""
}

variable "sf_schema" {
  type    = string
  default = "PUBLIC"
}

variable "sf_role" {
  type    = string
  default = ""
}

variable "sf_authenticator" {
  type    = string
  default = ""
}

variable "rds_password" {
  type      = string
  default   = ""
  sensitive = true
}

# ---------------------------------------------------------------------------
# Snowflake credentials
# ---------------------------------------------------------------------------

resource "aws_secretsmanager_secret" "snowflake_creds" {
  name                    = "${var.stack_name}/snowflake-credentials"
  description             = "Snowflake connection credentials for the Migration Agent"
  recovery_window_in_days = 0 # Allow immediate deletion for dev

  tags = {
    Stack = var.stack_name
  }
}

resource "aws_secretsmanager_secret_version" "snowflake_creds" {
  secret_id = aws_secretsmanager_secret.snowflake_creds.id
  secret_string = jsonencode({
    account       = var.sf_account
    user          = var.sf_user
    password      = var.sf_password
    warehouse     = var.sf_warehouse
    database      = var.sf_database
    schema        = var.sf_schema
    role          = var.sf_role
    authenticator = var.sf_authenticator
  })
}

# ---------------------------------------------------------------------------
# RDS credentials
# ---------------------------------------------------------------------------

resource "aws_secretsmanager_secret" "rds_creds" {
  name                    = "${var.stack_name}/rds-credentials"
  description             = "RDS PostgreSQL credentials for staging queries"
  recovery_window_in_days = 0

  tags = {
    Stack = var.stack_name
  }
}

resource "aws_secretsmanager_secret_version" "rds_creds" {
  secret_id = aws_secretsmanager_secret.rds_creds.id
  secret_string = jsonencode({
    password = var.rds_password
  })
}

# ---------------------------------------------------------------------------
# Outputs
# ---------------------------------------------------------------------------

output "snowflake_secret_arn" {
  value = aws_secretsmanager_secret.snowflake_creds.arn
}

output "rds_secret_arn" {
  value = aws_secretsmanager_secret.rds_creds.arn
}
