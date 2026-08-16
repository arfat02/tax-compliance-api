from flask import Flask, jsonify, request

app = Flask(__name__)

TAX_DATA = {
    "CH": {"country": "Switzerland", "standard_vat": 8.1, "reduced_vat": 2.6, "currency": "CHF"},
    "CA_ON": {"region": "Canada (Ontario)", "hst": 13.0, "gst": 5.0, "pst": 8.0, "currency": "CAD"},
    "CA_BC": {"region": "Canada (British Columbia)", "gst": 5.0, "pst": 7.0, "currency": "CAD"},
    "US_CA": {"region": "USA (California)", "avg_sales_tax": 8.82, "currency": "USD"},
    "DE": {"country": "Germany (EU)", "standard_vat": 19.0, "reduced_vat": 7.0, "currency": "EUR"}
}

@app.route('/', methods=['GET'])
def home():
    return jsonify({
        "status": "online",
        "service": "Global Tax & Compliance API Engine",
        "version": "1.0.0"
    })

@app.route('/api/v1/tax', methods=['GET'])
def get_tax_rate():
    code = request.args.get('code', '').upper()
    if not code:
        return jsonify({"error": "Please provide a valid location code (e.g., ?code=CH or ?code=CA_ON)"}), 400
    
    data = TAX_DATA.get(code)
    if data:
        return jsonify({"status": "success", "data": data})
    else:
        return jsonify({"error": "Location code not found"}), 404

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
