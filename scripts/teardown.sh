#!/usr/bin/env bash
# teardown.sh — Remove AWS resources created by bootstrap.sh.
#
# Usage:
#   ./scripts/teardown.sh --profile <AWS_PROFILE> [--region <REGION>]

set -euo pipefail

REGION="us-east-1"
DB_INSTANCE_ID="platform-agent-northwinds"
SG_NAME="platform-agent-rds-sg"
SUBNET_GROUP_NAME="platform-agent-db-subnets"

AWS_PROFILE=""
while [[ $# -gt 0 ]]; do
    case $1 in
        --profile)     AWS_PROFILE="$2"; shift 2 ;;
        --region)      REGION="$2"; shift 2 ;;
        --instance-id) DB_INSTANCE_ID="$2"; shift 2 ;;
        *) echo "Unknown option: $1"; exit 1 ;;
    esac
done

if [[ -z "$AWS_PROFILE" ]]; then
    echo "ERROR: --profile is required"
    exit 1
fi

export AWS_PROFILE AWS_DEFAULT_REGION="$REGION"

echo "=== Teardown AWS Platform Agent ==="

# Delete RDS instance (skip final snapshot)
DB_STATUS=$(aws rds describe-db-instances \
    --db-instance-identifier "$DB_INSTANCE_ID" \
    --query 'DBInstances[0].DBInstanceStatus' --output text 2>/dev/null || echo "not-found")

if [[ "$DB_STATUS" != "not-found" ]]; then
    echo "Deleting RDS instance: $DB_INSTANCE_ID (status: $DB_STATUS)..."
    aws rds delete-db-instance \
        --db-instance-identifier "$DB_INSTANCE_ID" \
        --skip-final-snapshot \
        --delete-automated-backups \
        > /dev/null 2>&1 || true
    echo "Waiting for deletion..."
    aws rds wait db-instance-deleted --db-instance-identifier "$DB_INSTANCE_ID" 2>/dev/null || true
    echo "RDS instance deleted."
else
    echo "RDS instance not found. Skipping."
fi

# Delete DB subnet group
aws rds delete-db-subnet-group \
    --db-subnet-group-name "$SUBNET_GROUP_NAME" 2>/dev/null && \
    echo "Deleted DB subnet group." || echo "DB subnet group not found. Skipping."

# Delete security group
VPC_ID=$(aws ec2 describe-vpcs \
    --filters "Name=isDefault,Values=true" \
    --query 'Vpcs[0].VpcId' --output text 2>/dev/null || echo "None")
if [[ "$VPC_ID" == "None" || -z "$VPC_ID" ]]; then
    VPC_ID=$(aws ec2 describe-vpcs \
        --query 'Vpcs[0].VpcId' --output text)
fi

SG_ID=$(aws ec2 describe-security-groups \
    --filters "Name=group-name,Values=$SG_NAME" "Name=vpc-id,Values=$VPC_ID" \
    --query 'SecurityGroups[0].GroupId' --output text 2>/dev/null || echo "None")

if [[ "$SG_ID" != "None" && -n "$SG_ID" ]]; then
    aws ec2 delete-security-group --group-id "$SG_ID" 2>/dev/null && \
        echo "Deleted security group: $SG_ID" || echo "Could not delete SG (may be in use)."
else
    echo "Security group not found. Skipping."
fi

echo ""
echo "=== Teardown complete ==="
