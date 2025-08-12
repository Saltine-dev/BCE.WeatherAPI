#!/bin/bash

# Local Development Script for Weather API
# This script helps set up and run the Weather API locally using SAM CLI

set -e

# Configuration
AWS_REGION=${AWS_REGION:-us-east-1}
ENVIRONMENT="local"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
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

print_command() {
    echo -e "${BLUE}[CMD]${NC} $1"
}

check_dependencies() {
    print_info "Checking dependencies..."
    
    # Check for Python
    if ! command -v python3 &> /dev/null; then
        print_error "Python 3 is not installed. Please install it first."
        exit 1
    fi
    
    # Check for AWS CLI
    if ! command -v aws &> /dev/null; then
        print_error "AWS CLI is not installed. Please install it first."
        exit 1
    fi
    
    # Check for SAM CLI
    if ! command -v sam &> /dev/null; then
        print_error "SAM CLI is not installed. Please install it first."
        print_info "Install with: pip install aws-sam-cli"
        exit 1
    fi
    
    # Check for Docker
    if ! command -v docker &> /dev/null; then
        print_error "Docker is not installed. Please install it first."
        exit 1
    fi
    
    # Check if Docker is running
    if ! docker info &> /dev/null; then
        print_error "Docker is not running. Please start Docker first."
        exit 1
    fi
    
    print_info "All dependencies are satisfied."
}

setup_local_dynamodb() {
    print_info "Setting up local DynamoDB..."
    
    # Check if DynamoDB Local is already running
    if docker ps | grep -q dynamodb-local; then
        print_info "DynamoDB Local is already running."
    else
        print_info "Starting DynamoDB Local..."
        docker run -d \
            --name dynamodb-local \
            -p 8000:8000 \
            amazon/dynamodb-local \
            -jar DynamoDBLocal.jar \
            -sharedDb \
            -dbPath /data
        
        # Wait for DynamoDB to start
        sleep 3
        
        # Create table
        print_info "Creating DynamoDB table..."
        aws dynamodb create-table \
            --table-name weather-aggregator-local-weather-data \
            --attribute-definitions \
                AttributeName=location,AttributeType=S \
                AttributeName=timestamp,AttributeType=S \
            --key-schema \
                AttributeName=location,KeyType=HASH \
                AttributeName=timestamp,KeyType=RANGE \
            --billing-mode PAY_PER_REQUEST \
            --endpoint-url http://localhost:8000 \
            --region "${AWS_REGION}" \
            2>/dev/null || print_warning "Table already exists"
    fi
}

create_env_file() {
    print_info "Creating environment file..."
    
    cat > .env.local <<EOF
# Local Development Environment Variables
DYNAMODB_TABLE_NAME=weather-aggregator-local-weather-data
DYNAMODB_ENDPOINT=http://host.docker.internal:8000
SECRET_MANAGER_ARN=arn:aws:secretsmanager:${AWS_REGION}:123456789012:secret:weather-api-keys
LOCATION=lewisville-tx
LATITUDE=33.0462
LONGITUDE=-96.9942
ENVIRONMENT=local
LOG_LEVEL=DEBUG
CORS_ORIGIN=*
AWS_REGION=${AWS_REGION}
EOF
    
    print_info "Environment file created: .env.local"
}

create_sam_template() {
    print_info "Creating SAM template for local development..."
    
    cat > template-local.yaml <<'EOF'
AWSTemplateFormatVersion: '2010-09-09'
Transform: AWS::Serverless-2016-10-31
Description: Local development SAM template for Weather API

Globals:
  Function:
    Runtime: python3.11
    Timeout: 30
    MemorySize: 256
    Environment:
      Variables:
        DYNAMODB_TABLE_NAME: weather-aggregator-local-weather-data
        DYNAMODB_ENDPOINT: http://host.docker.internal:8000
        LOCATION: lewisville-tx
        LATITUDE: '33.0462'
        LONGITUDE: '-96.9942'
        ENVIRONMENT: local
        LOG_LEVEL: DEBUG

Resources:
  WeatherCollectorFunction:
    Type: AWS::Serverless::Function
    Properties:
      CodeUri: src/lambdas/weather_collector/
      Handler: handler.lambda_handler
      Events:
        Schedule:
          Type: Schedule
          Properties:
            Schedule: rate(20 minutes)

  WeatherAPIFunction:
    Type: AWS::Serverless::Function
    Properties:
      CodeUri: src/lambdas/weather_api/
      Handler: handler.lambda_handler
      Events:
        CurrentWeather:
          Type: Api
          Properties:
            Path: /weather/current
            Method: GET
        HistoryWeather:
          Type: Api
          Properties:
            Path: /weather/history
            Method: GET
        Sources:
          Type: Api
          Properties:
            Path: /weather/sources
            Method: GET
        Health:
          Type: Api
          Properties:
            Path: /health
            Method: GET

Outputs:
  ApiEndpoint:
    Description: API Gateway endpoint URL for local development
    Value: !Sub 'http://localhost:3000'
EOF
    
    print_info "SAM template created: template-local.yaml"
}

create_api_keys_template() {
    print_info "Creating API keys template..."
    
    if [ ! -f "config/api-keys.json" ]; then
        mkdir -p config
        cat > config/api-keys.json <<'EOF'
{
  "openweathermap": "YOUR_OPENWEATHERMAP_API_KEY",
  "weatherapi": "YOUR_WEATHERAPI_KEY",
  "visualcrossing": "YOUR_VISUALCROSSING_KEY",
  "tomorrow_io": "YOUR_TOMORROW_IO_KEY"
}
EOF
        print_warning "Created config/api-keys.json template. Please update with your actual API keys."
    else
        print_info "config/api-keys.json already exists."
    fi
}

build_functions() {
    print_info "Building Lambda functions..."
    
    print_command "sam build --template template-local.yaml"
    sam build --template template-local.yaml
    
    print_info "Build completed successfully."
}

start_api() {
    print_info "Starting local API..."
    
    print_warning "Make sure to update config/api-keys.json with your actual API keys!"
    echo ""
    print_info "Starting SAM local API on http://localhost:3000"
    print_info "Press Ctrl+C to stop the API"
    echo ""
    
    print_command "sam local start-api --env-vars .env.local --docker-network bridge"
    sam local start-api --env-vars .env.local --docker-network bridge
}

invoke_collector() {
    print_info "Invoking Weather Collector function locally..."
    
    print_command "sam local invoke WeatherCollectorFunction --env-vars .env.local"
    sam local invoke WeatherCollectorFunction --env-vars .env.local
}

test_endpoints() {
    print_info "Testing API endpoints..."
    
    API_URL="http://localhost:3000"
    
    echo ""
    print_info "Testing health endpoint..."
    curl -s "${API_URL}/health" | python3 -m json.tool
    
    echo ""
    print_info "Testing sources endpoint..."
    curl -s "${API_URL}/weather/sources" | python3 -m json.tool
    
    echo ""
    print_info "Testing current weather endpoint..."
    curl -s "${API_URL}/weather/current" | python3 -m json.tool
    
    echo ""
    print_info "Testing history endpoint..."
    curl -s "${API_URL}/weather/history?hours=24" | python3 -m json.tool
}

stop_services() {
    print_info "Stopping local services..."
    
    # Stop DynamoDB Local
    if docker ps | grep -q dynamodb-local; then
        print_info "Stopping DynamoDB Local..."
        docker stop dynamodb-local
        docker rm dynamodb-local
    fi
    
    print_info "Services stopped."
}

show_help() {
    echo "Weather API Local Development Script"
    echo ""
    echo "Usage: $0 [command]"
    echo ""
    echo "Commands:"
    echo "  setup       Set up local development environment"
    echo "  start       Start local API server"
    echo "  build       Build Lambda functions"
    echo "  invoke      Invoke Weather Collector function"
    echo "  test        Test API endpoints"
    echo "  stop        Stop local services"
    echo "  help        Show this help message"
    echo ""
    echo "Examples:"
    echo "  $0 setup    # Set up local environment"
    echo "  $0 start    # Start API server"
    echo "  $0 test     # Test endpoints"
}

# Main execution
case "${1:-setup}" in
    setup)
        print_info "Setting up local development environment..."
        check_dependencies
        setup_local_dynamodb
        create_env_file
        create_sam_template
        create_api_keys_template
        build_functions
        print_info "Setup complete! Run '$0 start' to start the API."
        ;;
    start)
        check_dependencies
        setup_local_dynamodb
        start_api
        ;;
    build)
        check_dependencies
        build_functions
        ;;
    invoke)
        check_dependencies
        setup_local_dynamodb
        invoke_collector
        ;;
    test)
        test_endpoints
        ;;
    stop)
        stop_services
        ;;
    help)
        show_help
        ;;
    *)
        print_error "Unknown command: $1"
        show_help
        exit 1
        ;;
esac
