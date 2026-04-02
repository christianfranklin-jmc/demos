# -----------------------------------------------------------------------------
# AgentCore Gateway — MCP protocol with Lambda tool target
# Following FAST template: infra-terraform/modules/backend/gateway.tf
# -----------------------------------------------------------------------------

# --- Lambda: Data tools ---

data "archive_file" "data_tools" {
  type        = "zip"
  source_dir  = "${path.module}/../../../gateway/tools/data_tools"
  output_path = "${path.module}/../../../.build/data_tools.zip"
}

resource "aws_iam_role" "data_tools_lambda" {
  name = "${var.stack_name}-data-tools-lambda"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action    = "sts:AssumeRole"
      Effect    = "Allow"
      Principal = { Service = "lambda.amazonaws.com" }
    }]
  })

  tags = var.tags
}

resource "aws_iam_role_policy_attachment" "data_tools_basic" {
  role       = aws_iam_role.data_tools_lambda.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

resource "aws_lambda_function" "data_tools" {
  function_name = "${var.stack_name}-data-tools"
  role          = aws_iam_role.data_tools_lambda.arn
  handler       = "lambda_function.handler"
  runtime       = "python3.12"
  timeout       = 120
  memory_size   = 256

  filename         = data.archive_file.data_tools.output_path
  source_code_hash = data.archive_file.data_tools.output_base64sha256

  environment {
    variables = {
      DB_HOST        = var.db_host
      DB_PORT        = tostring(var.db_port)
      DB_NAME        = var.db_name
      DB_USER        = var.db_user
      DB_PASSWORD    = var.db_password
      DB_DRIVER_TYPE = var.db_driver_type
    }
  }

  # Lambda layer for psycopg2 (binary not available in Lambda runtime)
  # For production, use a Lambda layer or Docker-based Lambda
  # For now, psycopg2-binary is included in the zip

  tags = var.tags
}

resource "aws_cloudwatch_log_group" "data_tools" {
  name              = "/aws/lambda/${aws_lambda_function.data_tools.function_name}"
  retention_in_days = 30
  tags              = var.tags
}

# --- Gateway IAM Role ---

resource "aws_iam_role" "gateway" {
  name = "${var.stack_name}-gateway-role"

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

resource "aws_iam_role_policy" "gateway" {
  name = "${var.stack_name}-gateway-policy"
  role = aws_iam_role.gateway.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "InvokeLambda"
        Effect = "Allow"
        Action = "lambda:InvokeFunction"
        Resource = aws_lambda_function.data_tools.arn
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
        Sid    = "CognitoClientOps"
        Effect = "Allow"
        Action = [
          "cognito-idp:DescribeUserPoolClient",
        ]
        Resource = "arn:aws:cognito-idp:${var.region}:${var.account_id}:userpool/${var.user_pool_id}"
      },
    ]
  })
}

# --- AgentCore Gateway ---

# Allow IAM to propagate before creating Gateway
resource "time_sleep" "gateway_iam" {
  depends_on      = [aws_iam_role.gateway]
  create_duration = "10s"
}

resource "aws_bedrockagentcore_gateway" "main" {
  name           = "${var.stack_name}-gateway"
  description    = "MCP Gateway for ${var.stack_name} data tools"
  protocol_type  = "MCP"
  authorizer_type = "CUSTOM_JWT"
  role_arn       = aws_iam_role.gateway.arn

  protocol_configuration {
    mcp {}
  }

  authorizer_configuration {
    custom_jwt_authorizer {
      discovery_url    = var.oidc_discovery_url
      allowed_audience = []
      allowed_clients  = []
    }
  }

  depends_on = [time_sleep.gateway_iam]

  tags = var.tags
}

# --- Gateway Target: Data Tools Lambda ---

resource "aws_bedrockagentcore_gateway_target" "data_tools" {
  name               = "data-tools"
  gateway_identifier = aws_bedrockagentcore_gateway.main.gateway_id
  description        = "5 data tools: connect, scan, profile, query, DDL"

  target_configuration {
    mcp {
      lambda {
        lambda_arn = aws_lambda_function.data_tools.arn
        tool_schema {}
      }
    }
  }
}

# Allow Gateway to invoke the Lambda
resource "aws_lambda_permission" "gateway_invoke" {
  statement_id  = "AllowAgentCoreGateway"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.data_tools.function_name
  principal     = "bedrock-agentcore.amazonaws.com"
  source_arn    = aws_bedrockagentcore_gateway.main.gateway_arn
}
