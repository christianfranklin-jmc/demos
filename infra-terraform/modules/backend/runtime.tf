# -----------------------------------------------------------------------------
# AgentCore Runtime — Docker-based agent deployment
# Following FAST template: infra-terraform/modules/backend/runtime.tf
# -----------------------------------------------------------------------------

# --- ECR Repository (Docker mode) ---

resource "aws_ecr_repository" "agent" {
  count = var.deployment_type == "docker" ? 1 : 0

  name                 = "${var.stack_name}-agent"
  image_tag_mutability = "MUTABLE"
  force_delete         = true

  image_scanning_configuration {
    scan_on_push = true
  }

  tags = var.tags
}

resource "aws_ecr_lifecycle_policy" "agent" {
  count      = var.deployment_type == "docker" ? 1 : 0
  repository = aws_ecr_repository.agent[0].name

  policy = jsonencode({
    rules = [{
      rulePriority = 1
      description  = "Keep last 5 images"
      selection = {
        tagStatus   = "any"
        countType   = "imageCountMoreThan"
        countNumber = 5
      }
      action = {
        type = "expire"
      }
    }]
  })
}

# --- Runtime IAM Role ---

resource "aws_iam_role" "runtime" {
  name = "${var.stack_name}-runtime-role"

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

resource "aws_iam_role_policy" "runtime" {
  name = "${var.stack_name}-runtime-policy"
  role = aws_iam_role.runtime.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "ECRAccess"
        Effect = "Allow"
        Action = [
          "ecr:GetDownloadUrlForLayer",
          "ecr:BatchGetImage",
          "ecr:GetAuthorizationToken",
        ]
        Resource = "*"
      },
      {
        Sid    = "BedrockModelAccess"
        Effect = "Allow"
        Action = [
          "bedrock:InvokeModel",
          "bedrock:InvokeModelWithResponseStream",
        ]
        Resource = [
          "arn:aws:bedrock:*::foundation-model/anthropic.claude-*",
          "arn:aws:bedrock:*::foundation-model/us.anthropic.claude-*",
          "arn:aws:bedrock:${var.region}:${var.account_id}:inference-profile/us.anthropic.claude-*",
        ]
      },
      {
        Sid    = "MemoryAccess"
        Effect = "Allow"
        Action = [
          "bedrock-agentcore:CreateMemoryEvent",
          "bedrock-agentcore:GetMemoryEvent",
          "bedrock-agentcore:ListMemoryEvents",
        ]
        Resource = aws_bedrockagentcore_memory.main.arn
      },
      {
        Sid    = "SecretsManagerAccess"
        Effect = "Allow"
        Action = [
          "secretsmanager:GetSecretValue",
        ]
        Resource = aws_secretsmanager_secret.machine_client_secret.arn
      },
      {
        Sid    = "SSMAccess"
        Effect = "Allow"
        Action = [
          "ssm:GetParameter",
          "ssm:GetParameters",
        ]
        Resource = "arn:aws:ssm:${var.region}:${var.account_id}:parameter/${var.stack_name}/*"
      },
      {
        Sid    = "CloudWatchLogs"
        Effect = "Allow"
        Action = [
          "logs:CreateLogGroup",
          "logs:CreateLogStream",
          "logs:PutLogEvents",
        ]
        Resource = "arn:aws:logs:${var.region}:${var.account_id}:*"
      },
      {
        Sid    = "XRay"
        Effect = "Allow"
        Action = [
          "xray:PutTraceSegments",
          "xray:PutTelemetryRecords",
        ]
        Resource = "*"
      },
    ]
  })
}

# --- AgentCore Runtime ---

resource "aws_bedrockagentcore_agent_runtime" "main" {
  agent_runtime_name = "${replace(var.stack_name, "-", "_")}_runtime"
  description        = "Platform Agent runtime for ${var.stack_name}"
  role_arn           = aws_iam_role.runtime.arn

  agent_runtime_artifact {
    container_configuration {
      container_uri = var.deployment_type == "docker" ? "${aws_ecr_repository.agent[0].repository_url}:latest" : null
    }
  }

  environment_variables = {
    DB_HOST        = var.db_host
    DB_PORT        = tostring(var.db_port)
    DB_NAME        = var.db_name
    DB_USER        = var.db_user
    DB_PASSWORD    = var.db_password
    DB_DRIVER_TYPE = var.db_driver_type
    MEMORY_ID      = aws_bedrockagentcore_memory.main.id
    STACK_NAME     = var.stack_name
    AWS_REGION     = var.region
    # 001-dsa-agent-integration
    AGENT_MODE            = "deployed"
    API_PORT              = "8080"
    SESSION_HEADER_NAME   = "X-DSA-Session-ID"
    CORS_ALLOWED_ORIGINS  = var.cors_allowed_origins
    COGNITO_USER_POOL_ID  = var.user_pool_id
    COGNITO_APP_CLIENT_ID = var.web_client_id
  }

  network_configuration {
    network_mode = var.network_mode
  }

  authorizer_configuration {
    custom_jwt_authorizer {
      discovery_url   = var.oidc_discovery_url
      allowed_clients = [var.web_client_id]
    }
  }

  tags = var.tags

  depends_on = [aws_iam_role_policy.runtime]
}
