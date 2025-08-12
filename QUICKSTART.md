# Quick Start Guide

## 🚀 5-Minute Setup

### Prerequisites
- AWS Account
- AWS CLI configured (`aws configure`)
- Python 3.11+
- Git

### Step 1: Clone and Setup
```bash
git clone https://github.com/yourusername/weather-api-aggregator.git
cd weather-api-aggregator
make install
```

### Step 2: Get Free API Keys

Sign up for free accounts and get API keys:

1. **OpenWeatherMap**: https://openweathermap.org/api
2. **WeatherAPI**: https://www.weatherapi.com/
3. **Visual Crossing**: https://www.visualcrossing.com/
4. **Tomorrow.io**: https://www.tomorrow.io/
5. **Open-Meteo**: No key needed!

### Step 3: Configure API Keys
```bash
cp config/api-keys.template.json config/api-keys.json
# Edit config/api-keys.json with your API keys
nano config/api-keys.json
```

### Step 4: Deploy to AWS
```bash
make deploy ENVIRONMENT=prod
```

### Step 5: Test Your API
```bash
# Get your API endpoint
make status

# Test the API
make test-api
```

## 📊 Monitor Your Deployment

```bash
# View logs
make logs-collector  # Weather collection logs
make logs-api       # API access logs

# Check metrics
make metrics

# View status
make status
```

## 🧪 Local Development

```bash
# Setup local environment
make local-setup

# Start local API
make local-start

# Test locally
make local-test
```

## 🛠️ Common Commands

| Command | Description |
|---------|-------------|
| `make deploy` | Deploy to AWS |
| `make test` | Run tests |
| `make status` | Check deployment status |
| `make logs-collector` | View collector logs |
| `make logs-api` | View API logs |
| `make clean` | Clean build files |
| `make destroy` | Remove AWS resources |

## 📝 API Endpoints

After deployment, your API will be available at:
```
https://YOUR-API-ID.execute-api.us-east-1.amazonaws.com/prod
```

- `GET /health` - Health check
- `GET /weather/current` - Current weather
- `GET /weather/history?hours=24` - Historical data
- `GET /weather/sources` - Data sources info

## 🆘 Need Help?

- Check [Troubleshooting Guide](docs/TROUBLESHOOTING.md)
- Review [API Documentation](docs/API.md)
- Open an issue on GitHub

## 💰 Cost Estimate

- **Monthly cost**: ~$5-10 for moderate usage
- **Free tier eligible**: Yes
- **Pay only for what you use**: Serverless architecture

---

**Ready to go!** Your weather API will start collecting data every 20 minutes. 🌤️
