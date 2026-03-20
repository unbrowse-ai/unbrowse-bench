#!/bin/bash
# WebArena setup + benchmark runner
# Waits for Docker images to pull, starts containers, runs benchmark

WORKDIR="$HOME/projects/unbrowse-webarena-bench"
cd "$WORKDIR"

echo "=== WebArena Benchmark Setup ==="
echo "Waiting for Docker images to finish pulling..."

# Wait for forum image
while true; do
    if docker images webarenaimages/postmill-populated-exposed-withimg 2>/dev/null | grep -q latest; then
        echo "[$(date +%H:%M:%S)] Forum image ready!"
        break
    fi
    SIZE=$(docker system df 2>/dev/null | grep Images | awk '{print $4}')
    echo "[$(date +%H:%M:%S)] Still pulling... Images total: $SIZE"
    sleep 60
done

# Start forum container
echo "Starting forum container..."
docker rm -f forum 2>/dev/null
docker run --name forum -p 9999:80 -d webarenaimages/postmill-populated-exposed-withimg
echo "Waiting 60s for forum to start..."
sleep 60

# Check forum
HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:9999 2>/dev/null)
echo "Forum HTTP status: $HTTP_CODE"

# Check if shopping is also ready
if docker images webarenaimages/shopping_final_0712 2>/dev/null | grep -q latest; then
    echo "Shopping image ready! Starting container..."
    docker rm -f shopping 2>/dev/null
    docker run --name shopping -p 7770:80 -d webarenaimages/shopping_final_0712
    sleep 60
    # Configure shopping
    docker exec shopping /var/www/magento2/bin/magento setup:store-config:set --base-url="http://localhost:7770"
    docker exec shopping mysql -u magentouser -pMyPassword magentodb -e 'UPDATE core_config_data SET value="http://localhost:7770/" WHERE path = "web/secure/base_url";'
    docker exec shopping /var/www/magento2/bin/magento cache:flush
    HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:7770 2>/dev/null)
    echo "Shopping HTTP status: $HTTP_CODE"
fi

# Run benchmark
echo ""
echo "=== Running Benchmark ==="
python3 "$WORKDIR/run_benchmark.py"

echo ""
echo "=== Done ==="
echo "Results at: $WORKDIR/results/"
