# Neptune Serverless — knowledge graph for the Mapping Agent.
# Stores entity relationships, dbt lineage, and join paths.

variable "neptune_enabled" {
  type    = bool
  default = false
  description = "Set to true to provision Neptune Serverless (Phase 3)"
}

variable "subnet_ids" {
  type    = list(string)
  default = []
  description = "Subnet IDs for Neptune (required if neptune_enabled)"
}

variable "vpc_security_group_ids" {
  type    = list(string)
  default = []
  description = "Security group IDs for Neptune (required if neptune_enabled)"
}

# ---------------------------------------------------------------------------
# Neptune Serverless (conditionally created)
# ---------------------------------------------------------------------------

resource "aws_neptune_cluster" "knowledge_graph" {
  count = var.neptune_enabled ? 1 : 0

  cluster_identifier = "${var.stack_name}-kg"
  engine             = "neptune"
  serverless_v2_scaling_configuration {
    min_capacity = 1.0
    max_capacity = 8.0
  }
  vpc_security_group_ids = var.vpc_security_group_ids
  skip_final_snapshot    = true

  tags = {
    Purpose = "Knowledge graph for entity relationships and dbt lineage"
    Stack   = var.stack_name
  }
}

resource "aws_neptune_cluster_instance" "knowledge_graph" {
  count = var.neptune_enabled ? 1 : 0

  cluster_identifier = aws_neptune_cluster.knowledge_graph[0].id
  instance_class     = "db.serverless"
  engine             = "neptune"

  tags = {
    Stack = var.stack_name
  }
}

output "neptune_endpoint" {
  value = var.neptune_enabled ? aws_neptune_cluster.knowledge_graph[0].endpoint : ""
}
