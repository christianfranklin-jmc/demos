data "aws_caller_identity" "current" {}
data "aws_region" "current" {}

locals {
  account_id = data.aws_caller_identity.current.account_id
  region     = data.aws_region.current.name
  stack_name = var.stack_name_base

  common_tags = {
    Project   = "platform-agent"
    ManagedBy = "terraform"
    Stack     = var.stack_name_base
  }
}
