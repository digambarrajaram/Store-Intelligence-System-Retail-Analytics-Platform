#!/bin/bash
# AWS CLI commands to launch a test server for Store Intelligence System
# Run these from your local machine (AWS CLI must be configured)
# Prerequisites: aws configure (with your Access Key + Secret Key)

set -e

# ─── CONFIGURATION ────────────────────────────────────────────────────────────
INSTANCE_TYPE="t3.xlarge"        # 4 vCPU, 16GB RAM — minimum for all 8 services
REGION="ap-south-1"              # Mumbai — closest to Bangalore
AMI_ID="ami-0f58b397bc5c1f2e8"  # Ubuntu 22.04 LTS (ap-south-1) — free tier eligible base
KEY_NAME="store-intelligence-key"
SG_NAME="store-intelligence-sg"
INSTANCE_NAME="store-intelligence-test"
VOLUME_SIZE="30"                 # GB — YOLOv8 model + Docker images need ~15GB

# ─── STEP 1: Create SSH key pair ──────────────────────────────────────────────
echo "=== Creating key pair ==="
aws ec2 create-key-pair \
  --key-name $KEY_NAME \
  --region $REGION \
  --query 'KeyMaterial' \
  --output text > ~/.ssh/${KEY_NAME}.pem

chmod 400 ~/.ssh/${KEY_NAME}.pem
echo "Key saved to ~/.ssh/${KEY_NAME}.pem"

# ─── STEP 2: Create security group ───────────────────────────────────────────
echo "=== Creating security group ==="
SG_ID=$(aws ec2 create-security-group \
  --group-name $SG_NAME \
  --description "Store Intelligence System - Test Server" \
  --region $REGION \
  --query 'GroupId' \
  --output text)

echo "Security Group ID: $SG_ID"
# Strip any hidden Windows carriage returns (\r) from the variable
SG_ID=$(echo "$SG_ID" | tr -d '\r')


# Allow SSH
aws ec2 authorize-security-group-ingress \
  --group-id $SG_ID \
  --protocol tcp --port 22 --cidr 0.0.0.0/0 \
  --region $REGION

# Allow API (FastAPI)
aws ec2 authorize-security-group-ingress \
  --group-id $SG_ID \
  --protocol tcp --port 8000 --cidr 0.0.0.0/0 \
  --region $REGION

# Allow Dashboard (React/nginx)
aws ec2 authorize-security-group-ingress \
  --group-id $SG_ID \
  --protocol tcp --port 3000 --cidr 0.0.0.0/0 \
  --region $REGION

# Allow Grafana
aws ec2 authorize-security-group-ingress \
  --group-id $SG_ID \
  --protocol tcp --port 3001 --cidr 0.0.0.0/0 \
  --region $REGION

# Allow Prometheus
aws ec2 authorize-security-group-ingress \
  --group-id $SG_ID \
  --protocol tcp --port 9090 --cidr 0.0.0.0/0 \
  --region $REGION

# Allow Worker metrics
aws ec2 authorize-security-group-ingress \
  --group-id $SG_ID \
  --protocol tcp --port 8001 --cidr 0.0.0.0/0 \
  --region $REGION

echo "Security group rules added"

# ─── STEP 3: Create user-data script (auto-installs Docker on boot) ───────────
cat > /tmp/userdata.sh << 'USERDATA'
#!/bin/bash
apt-get update -y
apt-get install -y docker.io docker-compose-plugin git curl

# Start Docker
systemctl start docker
systemctl enable docker

# Add ubuntu user to docker group (no sudo needed)
usermod -aG docker ubuntu

# Install docker compose v2
mkdir -p /usr/local/lib/docker/cli-plugins
curl -SL https://github.com/docker/compose/releases/download/v2.24.0/docker-compose-linux-x86_64 \
  -o /usr/local/lib/docker/cli-plugins/docker-compose
chmod +x /usr/local/lib/docker/cli-plugins/docker-compose

echo "Docker setup complete" > /home/ubuntu/setup.log
USERDATA

# ─── STEP 4: Launch EC2 instance ─────────────────────────────────────────────
echo "=== Launching EC2 instance ==="
INSTANCE_ID=$(aws ec2 run-instances \
  --image-id $AMI_ID \
  --instance-type $INSTANCE_TYPE \
  --key-name $KEY_NAME \
  --security-group-ids $SG_ID \
  --block-device-mappings "[{\"DeviceName\":\"/dev/sda1\",\"Ebs\":{\"VolumeSize\":${VOLUME_SIZE},\"VolumeType\":\"gp3\"}}]" \
  --user-data file:///tmp/userdata.sh \
  --tag-specifications "ResourceType=instance,Tags=[{Key=Name,Value=${INSTANCE_NAME}}]" \
  --region $REGION \
  --query 'Instances[0].InstanceId' \
  --output text)

echo "Instance launched: $INSTANCE_ID"

# ─── STEP 5: Wait for instance to be running ─────────────────────────────────
echo "=== Waiting for instance to start (60-90 seconds) ==="
aws ec2 wait instance-running \
  --instance-ids $INSTANCE_ID \
  --region $REGION

# ─── STEP 6: Get public IP ───────────────────────────────────────────────────
PUBLIC_IP=$(aws ec2 describe-instances \
  --instance-ids $INSTANCE_ID \
  --region $REGION \
  --query 'Reservations[0].Instances[0].PublicIpAddress' \
  --output text)

echo ""
echo "======================================================"
echo "  Instance ready!"
echo "  Instance ID : $INSTANCE_ID"
echo "  Public IP   : $PUBLIC_IP"
echo "  Region      : $REGION"
echo "======================================================"
echo ""
echo "SSH command:"
echo "  ssh -i ~/.ssh/${KEY_NAME}.pem ubuntu@${PUBLIC_IP}"
echo ""
echo "Wait 2 minutes for Docker to finish installing, then:"
echo "  ssh -i ~/.ssh/${KEY_NAME}.pem ubuntu@${PUBLIC_IP}"
echo "  git clone https://github.com/YOUR_USERNAME/store-intelligence-system.git"
echo "  cd store-intelligence-system"
echo "  cp .env.example .env"
echo "  mkdir -p videos"
echo "  docker compose pull"
echo "  docker compose up -d"
echo ""
echo "Access URLs (after docker compose up):"
echo "  API        : http://${PUBLIC_IP}:8000/health"
echo "  Dashboard  : http://${PUBLIC_IP}:3000"
echo "  Grafana    : http://${PUBLIC_IP}:3001"
echo "  Prometheus : http://${PUBLIC_IP}:9090"
echo ""
echo "To STOP the instance (save money):"
echo "  aws ec2 stop-instances --instance-ids $INSTANCE_ID --region $REGION"
echo ""
echo "To TERMINATE (delete permanently):"
echo "  aws ec2 terminate-instances --instance-ids $INSTANCE_ID --region $REGION"
