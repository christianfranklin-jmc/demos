# -----------------------------------------------------------------------------
# SSM Parameters — Runtime configuration
# Following FAST template: infra-terraform/modules/backend/ssm.tf
# -----------------------------------------------------------------------------

resource "aws_ssm_parameter" "runtime_arn" {
  name  = "/${var.stack_name}/runtime_arn"
  type  = "String"
  value = aws_bedrockagentcore_agent_runtime.main.agent_runtime_arn
  tags  = var.tags
}

resource "aws_ssm_parameter" "memory_id" {
  name  = "/${var.stack_name}/memory_id"
  type  = "String"
  value = aws_bedrockagentcore_memory.main.id
  tags  = var.tags
}

resource "aws_ssm_parameter" "gateway_url" {
  name  = "/${var.stack_name}/gateway_url"
  type  = "String"
  value = aws_bedrockagentcore_gateway.main.gateway_url
  tags  = var.tags
}

resource "aws_ssm_parameter" "cognito_user_pool_id" {
  name  = "/${var.stack_name}/cognito_user_pool_id"
  type  = "String"
  value = var.user_pool_id
  tags  = var.tags
}

resource "aws_ssm_parameter" "cognito_domain_url" {
  name  = "/${var.stack_name}/cognito_domain_url"
  type  = "String"
  value = "https://cognito-idp.${var.region}.amazonaws.com/${var.user_pool_id}"
  tags  = var.tags
}
