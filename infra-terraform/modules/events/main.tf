# EventBridge + Step Functions — orchestration for the multi-agent pipeline.
# Step Functions runs: Migration → Enrichment → Quality → Mapping → Query.
# EventBridge triggers steady-state operations (schema change, quality failure).

variable "stack_name" {
  type = string
}

variable "aws_region" {
  type    = string
  default = "us-east-1"
}

variable "events_enabled" {
  type    = bool
  default = false
  description = "Set to true to provision EventBridge + Step Functions (Phase 4)"
}

# ---------------------------------------------------------------------------
# Step Functions — Migration Pipeline
# ---------------------------------------------------------------------------

resource "aws_iam_role" "step_functions" {
  count = var.events_enabled ? 1 : 0

  name = "${var.stack_name}-sfn-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action = "sts:AssumeRole"
      Effect = "Allow"
      Principal = {
        Service = "states.amazonaws.com"
      }
    }]
  })

  tags = {
    Stack = var.stack_name
  }
}

resource "aws_iam_role_policy" "step_functions" {
  count = var.events_enabled ? 1 : 0

  name = "${var.stack_name}-sfn-policy"
  role = aws_iam_role.step_functions[0].id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "bedrock-agentcore:InvokeAgent",
          "logs:*",
        ]
        Resource = "*"
      }
    ]
  })
}

resource "aws_sfn_state_machine" "migration_pipeline" {
  count = var.events_enabled ? 1 : 0

  name     = "${var.stack_name}-migration-pipeline"
  role_arn = aws_iam_role.step_functions[0].arn

  definition = jsonencode({
    Comment = "Snowflake → AWS migration pipeline: Migration → Enrichment → Quality → Mapping → Query"
    StartAt = "MigrationAgent"
    States = {
      MigrationAgent = {
        Type     = "Task"
        Resource = "arn:aws:states:::bedrock-agentcore:invokeAgent"
        Parameters = {
          "AgentId.$" = "$.migration_agent_id"
          "Prompt"    = "Extract and migrate all tables from Snowflake to Iceberg on S3. Validate row counts."
        }
        Next = "EnrichmentAgent"
      }
      EnrichmentAgent = {
        Type     = "Task"
        Resource = "arn:aws:states:::bedrock-agentcore:invokeAgent"
        Parameters = {
          "AgentId.$" = "$.enrichment_agent_id"
          "Prompt"    = "Generate descriptions for all migrated tables and columns. Publish to DataZone."
        }
        Next = "QualityAgent"
      }
      QualityAgent = {
        Type     = "Task"
        Resource = "arn:aws:states:::bedrock-agentcore:invokeAgent"
        Parameters = {
          "AgentId.$" = "$.quality_agent_id"
          "Prompt"    = "Deploy quality rules on all migrated tables. Run dbt tests. Quarantine failures."
        }
        Next = "MappingAgent"
      }
      MappingAgent = {
        Type     = "Task"
        Resource = "arn:aws:states:::bedrock-agentcore:invokeAgent"
        Parameters = {
          "AgentId.$" = "$.mapping_agent_id"
          "Prompt"    = "Extract entities and build the Neptune knowledge graph from migrated data and dbt lineage."
        }
        Next = "QueryAgent"
      }
      QueryAgent = {
        Type     = "Task"
        Resource = "arn:aws:states:::bedrock-agentcore:invokeAgent"
        Parameters = {
          "AgentId.$" = "$.query_agent_id"
          "Prompt"    = "Verify the semantic layer is queryable. Run 5 test questions against the migrated data."
        }
        End = true
      }
    }
  })

  tags = {
    Stack = var.stack_name
  }
}

# ---------------------------------------------------------------------------
# EventBridge Rules (steady-state triggers)
# ---------------------------------------------------------------------------

resource "aws_cloudwatch_event_rule" "schema_change" {
  count = var.events_enabled ? 1 : 0

  name        = "${var.stack_name}-schema-change"
  description = "Trigger re-enrichment when Glue schema changes"

  event_pattern = jsonencode({
    source      = ["aws.glue"]
    detail-type = ["Glue Data Catalog Table State Change"]
  })

  tags = {
    Stack = var.stack_name
  }
}

resource "aws_cloudwatch_event_rule" "quality_failure" {
  count = var.events_enabled ? 1 : 0

  name        = "${var.stack_name}-quality-failure"
  description = "Trigger auto-remediation when quality checks fail"

  event_pattern = jsonencode({
    source      = ["aws.glue-dataquality"]
    detail-type = ["Data Quality Evaluation Results Available"]
    detail = {
      state = ["FAILED"]
    }
  })

  tags = {
    Stack = var.stack_name
  }
}

# ---------------------------------------------------------------------------
# Outputs
# ---------------------------------------------------------------------------

output "pipeline_arn" {
  value = var.events_enabled ? aws_sfn_state_machine.migration_pipeline[0].arn : ""
}
