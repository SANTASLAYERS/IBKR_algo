# Multi-Ticker Options Flow Monitor API

## Overview

The Multi-Ticker Options Flow Monitor API provides programmatic access to options flow data, trade analytics, and ML-based trading signal predictions for multiple stock tickers (SLV, GLD, CVNA, and others). This API allows you to access real-time and historical options trades, minute-by-minute price data, and delta divergence metrics calculated from the options flow.

## Base URL

```
https://your-server-address/api/v1
```

## Authentication

All API requests require authentication using an API key.

- **Header Authentication**: Include the API key in the request headers:
  ```
  X-API-Key: your_api_key
  ```

- **Query Parameter Authentication**: Alternatively, you can include the API key as a query parameter:
  ```
  ?api_key=your_api_key
  ```

## Rate Limiting

API requests are rate limited to protect the service. Rate limits vary by endpoint but generally allow:
- Standard endpoints: 30 requests per minute
- Data-intensive endpoints: 15 requests per minute

When the rate limit is exceeded, the API returns a `429 Too Many Requests` status code. The response includes headers indicating your rate limit status:

```
X-RateLimit-Limit: 30
X-RateLimit-Remaining: 0
X-RateLimit-Reset: 45
```

## Common Parameters

Many endpoints accept the following parameters:

- `ticker` (required): Stock ticker symbol (e.g., SLV, GLD, CVNA)
- `limit`: Maximum number of records to return (default varies by endpoint)
- `start_date`: Start date in YYYY-MM-DD format
- `end_date`: End date in YYYY-MM-DD format
- `start_time`: Start time in HH:MM format (used with start_date)
- `end_time`: End time in HH:MM format (used with end_date)

## Endpoints

### Status

#### `GET /status`

Get system status information, including market hours and thread status.

**Example request:**
```
GET /api/v1/status
```

**Example response:**
```json
{
  "status": "success",
  "data": {
    "system": {
      "service": "Multi-Ticker Options Flow Monitor",
      "status": "running",
      "current_time_et": "2025-05-08 10:30:45",
      "timezone": "America/New_York"
    },
    "market": {
      "is_market_hours": true,
      "market_open": "9:00",
      "market_close": "16:15"
    },
    "tickers": ["SLV", "GLD", "CVNA", "TQQQ", "SQQQ", "SOXL"],
    "threads": {
      "ticker_manager": {
        "running": true,
        "active": true,
        "tickers": ["SLV", "GLD", "CVNA", "TQQQ", "SQQQ", "SOXL"]
      },
      "data_updaters": { /* ... */ },
      "stocks": { /* ... */ },
      "options": { /* ... */ }
    },
    "ml_system": {
      "running": true,
      "predictors": { /* ... */ }
    }
  }
}
```

### Supported Tickers

#### `GET /tickers`

Get a list of all tickers supported by the system.

**Example request:**
```
GET /api/v1/tickers
```

**Example response:**
```json
{
  "status": "success",
  "data": {
    "tickers": ["SLV", "GLD", "CVNA", "TQQQ", "SQQQ", "SOXL"],
    "count": 6
  }
}
```

### Options Trades

#### `GET /trades`

Get options trades for a specific ticker.

**Parameters:**
- `ticker` (required): Stock ticker symbol
- `start_date`: Start date in YYYY-MM-DD format
- `start_time`: Start time in HH:MM format
- `end_date`: End date in YYYY-MM-DD format
- `end_time`: End time in HH:MM format
- `limit`: Maximum number of records to return (default: 100)
- `recent`: If true, returns the most recent trades up to limit (ignores date parameters)

**Example request:**
```
GET /api/v1/trades?ticker=SLV&recent=true&limit=5
```

**Example response:**
```json
{
  "status": "success",
  "data": {
    "ticker": "SLV",
    "trades": [
      {
        "id": 12345,
        "ticker": "SLV",
        "option_symbol": "SLV230519C00023000",
        "trade_timestamp": 1684510200000,
        "trade_datetime": "2023-05-19T14:30:00+00:00",
        "price": 0.35,
        "size": 10,
        "trade_value": 350.0,
        "bid": 0.34,
        "ask": 0.36,
        "price_threshold": 0.5,
        "delta": 0.45,
        "updated_delta": 0.45,
        "underlying_price": 22.75,
        "underlying_bid": 22.74,
        "underlying_ask": 22.76,
        "date_added": "2023-05-19T14:30:01+00:00"
      },
      /* ... more trades ... */
    ],
    "count": 5
  }
}
```

### Minute Data

#### `GET /minute-data`

Get minute-by-minute OHLCV data for a specific ticker.

**Parameters:**
- `ticker` (required): Stock ticker symbol
- `start_date`: Start date in YYYY-MM-DD format
- `start_time`: Start time in HH:MM format
- `end_date`: End date in YYYY-MM-DD format
- `end_time`: End time in HH:MM format
- `limit`: Maximum number of records to return (default: 100)
- `recent`: If true, returns the most recent minute data up to limit (ignores date parameters)

**Example request:**
```
GET /api/v1/minute-data?ticker=GLD&recent=true&limit=5
```

**Example response:**
```json
{
  "status": "success",
  "data": {
    "ticker": "GLD",
    "minute_data": [
      {
        "ticker": "GLD",
        "timestamp": 1684510200000,
        "datetime": "2023-05-19T14:30:00+00:00",
        "open": 183.45,
        "high": 183.52,
        "low": 183.41,
        "close": 183.47,
        "volume": 1250,
        "date_added": "2023-05-19T14:30:01+00:00"
      },
      /* ... more minute data ... */
    ],
    "count": 5
  }
}
```

### Delta Divergence

#### `GET /divergence`

Get delta divergence data for a specific ticker.

**Parameters:**
- `ticker` (required): Stock ticker symbol
- `start_date`: Start date in YYYY-MM-DD format
- `start_time`: Start time in HH:MM format
- `end_date`: End date in YYYY-MM-DD format
- `end_time`: End time in HH:MM format
- `days`: Number of days of data to return (default: 1, overridden by date parameters)
- `limit`: Maximum number of records to return (default: none)

**Example request:**
```
GET /api/v1/divergence?ticker=CVNA&days=1&limit=5
```

**Example response:**
```json
{
  "status": "success",
  "data": {
    "ticker": "CVNA",
    "divergence_data": [
      {
        "ticker": "CVNA",
        "timestamp": 1684510200000,
        "datetime": "2023-05-19T14:30:00+00:00",
        "d_pos_short": 0.12,
        "d_neg_short": -0.08,
        "d_diff_short": 0.04,
        "d_diff_derivative_short": 0.01,
        "d_pos_long": 0.25,
        "d_neg_long": -0.15,
        "d_diff_long": 0.10,
        "d_diff_derivative_long": 0.02,
        "stock_price": 45.67,
        "sum_pos": 1.25,
        "sum_neg": -0.85,
        "number_of_trades": 25,
        "lambda_short": 0.45,
        "lambda_long": 0.9,
        "date_added": "2023-05-19T14:30:01+00:00"
      },
      /* ... more divergence data ... */
    ],
    "count": 5
  }
}
```

### Machine Learning Predictions

#### `GET /prediction/latest`

Get the latest ML prediction for a specific ticker.

**Parameters:**
- `ticker` (required): Stock ticker symbol
- `use_default_only`: If true, uses the default model instead of ticker-specific model (default: false)

**Example request:**
```
GET /api/v1/prediction/latest?ticker=SLV
```

**Example response:**
```json
{
  "status": "success",
  "data": {
    "ticker": "SLV",
    "prediction": {
      "ticker": "SLV",
      "signal": "BUY",
      "numeric": 1,
      "confidence": 0.85,
      "probabilities": [0.05, 0.10, 0.85],
      "timestamp": 1684510200000,
      "datetime": "2023-05-19T14:30:00+00:00",
      "datetime_of_data": "2023-05-19T14:30:00+00:00",
      "stock_price": 22.75,
      "feature_values": {
        "d_diff_short": 0.04,
        "d_diff_long": 0.10,
        /* ... more features ... */
      },
      "prediction_time": "2023-05-19T14:30:05+00:00"
    },
    "model_info": {
      "model_path": "models/slv_predictor.joblib",
      "is_ticker_specific": true,
      "using_default_only": false
    }
  }
}
```

#### `GET /predictions`

Get ML prediction history for a specific ticker.

**Parameters:**
- `ticker` (required): Stock ticker symbol
- `limit`: Maximum number of predictions to return (default: 100)
- `start_date`: ISO format date string
- `end_date`: ISO format date string
- `use_default_only`: If true, uses the default model instead of ticker-specific model (default: false)

**Example request:**
```
GET /api/v1/predictions?ticker=GLD&limit=5
```

**Example response:**
```json
{
  "status": "success",
  "data": {
    "ticker": "GLD",
    "predictions": [
      /* ... prediction objects similar to /prediction/latest ... */
    ],
    "count": 5,
    "model_info": {
      "model_path": "models/gld_predictor.joblib",
      "is_ticker_specific": true,
      "using_default_only": false
    }
  }
}
```

### Custom Data Range

#### `GET /data-range`

Get custom date range data with filter options. This takes a long time to run so dont tests it on large amounts of time (just do 1 day)

**Parameters:**
- `ticker` (required): Stock ticker symbol
- `start_date` (required): Eastern time zone date string (YYYY-MM-DD)
- `end_date` (required): Eastern time zone date string (YYYY-MM-DD)
- `lookback_hours`: Number of hours to look back for trades (default: 8)
- `lambda_short`: Short-term decay factor (default: 0.45)
- `lambda_long`: Long-term decay factor (default: 0.9)
- `min_value`: Minimum trade value filter
- `max_value`: Maximum trade value filter
- `min_size`: Minimum trade size filter
- `max_size`: Maximum trade size filter
- `min_delta`: Minimum delta value filter
- `max_delta`: Maximum delta value filter

**Example request:**
```
GET /api/v1/data-range?ticker=CVNA&start_date=2023-05-18&end_date=2023-05-19&lookback_hours=6&lambda_short=0.5&lambda_long=0.85&min_value=500
```

**Example response:**
```json
{
  "status": "success",
  "data": {
    "ticker": "CVNA",
    "parameters": {
      "start_date": "2023-05-18T09:00:00",
      "end_date": "2023-05-19T16:15:00",
      "lookback_hours": 6,
      "lambda_short": 0.5,
      "lambda_long": 0.85,
      "date_range": "2023-05-18 to 2023-05-19",
      "filters": {
        "min_value": 500
      }
    },
    "data_info": {
      "original_trades": 1250,
      "filtered_trades": 465,
      "minute_data_points": 780,
      "divergence_points": 780
    },
    "divergence_data": [
      /* ... divergence data objects ... */
    ]
  }
}
```

## Error Responses

The API returns errors in a consistent format:

```json
{
  "status": "error",
  "error": "Error message",
  "code": 400,
  "message": "Additional details if available"
}
```

Common error codes:
- `400`: Bad request (missing or invalid parameters)
- `401`: Unauthorized (invalid API key)
- `404`: Resource not found
- `429`: Rate limit exceeded
- `500`: Internal server error
- `501`: Feature not implemented

## API Documentation

OpenAPI/Swagger documentation is available at:
```
/api/docs
```

This interactive documentation allows you to explore and test API endpoints directly in your browser.

## Code Examples

### Python

```python
import requests
import json
from datetime import datetime, timedelta

# Base URL and API key
base_url = "https://your-server-address/api/v1"
api_key = "your_api_key"
headers = {"X-API-Key": api_key}

# Get the latest prediction for SLV
response = requests.get(
    f"{base_url}/prediction/latest", 
    params={"ticker": "SLV"}, 
    headers=headers
)

if response.status_code == 200:
    prediction = response.json()
    print(f"Latest prediction for SLV: {prediction['data']['prediction']['signal']}")
    print(f"Confidence: {prediction['data']['prediction']['confidence']}")
    print(f"Stock price: {prediction['data']['prediction']['stock_price']}")
else:
    print(f"Error: {response.json()['error']}")

# Get custom data range for GLD
yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
today = datetime.now().strftime("%Y-%m-%d")

response = requests.get(
    f"{base_url}/data-range", 
    params={
        "ticker": "GLD",
        "start_date": yesterday,
        "end_date": today,
        "lookback_hours": 6,
        "lambda_short": 0.45,
        "lambda_long": 0.9,
        "min_value": 1000
    },
    headers=headers
)

if response.status_code == 200:
    data = response.json()
    print(f"Retrieved {data['data']['data_info']['divergence_points']} data points")
else:
    print(f"Error: {response.json()['error']}")
```