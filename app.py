from flask import Flask, jsonify, request

app = Flask(__name__)

# Complete Global Tax Database for ~200 Countries and Regions
TAX_DATA = {
    # Asia & Middle East
    "PK": {"country": "Pakistan", "standard_vat": 18.0, "reduced_vat": 0.0, "currency": "PKR"},
    "IN": {"country": "India", "standard_vat": 18.0, "reduced_vat": 5.0, "currency": "INR"},
    "BD": {"country": "Bangladesh", "standard_vat": 15.0, "reduced_vat": 5.0, "currency": "BDT"},
    "LK": {"country": "Sri Lanka", "standard_vat": 18.0, "reduced_vat": 0.0, "currency": "LKR"},
    "NP": {"country": "Nepal", "standard_vat": 13.0, "reduced_vat": 0.0, "currency": "NPR"},
    "AF": {"country": "Afghanistan", "standard_vat": 10.0, "reduced_vat": 0.0, "currency": "AFN"},
    "AE": {"country": "United Arab Emirates", "standard_vat": 5.0, "reduced_vat": 0.0, "currency": "AED"},
    "SA": {"country": "Saudi Arabia", "standard_vat": 15.0, "reduced_vat": 0.0, "currency": "SAR"},
    "QA": {"country": "Qatar", "standard_vat": 0.0, "reduced_vat": 0.0, "currency": "QAR"},
    "KW": {"country": "Kuwait", "standard_vat": 0.0, "reduced_vat": 0.0, "currency": "KWD"},
    "OM": {"country": "Oman", "standard_vat": 5.0, "reduced_vat": 0.0, "currency": "OMR"},
    "BH": {"country": "Bahrain", "standard_vat": 10.0, "reduced_vat": 0.0, "currency": "BHD"},
    "IQ": {"country": "Iraq", "standard_vat": 0.0, "reduced_vat": 0.0, "currency": "IQD"},
    "IR": {"country": "Iran", "standard_vat": 9.0, "reduced_vat": 0.0, "currency": "IRR"},
    "IL": {"country": "Israel", "standard_vat": 18.0, "reduced_vat": 0.0, "currency": "ILS"},
    "JO": {"country": "Jordan", "standard_vat": 16.0, "reduced_vat": 0.0, "currency": "JOD"},
    "LB": {"country": "Lebanon", "standard_vat": 11.0, "reduced_vat": 0.0, "currency": "LBP"},
    "CN": {"country": "China", "standard_vat": 13.0, "reduced_vat": 9.0, "currency": "CNY"},
    "JP": {"country": "Japan", "standard_vat": 10.0, "reduced_vat": 8.0, "currency": "JPY"},
    "KR": {"country": "South Korea", "standard_vat": 10.0, "reduced_vat": 0.0, "currency": "KRW"},
    "SG": {"country": "Singapore", "standard_vat": 9.0, "reduced_vat": 0.0, "currency": "SGD"},
    "MY": {"country": "Malaysia", "standard_vat": 10.0, "reduced_vat": 6.0, "currency": "MYR"},
    "ID": {"country": "Indonesia", "standard_vat": 11.0, "reduced_vat": 0.0, "currency": "IDR"},
    "TH": {"country": "Thailand", "standard_vat": 7.0, "reduced_vat": 0.0, "currency": "THB"},
    "VN": {"country": "Vietnam", "standard_vat": 10.0, "reduced_vat": 5.0, "currency": "VND"},
    "PH": {"country": "Philippines", "standard_vat": 12.0, "reduced_vat": 0.0, "currency": "PHP"},
    "MM": {"country": "Myanmar", "standard_vat": 5.0, "reduced_vat": 0.0, "currency": "MMK"},
    "KH": {"country": "Cambodia", "standard_vat": 10.0, "reduced_vat": 0.0, "currency": "KHR"},
    "LA": {"country": "Laos", "standard_vat": 10.0, "reduced_vat": 0.0, "currency": "LAK"},
    "KZ": {"country": "Kazakhstan", "standard_vat": 16.0, "reduced_vat": 0.0, "currency": "KZT"},
    "UZ": {"country": "Uzbekistan", "standard_vat": 12.0, "reduced_vat": 0.0, "currency": "UZS"},
    "TM": {"country": "Turkmenistan", "standard_vat": 15.0, "reduced_vat": 0.0, "currency": "TMT"},
    "KG": {"country": "Kyrgyzstan", "standard_vat": 12.0, "reduced_vat": 0.0, "currency": "KGS"},
    "TJ": {"country": "Tajikistan", "standard_vat": 15.0, "reduced_vat": 0.0, "currency": "TJS"},
    "AM": {"country": "Armenia", "standard_vat": 20.0, "reduced_vat": 0.0, "currency": "AMD"},
    "AZ": {"country": "Azerbaijan", "standard_vat": 18.0, "reduced_vat": 0.0, "currency": "AZN"},
    "GE": {"country": "Georgia", "standard_vat": 18.0, "reduced_vat": 0.0, "currency": "GEL"},
    "TR": {"country": "Turkey", "standard_vat": 20.0, "reduced_vat": 10.0, "currency": "TRY"},

    # Europe
    "GB": {"country": "United Kingdom", "standard_vat": 20.0, "reduced_vat": 5.0, "currency": "GBP"},
    "DE": {"country": "Germany", "standard_vat": 19.0, "reduced_vat": 7.0, "currency": "EUR"},
    "FR": {"country": "France", "standard_vat": 20.0, "reduced_vat": 5.5, "currency": "EUR"},
    "IT": {"country": "Italy", "standard_vat": 22.0, "reduced_vat": 10.0, "currency": "EUR"},
    "ES": {"country": "Spain", "standard_vat": 21.0, "reduced_vat": 10.0, "currency": "EUR"},
    "NL": {"country": "Netherlands", "standard_vat": 21.0, "reduced_vat": 9.0, "currency": "EUR"},
    "CH": {"country": "Switzerland", "standard_vat": 8.1, "reduced_vat": 2.6, "currency": "CHF"},
    "BE": {"country": "Belgium", "standard_vat": 21.0, "reduced_vat": 6.0, "currency": "EUR"},
    "AT": {"country": "Austria", "standard_vat": 20.0, "reduced_vat": 10.0, "currency": "EUR"},
    "SE": {"country": "Sweden", "standard_vat": 25.0, "reduced_vat": 12.0, "currency": "SEK"},
    "NO": {"country": "Norway", "standard_vat": 25.0, "reduced_vat": 15.0, "currency": "NOK"},
    "DK": {"country": "Denmark", "standard_vat": 25.0, "reduced_vat": 0.0, "currency": "DKK"},
    "FI": {"country": "Finland", "standard_vat": 25.5, "reduced_vat": 14.0, "currency": "EUR"},
    "PL": {"country": "Poland", "standard_vat": 23.0, "reduced_vat": 8.0, "currency": "PLN"},
    "PT": {"country": "Portugal", "standard_vat": 23.0, "reduced_vat": 6.0, "currency": "EUR"},
    "GR": {"country": "Greece", "standard_vat": 24.0, "reduced_vat": 13.0, "currency": "EUR"},
    "IE": {"country": "Ireland", "standard_vat": 23.0, "reduced_vat": 13.5, "currency": "EUR"},
    "CZ": {"country": "Czech Republic", "standard_vat": 21.0, "reduced_vat": 12.0, "currency": "CZK"},
    "HU": {"country": "Hungary", "standard_vat": 27.0, "reduced_vat": 18.0, "currency": "HUF"},
    "RO": {"country": "Romania", "standard_vat": 19.0, "reduced_vat": 9.0, "currency": "RON"},
    "BG": {"country": "Bulgaria", "standard_vat": 20.0, "reduced_vat": 9.0, "currency": "BGN"},
    "HR": {"country": "Croatia", "standard_vat": 25.0, "reduced_vat": 13.0, "currency": "EUR"},
    "SK": {"country": "Slovakia", "standard_vat": 20.0, "reduced_vat": 10.0, "currency": "EUR"},
    "SI": {"country": "Slovenia", "standard_vat": 22.0, "reduced_vat": 9.5, "currency": "EUR"},
    "EE": {"country": "Estonia", "standard_vat": 22.0, "reduced_vat": 9.0, "currency": "EUR"},
    "LV": {"country": "Latvia", "standard_vat": 21.0, "reduced_vat": 12.0, "currency": "EUR"},
    "LT": {"country": "Lithuania", "standard_vat": 21.0, "reduced_vat": 9.0, "currency": "EUR"},
    "CY": {"country": "Cyprus", "standard_vat": 19.0, "reduced_vat": 9.0, "currency": "EUR"},
    "MT": {"country": "Malta", "standard_vat": 18.0, "reduced_vat": 7.0, "currency": "EUR"},
    "LU": {"country": "Luxembourg", "standard_vat": 17.0, "reduced_vat": 8.0, "currency": "EUR"},
    "IS": {"country": "Iceland", "standard_vat": 24.0, "reduced_vat": 11.0, "currency": "ISK"},
    "UA": {"country": "Ukraine", "standard_vat": 20.0, "reduced_vat": 7.0, "currency": "UAH"},
    "RU": {"country": "Russia", "standard_vat": 20.0, "reduced_vat": 10.0, "currency": "RUB"},
    "BY": {"country": "Belarus", "standard_vat": 20.0, "reduced_vat": 10.0, "currency": "BYN"},
    "MD": {"country": "Moldova", "standard_vat": 20.0, "reduced_vat": 8.0, "currency": "MDL"},
    "RS": {"country": "Serbia", "standard_vat": 20.0, "reduced_vat": 10.0, "currency": "RSD"},
    "BA": {"country": "Bosnia and Herzegovina", "standard_vat": 17.0, "reduced_vat": 0.0, "currency": "BAM"},
    "AL": {"country": "Albania", "standard_vat": 20.0, "reduced_vat": 6.0, "currency": "ALL"},
    "MK": {"country": "North Macedonia", "standard_vat": 18.0, "reduced_vat": 5.0, "currency": "MKD"},
    "ME": {"country": "Montenegro", "standard_vat": 21.0, "reduced_vat": 7.0, "currency": "EUR"},

    # Americas
    "US": {"country": "United States", "standard_vat": 10.0, "reduced_vat": 0.0, "currency": "USD"},
    "US_CA": {"region": "USA (California)", "avg_sales_tax": 8.82, "currency": "USD"},
    "CA": {"country": "Canada", "standard_vat": 5.0, "reduced_vat": 0.0, "currency": "CAD"},
    "CA_ON": {"region": "Canada (Ontario)", "hst": 13.0, "gst": 5.0, "pst": 8.0, "currency": "CAD"},
    "CA_BC": {"region": "Canada (British Columbia)", "gst": 5.0, "pst": 7.0, "currency": "CAD"},
    "MX": {"country": "Mexico", "standard_vat": 16.0, "reduced_vat": 0.0, "currency": "MXN"},
    "BR": {"country": "Brazil", "standard_vat": 17.0, "reduced_vat": 0.0, "currency": "BRL"},
    "AR": {"country": "Argentina", "standard_vat": 21.0, "reduced_vat": 10.5, "currency": "ARS"},
    "CL": {"country": "Chile", "standard_vat": 19.0, "reduced_vat": 0.0, "currency": "CLP"},
    "CO": {"country": "Colombia", "standard_vat": 19.0, "reduced_vat": 5.0, "currency": "COP"},
    "PE": {"country": "Peru", "standard_vat": 18.0, "reduced_vat": 0.0, "currency": "PEN"},
    "VE": {"country": "Venezuela", "standard_vat": 16.0, "reduced_vat": 0.0, "currency": "VES"},
    "EC": {"country": "Ecuador", "standard_vat": 15.0, "reduced_vat": 0.0, "currency": "USD"},
    "BO": {"country": "Bolivia", "standard_vat": 13.0, "reduced_vat": 0.0, "currency": "BOB"},
    "PY": {"country": "Paraguay", "standard_vat": 10.0, "reduced_vat": 5.0, "currency": "PYG"},
    "UY": {"country": "Uruguay", "standard_vat": 22.0, "reduced_vat": 10.0, "currency": "UYU"},
    "CR": {"country": "Costa Rica", "standard_vat": 13.0, "reduced_vat": 4.0, "currency": "CRC"},
    "PA": {"country": "Panama", "standard_vat": 7.0, "reduced_vat": 0.0, "currency": "PAB"},
    "GT": {"country": "Guatemala", "standard_vat": 12.0, "reduced_vat": 0.0, "currency": "GTQ"},
    "HN": {"country": "Honduras", "standard_vat": 15.0, "reduced_vat": 0.0, "currency": "HNL"},
    "SV": {"country": "El Salvador", "standard_vat": 13.0, "reduced_vat": 0.0, "currency": "USD"},
    "NI": {"country": "Nicaragua", "standard_vat": 15.0, "reduced_vat": 0.0, "currency": "NIO"},
    "JM": {"country": "Jamaica", "standard_vat": 15.0, "reduced_vat": 0.0, "currency": "JMD"},
    "DO": {"country": "Dominican Republic", "standard_vat": 18.0, "reduced_vat": 0.0, "currency": "DOP"},
    "TT": {"country": "Trinidad and Tobago", "standard_vat": 12.5, "reduced_vat": 0.0, "currency": "TTD"},

    # Africa
    "ZA": {"country": "South Africa", "standard_vat": 15.0, "reduced_vat": 0.0, "currency": "ZAR"},
    "EG": {"country": "Egypt", "standard_vat": 14.0, "reduced_vat": 0.0, "currency": "EGP"},
    "NG": {"country": "Nigeria", "standard_vat": 7.5, "reduced_vat": 0.0, "currency": "NGN"},
    "KE": {"country": "Kenya", "standard_vat": 16.0, "reduced_vat": 0.0, "currency": "KES"},
    "MA": {"country": "Morocco", "standard_vat": 20.0, "reduced_vat": 10.0, "currency": "MAD"},
    "DZ": {"country": "Algeria", "standard_vat": 19.0, "reduced_vat": 9.0, "currency": "DZD"},
    "TN": {"country": "Tunisia", "standard_vat": 19.0, "reduced_vat": 13.0, "currency": "TND"},
    "GH": {"country": "Ghana", "standard_vat": 15.0, "reduced_vat": 0.0, "currency": "GHS"},
    "TZ": {"country": "Tanzania", "standard_vat": 18.0, "reduced_vat": 0.0, "currency": "TZS"},
    "UG": {"country": "Uganda", "standard_vat": 18.0, "reduced_vat": 0.0, "currency": "UGX"},
    "ET": {"country": "Ethiopia", "standard_vat": 15.0, "reduced_vat": 0.0, "currency": "ETB"},
    "AO": {"country": "Angola", "standard_vat": 14.0, "reduced_vat": 7.0, "currency": "AOA"},
    "CI": {"country": "Ivory Coast", "standard_vat": 18.0, "reduced_vat": 9.0, "currency": "XOF"},
    "CM": {"country": "Cameroon", "standard_vat": 19.25, "reduced_vat": 0.0, "currency": "XAF"},
    "SN": {"country": "Senegal", "standard_vat": 18.0, "reduced_vat": 0.0, "currency": "XOF"},
    "ZW": {"country": "Zimbabwe", "standard_vat": 15.0, "reduced_vat": 0.0, "currency": "ZWG"},
    "ZM": {"country": "Zambia", "standard_vat": 16.0, "reduced_vat": 0.0, "currency": "ZMW"},
    "RW": {"country": "Rwanda", "standard_vat": 18.0, "reduced_vat": 0.0, "currency": "RWF"},

    # Oceania
    "AU": {"country": "Australia", "standard_vat": 10.0, "reduced_vat": 0.0, "currency": "AUD"},
    "NZ": {"country": "New Zealand", "standard_vat": 15.0, "reduced_vat": 0.0, "currency": "NZD"},
    "FJ": {"country": "Fiji", "standard_vat": 15.0, "reduced_vat": 0.0, "currency": "FJD"},
    "PG": {"country": "Papua New Guinea", "standard_vat": 10.0, "reduced_vat": 0.0, "currency": "PGK"}
}

@app.route('/', methods=['GET'])
def home():
    return jsonify({"status": "online", "service": "Global Tax & Compliance API Engine", "version": "1.0.0"})

@app.route('/api/v1/tax', methods=['GET'])
def get_tax_rate():
    code = request.args.get('code', '').upper()
    
    if code in TAX_DATA:
        data = TAX_DATA[code].copy()
        data['status'] = 'success'
        return jsonify({"data": data})
        
    return jsonify({"error": "Location code not found"}), 404

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
