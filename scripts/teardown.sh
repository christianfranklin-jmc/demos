#!/usr/bin/env bash
# teardown.sh — Remove AWS resources created by bootstrap.sh, Terraform, and agentcore.
#
# Destruction order:
#   1. Terraform (AgentCore Runtime, Gateway, Memory, Cognito, Amplify)
#   2. AgentCore CLI (legacy resources if any)
#   3. RDS instance, subnet group, security group
#
# Usage:
#   ./scripts/teardown.sh --profile <AWS_PROFILE> [--services <LIST>] [--region <REGION>]
#
# Services (comma-separated): rds, redshift, all (default: all)

set -euo pipefail

REGION="us-east-1"
DB_INSTANCE_ID="platform-agent-northwinds"
SG_NAME="platform-agent-rds-sg"
SUBNET_GROUP_NAME="platform-agent-db-subnets"
SERVICES="all"

AWS_PROFILE=""
while [[ $# -gt 0 ]]; do
    case $1 in
        --profile)     AWS_PROFILE="$2"; shift 2 ;;
        --region)      REGION="$2"; shift 2 ;;
        --instance-id) DB_INSTANCE_ID="$2"; shift 2 ;;
        --services)    SERVICES="$2"; shift 2 ;;
        *) echo "Unknown option: $1"; exit 1 ;;
    esac
done

if [[ -z "$AWS_PROFILE" ]]; then
    echo "ERROR: --profile is required"
    exit 1
fi

# Parse services into flags
DO_RDS=false
DO_REDSHIFT=false

IFS=',' read -ra SVC_ARRAY <<< "$SERVICES"
for svc in "${SVC_ARRAY[@]}"; do
    case "$(echo "$svc" | tr '[:upper:]' '[:lower:]' | xargs)" in
        rds)      DO_RDS=true ;;
        redshift) DO_REDSHIFT=true ;;
        all)      DO_RDS=true; DO_REDSHIFT=true ;;
        *) echo "Unknown service: $svc"; exit 1 ;;
    esac
done

export AWS_PROFILE AWS_DEFAULT_REGION="$REGION"
AWS="aws"

echo "=== Teardown AWS Platform Agent ==="
echo "Services: $SERVICES"

# ---------------------------------------------------------------------------
# Destroy Terraform infrastructure (AgentCore Gateway, Runtime, Memory, Cognito, Amplify)
# ---------------------------------------------------------------------------
echo "--- Terraform (infra-terraform/) ---"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TF_DIR="$SCRIPT_DIR/../infra-terraform"
if [[ -d "$TF_DIR/.terraform" ]]; then
    echo "Destroying Terraform-managed resources..."
    (cd "$TF_DIR" && terraform destroy -auto-approve 2>&1) || \
        echo "Terraform destroy completed (or had errors — check output above)."
elif [[ -d "$TF_DIR" ]]; then
    echo "Terraform not initialized. Run 'cd infra-terraform && terraform init' first."
    echo "Skipping Terraform teardown."
else
    echo "infra-terraform/ not found. Skipping Terraform teardown."
fi

# ---------------------------------------------------------------------------
# Destroy AgentCore resources (legacy — agent runtime, ECR repo, gateway)
# ---------------------------------------------------------------------------
echo ""
echo "--- AgentCore CLI (legacy) ---"
if command -v agentcore &> /dev/null; then
    echo "Destroying AgentCore resources..."
    agentcore destroy --force --delete-ecr-repo 2>&1 || echo "AgentCore destroy completed (or no resources found)."
else
    echo "agentcore CLI not found. Skipping AgentCore teardown."
    echo "  Install: uv pip install 'bedrock-agentcore[ag-ui]'"
    echo "  Then run: agentcore destroy --force --delete-ecr-repo"
fi

# ---------------------------------------------------------------------------
# Delete Redshift Serverless (workgroup then namespace)
# ---------------------------------------------------------------------------
if [[ "$DO_REDSHIFT" == "true" ]]; then
echo ""
echo "--- Redshift Serverless ---"
RS_WORKGROUP="platform-agent-wg"
RS_NAMESPACE="platform-agent-ns"

RS_WG_STATUS=$($AWS redshift-serverless get-workgroup \
    --workgroup-name "$RS_WORKGROUP" \
    --query 'workgroup.status' --output text 2>/dev/null || echo "not-found")

if [[ "$RS_WG_STATUS" != "not-found" ]]; then
    echo "Deleting Redshift workgroup: $RS_WORKGROUP..."
    $AWS redshift-serverless delete-workgroup \
        --workgroup-name "$RS_WORKGROUP" > /dev/null 2>&1 || true
    echo "Waiting for workgroup deletion..."
    for i in {1..60}; do
        WG_CHECK=$($AWS redshift-serverless describe-workgroup \
            --workgroup-name "$RS_WORKGROUP" \
            --query 'workgroup.status' --output text 2>/dev/null || echo "deleted")
        [[ "$WG_CHECK" == "deleted" ]] && break
        sleep 5
    done
    echo "Workgroup deleted."
else
    echo "Redshift workgroup not found. Skipping."
fi

RS_NS_STATUS=$($AWS redshift-serverless get-namespace \
    --namespace-name "$RS_NAMESPACE" \
    --query 'namespace.status' --output text 2>/dev/null || echo "not-found")

if [[ "$RS_NS_STATUS" != "not-found" ]]; then
    echo "Deleting Redshift namespace: $RS_NAMESPACE..."
    $AWS redshift-serverless delete-namespace \
        --namespace-name "$RS_NAMESPACE" > /dev/null 2>&1 || true
    echo "Namespace deleted."
else
    echo "Redshift namespace not found. Skipping."
fi
fi  # DO_REDSHIFT

# ---------------------------------------------------------------------------
# Delete RDS instance (skip final snapshot)
# ---------------------------------------------------------------------------
if [[ "$DO_RDS" == "true" ]]; then
echo ""
echo "--- RDS ---"
DB_STATUS=$($AWS rds describe-db-instances \
    --db-instance-identifier "$DB_INSTANCE_ID" \
    --query 'DBInstances[0].DBInstanceStatus' --output text 2>/dev/null || echo "not-found")

if [[ "$DB_STATUS" != "not-found" ]]; then
    echo "Deleting RDS instance: $DB_INSTANCE_ID (status: $DB_STATUS)..."
    $AWS rds delete-db-instance \
        --db-instance-identifier "$DB_INSTANCE_ID" \
        --skip-final-snapshot \
        --delete-automated-backups \
        > /dev/null 2>&1 || true
    echo "Waiting for deletion..."
    $AWS rds wait db-instance-deleted --db-instance-identifier "$DB_INSTANCE_ID" 2>/dev/null || true
    echo "RDS instance deleted."
else
    echo "RDS instance not found. Skipping."
fi
fi  # DO_RDS

# Delete shared resources only if BOTH rds and redshift are being torn down
if [[ "$DO_RDS" == "true" && "$DO_REDSHIFT" == "true" ]]; then
    # Delete DB subnet group
    $AWS rds delete-db-subnet-group \
        --db-subnet-group-name "$SUBNET_GROUP_NAME" 2>/dev/null && \
        echo "Deleted DB subnet group." || echo "DB subnet group not found. Skipping."

    # Delete security group
    VPC_ID=$($AWS ec2 describe-vpcs \
        --filters "Name=isDefault,Values=true" \
        --query 'Vpcs[0].VpcId' --output text 2>/dev/null || echo "None")
    if [[ "$VPC_ID" == "None" || -z "$VPC_ID" ]]; then
        VPC_ID=$($AWS ec2 describe-vpcs \
            --query 'Vpcs[0].VpcId' --output text)
    fi

    SG_ID=$($AWS ec2 describe-security-groups \
        --filters "Name=group-name,Values=$SG_NAME" "Name=vpc-id,Values=$VPC_ID" \
        --query 'SecurityGroups[0].GroupId' --output text 2>/dev/null || echo "None")

    if [[ "$SG_ID" != "None" && -n "$SG_ID" ]]; then
        $AWS ec2 delete-security-group --group-id "$SG_ID" 2>/dev/null && \
            echo "Deleted security group: $SG_ID" || echo "Could not delete SG (may be in use)."
    else
        echo "Security group not found. Skipping."
    fi
else
    echo ""
    echo "Shared resources (subnet group, security group) preserved — not all services torn down."
fi

echo ""
echo "=== Teardown complete ==="
