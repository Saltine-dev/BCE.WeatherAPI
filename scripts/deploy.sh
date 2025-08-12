#!/bin/bash

# Weather API Deployment Script
# This script packages and deploys the Weather API to AWS

set -e

# Configuration
ENVIRONMENT=${1:-dev}
AWS_REGION=${AWS_REGION:-us-east-1}
STACK_NAME="weather-aggregator-${ENVIRONMENT}"
API_NAME="weather-aggregator"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Functions
print_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

check_dependencies() {
    print_info "Checking dependencies..."
    
    # Check for AWS CLI
    if ! command -v aws &> /dev/null; then
        print_error "AWS CLI is not installed. Please install it first."
        exit 1
    fi
    
    # Check for Python
    if ! command -v python3 &> /dev/null; then
        print_error "Python 3 is not installed. Please install it first."
        exit 1
    fi
    
    # Check for zip
    if ! command -v zip &> /dev/null; then
        print_error "zip is not installed. Please install it first."
        exit 1
    fi
    
    # Check AWS credentials
    if ! aws sts get-caller-identity &> /dev/null; then
        print_error "AWS credentials are not configured. Please configure them first."
        exit 1
    fi
    
    print_info "All dependencies are satisfied."
}

create_deployment_bucket() {
    print_info "Creating deployment bucket..."
    
    ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
    BUCKET_NAME="${API_NAME}-${ENVIRONMENT}-deployment-${ACCOUNT_ID}"
    
    if aws s3 ls "s3://${BUCKET_NAME}" 2>/dev/null; then
        print_info "Deployment bucket already exists: ${BUCKET_NAME}"
    else
        print_info "Creating deployment bucket: ${BUCKET_NAME}"
        aws s3 mb "s3://${BUCKET_NAME}" --region "${AWS_REGION}"
        aws s3api put-bucket-versioning \
            --bucket "${BUCKET_NAME}" \
            --versioning-configuration Status=Enabled
        aws s3api put-public-access-block \
            --bucket "${BUCKET_NAME}" \
            --public-access-block-configuration \
            "BlockPublicAcls=true,IgnorePublicAcls=true,BlockPublicPolicy=true,RestrictPublicBuckets=true"
    fi
    
    echo "${BUCKET_NAME}"
}

package_lambda_functions() {
    print_info "Packaging Lambda functions..."
    
    # Create build directory
    rm -rf build
    mkdir -p build/lambdas
    
    # Package Weather Collector Lambda
    print_info "Packaging Weather Collector Lambda..."
    cd src/lambdas/weather_collector
    cp -r . ../../../build/weather_collector_temp
    cd ../../../build/weather_collector_temp
    pip install -r requirements.txt -t . --quiet
    zip -r ../lambdas/weather-collector.zip . -x "*.pyc" -x "__pycache__/*" > /dev/null
    cd ../..
    rm -rf build/weather_collector_temp
    
    # Package Weather API Lambda
    print_info "Packaging Weather API Lambda..."
    cd src/lambdas/weather_api
    cp -r . ../../../build/weather_api_temp
    cd ../../../build/weather_api_temp
    pip install -r requirements.txt -t . --quiet
    zip -r ../lambdas/weather-api.zip . -x "*.pyc" -x "__pycache__/*" > /dev/null
    cd ../..
    rm -rf build/weather_api_temp
    
    # Create common dependencies layer
    print_info "Creating common dependencies layer..."
    mkdir -p build/layers/python
    pip install requests boto3 -t build/layers/python/ --quiet
    cd build/layers
    zip -r ../common-dependencies.zip python -x "*.pyc" -x "__pycache__/*" > /dev/null
    cd ../..
    
    print_info "Lambda functions packaged successfully."
}

upload_to_s3() {
    local bucket_name=$1
    print_info "Uploading packages to S3..."
    
    TIMESTAMP=$(date +%Y%m%d%H%M%S)
    
    # Upload Lambda packages
    aws s3 cp build/lambdas/weather-collector.zip \
        "s3://${bucket_name}/lambdas/weather-collector-${TIMESTAMP}.zip" \
        --region "${AWS_REGION}"
    aws s3 cp build/lambdas/weather-api.zip \
        "s3://${bucket_name}/lambdas/weather-api-${TIMESTAMP}.zip" \
        --region "${AWS_REGION}"
    
    # Upload layer
    aws s3 cp build/common-dependencies.zip \
        "s3://${bucket_name}/layers/common-dependencies-${TIMESTAMP}.zip" \
        --region "${AWS_REGION}"
    
    # Create latest copies
    aws s3 cp "s3://${bucket_name}/lambdas/weather-collector-${TIMESTAMP}.zip" \
        "s3://${bucket_name}/lambdas/weather-collector.zip" \
        --region "${AWS_REGION}"
    aws s3 cp "s3://${bucket_name}/lambdas/weather-api-${TIMESTAMP}.zip" \
        "s3://${bucket_name}/lambdas/weather-api.zip" \
        --region "${AWS_REGION}"
    aws s3 cp "s3://${bucket_name}/layers/common-dependencies-${TIMESTAMP}.zip" \
        "s3://${bucket_name}/layers/common-dependencies.zip" \
        --region "${AWS_REGION}"
    
    print_info "Packages uploaded successfully."
}

deploy_cloudformation_stack() {
    local bucket_name=$1
    print_info "Deploying CloudFormation stack..."
    
    # Check if stack exists
    if aws cloudformation describe-stacks --stack-name "${STACK_NAME}" --region "${AWS_REGION}" 2>/dev/null; then
        STACK_ACTION="update-stack"
        WAIT_ACTION="stack-update-complete"
        print_info "Updating existing stack: ${STACK_NAME}"
    else
        STACK_ACTION="create-stack"
        WAIT_ACTION="stack-create-complete"
        print_info "Creating new stack: ${STACK_NAME}"
    fi
    
    # Deploy stack
    aws cloudformation ${STACK_ACTION} \
        --stack-name "${STACK_NAME}" \
        --template-body file://templates/weather-api-stack.yaml \
        --parameters \
            ParameterKey=Environment,ParameterValue="${ENVIRONMENT}" \
            ParameterKey=ApiName,ParameterValue="${API_NAME}" \
            ParameterKey=DataRetentionDays,ParameterValue=30 \
            ParameterKey=Location,ParameterValue=lewisville-tx \
            ParameterKey=Latitude,ParameterValue=33.0462 \
            ParameterKey=Longitude,ParameterValue=-96.9942 \
            ParameterKey=DeploymentBucketName,ParameterValue="${bucket_name}" \
            ParameterKey=CollectorPackageKey,ParameterValue=lambdas/weather-collector.zip \
            ParameterKey=ApiPackageKey,ParameterValue=lambdas/weather-api.zip \
            ParameterKey=UseCommonLayer,ParameterValue=true \
            ParameterKey=CommonLayerKey,ParameterValue=layers/common-dependencies.zip \
        --capabilities CAPABILITY_NAMED_IAM \
        --region "${AWS_REGION}" \
        || true
    
    # Wait for stack to complete
    print_info "Waiting for stack operation to complete..."
    if aws cloudformation wait ${WAIT_ACTION} --stack-name "${STACK_NAME}" --region "${AWS_REGION}"; then
        print_info "Stack operation completed successfully."
    else
        print_error "Stack operation failed or timed out."
        aws cloudformation describe-stack-events \
            --stack-name "${STACK_NAME}" \
            --query 'StackEvents[?ResourceStatus==`CREATE_FAILED` || ResourceStatus==`UPDATE_FAILED`].[LogicalResourceId,ResourceStatusReason]' \
            --output table \
            --region "${AWS_REGION}"
        exit 1
    fi
}

update_lambda_code() {
    local bucket_name=$1
    print_info "Updating Lambda function code..."
    
    # Get Lambda function names from stack outputs
    COLLECTOR_FUNCTION=$(aws cloudformation describe-stacks \
        --stack-name "${STACK_NAME}" \
        --query "Stacks[0].Outputs[?OutputKey=='WeatherCollectorFunctionArn'].OutputValue" \
        --output text \
        --region "${AWS_REGION}" | awk -F: '{print $NF}')
    
    API_FUNCTION=$(aws cloudformation describe-stacks \
        --stack-name "${STACK_NAME}" \
        --query "Stacks[0].Outputs[?OutputKey=='WeatherAPIFunctionArn'].OutputValue" \
        --output text \
        --region "${AWS_REGION}" | awk -F: '{print $NF}')
    
    # Update Lambda function code
    print_info "Updating Weather Collector Lambda function..."
    aws lambda update-function-code \
        --function-name "${COLLECTOR_FUNCTION}" \
        --s3-bucket "${bucket_name}" \
        --s3-key "lambdas/weather-collector.zip" \
        --publish \
        --region "${AWS_REGION}" > /dev/null
    
    print_info "Updating Weather API Lambda function..."
    aws lambda update-function-code \
        --function-name "${API_FUNCTION}" \
        --s3-bucket "${bucket_name}" \
        --s3-key "lambdas/weather-api.zip" \
        --publish \
        --region "${AWS_REGION}" > /dev/null
}

update_api_keys() {
    print_info "Updating API keys in Secrets Manager..."
    
    SECRET_ARN=$(aws cloudformation describe-stacks \
        --stack-name "${STACK_NAME}" \
        --query "Stacks[0].Outputs[?OutputKey=='SecretsManagerArn'].OutputValue" \
        --output text \
        --region "${AWS_REGION}")
    
    if [ -f "config/api-keys.json" ]; then
        print_info "Updating API keys from config/api-keys.json"
        aws secretsmanager update-secret \
            --secret-id "${SECRET_ARN}" \
            --secret-string file://config/api-keys.json \
            --region "${AWS_REGION}"
    else
        print_warning "config/api-keys.json not found. Please update API keys manually in AWS Secrets Manager."
        print_warning "Secret ARN: ${SECRET_ARN}"
    fi
}

display_outputs() {
    print_info "Deployment complete! Here are the stack outputs:"
    echo ""
    
    # Get and display stack outputs
    API_ENDPOINT=$(aws cloudformation describe-stacks \
        --stack-name "${STACK_NAME}" \
        --query "Stacks[0].Outputs[?OutputKey=='ApiEndpoint'].OutputValue" \
        --output text \
        --region "${AWS_REGION}")
    
    TABLE_NAME=$(aws cloudformation describe-stacks \
        --stack-name "${STACK_NAME}" \
        --query "Stacks[0].Outputs[?OutputKey=='DynamoDBTableName'].OutputValue" \
        --output text \
        --region "${AWS_REGION}")
    
    DASHBOARD_URL=$(aws cloudformation describe-stacks \
        --stack-name "${STACK_NAME}" \
        --query "Stacks[0].Outputs[?OutputKey=='DashboardURL'].OutputValue" \
        --output text \
        --region "${AWS_REGION}")
    
    echo "======================================"
    echo "Deployment Information"
    echo "======================================"
    echo "Environment: ${ENVIRONMENT}"
    echo "Stack Name: ${STACK_NAME}"
    echo "Region: ${AWS_REGION}"
    echo ""
    echo "API Endpoint: ${API_ENDPOINT}"
    echo "DynamoDB Table: ${TABLE_NAME}"
    echo "CloudWatch Dashboard: ${DASHBOARD_URL}"
    echo ""
    echo "API Endpoints:"
    echo "  - GET ${API_ENDPOINT}/weather/current"
    echo "  - GET ${API_ENDPOINT}/weather/history?hours=24"
    echo "  - GET ${API_ENDPOINT}/weather/sources"
    echo "  - GET ${API_ENDPOINT}/health"
    echo ""
    echo "Next Steps:"
    echo "1. Update API keys in AWS Secrets Manager (if not already done)"
    echo "2. Test the API endpoints"
    echo "3. Monitor the CloudWatch dashboard"
    echo "======================================"
}

# Main execution
main() {
    print_info "Starting Weather API deployment for environment: ${ENVIRONMENT}"
    
    check_dependencies
    BUCKET_NAME=$(create_deployment_bucket)
    package_lambda_functions
    upload_to_s3 "${BUCKET_NAME}"
    deploy_cloudformation_stack "${BUCKET_NAME}"
    update_lambda_code "${BUCKET_NAME}"
    update_api_keys
    display_outputs
    
    print_info "Deployment completed successfully!"
}

# Run main function
main
