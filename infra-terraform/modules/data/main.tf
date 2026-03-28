# Data services module — S3, Glue Catalog, and supporting resources
# for the Snowflake → Iceberg migration pipeline.

variable "stack_name" {
  type        = string
  description = "Stack name prefix for all resources"
}

variable "aws_region" {
  type    = string
  default = "us-east-1"
}

variable "glue_database_name" {
  type    = string
  default = "semantic_lake"
}

# ---------------------------------------------------------------------------
# S3 Buckets
# ---------------------------------------------------------------------------

resource "aws_s3_bucket" "data_lake" {
  bucket        = "${var.stack_name}-data-lake"
  force_destroy = true

  tags = {
    Purpose = "Iceberg table data (Parquet files)"
    Stack   = var.stack_name
  }
}

resource "aws_s3_bucket" "quarantine" {
  bucket        = "${var.stack_name}-quarantine"
  force_destroy = true

  tags = {
    Purpose = "Quarantined records from quality checks"
    Stack   = var.stack_name
  }
}

resource "aws_s3_bucket" "dbt_artifacts" {
  bucket        = "${var.stack_name}-dbt-artifacts"
  force_destroy = true

  tags = {
    Purpose = "Generated dbt projects and compiled artifacts"
    Stack   = var.stack_name
  }
}

resource "aws_s3_bucket_versioning" "data_lake" {
  bucket = aws_s3_bucket.data_lake.id
  versioning_configuration {
    status = "Enabled"
  }
}

# ---------------------------------------------------------------------------
# Glue Data Catalog
# ---------------------------------------------------------------------------

resource "aws_glue_catalog_database" "semantic_lake" {
  name        = var.glue_database_name
  description = "Iceberg tables migrated from Snowflake"
}

# ---------------------------------------------------------------------------
# Outputs
# ---------------------------------------------------------------------------

output "data_lake_bucket" {
  value = aws_s3_bucket.data_lake.bucket
}

output "data_lake_arn" {
  value = aws_s3_bucket.data_lake.arn
}

output "quarantine_bucket" {
  value = aws_s3_bucket.quarantine.bucket
}

output "dbt_artifacts_bucket" {
  value = aws_s3_bucket.dbt_artifacts.bucket
}

output "glue_database_name" {
  value = aws_glue_catalog_database.semantic_lake.name
}
