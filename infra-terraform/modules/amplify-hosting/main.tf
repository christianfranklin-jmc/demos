# -----------------------------------------------------------------------------
# Amplify Hosting — S3 staging + Amplify App
# Following FAST template: infra-terraform/modules/amplify-hosting/
# -----------------------------------------------------------------------------

variable "stack_name" {
  type = string
}

variable "tags" {
  type    = map(string)
  default = {}
}

# --- S3: Access logs bucket ---

resource "aws_s3_bucket" "access_logs" {
  bucket_prefix = "${var.stack_name}-access-logs-"
  force_destroy = true
  tags          = var.tags
}

resource "aws_s3_bucket_lifecycle_configuration" "access_logs" {
  bucket = aws_s3_bucket.access_logs.id

  rule {
    id     = "expire-logs"
    status = "Enabled"

    expiration {
      days = 90
    }
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "access_logs" {
  bucket = aws_s3_bucket.access_logs.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

# --- S3: Staging bucket (Amplify artifacts) ---

resource "aws_s3_bucket" "staging" {
  bucket_prefix = "${var.stack_name}-staging-"
  force_destroy = true
  tags          = var.tags
}

resource "aws_s3_bucket_versioning" "staging" {
  bucket = aws_s3_bucket.staging.id
  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_logging" "staging" {
  bucket        = aws_s3_bucket.staging.id
  target_bucket = aws_s3_bucket.access_logs.id
  target_prefix = "s3-access-logs/"
}

resource "aws_s3_bucket_server_side_encryption_configuration" "staging" {
  bucket = aws_s3_bucket.staging.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

resource "aws_s3_bucket_lifecycle_configuration" "staging" {
  bucket = aws_s3_bucket.staging.id

  rule {
    id     = "expire-old-versions"
    status = "Enabled"

    noncurrent_version_expiration {
      noncurrent_days = 30
    }
  }
}

resource "aws_s3_bucket_public_access_block" "staging" {
  bucket = aws_s3_bucket.staging.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_policy" "staging" {
  bucket = aws_s3_bucket.staging.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid       = "EnforceTLS"
        Effect    = "Deny"
        Principal = "*"
        Action    = "s3:*"
        Resource = [
          aws_s3_bucket.staging.arn,
          "${aws_s3_bucket.staging.arn}/*"
        ]
        Condition = {
          Bool = { "aws:SecureTransport" = "false" }
        }
      },
      {
        Sid       = "AllowAmplifyAccess"
        Effect    = "Allow"
        Principal = { Service = "amplify.amazonaws.com" }
        Action = [
          "s3:GetObject",
          "s3:GetObjectVersion"
        ]
        Resource = "${aws_s3_bucket.staging.arn}/*"
      }
    ]
  })
}

# --- Amplify App ---

resource "aws_amplify_app" "frontend" {
  name = "${var.stack_name}-frontend"
  tags = var.tags

  # Auto-build disabled — we deploy via script
  # SPA fallback: serve static files if they exist, otherwise index.html
  custom_rule {
    source = "</^[^.]+$|\\.(?!(css|gif|ico|jpg|js|png|txt|svg|woff|woff2|ttf|map|json|webp)$)([^.]+$)/>"
    target = "/index.html"
    status = "200"
  }
}

resource "aws_amplify_branch" "main" {
  app_id      = aws_amplify_app.frontend.id
  branch_name = "main"
  stage       = "PRODUCTION"
  tags        = var.tags
}

# --- Outputs ---

output "app_id" {
  value = aws_amplify_app.frontend.id
}

output "app_url" {
  value = "https://main.${aws_amplify_app.frontend.id}.amplifyapp.com"
}

output "staging_bucket_name" {
  value = aws_s3_bucket.staging.id
}
