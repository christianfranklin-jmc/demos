# ElastiCache Valkey — semantic query cache for the Query Agent.
# Vector similarity search for cached query results.

variable "elasticache_enabled" {
  type    = bool
  default = false
  description = "Set to true to provision ElastiCache Valkey (Phase 3)"
}

variable "elasticache_node_type" {
  type    = string
  default = "cache.t3.micro"
}

# ---------------------------------------------------------------------------
# ElastiCache Valkey (conditionally created)
# ---------------------------------------------------------------------------

resource "aws_elasticache_cluster" "semantic_cache" {
  count = var.elasticache_enabled ? 1 : 0

  cluster_id      = "${var.stack_name}-cache"
  engine          = "valkey"
  node_type       = var.elasticache_node_type
  num_cache_nodes = 1

  tags = {
    Purpose = "Semantic query cache for NL-to-SQL results"
    Stack   = var.stack_name
  }
}

output "elasticache_endpoint" {
  value = var.elasticache_enabled ? aws_elasticache_cluster.semantic_cache[0].cache_nodes[0].address : ""
}
