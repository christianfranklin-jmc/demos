# -----------------------------------------------------------------------------
# AgentCore Memory — Short-term conversation persistence
# Following FAST template: infra-terraform/modules/backend/memory.tf
# -----------------------------------------------------------------------------

# --- Memory IAM Role ---

resource "aws_iam_role" "memory" {
  name = "${var.stack_name}-memory-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action    = "sts:AssumeRole"
      Effect    = "Allow"
      Principal = { Service = "bedrock-agentcore.amazonaws.com" }
    }]
  })

  tags = var.tags
}

resource "aws_iam_role_policy_attachment" "memory_bedrock" {
  role       = aws_iam_role.memory.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonBedrockAgentCoreMemoryBedrockModelInferenceExecutionRolePolicy"
}

# --- AgentCore Memory Resource ---

resource "aws_bedrockagentcore_memory" "main" {
  name                   = "${replace(var.stack_name, "-", "_")}_memory"
  description            = "Short-term memory for ${var.stack_name} agent"
  event_expiry_duration  = 30
  memory_execution_role_arn = aws_iam_role.memory.arn

  tags = var.tags
}
