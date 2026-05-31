#!/bin/bash
set -e

API_BASE="http://localhost:8000"
CSV_FILE="Brigade_Bangalore_10_April_26 (1)bc6219c.csv"

echo "Starting demo..."
echo "Ingesting POS CSV..."
curl -s -X POST "${API_BASE}/api/v1/pos/ingest" -F "file=@${CSV_FILE}"
echo -e "\nPOS ingest completed."

# Define traffic levels: low, medium, high
declare -a levels=(
    "low:10:2:1:5"      # entries:exits:anomalies:dwell_seconds
    "medium:50:10:5:15"
    "high:120:20:10:30"
)

for level in "${levels[@]}"; do
    IFS=':' read -r name entries exits anomalies dwell <<< "$level"
    echo -e "\n=== Simulating $name traffic (entries=$entries, exits=$exits, anomalies=$anomalies, dwell=$dwell) ==="
    
    # Call simulate endpoint
    response=$(curl -s -X POST "${API_BASE}/api/v1/simulate" \
        -H "Content-Type: application/json" \
        -d "{\"entries\": $entries, \"exits\": $exits, \"anomalies\": $anomalies, \"dwell_seconds\": $dwell}")
    echo "Simulate response: $response"
    
    # Wait a moment for processing
    sleep 2
    
    # Get and display metrics
    echo -e "\n--- Metrics ---"
    curl -s "${API_BASE}/api/v1/metrics" | jq .
    
    # Get and display funnel
    echo -e "\n--- Funnel ---"
    curl -s "${API_BASE}/api/v1/funnel" | jq .
    
    echo -e "\nWaiting 5 seconds before next level..."
    sleep 5
done

echo -e "\nDemo completed."