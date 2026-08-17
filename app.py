from flask import Flask, jsonify, request
import requests

app = Flask(__name__)

@app.route('/', methods=['GET'])
def home():
    return jsonify({"message": "Global Tax and Compliance Engine API is live!"})

@app.route('/api/v1/calculate', methods=['POST'])
def calculate_tax():
    try:
        data = request.get_json() or {}
        code = data.get('code', '').upper()
        amount = float(data.get('amount', 0))

        if not code:
            return jsonify({"error": "Country code is required"}), 400

        # Live external API se data fetch karna
        external_url = f"https://api.taxrates.api/v1/vat?country={code}" # Ya aapka pehla live API link
        response = requests.get(external_url)
        
        if response.status_code != 200:
            return jsonify({"error": "Failed to fetch live tax rate from external source"}), 500

        live_data = response.json()
        standard_vat = float(live_data.get('standard_vat', 0))
        country_name = live_data.get('country_name', code)
        currency = live_data.get('currency', 'USD')

        # Calculation perform karna
        calculated_tax = (amount * standard_vat) / 100
        total_amount = amount + calculated_tax

        return jsonify({
            "status": "success",
            "country_code": code,
            "country_name": country_name,
            "currency": currency,
            "standard_vat": standard_vat,
            "entered_amount": amount,
            "calculated_tax": calculated_tax,
            "total_amount": total_amount
        }), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
