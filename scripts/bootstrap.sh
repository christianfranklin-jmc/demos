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

# ---------------------------------------------------------------------------
# Step 7: Redshift Serverless
# ---------------------------------------------------------------------------
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
    # Use the same security group and subnets as RDS for network access
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

# Seed Northwinds into Redshift (if available and not already seeded)
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
        echo "  Then seed manually via the Streamlit app or CLI agent."
    fi
fi

# ---------------------------------------------------------------------------
# Step 8: Generate config files
# ---------------------------------------------------------------------------
echo ""
echo "--- Step 8: Generating config files ---"

# .env file
cat > "$PROJECT_DIR/.env" <<ENVEOF
# AWS Platform Agent — generated by bootstrap.sh
AWS_PROFILE=$AWS_PROFILE
AWS_DEFAULT_REGION=$REGION

# PostgreSQL (RDS) connection
DB_HOST=$DB_ENDPOINT
DB_PORT=$DB_PORT
DB_NAME=$DB_NAME
DB_USER=$DB_USER
DB_PASSWORD=$DB_PASSWORD
DB_DRIVER_TYPE=postgresql

# Redshift Serverless connection
RS_HOST=$RS_ENDPOINT
RS_PORT=${RS_PORT:-5439}
RS_DB_NAME=$RS_DB_NAME
RS_USER=$RS_ADMIN_USER
RS_PASSWORD=$RS_ADMIN_PASSWORD
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
# Step 9: Install Python dependencies
# ---------------------------------------------------------------------------
echo ""
echo "--- Step 9: Installing Python dependencies ---"
cd "$PROJECT_DIR"
if command -v uv &> /dev/null; then
    uv pip install -e ".[dev]" 2>&1 | tail -1
    uv pip install -e ".[redshift]" 2>&1 | tail -1
    echo "Python dependencies installed via uv (core + redshift)."
else
    echo "WARNING: uv not found. Install with: curl -LsSf https://astral.sh/uv/install.sh | sh"
    echo "Then run: uv pip install -e '.[dev]' && uv pip install -e '.[redshift]'"
fi

# ---------------------------------------------------------------------------
# Step 10: Verify dbt
# ---------------------------------------------------------------------------
echo ""
echo "--- Step 10: Verifying dbt project ---"
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
echo "PostgreSQL (RDS):  $DB_ENDPOINT:$DB_PORT"
echo "Redshift:          ${RS_ENDPOINT:-PENDING}:${RS_PORT:-5439}"
echo "Database:          $DB_NAME (PostgreSQL), $RS_DB_NAME (Redshift)"
echo "Config files:      .env, toolkit.conf, dbt_output/northwinds_dw/profiles.yml"
echo ""
echo "Next steps:"
echo "  source .env"
echo "  uv run python -m platform_agent --profile $AWS_PROFILE"
echo "  uv run streamlit run streamlit_app/app.py --server.port 8501"
echo ""
echo "To connect to Redshift in the agent:"
echo "  connect_to_database(host=RS_HOST, port=5439, database='dev', user='admin',"
echo "                      password=..., driver_type='redshift')"
