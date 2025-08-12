# Troubleshooting Guide

## Common Issues and Solutions

### 1. Deployment Issues

#### CloudFormation Stack Creation Failed

**Error:** `Stack creation failed with CREATE_FAILED status`

**Solutions:**
1. Check IAM permissions - ensure your AWS user has necessary permissions
2. Verify S3 bucket name is unique (deployment bucket)
3. Check CloudWatch logs for detailed error messages
4. Ensure Lambda function code is properly packaged

```bash
# Check stack events
aws cloudformation describe-stack-events \
  --stack-name weather-aggregator-prod \
  --query 'StackEvents[?ResourceStatus==`CREATE_FAILED`]'

# Delete failed stack and retry
aws cloudformation delete-stack --stack-name weather-aggregator-prod
```

#### Lambda Function Not Found

**Error:** `Function not found: weather-aggregator-prod-collector`

**Solutions:**
1. Ensure CloudFormation stack creation completed successfully
2. Check the correct function name in stack outputs
3. Verify AWS region is correct

```bash
# List Lambda functions
aws lambda list-functions --query 'Functions[?contains(FunctionName, `weather`)]'

# Get function from stack outputs
aws cloudformation describe-stacks \
  --stack-name weather-aggregator-prod \
  --query 'Stacks[0].Outputs[?OutputKey==`WeatherCollectorFunctionArn`]'
```

### 2. API Issues

#### 404 Not Found - No Weather Data

**Error:** `{"error": "No weather data found"}`

**Causes:**
- Weather collector hasn't run yet
- All API calls failed
- DynamoDB table is empty

**Solutions:**
1. Wait for the first scheduled collection (up to 20 minutes)
2. Manually trigger the collector function
3. Check API keys are correctly configured

```bash
# Manually invoke collector
aws lambda invoke \
  --function-name weather-aggregator-prod-collector \
  --invocation-type Event \
  output.json

# Check DynamoDB for data
aws dynamodb scan \
  --table-name weather-aggregator-prod-weather-data \
  --limit 1
```

#### 500 Internal Server Error

**Error:** `{"error": "Internal server error"}`

**Solutions:**
1. Check CloudWatch logs for Lambda functions
2. Verify DynamoDB table exists and is accessible
3. Check IAM roles have proper permissions

```bash
# View Lambda logs
aws logs tail /aws/lambda/weather-aggregator-prod-api --follow

# Test DynamoDB access
aws dynamodb describe-table \
  --table-name weather-aggregator-prod-weather-data
```

#### CORS Errors

**Error:** `Access to fetch at 'api-url' from origin 'http://localhost:3000' has been blocked by CORS policy`

**Solutions:**
1. Ensure API Gateway CORS is configured
2. Check Lambda returns proper CORS headers
3. Verify OPTIONS method is configured

```javascript
// Proper CORS headers in Lambda response
{
  'Access-Control-Allow-Origin': '*',
  'Access-Control-Allow-Headers': 'Content-Type,X-Amz-Date,Authorization,X-Api-Key',
  'Access-Control-Allow-Methods': 'GET,OPTIONS'
}
```

### 3. Data Collection Issues

#### No Data from Weather APIs

**Symptoms:**
- Data quality score is 0
- Empty sources array
- No weather data in responses

**Solutions:**
1. Verify API keys in Secrets Manager
2. Check API rate limits haven't been exceeded
3. Test API keys manually

```bash
# Check secrets
aws secretsmanager get-secret-value \
  --secret-id weather-aggregator-prod-api-keys \
  --query SecretString

# Test OpenWeatherMap API
curl "https://api.openweathermap.org/data/2.5/weather?lat=33.0462&lon=-96.9942&appid=YOUR_KEY"

# Check Lambda environment variables
aws lambda get-function-configuration \
  --function-name weather-aggregator-prod-collector \
  --query 'Environment.Variables'
```

#### Incomplete Data / Low Quality Score

**Causes:**
- Some APIs failing
- Network timeouts
- Invalid API responses

**Solutions:**
1. Check individual API health
2. Review CloudWatch logs for specific API errors
3. Increase Lambda timeout if needed

```bash
# Search for API errors in logs
aws logs filter-log-events \
  --log-group-name /aws/lambda/weather-aggregator-prod-collector \
  --filter-pattern "ERROR"
```

### 4. Local Development Issues

#### Docker Not Running

**Error:** `Cannot connect to Docker daemon`

**Solutions:**
```bash
# Start Docker
sudo systemctl start docker  # Linux
open -a Docker  # macOS

# Verify Docker is running
docker ps
```

#### SAM Local API Not Starting

**Error:** `Error: Unable to find AWS SAM installation`

**Solutions:**
```bash
# Install SAM CLI
pip install aws-sam-cli

# Verify installation
sam --version

# Build before starting
sam build --template template-local.yaml
```

#### DynamoDB Local Connection Issues

**Error:** `Could not connect to the endpoint URL: "http://localhost:8000/"`

**Solutions:**
```bash
# Start DynamoDB Local
docker run -d -p 8000:8000 amazon/dynamodb-local

# Test connection
aws dynamodb list-tables --endpoint-url http://localhost:8000
```

### 5. Cost and Performance Issues

#### High AWS Costs

**Symptoms:**
- Monthly bill exceeds expectations
- High Lambda invocation count
- Large DynamoDB usage

**Solutions:**
1. Check EventBridge rule frequency
2. Verify DynamoDB TTL is enabled
3. Review CloudWatch log retention
4. Optimize Lambda memory allocation

```bash
# Check invocation metrics
aws cloudwatch get-metric-statistics \
  --namespace AWS/Lambda \
  --metric-name Invocations \
  --dimensions Name=FunctionName,Value=weather-aggregator-prod-collector \
  --start-time 2024-01-01T00:00:00Z \
  --end-time 2024-01-31T23:59:59Z \
  --period 86400 \
  --statistics Sum

# Verify TTL configuration
aws dynamodb describe-time-to-live \
  --table-name weather-aggregator-prod-weather-data
```

#### Slow API Response Times

**Causes:**
- Cold starts
- Inefficient DynamoDB queries
- Large response payloads

**Solutions:**
1. Enable Lambda reserved concurrency
2. Optimize DynamoDB queries with proper indexes
3. Implement caching with CloudFront
4. Reduce response payload size

```bash
# Set reserved concurrency
aws lambda put-function-concurrency \
  --function-name weather-aggregator-prod-api \
  --reserved-concurrent-executions 2
```

### 6. Security Issues

#### Secrets Manager Access Denied

**Error:** `User is not authorized to perform: secretsmanager:GetSecretValue`

**Solutions:**
1. Update IAM role policies
2. Verify secret ARN is correct
3. Check resource-based policies on secret

```bash
# Update Lambda role policy
aws iam attach-role-policy \
  --role-name weather-aggregator-prod-collector-role \
  --policy-arn arn:aws:iam::aws:policy/SecretsManagerReadWrite
```

#### API Gateway Authorization

**Note:** Currently, the API is open. To add security:

1. Implement API keys
2. Add AWS IAM authorization
3. Use Lambda authorizers

```yaml
# CloudFormation template modification for API keys
ApiKey:
  Type: AWS::ApiGateway::ApiKey
  Properties:
    Name: weather-api-key
    Enabled: true

UsagePlan:
  Type: AWS::ApiGateway::UsagePlan
  Properties:
    ApiStages:
      - ApiId: !Ref WeatherAPI
        Stage: !Ref Environment
    Throttle:
      BurstLimit: 100
      RateLimit: 50
```

### 7. Monitoring and Alerting

#### CloudWatch Alarms Not Triggering

**Solutions:**
1. Verify alarm configuration
2. Check metric namespace and dimensions
3. Test alarm manually

```bash
# List alarms
aws cloudwatch describe-alarms \
  --alarm-name-prefix weather-aggregator

# Set alarm state for testing
aws cloudwatch set-alarm-state \
  --alarm-name weather-aggregator-prod-collector-errors \
  --state-value ALARM \
  --state-reason "Testing alarm"
```

#### Missing Metrics

**Solutions:**
1. Enable detailed monitoring
2. Check metric filters in CloudWatch Logs
3. Verify Lambda is publishing metrics

```bash
# Create custom metric
aws logs put-metric-filter \
  --log-group-name /aws/lambda/weather-aggregator-prod-collector \
  --filter-name DataQualityScore \
  --filter-pattern '[..., quality_score]' \
  --metric-transformations \
    metricName=DataQualityScore,metricNamespace=WeatherAPI,metricValue='$quality_score'
```

## Debug Commands

### Check System Status

```bash
#!/bin/bash
# System health check script

API_ENDPOINT="https://your-api.execute-api.us-east-1.amazonaws.com/prod"
STACK_NAME="weather-aggregator-prod"

echo "Checking API health..."
curl -s "$API_ENDPOINT/health" | jq .

echo "Checking Lambda functions..."
aws lambda list-functions --query "Functions[?contains(FunctionName, 'weather')].[FunctionName,State]" --output table

echo "Checking DynamoDB table..."
aws dynamodb describe-table --table-name "$STACK_NAME-weather-data" --query "Table.TableStatus"

echo "Checking recent invocations..."
aws cloudwatch get-metric-statistics \
  --namespace AWS/Lambda \
  --metric-name Invocations \
  --dimensions Name=FunctionName,Value="$STACK_NAME-collector" \
  --start-time $(date -u -d '1 hour ago' +%Y-%m-%dT%H:%M:%S) \
  --end-time $(date -u +%Y-%m-%dT%H:%M:%S) \
  --period 300 \
  --statistics Sum
```

### View Recent Logs

```bash
# Collector function logs
aws logs tail /aws/lambda/weather-aggregator-prod-collector --follow

# API function logs
aws logs tail /aws/lambda/weather-aggregator-prod-api --follow

# Search for errors
aws logs filter-log-events \
  --log-group-name /aws/lambda/weather-aggregator-prod-collector \
  --start-time $(date -d '1 hour ago' +%s)000 \
  --filter-pattern ERROR
```

## Getting Help

1. **Check logs first** - Most issues are evident in CloudWatch logs
2. **Review configuration** - Ensure all environment variables and parameters are correct
3. **Test manually** - Use AWS CLI to test individual components
4. **Open an issue** - Include error messages, logs, and steps to reproduce

## Useful Resources

- [AWS Lambda Troubleshooting](https://docs.aws.amazon.com/lambda/latest/dg/troubleshooting.html)
- [API Gateway Troubleshooting](https://docs.aws.amazon.com/apigateway/latest/developerguide/troubleshooting.html)
- [DynamoDB Best Practices](https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/best-practices.html)
- [CloudFormation Troubleshooting](https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/troubleshooting.html)
