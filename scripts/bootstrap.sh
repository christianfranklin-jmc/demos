#!/usr/bin/env bash
# bootstrap.sh — Provision AWS infrastructure and seed the Northwinds database.
#
# This script recreates the entire AWS Platform Agent environment from scratch:
#   1. Finds or creates a VPC with public subnets
#   2. Creates a security group allowing PostgreSQL access
#   3. Creates a DB subnet group
#   4. Provisions an RDS PostgreSQL instance
#   5. Waits for the instance to become available
#   6. Seeds the Northwinds dataset
#   7. Generates config files (toolkit.conf, .env, dbt profiles.yml)
#   8. Installs Python dependencies
#
# Prerequisites:
#   - AWS CLI v2 configured with a profile that has AdministratorAccess
#   - psql (PostgreSQL client) installed
#   - uv (Python package manager) installed
#   - This repo checked out
#
# Usage:
#   ./scripts/bootstrap.sh --profile <AWS_PROFILE> [--region <REGION>] [--password <DB_PASSWORD>]
#
# Example:
#   ./scripts/bootstrap.sh --profile AdministratorAccess-637119802057

set -euo pipefail

# ---------------------------------------------------------------------------
# Defaults
# ---------------------------------------------------------------------------
REGION="us-east-1"
DB_INSTANCE_ID="platform-agent-northwinds"
DB_NAME="northwinds"
DB_USER="postgres"
DB_PASSWORD="PlatformAgent2026!"
DB_INSTANCE_CLASS="db.t3.micro"
DB_ENGINE="postgres"
DB_ENGINE_VERSION="16.6"
DB_ALLOCATED_STORAGE=20
SG_NAME="platform-agent-rds-sg"
SUBNET_GROUP_NAME="platform-agent-db-subnets"
PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"

# ---------------------------------------------------------------------------
# Parse arguments
# ---------------------------------------------------------------------------
AWS_PROFILE=""
while [[ $# -gt 0 ]]; do
    case $1 in
        --profile)   AWS_PROFILE="$2"; shift 2 ;;
        --region)    REGION="$2"; shift 2 ;;
        --password)  DB_PASSWORD="$2"; shift 2 ;;
        --instance-id) DB_INSTANCE_ID="$2"; shift 2 ;;
        -h|--help)
            echo "Usage: $0 --profile <AWS_PROFILE> [--region <REGION>] [--password <DB_PASSWORD>]"
            exit 0 ;;
        *) echo "Unknown option: $1"; exit 1 ;;
    esac
done

if [[ -z "$AWS_PROFILE" ]]; then
    echo "ERROR: --profile is required (e.g., --profile AdministratorAccess-637119802057)"
    exit 1
fi

export AWS_PROFILE AWS_DEFAULT_REGION="$REGION"
AWS="aws"

echo "=== AWS Platform Agent Bootstrap ==="
echo "Profile:  $AWS_PROFILE"
echo "Region:   $REGION"
echo "Instance: $DB_INSTANCE_ID"
echo ""

# ---------------------------------------------------------------------------
# Step 1: Find a VPC with public subnets
# ---------------------------------------------------------------------------
echo "--- Step 1: Finding VPC ---"
VPC_ID=$($AWS ec2 describe-vpcs \
    --filters "Name=isDefault,Values=false" \
    --query 'Vpcs[0].VpcId' --output text 2>/dev/null || echo "None")

if [[ "$VPC_ID" == "None" || -z "$VPC_ID" ]]; then
    VPC_ID=$($AWS ec2 describe-vpcs \
        --filters "Name=isDefault,Values=true" \
        --query 'Vpcs[0].VpcId' --output text)
fi
echo "Using VPC: $VPC_ID"

# Get subnets (need at least 2 in different AZs for DB subnet group)
SUBNET_IDS=$($AWS ec2 describe-subnets \
    --filters "Name=vpc-id,Values=$VPC_ID" \
    --query 'Subnets[?MapPublicIpOnLaunch==`true`].SubnetId' --output text)

if [[ -z "$SUBNET_IDS" ]]; then
    # Fall back to any subnets
    SUBNET_IDS=$($AWS ec2 describe-subnets \
        --filters "Name=vpc-id,Values=$VPC_ID" \
        --query 'Subnets[].SubnetId' --output text)
fi

SUBNET_ARRAY=($SUBNET_IDS)
if [[ ${#SUBNET_ARRAY[@]} -lt 2 ]]; then
    echo "ERROR: Need at least 2 subnets in different AZs. Found: ${#SUBNET_ARRAY[@]}"
    exit 1
fi
echo "Using subnets: ${SUBNET_ARRAY[*]}"

# ---------------------------------------------------------------------------
# Step 2: Security group
# ---------------------------------------------------------------------------
echo ""
echo "--- Step 2: Security group ---"
SG_ID=$($AWS ec2 describe-security-groups \
    --filters "Name=group-name,Values=$SG_NAME" "Name=vpc-id,Values=$VPC_ID" \
    --query 'SecurityGroups[0].GroupId' --output text 2>/dev/null || echo "None")

if [[ "$SG_ID" == "None" || -z "$SG_ID" ]]; then
    SG_ID=$($AWS ec2 create-security-group \
        --group-name "$SG_NAME" \
        --description "PostgreSQL access for Platform Agent" \
        --vpc-id "$VPC_ID" \
        --query 'GroupId' --output text)
    echo "Created security group: $SG_ID"

    # Allow PostgreSQL from anywhere (demo only — restrict in production)
    $AWS ec2 authorize-security-group-ingress \
        --group-id "$SG_ID" \
        --protocol tcp --port 5432 --cidr 0.0.0.0/0 \
        > /dev/null
    echo "Opened port 5432 (0.0.0.0/0 — demo only)"
else
    echo "Reusing security group: $SG_ID"
fi

# ---------------------------------------------------------------------------
# Step 3: DB subnet group
# ---------------------------------------------------------------------------
echo ""
echo "--- Step 3: DB subnet group ---"
EXISTING_SUBNET_GROUP=$($AWS rds describe-db-subnet-groups \
    --db-subnet-group-name "$SUBNET_GROUP_NAME" \
    --query 'DBSubnetGroups[0].DBSubnetGroupName' --output text 2>/dev/null || echo "None")

if [[ "$EXISTING_SUBNET_GROUP" == "None" ]]; then
    $AWS rds create-db-subnet-group \
        --db-subnet-group-name "$SUBNET_GROUP_NAME" \
        --db-subnet-group-description "Subnets for Platform Agent RDS" \
        --subnet-ids "${SUBNET_ARRAY[@]}" \
        > /dev/null
    echo "Created DB subnet group: $SUBNET_GROUP_NAME"
else
    echo "Reusing DB subnet group: $SUBNET_GROUP_NAME"
fi

# ---------------------------------------------------------------------------
# Step 4: RDS instance
# ---------------------------------------------------------------------------
echo ""
echo "--- Step 4: RDS instance ---"
DB_STATUS=$($AWS rds describe-db-instances \
    --db-instance-identifier "$DB_INSTANCE_ID" \
    --query 'DBInstances[0].DBInstanceStatus' --output text 2>/dev/null || echo "not-found")

if [[ "$DB_STATUS" == "not-found" ]]; then
    echo "Creating RDS instance (this takes 5-10 minutes)..."
    $AWS rds create-db-instance \
        --db-instance-identifier "$DB_INSTANCE_ID" \
        --db-instance-class "$DB_INSTANCE_CLASS" \
        --engine "$DB_ENGINE" \
        --engine-version "$DB_ENGINE_VERSION" \
        --master-username "$DB_USER" \
        --master-user-password "$DB_PASSWORD" \
        --allocated-storage "$DB_ALLOCATED_STORAGE" \
        --db-name "$DB_NAME" \
        --vpc-security-group-ids "$SG_ID" \
        --db-subnet-group-name "$SUBNET_GROUP_NAME" \
        --publicly-accessible \
        --no-multi-az \
        --storage-type gp2 \
        --backup-retention-period 0 \
        --no-deletion-protection \
        > /dev/null
    echo "RDS instance creation initiated."
else
    echo "RDS instance already exists (status: $DB_STATUS)"
fi

# ---------------------------------------------------------------------------
# Step 5: Wait for RDS to become available
# ---------------------------------------------------------------------------
echo ""
echo "--- Step 5: Waiting for RDS to become available ---"
echo "(This can take 5-10 minutes for a new instance...)"
$AWS rds wait db-instance-available --db-instance-identifier "$DB_INSTANCE_ID"

DB_ENDPOINT=$($AWS rds describe-db-instances \
    --db-instance-identifier "$DB_INSTANCE_ID" \
    --query 'DBInstances[0].Endpoint.Address' --output text)
DB_PORT=$($AWS rds describe-db-instances \
    --db-instance-identifier "$DB_INSTANCE_ID" \
    --query 'DBInstances[0].Endpoint.Port' --output text)
echo "RDS available at: $DB_ENDPOINT:$DB_PORT"

# ---------------------------------------------------------------------------
# Step 6: Seed the database
# ---------------------------------------------------------------------------
echo ""
echo "--- Step 6: Seeding Northwinds database ---"
# Check if data already exists
ROW_COUNT=$(PGPASSWORD="$DB_PASSWORD" psql \
    -h "$DB_ENDPOINT" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" \
    --set=sslmode=require -tAc \
    "SELECT count(*) FROM information_schema.tables WHERE table_schema='public' AND table_type='BASE TABLE'" \
    2>/dev/null || echo "0")

if [[ "$ROW_COUNT" -gt 5 ]]; then
    echo "Database already seeded ($ROW_COUNT tables found). Skipping."
else
    echo "Loading seed data..."
    PGPASSWORD="$DB_PASSWORD" psql \
        -h "$DB_ENDPOINT" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" \
        --set=sslmode=require \
        -f "$PROJECT_DIR/scripts/seed_northwinds.sql" \
        > /dev/null 2>&1
    echo "Northwinds data loaded."
fi

# ---------------------------------------------------------------------------
# Step 7: Generate config files
# ---------------------------------------------------------------------------
echo ""
echo "--- Step 7: Generating config files ---"

# .env file
cat > "$PROJECT_DIR/.env" <<ENVEOF
# AWS Platform Agent — generated by bootstrap.sh
AWS_PROFILE=$AWS_PROFILE
AWS_DEFAULT_REGION=$REGION

# Database connection
DB_HOST=$DB_ENDPOINT
DB_PORT=$DB_PORT
DB_NAME=$DB_NAME
DB_USER=$DB_USER
DB_PASSWORD=$DB_PASSWORD
ENVEOF
echo "Created .env"

# toolkit.conf
cat > "$PROJECT_DIR/toolkit.conf" <<TKEOF
connections {
  northwinds {
    url = "jdbc:postgresql://${DB_ENDPOINT}:${DB_PORT}/${DB_NAME}?sslmode=require"
    username = "$DB_USER"
    password = "$DB_PASSWORD"
  }
}

ds {
  datasources {
    northwinds {
      connection = \${connections.northwinds}
    }
  }
}
TKEOF
echo "Created toolkit.conf"

# dbt profiles.yml (direct credentials for local dev)
mkdir -p "$PROJECT_DIR/dbt_output/northwinds_dw"
cat > "$PROJECT_DIR/dbt_output/northwinds_dw/profiles.yml" <<DBTEOF
northwinds_dw:
  target: dev
  outputs:
    dev:
      type: postgres
      host: $DB_ENDPOINT
      port: $DB_PORT
      user: $DB_USER
      pass: "$DB_PASSWORD"
      dbname: $DB_NAME
      schema: public
      threads: 4
      sslmode: require
DBTEOF
echo "Created dbt profiles.yml"

# ---------------------------------------------------------------------------
# Step 8: Install Python dependencies
# ---------------------------------------------------------------------------
echo ""
echo "--- Step 8: Installing Python dependencies ---"
cd "$PROJECT_DIR"
if command -v uv &> /dev/null; then
    uv pip install -e ".[dev]" 2>&1 | tail -1
    echo "Python dependencies installed via uv."
else
    echo "WARNING: uv not found. Install with: curl -LsSf https://astral.sh/uv/install.sh | sh"
    echo "Then run: uv pip install -e '.[dev]'"
fi

# ---------------------------------------------------------------------------
# Step 9: Verify dbt
# ---------------------------------------------------------------------------
echo ""
echo "--- Step 9: Verifying dbt project ---"
cd "$PROJECT_DIR"
if uv run dbt deps --project-dir dbt_output/northwinds_dw --profiles-dir dbt_output/northwinds_dw > /dev/null 2>&1; then
    uv run dbt compile --project-dir dbt_output/northwinds_dw --profiles-dir dbt_output/northwinds_dw > /dev/null 2>&1
    echo "dbt compile: OK"
else
    echo "WARNING: dbt deps/compile failed. Run manually after checking profiles.yml."
fi

# ---------------------------------------------------------------------------
# Done
# ---------------------------------------------------------------------------
echo ""
echo "=== Bootstrap complete ==="
echo ""
echo "RDS endpoint: $DB_ENDPOINT"
echo "Database:     $DB_NAME"
echo "Config files: .env, toolkit.conf, dbt_output/northwinds_dw/profiles.yml"
echo ""
echo "Next steps:"
echo "  source .env"
echo "  uv run python -m platform_agent --profile $AWS_PROFILE"
echo "  uv run streamlit run streamlit_app/app.py --server.port 8501"
