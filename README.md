# WAAS - Weather API Aggregation System

A comprehensive serverless weather API that aggregates data from multiple free weather APIs, stores it in AWS DynamoDB, and serves it through a unified REST API endpoint. Built with AWS Lambda, API Gateway, and automated CI/CD using GitHub Actions.

## 🌟 Features

- **Multi-Source Data Aggregation**: Collects weather data from 5+ free weather APIs
- **Serverless Architecture**: Built on AWS Lambda for cost-effectiveness and scalability
- **Automated Data Collection**: Scheduled collection every 20 minutes via EventBridge
- **RESTful API**: Clean API endpoints for current and historical weather data
- **Data Quality Scoring**: Automatic quality assessment of aggregated data
- **Cost-Optimized**: Designed to run under $10/month for moderate usage
- **CI/CD Pipeline**: Automated deployment via GitHub Actions
- **Infrastructure as Code**: Complete CloudFormation template included
- **Local Development**: SAM CLI support for local testing

## 📋 Table of Contents

- [Architecture](#architecture)
- [Prerequisites](#prerequisites)
- [Quick Start](#quick-start)
- [API Documentation](#api-documentation)
- [Local Development](#local-development)
- [Deployment](#deployment)
- [Configuration](#configuration)
- [Monitoring](#monitoring)
- [Cost Analysis](#cost-analysis)
- [Contributing](#contributing)

## 🏗️ Architecture

```mermaid
graph TD

  %% Personas
  U["Clients / Apps"]

  %% Data sources
  subgraph "Data Sources"
    OWM["OpenWeatherMap"]
    WA["WeatherAPI"]
    VC["Visual Crossing"]
    OM["Open-Meteo"]
    TIO["Tomorrow.io"]
  end

  %% Ingestion layer
  subgraph "Ingestion"
    EB["Amazon EventBridge\n(every 20 min)"]
    COL["Lambda: Weather Collector"]
    SM["AWS Secrets Manager\n(API keys)"]
  end

  %% Storage
  subgraph "Storage"
    DDB[("DynamoDB\n(weather data)")]
  end

  %% API layer
  subgraph "API"
    APIGW["API Gateway"]
    API["Lambda: Weather API"]
  end

  %% Observability
  subgraph "Observability"
    CW["CloudWatch\n(Logs • Alarms • Dashboard)"]
  end

  %% CI/CD
  subgraph "CI/CD"
    GH["GitHub Actions"]
    S3A["S3 (artifacts)"]
    CFN["CloudFormation\n(Stack)"]
  end

  %% Edges: data flow
  OWM --> COL
  WA  --> COL
  VC  --> COL
  OM  --> COL
  TIO --> COL
  EB  --> COL
  SM  --> COL
  COL --> DDB
  COL --> CW

  U --> APIGW --> API --> DDB
  API --> CW

  %% Edges: CI/CD provisioning
  GH --> S3A --> CFN
  CFN --> APIGW
  CFN --> API
  CFN --> COL
  CFN --> DDB
  CFN --> SM
  CFN --> CW
```

### Components

- **Lambda Collector**: Fetches data from weather APIs and stores in DynamoDB
- **Lambda API**: Serves aggregated weather data through REST endpoints
- **DynamoDB**: NoSQL database for time-series weather data
- **API Gateway**: REST API exposure with rate limiting
- **EventBridge**: Scheduled triggers for data collection
- **Secrets Manager**: Secure storage of API keys
- **CloudWatch**: Logging, monitoring, and dashboards

## 📦 Prerequisites

### Required

- AWS Account with appropriate permissions
- Python 3.11 or Node.js 18.x
- AWS CLI configured
- Git

### API Keys (Free Tier)

Sign up for free API keys from:

1. [OpenWeatherMap](https://openweathermap.org/api) - 1,000 calls/day
2. [WeatherAPI](https://www.weatherapi.com/) - 1M calls/month
3. [Visual Crossing](https://www.visualcrossing.com/) - 1,000 records/day
4. [Tomorrow.io](https://www.tomorrow.io/) - 500 calls/day
5. [Open-Meteo](https://open-meteo.com/) - No API key required

## 🚀 Quick Start (GitHub CI/CD deployment)

### 1) Fork/clone the repo

```bash
git clone https://github.com/yourusername/BCE.WeatherAPI.git
cd BCE.WeatherAPI
```

### 2) Configure GitHub Actions secrets (for CI/CD)

In GitHub → your repo → Settings → Secrets and variables → Actions → New repository secret:

- AWS_ACCESS_KEY_ID
- AWS_SECRET_ACCESS_KEY
- AWS_REGION = us-east-1
- AWS_ACCOUNT_ID = <your 12-digit account id>

Pushes to `main` deploy to prod; pushes to `develop` deploy to dev (see `.github/workflows/deploy.yml`).

### 3) Push to trigger deployment

```bash
git add -A
git commit -m "Initial publish"
git push -u origin main
```

The workflow will:
- Build and package Lambda functions and layer
- Upload artifacts to an S3 deployment bucket
- Create/Update the CloudFormation stack with required capabilities
- Handle `ROLLBACK_COMPLETE` by deleting/recreating the stack
- Run basic integration checks and print outputs

### 4) Add weather API provider keys in Secrets Manager

AWS Console → Secrets Manager → find secret like `weather-aggregator-prod-api-keys` → Edit → paste JSON (example):

```json
{
  "openweathermap": "YOUR_OPENWEATHERMAP_API_KEY",
  "weatherapi": "YOUR_WEATHERAPI_KEY",
  "visualcrossing": "YOUR_VISUALCROSSING_KEY",
  "tomorrow_io": "YOUR_TOMORROW_IO_KEY"
}
```

Alternatively (CLI) if you have `config/api-keys.json` locally:

```bash
aws secretsmanager update-secret \
  --secret-id weather-aggregator-prod-api-keys \
  --secret-string file://config/api-keys.json
```

### 5) Trigger the collector once (don’t wait 20 minutes)

```bash
aws lambda invoke \
  --function-name weather-aggregator-prod-collector \
  --invocation-type Event out.json
```

### 6) Verify

Get the API endpoint from CloudFormation stack outputs (key `ApiEndpoint`) and test:

```bash
curl <ApiEndpoint>/health
curl <ApiEndpoint>/weather/sources
curl <ApiEndpoint>/weather/current
curl <ApiEndpoint>/weather/history?hours=24
```

## 📚 API Documentation

### Base URL

```
https://your-api-id.execute-api.us-east-1.amazonaws.com/prod
```

### Endpoints

#### GET /health

Health check endpoint

**Response:**
```json
{
  "status": "healthy",
  "timestamp": "2024-01-15T12:00:00Z",
  "location": "lewisville-tx",
  "database": {
    "status": "connected",
    "table": "weather-aggregator-prod-weather-data"
  },
  "data": {
    "last_update": "2024-01-15T11:50:00Z",
    "is_fresh": true
  },
  "version": "1.0.0"
}
```

#### GET /weather/current

Get current weather conditions

**Response:**
```json
{
  "location": "lewisville-tx",
  "timestamp": "2024-01-15T12:00:00Z",
  "data_quality_score": 0.85,
  "sources": ["openweathermap", "weatherapi", "openmeteo"],
  "current_conditions": {
    "temperature": {
      "value": 25.5,
      "min": 24.0,
      "max": 27.0,
      "unit": "celsius"
    },
    "humidity": {
      "value": 65,
      "min": 60,
      "max": 70,
      "unit": "percent"
    },
    "pressure": {
      "value": 1013,
      "unit": "hPa"
    },
    "wind": {
      "speed": {
        "value": 3.5,
        "unit": "m/s"
      },
      "direction": {
        "value": 180,
        "unit": "degrees"
      }
    },
    "weather": "Partly cloudy"
  }
}
```

#### GET /weather/history?hours=24

Get historical weather data

**Parameters:**
- `hours` (optional): Number of hours of history (default: 24, max: 168)

**Response:**
```json
{
  "location": "lewisville-tx",
  "period": {
    "start": "2024-01-14T12:00:00Z",
    "end": "2024-01-15T12:00:00Z",
    "hours": 24
  },
  "data_points": 72,
  "statistics": {
    "temperature": {
      "avg": 23.5,
      "min": 18.0,
      "max": 28.0
    }
  },
  "history": [
    {
      "timestamp": "2024-01-15T12:00:00Z",
      "temperature": 25.5,
      "humidity": 65,
      "weather": "Partly cloudy"
    }
  ]
}
```

#### GET /weather/sources

Get information about data sources

**Response:**
```json
{
  "location": "lewisville-tx",
  "coordinates": {
    "latitude": 33.0462,
    "longitude": -96.9942
  },
  "available_sources": [
    {
      "name": "OpenWeatherMap",
      "id": "openweathermap",
      "description": "Current weather, temperature, humidity, pressure, wind",
      "update_frequency": "Every 20 minutes",
      "free_tier_limit": "1000 calls/day"
    }
  ],
  "aggregation_method": "Average values from all available sources",
  "update_schedule": "Every 20 minutes",
  "data_retention": "30 days"
}
```

## 💻 Local Development

Prerequisites: Python 3.11+, Docker, AWS CLI, SAM CLI.

### Setup

```bash
chmod +x scripts/local-dev.sh
./scripts/local-dev.sh setup
```

This will:
- Start DynamoDB Local in Docker
- Create a local table
- Generate `.env.local` and `template-local.yaml`
- Build functions with SAM

### Start locally and test

```bash
./scripts/local-dev.sh start   # starts API at http://localhost:3000
./scripts/local-dev.sh test    # calls all endpoints
./scripts/local-dev.sh invoke  # invokes the collector once
```

### Run tests

```bash
pytest tests/unit/ -v
export API_ENDPOINT=http://localhost:3000
pytest tests/integration/ -v
```

## 🚢 Deployment (details)

The GitHub Actions workflow `.github/workflows/deploy.yml` does the following on push:

- Run unit tests
- Validate the CloudFormation template
- Package Lambdas and layer
- Upload artifacts to S3 (creates bucket if needed)
- Create/Update the stack with `CAPABILITY_NAMED_IAM` and `CAPABILITY_AUTO_EXPAND`
- Auto-handle `ROLLBACK_COMPLETE` by deleting/recreating the stack
- Run integration tests and print stack outputs

Environments:
- `main` → prod
- `develop` → dev

## ⚙️ Configuration

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `DYNAMODB_TABLE_NAME` | DynamoDB table name | weather-data |
| `SECRET_MANAGER_ARN` | Secrets Manager ARN | - |
| `LOCATION` | Location identifier | lewisville-tx |
| `LATITUDE` | Location latitude | 33.0462 |
| `LONGITUDE` | Location longitude | -96.9942 |
| `CORS_ORIGIN` | CORS allowed origin | * |

### CloudFormation Parameters

| Parameter | Description | Default |
|-----------|-------------|---------|
| `Environment` | Deployment environment | prod |
| `ApiName` | API name | weather-aggregator |
| `DataRetentionDays` | Days to retain data | 30 |
| `Location` | Weather location | lewisville-tx |

## 📊 Monitoring

### CloudWatch Dashboard

Access the automatically created dashboard:

```
https://console.aws.amazon.com/cloudwatch/home?region=us-east-1#dashboards:name=weather-aggregator-prod-dashboard
```

### Metrics

- Lambda invocations and errors
- API Gateway requests and latency
- DynamoDB read/write capacity
- Data freshness monitoring

### Alarms

- Collector function errors
- API high error rate
- Data staleness (no updates for 30+ minutes)

## 💰 Cost Analysis

### Estimated Monthly Costs (Moderate Usage)

| Service | Usage | Cost |
|---------|-------|------|
| Lambda | 2,880 invocations @ 512MB | $0.50 |
| API Gateway | 10,000 requests | $0.04 |
| DynamoDB | On-demand, < 1GB storage | $1.50 |
| CloudWatch | Logs and metrics | $2.00 |
| Secrets Manager | 1 secret | $0.40 |
| **Total** | | **~$4.44/month** |

### Cost Optimization Tips

1. Use DynamoDB on-demand pricing for variable workloads
2. Set CloudWatch log retention to 7 days
3. Monitor Lambda memory allocation and optimize
4. Use caching to reduce API calls
5. Implement DynamoDB TTL for automatic cleanup

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit your changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

- Weather data provided by free tier APIs
- Built with AWS serverless services
- Inspired by the need for consolidated weather data

## 📞 Support

For issues, questions, or suggestions:
- Open an issue on GitHub
- Check the [API Documentation](docs/API.md)
- Review the [Troubleshooting Guide](docs/TROUBLESHOOTING.md)

---

**Made with ❤️ by a sleepless developer.**