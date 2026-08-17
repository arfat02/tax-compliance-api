# Global Tax & Compliance API Engine

A high-performance, real-time REST API designed to deliver accurate standard VAT, sales tax, and regional compliance data across the globe. Built with Python Flask and hosted on high-availability cloud infrastructure.

## 🚀 Features
- **Global Coverage:** Instant access to tax rates for international markets and major economies.
- **Regional Precision:** Handles complex multi-tier tax structures and localized provincial rates.
- **High-Speed Reliability:** Powered by a verified core database combined with automated fallback engines.
- **Developer-Friendly:** Lightweight REST endpoints with clean, predictable JSON responses.

## 📡 Endpoints Overview

### 1. Health Check
* **Endpoint:** `GET /`
* **Description:** Verifies system uptime and active API engine version.

### 2. Get Tax Rates
* **Endpoint:** `GET /api/v1/tax`
* **Parameters:**
  * `code` (string, required): The ISO 2-letter country code or regional identifier (e.g., `PK`, `DE`, `GB`).
* **Example Request (cURL):**
  ```bash
  curl --request GET \
    --url '[https://your-api-url.onrender.com/api/v1/tax?code=PK](https://your-api-url.onrender.com/api/v1/tax?code=PK)'
