#!/bin/bash
# Download WebArena Docker images
# Expected total: ~100 GB, takes 3-8 hours depending on bandwidth
# Run this and leave it overnight

set -e
DIR="$HOME/projects/webarena/docker_images"
mkdir -p "$DIR"
cd "$DIR"

echo "=== WebArena Docker Image Download ==="
echo "Expected: ~100GB total, 3-8 hours"
echo ""

# Forum (Reddit clone) - 49.7GB uncompressed
echo "[1/2] Downloading forum (postmill)..."
if [ ! -f postmill-populated-exposed-withimg.tar ]; then
    aria2c -x 16 -s 16 --file-allocation=none \
        "http://metis.lti.cs.cmu.edu/webarena-images/postmill-populated-exposed-withimg.tar" \
        -o postmill-populated-exposed-withimg.tar \
        --summary-interval=60
else
    echo "Already downloaded"
fi

# Shopping (Magento) - 62.9GB uncompressed  
echo "[2/2] Downloading shopping..."
if [ ! -f shopping_final_0712.tar ]; then
    aria2c -x 16 -s 16 --file-allocation=none \
        "http://metis.lti.cs.cmu.edu/webarena-images/shopping_final_0712.tar" \
        -o shopping_final_0712.tar \
        --summary-interval=60
else
    echo "Already downloaded"
fi

echo ""
echo "=== Downloads complete ==="
echo "Now load into Docker:"
echo "  docker load --input $DIR/postmill-populated-exposed-withimg.tar"
echo "  docker load --input $DIR/shopping_final_0712.tar"
echo ""
echo "Or pull from Docker Hub (may be faster):"
echo "  docker pull webarenaimages/postmill-populated-exposed-withimg"
echo "  docker pull webarenaimages/shopping_final_0712"
echo ""
echo "Then run: ~/projects/unbrowse-webarena-bench/setup_and_run.sh"
