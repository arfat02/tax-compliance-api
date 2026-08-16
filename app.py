from flask import Flask, jsonify, request
import requests

app = Flask(__name__)

# Complete Reliable Global Tax Database
TAX_DATA = {
    "PK": {"country_name": "Pakistan", "standard_vat": 18.0, "reduced_vat": 0.0, "currency": "PKR"},
    "IN": {"country_name": "India", "standard_vat": 18.0, "reduced_vat": 5.0, "currency": "INR"},
    "BD": {"country_name": "Bangladesh", "standard_vat": 15.0, "reduced_vat": 5.0, "currency": "BDT"},
    "US": {"country_name": "United States", "standard_vat": 10.0, "reduced_vat": 0.0, "currency": "USD"},
    "US_CA": {"region": "USA (California)", "avg_sales_tax": 8.82, "currency": "USD"},
    "CA": {"country_name": "Canada", "standard_vat": 5.0, "reduced_vat": 0.0, "currency": "CAD"},
    "CA_ON": {"region": "Canada (Ontario)", "hst": 13.0, "gst": 5.0, "pst": 8.0, "currency": "CAD"},
    "CA_BC": {"region": "Canada (British Columbia)", "gst": 5.0, "pst": 7.0, "currency": "CAD"},
    "GB": {"country_name": "United Kingdom", "standard_vat": 20.0, "reduced_vat": 5.0, "currency": "GBP"},
    "DE": {"country_name": "Germany", "standard_vat": 19.0, "reduced_vat": 7.0, "currency": "EUR"},
    "FR": {"country_name": "France", "standard_vat": 20.0, "reduced_vat": 5.5, "currency": "EUR"},
    "IT": {"country_name": "Italy", "standard_vat": 22.0, "reduced_vat": 10.0, "currency": "EUR"},
    "ES": {"country_name": "Spain", "standard_vat": 21.0, "reduced_vat": 10.0, "currency": "EUR"},
    "NL": {"country_name": "Netherlands", "standard_vat": 21.0, "reduced_vat": 9.0, "currency": "EUR"},
    "CH": {"country_name": "Switzerland", "standard_vat": 8.1, "reduced_vat": 2.6, "currency": "CHF"},
    "AE": {"country_name": "United Arab Emirates", "standard_vat": 5.0, "reduced_vat": 0.0, "currency": "AED"},
    "SA": {"country_name": "Saudi Arabia", "standard_vat": 15.0, "reduced_vat": 0.0, "currency": "SAR"},
    "QA": {"country_name": "Qatar", "standard_vat": 0.0, "reduced_vat": 0.0, "currency": "QAR"},
    "KW": {"country_name": "Kuwait", "standard_vat": 0.0, "reduced_vat": 0.0, "currency": "KWD"},
    "OM": {"country_name": "Oman", "standard_vat": 5.0, "reduced_vat": 0.0, "currency": "OMR"},
    "BH": {"country_name": "Bahrain", "standard_vat": 10.0, "reduced_vat": 0.0, "currency": "BHD"},
    "CN": {"country_name": "China", "standard_vat": 13.0, "reduced_vat": 9.0, "currency": "CNY"},
    "JP": {"country_name": "Japan", "standard_vat": 10.0, "reduced_vat": 8.0, "currency": "JPY"},
    "KR": {"country_name": "South Korea", "standard_vat": 10.0, "reduced_vat": 0.0, "currency": "KRW"},
    "SG": {"country_name": "Singapore", "standard_vat": 9.0, "reduced_vat": 0.0, "currency": "SGD"},
    "MY": {"country_name": "Malaysia", "standard_vat": 10.0, "reduced_vat": 6.0, "currency": "MYR"},
    "ID": {"country_name": "Indonesia", "standard_vat": 11.0, "reduced_vat": 0.0, "currency": "IDR"},
    "TH": {"country_name": "Thailand", "standard_vat": 7.0, "reduced_vat": 0.0, "currency": "THB"},
    "PH": {"country_name": "Philippines", "standard_vat": 12.0, "reduced_vat": 0.0, "currency": "PHP"},
    "AU": {"country_name": "Australia", "standard_vat": 10.0, "reduced_vat": 0.0, "currency": "AUD"},
    "NZ": {"country_name": "New Zealand", "standard_vat": 15.0, "reduced_vat": 0.0, "currency": "NZD"},
    "ZA": {"country_name": "South Africa", "standard_vat": 15.0, "reduced_vat": 0.0, "currency": "ZAR"},
    "EG": {"country_name": "Egypt", "standard_vat": 14.0, "reduced_vat": 0.0, "currency": "EGP"},
    "NG": {"country_name": "Nigeria", "standard_vat": 7.5, "reduced_vat": 0.0, "currency": "NGN"},
    "KE": {"country_name": "Kenya", "standard_vat": 16.0, "reduced_vat": 0.0, "currency": "KES"},
    "BR": {"country_name": "Brazil", "standard_vat": 17.0, "reduced_vat": 0.0, "currency": "BRL"},
    "MX": {"country_name": "Mexico", "standard_vat": 16.0, "reduced_vat": 0.0, "currency": "MXN"},
    "AR": {"country_name": "Argentina", "standard_vat": 21.0, "reduced_vat": 10.5, "currency": "ARS"},
    "TR": {"country_name": "Turkey", "standard_vat": 20.0, "reduced_vat": 10.0, "currency": "TRY"}
}

@app.route('/', methods=['GET'])
def home():
    return jsonify({"status": "online", "service": "Global Tax API", "version": "2.1.0"})

@app.route('/api/v1/tax', methods=['GET'])
def get_tax_rate():
    code = request.args.get('code', '').upper()
    
    if not code:
        return jsonify({"error": "Country code required (?code=PK)"}), 400

    # Primary Local Lookup
    if code in TAX_DATA:
        data = TAX_DATA[code].copy()
        data['country_code'] = code
        data['source'] = 'verified_tax_database'
        data['status'] = 'success'
        return jsonify({"data": data})

    # Live Provider Fallback
    try:
        resp = requests.get(f"https://api.vatcomply.com/rates?country={code}", timeout=3)
        if resp.status_code == 200:
            live = resp.json()
            rate = live.get("rates", {}).get(code) or live.get("rate")
            if rate is not None:
                return jsonify({
                    "data": {
                        "country_code": code,
                        "country_name": live.get("name", code),
                        "standard_vat": float(rate),
                        "currency": live.get("currency", "USD"),
                        "source": "live_realtime_provider",
                        "status": "success"
                    }
                })
    except Exception as e:
        print(f"Fallback Error: {e}")

    return jsonify({"error": f"Location code '{code}' not found"}), 404

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
