#!/bin/bash
# Run this to terminate the instance and delete resources when done testing
# Prevents ongoing charges

REGION="ap-south-1"
INSTANCE_NAME="store-intelligence-test"

# Get instance ID by name tag
INSTANCE_ID=$(aws ec2 describe-instances \
  --filters "Name=tag:Name,Values=${INSTANCE_NAME}" "Name=instance-state-name,Values=running,stopped" \
  --region $REGION \
  --query 'Reservations[0].Instances[0].InstanceId' \
  --output text)

if [ "$INSTANCE_ID" == "None" ] || [ -z "$INSTANCE_ID" ]; then
  echo "No instance found with name: $INSTANCE_NAME"
  exit 0
fi

echo "Terminating instance: $INSTANCE_ID"
aws ec2 terminate-instances \
  --instance-ids $INSTANCE_ID \
  --region $REGION

echo "Deleting key pair..."
aws ec2 delete-key-pair \
  --key-name store-intelligence-key \
  --region $REGION
rm -f ~/.ssh/store-intelligence-key.pem

echo "Done. Instance terminated. No further charges."
echo "Note: Security group will auto-delete once instance is terminated."
