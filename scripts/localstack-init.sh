#!/bin/bash
set -e

echo "Initializing LocalStack resources..."

# Create Kinesis stream
awslocal kinesis create-stream \
    --stream-name secure-api-events \
    --shard-count 1

# Create S3 bucket for media
awslocal s3 mb s3://omnichannel-media

# Verify resources
echo "Kinesis streams:"
awslocal kinesis list-streams

echo "S3 buckets:"
awslocal s3 ls

echo "LocalStack initialization complete!"
