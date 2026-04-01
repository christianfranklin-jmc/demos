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
#   ./scripts/bootstrap.sh --profile <AWS_PROFILE> [--services <LIST>] [--region <REGION>]
#
# Services (comma-separated):
#   rds       — PostgreSQL on RDS (default)
#   redshift  — Redshift Serverless
#   snowflake — Snowflake config generation (no AWS provisioning)
#   all       — All of the above
#
# Examples:
#   ./scripts/bootstrap.sh --profile AdministratorAccess-637119802057
#   ./scripts/bootstrap.sh --profile AdministratorAccess-637119802057 --services rds
#   ./scripts/bootstrap.sh --profile AdministratorAccess-637119802057 --services rds,redshift
#   ./scripts/bootstrap.sh --profile AdministratorAccess-637119802057 --services snowflake
#   ./scripts/bootstrap.sh --profile AdministratorAccess-637119802057 --services all

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
SERVICES="rds"

# Snowflake defaults (used with --services snowflake)
SF_ACCOUNT=""
SF_USER=""
SF_WAREHOUSE="COMPUTE_WH"
SF_DATABASE=""
SF_SCHEMA="PUBLIC"
SF_ROLE=""
SF_AUTHENTICATOR="externalbrowser"

# ---------------------------------------------------------------------------
# Parse arguments
# ---------------------------------------------------------------------------
AWS_PROFILE=""
while [[ $# -gt 0 ]]; do
    case $1 in
        --profile)      AWS_PROFILE="$2"; shift 2 ;;
        --region)       REGION="$2"; shift 2 ;;
        --password)     DB_PASSWORD="$2"; shift 2 ;;
        --instance-id)  DB_INSTANCE_ID="$2"; shift 2 ;;
        --services)     SERVICES="$2"; shift 2 ;;
        --sf-account)   SF_ACCOUNT="$2"; shift 2 ;;
        --sf-user)      SF_USER="$2"; shift 2 ;;
        --sf-warehouse) SF_WAREHOUSE="$2"; shift 2 ;;
        --sf-database)  SF_DATABASE="$2"; shift 2 ;;
        --sf-schema)    SF_SCHEMA="$2"; shift 2 ;;
        --sf-role)      SF_ROLE="$2"; shift 2 ;;
        -h|--help)
            echo "Usage: $0 --profile <AWS_PROFILE> [--services <LIST>] [--region <REGION>]"
            echo ""
            echo "Services (comma-separated): rds, redshift, snowflake, all"
            echo "Default: rds"
            echo ""
            echo "Snowflake flags (used with --services snowflake):"
            echo "  --sf-account, --sf-user, --sf-warehouse, --sf-database, --sf-schema, --sf-role"
            exit 0 ;;
        *) echo "Unknown option: $1"; exit 1 ;;
    esac
done

if [[ -z "$AWS_PROFILE" ]]; then
    echo "ERROR: --profile is required (e.g., --profile AdministratorAccess-637119802057)"
    exit 1
fi

# Parse services into flags
DO_RDS=false
DO_REDSHIFT=false
DO_SNOWFLAKE=false

IFS=',' read -ra SVC_ARRAY <<< "$SERVICES"
for svc in "${SVC_ARRAY[@]}"; do
    case "$(echo "$svc" | tr '[:upper:]' '[:lower:]' | xargs)" in
        rds)       DO_RDS=true ;;
        redshift)  DO_REDSHIFT=true ;;
        snowflake) DO_SNOWFLAKE=true ;;
        all)       DO_RDS=true; DO_REDSHIFT=true; DO_SNOWFLAKE=true ;;
        *) echo "ERROR: Unknown service '$svc'. Valid: rds, redshift, snowflake, all"; exit 1 ;;
    esac
done

export AWS_PROFILE AWS_DEFAULT_REGION="$REGION"
AWS="aws"

echo "=== AWS Platform Agent Bootstrap ==="
echo "Profile:  $AWS_PROFILE"
echo "Region:   $REGION"
echo "Services: $SERVICES"
echo ""

# ---------------------------------------------------------------------------
# Step 1: Find a VPC with public subnets and internet gateway
# ---------------------------------------------------------------------------
echo "--- Step 1: Finding VPC with internet access ---"

# Helper: check if a VPC has an internet gateway attached
has_igw() {
    local vpc="$1"
    local igw
    igw=$($AWS ec2 describe-internet-gateways \
        --filters "Name=attachment.vpc-id,Values=$vpc" \
        --query 'InternetGateways[0].InternetGatewayId' --output text 2>/dev/null)
    [[ -n "$igw" && "$igw" != "None" ]]
}

# Try default VPC first (most likely to have internet access)
VPC_ID=$($AWS ec2 describe-vpcs \
    --filters "Name=isDefault,Values=true" \
    --query 'Vpcs[0].VpcId' --output text 2>/dev/null || echo "None")

if [[ "$VPC_ID" == "None" || -z "$VPC_ID" ]]; then
    # No default VPC — pick the first non-default VPC
    VPC_ID=$($AWS ec2 describe-vpcs \
        --query 'Vpcs[0].VpcId' --output text 2>/dev/null || echo "None")
fi

if [[ "$VPC_ID" == "None" || -z "$VPC_ID" ]]; then
    echo "ERROR: No VPC found in region $REGION"
    exit 1
fi
echo "Using VPC: $VPC_ID"

# Ensure VPC has an internet gateway (required for public RDS access)
IGW_ID=$($AWS ec2 describe-internet-gateways \
    --filters "Name=attachment.vpc-id,Values=$VPC_ID" \
    --query 'InternetGateways[0].InternetGatewayId' --output text 2>/dev/null || echo "None")

if [[ "$IGW_ID" == "None" || -z "$IGW_ID" ]]; then
    echo "No internet gateway found — creating one..."
    IGW_ID=$($AWS ec2 create-internet-gateway \
        --query 'InternetGateway.InternetGatewayId' --output text)
    $AWS ec2 attach-internet-gateway --internet-gateway-id "$IGW_ID" --vpc-id "$VPC_ID"
    echo "Created and attached IGW: $IGW_ID"
else
    echo "Internet gateway: $IGW_ID"
fi

# Ensure the main route table has a route to the IGW
MAIN_RTB=$($AWS ec2 describe-route-tables \
    --filters "Name=vpc-id,Values=$VPC_ID" "Name=association.main,Values=true" \
    --query 'RouteTables[0].RouteTableId' --output text)

EXISTING_IGW_ROUTE=$($AWS ec2 describe-route-tables \
    --route-table-ids "$MAIN_RTB" \
    --query "RouteTables[0].Routes[?GatewayId=='$IGW_ID' && DestinationCidrBlock=='0.0.0.0/0']" \
    --output text 2>/dev/null)

if [[ -z "$EXISTING_IGW_ROUTE" ]]; then
    echo "Adding 0.0.0.0/0 route to IGW in main route table..."
    $AWS ec2 create-route \
        --route-table-id "$MAIN_RTB" \
        --destination-cidr-block 0.0.0.0/0 \
        --gateway-id "$IGW_ID" > /dev/null 2>&1 || \
    $AWS ec2 replace-route \
        --route-table-id "$MAIN_RTB" \
        --destination-cidr-block 0.0.0.0/0 \
        --gateway-id "$IGW_ID" > /dev/null
    echo "Route added."
else
    echo "IGW route exists in main route table."
fi

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

    # Allow PostgreSQL + Redshift from anywhere (demo only — restrict in production)
    $AWS ec2 authorize-security-group-ingress \
        --group-id "$SG_ID" \
        --protocol tcp --port 5432 --cidr 0.0.0.0/0 \
        > /dev/null
    $AWS ec2 authorize-security-group-ingress \
        --group-id "$SG_ID" \
        --protocol tcp --port 5439 --cidr 0.0.0.0/0 \
        > /dev/null
    echo "Opened ports 5432 (PostgreSQL) and 5439 (Redshift) — demo only"
else
    echo "Reusing security group: $SG_ID"
    # Ensure Redshift port is open (may not exist if SG was created before Redshift support)
    $AWS ec2 authorize-security-group-ingress \
        --group-id "$SG_ID" \
        --protocol tcp --port 5439 --cidr 0.0.0.0/0 \
        > /dev/null 2>&1 || true
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
DB_ENDPOINT=""
DB_PORT=""

if [[ "$DO_RDS" == "true" ]]; then
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
    # Reset password to ensure it matches the script's value
    echo "Resetting master password to ensure consistency..."
    $AWS rds modify-db-instance \
        --db-instance-identifier "$DB_INSTANCE_ID" \
        --master-user-password "$DB_PASSWORD" \
        --apply-immediately > /dev/null 2>&1 || true
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

# Wait briefly for password change to take effect (if modified above)
if [[ "$DB_STATUS" != "not-found" ]]; then
    echo "Waiting 15s for password change to propagate..."
    sleep 15
fi

# ---------------------------------------------------------------------------
# Step 6: Seed the database
# ---------------------------------------------------------------------------
echo ""
echo "--- Step 6: Seeding Northwinds database ---"
# Check if data already exists
ROW_COUNT=$(PGSSLMODE=require PGPASSWORD="$DB_PASSWORD" psql \
    -h "$DB_ENDPOINT" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" \
    -tAc \
    "SELECT count(*) FROM information_schema.tables WHERE table_schema='public' AND table_type='BASE TABLE'" \
    2>/dev/null || echo "0")

if [[ "$ROW_COUNT" -gt 5 ]]; then
    echo "Database already seeded ($ROW_COUNT tables found). Skipping."
else
    echo "Loading seed data..."
    PGSSLMODE=require PGPASSWORD="$DB_PASSWORD" psql \
        -h "$DB_ENDPOINT" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" \
        -f "$PROJECT_DIR/scripts/seed_northwinds.sql" \
        > /dev/null 2>&1
    echo "Northwinds data loaded."
fi

else
    echo ""
    echo "--- Skipping RDS (not in --services) ---"
fi  # DO_RDS

# ---------------------------------------------------------------------------
# Step 7: Redshift Serverless
# ---------------------------------------------------------------------------
RS_ENDPOINT=""
RS_PORT=5439

if [[ "$DO_REDSHIFT" == "true" ]]; then
echo ""
echo "--- Step 7: Redshift Serverless ---"

RS_NAMESPACE="platform-agent-ns"
RS_WORKGROUP="platform-agent-wg"
RS_DB_NAME="dev"
RS_ADMIN_USER="admin"
RS_ADMIN_PASSWORD="$DB_PASSWORD"

# Check if namespace exists
RS_NS_STATUS=$($AWS redshift-serverless get-namespace \
    --namespace-name "$RS_NAMESPACE" \
    --query 'namespace.status' --output text 2>/dev/null || echo "not-found")

if [[ "$RS_NS_STATUS" == "not-found" ]]; then
    echo "Creating Redshift Serverless namespace: $RS_NAMESPACE..."
    $AWS redshift-serverless create-namespace \
        --namespace-name "$RS_NAMESPACE" \
        --db-name "$RS_DB_NAME" \
        --admin-username "$RS_ADMIN_USER" \
        --admin-user-password "$RS_ADMIN_PASSWORD" \
        > /dev/null
    echo "Namespace created."
else
    echo "Reusing namespace: $RS_NAMESPACE (status: $RS_NS_STATUS)"
fi

# Check if workgroup exists
RS_WG_STATUS=$($AWS redshift-serverless describe-workgroup \
    --workgroup-name "$RS_WORKGROUP" \
    --query 'workgroup.status' --output text 2>/dev/null || echo "not-found")

if [[ "$RS_WG_STATUS" == "not-found" ]]; then
    echo "Creating Redshift Serverless workgroup: $RS_WORKGROUP..."
    $AWS redshift-serverless create-workgroup \
        --workgroup-name "$RS_WORKGROUP" \
        --namespace-name "$RS_NAMESPACE" \
        --base-capacity 8 \
        --publicly-accessible \
        --security-group-ids "$SG_ID" \
        --subnet-ids "${SUBNET_ARRAY[@]}" \
        > /dev/null
    echo "Workgroup creation initiated (takes 2-5 minutes)..."
else
    echo "Reusing workgroup: $RS_WORKGROUP (status: $RS_WG_STATUS)"
fi

# Wait for workgroup to become available
echo "Waiting for Redshift Serverless workgroup..."
for i in {1..60}; do
    RS_WG_STATUS=$($AWS redshift-serverless get-workgroup \
        --workgroup-name "$RS_WORKGROUP" \
        --query 'workgroup.status' --output text 2>/dev/null || echo "not-found")
    if [[ "$RS_WG_STATUS" == "AVAILABLE" ]]; then
        break
    fi
    sleep 5
done

if [[ "$RS_WG_STATUS" != "AVAILABLE" ]]; then
    echo "WARNING: Redshift workgroup not yet available (status: $RS_WG_STATUS)."
    echo "It may still be creating. Check the AWS console."
    RS_ENDPOINT="PENDING"
    RS_PORT=5439
else
    RS_ENDPOINT=$($AWS redshift-serverless get-workgroup \
        --workgroup-name "$RS_WORKGROUP" \
        --query 'workgroup.endpoint.address' --output text)
    RS_PORT=$($AWS redshift-serverless get-workgroup \
        --workgroup-name "$RS_WORKGROUP" \
        --query 'workgroup.endpoint.port' --output text)
    echo "Redshift Serverless available at: ${RS_ENDPOINT}:${RS_PORT}"
fi

# Wait for network connectivity (workgroup may show AVAILABLE before network is ready)
if [[ "$RS_ENDPOINT" != "PENDING" ]]; then
    echo "Verifying Redshift network connectivity..."
    RS_CONNECTED=false
    for attempt in {1..12}; do
        if uv run python -c "
import redshift_connector
conn = redshift_connector.connect(host='${RS_ENDPOINT}', port=${RS_PORT},
    database='${RS_DB_NAME}', user='${RS_ADMIN_USER}',
    password='${RS_ADMIN_PASSWORD}', ssl=True, timeout=10)
conn.close()
print('OK')
" 2>/dev/null | grep -q "OK"; then
            echo "Redshift connectivity confirmed."
            RS_CONNECTED=true
            break
        fi
        echo "  Attempt $attempt/12 — waiting 10 seconds..."
        sleep 10
    done

    if [[ "$RS_CONNECTED" != "true" ]]; then
        echo "WARNING: Could not connect to Redshift after 2 minutes."
        echo "  The workgroup may need more time. Try again later or check the console."
        RS_ENDPOINT="PENDING"
    fi
fi

# Seed Northwinds into Redshift (if connected and not already seeded)
if [[ "$RS_ENDPOINT" != "PENDING" ]]; then
    echo "Seeding Northwinds data into Redshift..."
    if command -v uv &> /dev/null && uv run python -c "import redshift_connector" 2>/dev/null; then
        uv run python -c "
import redshift_connector
conn = redshift_connector.connect(
    host='${RS_ENDPOINT}', port=${RS_PORT},
    database='${RS_DB_NAME}', user='${RS_ADMIN_USER}',
    password='${RS_ADMIN_PASSWORD}', ssl=True
)
conn.autocommit = True
cur = conn.cursor()
cur.execute(\"SELECT COUNT(*) FROM information_schema.tables WHERE table_schema='public' AND table_type='BASE TABLE'\")
count = cur.fetchone()[0]
if count >= 10:
    print(f'Redshift already has {count} tables — skipping seed.')
else:
    print('Loading seed data into Redshift...')
    with open('scripts/seed_northwinds.sql', 'r') as f:
        sql = f.read()
    cur.execute(sql)
    cur.execute(\"SELECT COUNT(*) FROM information_schema.tables WHERE table_schema='public' AND table_type='BASE TABLE'\")
    print(f'Redshift seeded: {cur.fetchone()[0]} tables')
cur.close(); conn.close()
" 2>&1
    else
        echo "WARNING: redshift_connector not installed. Skipping Redshift seed."
        echo "  Install with: uv pip install -e '.[redshift]'"
    fi
fi

else
    echo ""
    echo "--- Skipping Redshift (not in --services) ---"
    RS_ENDPOINT=""
    RS_PORT=5439
    RS_DB_NAME="dev"
    RS_ADMIN_USER="admin"
    RS_ADMIN_PASSWORD="$DB_PASSWORD"
fi  # DO_REDSHIFT

# ---------------------------------------------------------------------------
# Step 8: Snowflake config (no AWS provisioning)
# ---------------------------------------------------------------------------
if [[ "$DO_SNOWFLAKE" == "true" ]]; then
echo ""
echo "--- Step 8: Snowflake configuration ---"

# Prompt for credentials if not provided via flags
if [[ -z "$SF_ACCOUNT" ]]; then
    read -rp "  Snowflake account (e.g., lga76011): " SF_ACCOUNT
fi
if [[ -z "$SF_USER" ]]; then
    read -rp "  Snowflake user (e.g., user@company.com): " SF_USER
fi
if [[ -z "$SF_DATABASE" ]]; then
    read -rp "  Snowflake database: " SF_DATABASE
fi
if [[ -z "$SF_ROLE" ]]; then
    read -rp "  Snowflake role (leave blank for default): " SF_ROLE
fi

echo "Snowflake config:"
echo "  Account:   $SF_ACCOUNT"
echo "  User:      $SF_USER"
echo "  Warehouse: $SF_WAREHOUSE"
echo "  Database:  $SF_DATABASE"
echo "  Schema:    $SF_SCHEMA"
echo "  Role:      ${SF_ROLE:-<default>}"
echo "  Auth:      $SF_AUTHENTICATOR"
fi

# ---------------------------------------------------------------------------
# Step 9: Generate config files (additive — preserves existing vars)
# ---------------------------------------------------------------------------
echo ""
echo "--- Step 9: Generating config files ---"

# Build .env content — start with common vars, add per-service blocks
ENV_CONTENT="# AWS Platform Agent — generated by bootstrap.sh
AWS_PROFILE=$AWS_PROFILE
AWS_DEFAULT_REGION=$REGION
"

if [[ "$DO_RDS" == "true" && -n "$DB_ENDPOINT" ]]; then
ENV_CONTENT+="
# PostgreSQL (RDS) connection
DB_HOST=$DB_ENDPOINT
DB_PORT=$DB_PORT
DB_NAME=$DB_NAME
DB_USER=$DB_USER
DB_PASSWORD=$DB_PASSWORD
DB_DRIVER_TYPE=postgresql
"
fi

if [[ "$DO_REDSHIFT" == "true" ]]; then
ENV_CONTENT+="
# Redshift Serverless connection
RS_HOST=${RS_ENDPOINT:-PENDING}
RS_PORT=${RS_PORT:-5439}
RS_DB_NAME=${RS_DB_NAME:-dev}
RS_USER=${RS_ADMIN_USER:-admin}
RS_PASSWORD=${RS_ADMIN_PASSWORD:-$DB_PASSWORD}
"
fi

if [[ "$DO_SNOWFLAKE" == "true" && -n "$SF_ACCOUNT" ]]; then
ENV_CONTENT+="
# Snowflake connection
SF_ACCOUNT=$SF_ACCOUNT
SF_USER=$SF_USER
SF_AUTHENTICATOR=$SF_AUTHENTICATOR
SF_WAREHOUSE=$SF_WAREHOUSE
SF_DATABASE=$SF_DATABASE
SF_SCHEMA=$SF_SCHEMA
SF_ROLE=$SF_ROLE
"
fi

# Preserve existing .env vars that we're not overwriting
if [[ -f "$PROJECT_DIR/.env" ]]; then
    # Read existing vars, skip ones we're about to write
    EXISTING_VARS=""
    while IFS= read -r line; do
        # Skip empty lines, comments, and vars we're replacing
        [[ -z "$line" || "$line" == \#* ]] && continue
        VAR_NAME="${line%%=*}"
        if ! echo "$ENV_CONTENT" | grep -q "^${VAR_NAME}="; then
            EXISTING_VARS+="$line"$'\n'
        fi
    done < "$PROJECT_DIR/.env"
    if [[ -n "$EXISTING_VARS" ]]; then
        ENV_CONTENT+="
# Preserved from previous .env
${EXISTING_VARS}"
    fi
fi

echo "$ENV_CONTENT" > "$PROJECT_DIR/.env"
echo "Created .env"

# toolkit.conf (only if RDS is provisioned)
if [[ "$DO_RDS" == "true" && -n "$DB_ENDPOINT" ]]; then
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
fi

# ---------------------------------------------------------------------------
# Step 10: Install Python dependencies
# ---------------------------------------------------------------------------
echo ""
echo "--- Step 10: Installing Python dependencies ---"
cd "$PROJECT_DIR"
if command -v uv &> /dev/null; then
    uv pip install -e ".[dev]" 2>&1 | tail -1
    if [[ "$DO_REDSHIFT" == "true" ]]; then
        uv pip install -e ".[redshift]" 2>&1 | tail -1
    fi
    if [[ "$DO_SNOWFLAKE" == "true" ]]; then
        uv pip install -e ".[snowflake]" 2>&1 | tail -1
    fi
    echo "Python dependencies installed via uv."
else
    echo "WARNING: uv not found. Install with: curl -LsSf https://astral.sh/uv/install.sh | sh"
fi

# ---------------------------------------------------------------------------
# Step 11: Verify dbt (only if RDS was provisioned)
# ---------------------------------------------------------------------------
if [[ "$DO_RDS" == "true" && -n "$DB_ENDPOINT" ]]; then
echo ""
echo "--- Step 11: Verifying dbt project ---"
cd "$PROJECT_DIR"
if uv run dbt deps --project-dir dbt_output/northwinds_dw --profiles-dir dbt_output/northwinds_dw > /dev/null 2>&1; then
    uv run dbt compile --project-dir dbt_output/northwinds_dw --profiles-dir dbt_output/northwinds_dw > /dev/null 2>&1
    echo "dbt compile: OK"
else
    echo "WARNING: dbt deps/compile failed. Run manually after checking profiles.yml."
fi
fi

# ---------------------------------------------------------------------------
# Done
# ---------------------------------------------------------------------------
echo ""
echo "=== Bootstrap complete ==="
echo ""
echo "Services provisioned: $SERVICES"
if [[ "$DO_RDS" == "true" && -n "$DB_ENDPOINT" ]]; then
    echo "PostgreSQL (RDS):  $DB_ENDPOINT:$DB_PORT"
fi
if [[ "$DO_REDSHIFT" == "true" ]]; then
    echo "Redshift:          ${RS_ENDPOINT:-PENDING}:${RS_PORT:-5439}"
fi
if [[ "$DO_SNOWFLAKE" == "true" && -n "$SF_ACCOUNT" ]]; then
    echo "Snowflake:         $SF_ACCOUNT ($SF_DATABASE.$SF_SCHEMA)"
fi
echo "Config files:      .env"
echo ""
echo "Next steps:"
echo "  source .env"
echo "  uv run streamlit run streamlit_app/app.py --server.port 8501"
