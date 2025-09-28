#!/bin/bash

# IoT Data Processing System Deployment Script
set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Configuration
STAGE=${1:-dev}
REGION="eu-north-1"

echo -e "${GREEN}🚀 Deploying IoT Data Processing System${NC}"
echo -e "${YELLOW}Stage: $STAGE${NC}"
echo -e "${YELLOW}Region: $REGION${NC}"

# Check prerequisites
echo -e "\n${YELLOW}Checking prerequisites...${NC}"

if ! command -v node &> /dev/null; then
    echo -e "${RED}❌ Node.js is not installed${NC}"
    exit 1
fi

if ! command -v python3 &> /dev/null; then
    echo -e "${RED}❌ Python 3 is not installed${NC}"
    exit 1
fi

if ! command -v aws &> /dev/null; then
    echo -e "${RED}❌ AWS CLI is not installed${NC}"
    exit 1
fi

if ! command -v serverless &> /dev/null; then
    echo -e "${RED}❌ Serverless Framework is not installed${NC}"
    echo -e "${YELLOW}Install it with: npm install -g serverless${NC}"
    exit 1
fi

echo -e "${GREEN}✅ Prerequisites check passed${NC}"

# Check AWS credentials
echo -e "\n${YELLOW}Checking AWS credentials...${NC}"
if ! aws sts get-caller-identity &> /dev/null; then
    echo -e "${RED}❌ AWS credentials not configured${NC}"
    echo -e "${YELLOW}Configure AWS credentials with: aws configure${NC}"
    exit 1
fi

ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
echo -e "${GREEN}✅ AWS Account ID: $ACCOUNT_ID${NC}"

# Install dependencies
echo -e "\n${YELLOW}Installing Node.js dependencies...${NC}"
npm install

echo -e "\n${YELLOW}Installing Python dependencies...${NC}"
pip3 install -r requirements.txt

# Validate serverless configuration
echo -e "\n${YELLOW}Validating serverless configuration...${NC}"
serverless print --stage $STAGE > /dev/null

# Check if MySQL secret exists
echo -e "\n${YELLOW}Checking MySQL secret...${NC}"
SECRET_ARN="arn:aws:secretsmanager:$REGION:$ACCOUNT_ID:secret:instagram-app-db-credentials"

if aws secretsmanager describe-secret --secret-id "instagram-app-db-credentials" --region $REGION &> /dev/null; then
    echo -e "${GREEN}✅ MySQL secret found${NC}"
else
    echo -e "${RED}❌ MySQL secret 'instagram-app-db-credentials' not found in $REGION${NC}"
    echo -e "${YELLOW}Please create the secret with the following keys:${NC}"
    echo -e "${YELLOW}  - DB_HOST${NC}"
    echo -e "${YELLOW}  - DB_USER${NC}"
    echo -e "${YELLOW}  - DB_PASSWORD${NC}"
    echo -e "${YELLOW}  - DB_NAME${NC}"
    echo -e "${YELLOW}  - DB_PORT (optional, defaults to 3306)${NC}"
    exit 1
fi

# Deploy
echo -e "\n${GREEN}🚀 Starting deployment to $STAGE...${NC}"
serverless deploy --stage $STAGE --verbose

# Get outputs
echo -e "\n${GREEN}📊 Deployment completed! Getting outputs...${NC}"
serverless info --stage $STAGE

# Display important URLs and information
echo -e "\n${GREEN}🎉 Deployment Summary${NC}"
echo -e "${GREEN}===================${NC}"
echo -e "${YELLOW}Stage:${NC} $STAGE"
echo -e "${YELLOW}Region:${NC} $REGION"
echo -e "${YELLOW}Account:${NC} $ACCOUNT_ID"

# Get the API Gateway URL
API_URL=$(aws cloudformation describe-stacks \
    --region $REGION \
    --stack-name iot-data-processing-system-$STAGE \
    --query 'Stacks[0].Outputs[?OutputKey==`HistoricalDataApiUrl`].OutputValue' \
    --output text 2>/dev/null || echo "Not found")

if [ "$API_URL" != "Not found" ]; then
    echo -e "${YELLOW}API URL:${NC} $API_URL"
    echo -e "\n${YELLOW}Available endpoints:${NC}"
    echo -e "  GET $API_URL/health"
    echo -e "  GET $API_URL/api/v1/sensors/historical"
    echo -e "  GET $API_URL/api/v1/sensors/status"
    echo -e "  GET $API_URL/docs (Swagger UI)"
fi

echo -e "\n${GREEN}✅ Deployment completed successfully!${NC}"
echo -e "${YELLOW}Monitor your functions in AWS Lambda console${NC}"
echo -e "${YELLOW}Monitor your queues in AWS SQS console${NC}"
echo -e "${YELLOW}Check CloudWatch logs for debugging${NC}"