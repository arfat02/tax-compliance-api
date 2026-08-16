from flask import Flask, jsonify, request
import requests

app = Flask(__name__)

# Fallback local data for special regions / overrides
LOCAL_OVERVIEW = {
    "US_CA": {"region": "USA (California)", "avg_sales_tax": 8.82, "currency": "USD"},
    "CA_ON": {"region": "Canada (Ontario)", "hst": 13.0, "gst": 5.0, "pst": 8.0, "currency": "CAD"},
    "CA_BC": {"region": "Canada (British Columbia)", "gst": 5.0, "pst": 7.0, "currency": "CAD"}
}

@app.route('/', methods=['GET'])
def home():
    return jsonify({
        "status": "online",
        "service": "Global Live Tax & Compliance API Engine",
        "version": "2.0.0"
    })

@app.route('/api/v1/tax', methods=['GET'])
def get_tax_rate():
    code = request.args.get('code', '').upper()
    
    if not code:
        return jsonify({"error": "Country code is required. E.g. ?code=PK"}), 400

    # 1. Check local region overrides first
    if code in LOCAL_OVERVIEW:
        data = LOCAL_OVERVIEW[code].copy()
        data['source'] = 'local_database'
        data['status'] = 'success'
        return jsonify({"data": data})

    # 2. Fetch live global tax rate from Live API
    try:
        live_response = requests.get(f"https://api.vatcomply.com/rates?country={code}", timeout=5)
        
        if live_response.status_code == 200:
            live_data = live_response.json()
            return jsonify({
                "data": {
                    "country_code": code,
                    "country_name": live_data.get("name"),
                    "standard_vat": live_data.get("rate"),
                    "currency": live_data.get("currency"),
                    "source": "live_realtime_provider",
                    "status": "success"
                }
            })
    except Exception as e:
        print(f"Live API Fetch Error: {e}")

    return jsonify({"error": f"Location code '{code}' not found or service unavailable"}), 404

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
