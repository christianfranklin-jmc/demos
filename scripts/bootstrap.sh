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
#   terraform — AgentCore infra (Terraform + Docker build + Amplify deploy)
#   all       — All of the above
#
# Examples:
#   ./scripts/bootstrap.sh --profile AdministratorAccess-637119802057
#   ./scripts/bootstrap.sh --profile AdministratorAccess-637119802057 --services rds
#   ./scripts/bootstrap.sh --profile AdministratorAccess-637119802057 --services rds,redshift
#   ./scripts/bootstrap.sh --profile AdministratorAccess-637119802057 --services terraform
#   ./scripts/bootstrap.sh --profile AdministratorAccess-637119802057 --services rds,terraform
#   ./scripts/bootstrap.sh --profile AdministratorAccess-637119802057 --services all

set -euo pipefail

# ---------------------------------------------------------------------------
# Defaults
# ---------------------------------------------------------------------------
REGION="us-east-1"
DB_INSTANCE_ID="platform-agent-pinnacle"
DB_NAME="pinnacle"
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
            echo "Services (comma-separated): rds, redshift, snowflake, terraform, all"
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
DO_TERRAFORM=false

IFS=',' read -ra SVC_ARRAY <<< "$SERVICES"
for svc in "${SVC_ARRAY[@]}"; do
    case "$(echo "$svc" | tr '[:upper:]' '[:lower:]' | xargs)" in
        rds)       DO_RDS=true ;;
        redshift)  DO_REDSHIFT=true ;;
        snowflake) DO_SNOWFLAKE=true ;;
        terraform) DO_TERRAFORM=true ;;
        all)       DO_RDS=true; DO_REDSHIFT=true; DO_SNOWFLAKE=true; DO_TERRAFORM=true ;;
        *) echo "ERROR: Unknown service '$svc'. Valid: rds, redshift, snowflake, terraform, all"; exit 1 ;;
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
echo "--- Step 6: Seeding Pinnacle database ---"
# Pinnacle uses per-process schemas (ap, billing, crm, gl, hr, performance,
# planning, portfolio) instead of a flat public namespace. Count tables across
# all non-system schemas to detect prior seeding (FR-042).
ROW_COUNT=$(PGSSLMODE=require PGPASSWORD="$DB_PASSWORD" psql \
    -h "$DB_ENDPOINT" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" \
    -tAc \
    "SELECT count(*) FROM information_schema.tables WHERE table_type='BASE TABLE' AND table_schema NOT IN ('pg_catalog','information_schema') AND table_schema NOT LIKE 'pg_temp_%' AND table_schema NOT LIKE 'pg_toast%'" \
    2>/dev/null || echo "0")

# Pinnacle has ~34 user tables across the 8 process schemas; threshold = 20
# is well below that and well above any empty-DB control rows.
if [[ "$ROW_COUNT" -gt 20 ]]; then
    echo "Database already seeded ($ROW_COUNT tables found across business-process schemas). Skipping."
elif [[ -f "$PROJECT_DIR/scripts/seed_pinnacle.sql" ]]; then
    echo "Loading Pinnacle seed data..."
    PGSSLMODE=require PGPASSWORD="$DB_PASSWORD" psql \
        -h "$DB_ENDPOINT" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" \
        -f "$PROJECT_DIR/scripts/seed_pinnacle.sql" \
        > /dev/null 2>&1
    echo "Pinnacle data loaded."
else
    echo "WARNING: scripts/seed_pinnacle.sql not found." >&2
    echo "  The Pinnacle DB is expected to be already seeded out-of-band." >&2
    echo "  To regenerate the seed file from a live DB, run:" >&2
    echo "    scripts/regenerate_pinnacle_seed.sh" >&2
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

# Check if workgroup exists. Note: the subcommand is `get-workgroup`
# (not `describe-workgroup`, which does not exist in the redshift-serverless
# service and silently fails, leading to a spurious create attempt that
# then trips ConflictException).
RS_WG_STATUS=$($AWS redshift-serverless get-workgroup \
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
    import re
    with open('scripts/seed_northwinds.sql', 'r') as f:
        sql = f.read()
    # Adapt PostgreSQL types for Redshift compatibility
    sql = sql.replace(' bytea', ' VARCHAR(1)')    # bytea not supported
    sql = re.sub(r\" text([,\n)])\", r' VARCHAR(MAX)\1', sql)  # text -> VARCHAR(MAX)
    # Remove SET statements that Redshift doesn't support
    sql = re.sub(r'SET\s+statement_timeout\s*=.*?;', '', sql)
    sql = re.sub(r'SET\s+lock_timeout\s*=.*?;', '', sql)
    sql = re.sub(r'SET\s+client_encoding\s*=.*?;', '', sql)
    sql = re.sub(r'SET\s+standard_conforming_strings\s*=.*?;', '', sql)
    sql = re.sub(r'SET\s+check_function_bodies\s*=.*?;', '', sql)
    sql = re.sub(r'SET\s+client_min_messages\s*=.*?;', '', sql)
    sql = re.sub(r'SET\s+default_tablespace\s*=.*?;', '', sql)
    sql = re.sub(r'SET\s+default_with_oids\s*=.*?;', '', sql)
    # Remove bytea INSERT values (binary data can't load into VARCHAR)
    sql = re.sub(r\"'\\\\\\\\x[0-9a-fA-F]+'\", \"''\", sql)
    # Execute statement by statement to skip errors on individual statements
    statements = [s.strip() for s in sql.split(';') if s.strip()]
    errors = 0
    for stmt in statements:
        try:
            cur.execute(stmt)
        except Exception as e:
            errors += 1
            if errors <= 3:
                print(f'  Warning: {str(e)[:80]}')
    cur.execute(\"SELECT COUNT(*) FROM information_schema.tables WHERE table_schema='public' AND table_type='BASE TABLE'\")
    tbl_count = cur.fetchone()[0]
    print(f'Redshift seeded: {tbl_count} tables ({errors} statements skipped)')
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

# Prompt for credentials only when stdin is a terminal AND the flag was not
# supplied. Under set -euo pipefail a `read -rp` with no input (piped/
# background run) returns EOF and aborts the script silently — we detect
# that here and skip the prompt block instead. Non-interactive runs that
# want Snowflake wired must pass --sf-account / --sf-user / --sf-database.
if [[ -t 0 ]]; then
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
elif [[ -z "$SF_ACCOUNT" ]]; then
    echo "  Non-interactive run: skipping Snowflake prompts (no --sf-account supplied)."
fi

echo "Snowflake config:"
echo "  Account:   ${SF_ACCOUNT:-<unset>}"
echo "  User:      ${SF_USER:-<unset>}"
echo "  Warehouse: $SF_WAREHOUSE"
echo "  Database:  ${SF_DATABASE:-<unset>}"
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
# `uv run dbt` does not register dbt as a uv script — the executable lives at
# .venv/bin/dbt. Use that full path so failures stay confined to an if/else
# instead of crashing the whole bootstrap under set -euo pipefail.
DBT_BIN="$PROJECT_DIR/.venv/bin/dbt"
if [[ -x "$DBT_BIN" && -d "dbt_output/northwinds_dw" ]]; then
    if "$DBT_BIN" deps --project-dir dbt_output/northwinds_dw --profiles-dir dbt_output/northwinds_dw > /dev/null 2>&1; then
        "$DBT_BIN" compile --project-dir dbt_output/northwinds_dw --profiles-dir dbt_output/northwinds_dw > /dev/null 2>&1 \
            && echo "dbt compile: OK" \
            || echo "WARNING: dbt compile failed. Run manually."
    else
        echo "WARNING: dbt deps failed. Run manually after checking profiles.yml."
    fi
else
    echo "Skipping dbt verify (no dbt binary or no dbt_output/northwinds_dw project — harmless)."
fi
fi

# ---------------------------------------------------------------------------
# Step 12: Terraform + Docker + Amplify (when --services terraform)
# ---------------------------------------------------------------------------
if [[ "$DO_TERRAFORM" == "true" ]]; then
echo ""
echo "--- Step 12: Terraform Infrastructure ---"
TF_DIR="$PROJECT_DIR/infra-terraform"
cd "$TF_DIR"

# Create terraform.tfvars if missing
if [[ ! -f terraform.tfvars ]]; then
    echo "Generating terraform.tfvars from .env..."
    cat > terraform.tfvars << TFEOF
stack_name_base = "platform-agent"
admin_user_email = "${DB_USER}@example.com"
backend_pattern = "platform-agent"
backend_deployment_type = "docker"
backend_network_mode = "PUBLIC"
db_host = "${DB_ENDPOINT:-}"
db_port = ${DB_PORT:-5432}
db_name = "${DB_NAME}"
db_user = "${DB_USER}"
db_password = "${DB_PASSWORD}"
db_driver_type = "postgresql"
TFEOF
    echo "Created terraform.tfvars (edit admin_user_email before applying)"
fi

# Init and apply
terraform init
terraform apply -auto-approve

# Capture outputs
RUNTIME_ARN=$(terraform output -raw runtime_arn 2>/dev/null || echo "")
ECR_URL=$(terraform output -raw ecr_repository_url 2>/dev/null || echo "")
COGNITO_POOL_ID=$(terraform output -raw cognito_user_pool_id 2>/dev/null || echo "")
COGNITO_CLIENT_ID=$(terraform output -raw cognito_web_client_id 2>/dev/null || echo "")
COGNITO_DOMAIN=$(terraform output -raw cognito_domain_url 2>/dev/null || echo "")
AMPLIFY_URL=$(terraform output -raw amplify_app_url 2>/dev/null || echo "")
cd "$PROJECT_DIR"

# Docker build + push (if Docker is available)
if command -v docker &> /dev/null && docker info > /dev/null 2>&1; then
    echo ""
    echo "--- Building and pushing agent container ---"
    ECR_HOST=$(echo "$ECR_URL" | cut -d/ -f1)
    $AWS ecr get-login-password --region "$REGION" | \
        docker login --username AWS --password-stdin "$ECR_HOST" 2>/dev/null
    docker build --platform linux/arm64 -t platform-agent \
        -f patterns/platform-agent/Dockerfile . 2>&1 | tail -3
    docker tag platform-agent:latest "${ECR_URL}:latest"
    docker push "${ECR_URL}:latest" 2>&1 | tail -3

    # Re-apply to pick up the image
    cd "$TF_DIR" && terraform apply -auto-approve 2>&1 | tail -5
    cd "$PROJECT_DIR"
    echo "Agent container deployed."
else
    echo "WARNING: Docker not running. Skipping container build."
    echo "  Start Docker Desktop, then run:"
    echo "  docker build --platform linux/arm64 -t platform-agent -f patterns/platform-agent/Dockerfile ."
    echo "  docker tag platform-agent:latest ${ECR_URL}:latest"
    echo "  docker push ${ECR_URL}:latest"
fi

# Deploy React frontend to Amplify
if command -v npm &> /dev/null && [[ -n "$AMPLIFY_URL" ]]; then
    echo ""
    echo "--- Deploying React frontend to Amplify ---"
    cd "$PROJECT_DIR/frontend"

    cat > .env.production << FEEOF
VITE_AGENTCORE_RUNTIME_ARN=${RUNTIME_ARN}
VITE_AGENTCORE_REGION=${REGION}
VITE_AGENTCORE_PATTERN=strands-single-agent
VITE_COGNITO_POOL_ID=${COGNITO_POOL_ID}
VITE_COGNITO_CLIENT_ID=${COGNITO_CLIENT_ID}
VITE_COGNITO_DOMAIN=${COGNITO_DOMAIN}
VITE_COGNITO_REDIRECT_URI=${AMPLIFY_URL}/auth/callback
FEEOF

    npm install --silent 2>/dev/null
    npm run build 2>&1 | tail -5
    cp public/aws-exports.json dist/ 2>/dev/null || true

    cd dist
    zip -qr /tmp/amplify-deploy.zip .
    BUCKET=$($AWS s3 ls | grep platform-agent-staging | awk '{print $3}' | head -1)
    $AWS s3 cp /tmp/amplify-deploy.zip "s3://$BUCKET/deploy.zip" --no-progress
    APP_ID=$($AWS amplify list-apps \
        --query 'apps[?contains(name,`platform-agent`)].appId' --output text)
    $AWS amplify start-deployment \
        --app-id "$APP_ID" --branch-name main \
        --source-url "s3://$BUCKET/deploy.zip" > /dev/null
    rm -f /tmp/amplify-deploy.zip
    cd "$PROJECT_DIR"
    echo "Frontend deployed to: $AMPLIFY_URL"
else
    echo "WARNING: npm not found or Amplify not configured. Skipping frontend deploy."
fi

else
    echo ""
    echo "--- Skipping Terraform/AgentCore (not in --services) ---"
fi  # DO_TERRAFORM

# ---------------------------------------------------------------------------
# Done
# ---------------------------------------------------------------------------
echo ""
echo "=== Bootstrap complete ==="
echo ""
echo "Services provisioned: $SERVICES"
if [[ "$DO_RDS" == "true" && -n "${DB_ENDPOINT:-}" ]]; then
    echo "PostgreSQL (RDS):  $DB_ENDPOINT:$DB_PORT"
fi
if [[ "$DO_REDSHIFT" == "true" ]]; then
    echo "Redshift:          ${RS_ENDPOINT:-PENDING}:${RS_PORT:-5439}"
fi
if [[ "$DO_SNOWFLAKE" == "true" && -n "${SF_ACCOUNT:-}" ]]; then
    echo "Snowflake:         $SF_ACCOUNT ($SF_DATABASE.$SF_SCHEMA)"
fi
if [[ "$DO_TERRAFORM" == "true" ]]; then
    echo "AgentCore Runtime: ${RUNTIME_ARN:-NOT DEPLOYED}"
    echo "React Frontend:    ${AMPLIFY_URL:-NOT DEPLOYED}"
fi
echo "Config files:      .env"
echo ""
echo "Next steps:"
echo "  source .env"
if [[ "$DO_TERRAFORM" == "true" ]]; then
    echo "  Open: ${AMPLIFY_URL:-https://your-amplify-url}"
else
    echo "  uv run streamlit run streamlit_app/app.py --server.port 8501"
fi
