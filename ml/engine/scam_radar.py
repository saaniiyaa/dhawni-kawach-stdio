# ml/engine/scam_radar.py — v3.1: combination rule kills false alarms
# family_emergency fires ONLY on (distress + money/urgency together) or strong words

SCAM_PATTERNS = {
    "digital_arrest": [
        "digital arrest", "cbi", "police station", "warrant", "case filed",
        "legal action", "narcotics", "money laundering", "custody", "fir",
        "summons", "cyber cell", "interpol", "court order", "arrest warrant",
        "sim card misuse", "डिजिटल अरेस्ट", "गिरफ्तारी वारंट", "सीबीआई",
        "कस्टडी में", "ডিজিটাল অ্যারেস্ট", "ग্রেপ্তার", "டிஜிட்டல் அரெஸ்ட்",
        "கைது உத்தரவு", "డిజిటల్ అరెస్ట్", "అరెస్ట్ వారెంట్", "ಡಿಜಿಟಲ್ ಅರೆಸ್ಟ್",
        "ഡിജിറ്റൽ അറസ്റ്റ്", "पोलीस स्टेशन", "police ne pakad leya",
    ],
    "upi_otp": [
        "otp", "cvv", "upi", "gpay", "phonepe", "paytm", "qr code",
        "account block", "kyc", "bank manager", "card details", "screen share",
        "anydesk", "otp dasso", "ओटीपी बताओ", "अकाउंट ब्लॉक", "टাকা পাঠাও",
        "ওটিপি দাও", "ஓடிபி சொல்லு", "OTP ఇవ్వు", "OTP ನೀಡು", "OTP തരൂ",
        "OTP दे", "OTP આપો", "OTP ਦੱਸੋ", "OTP ଦିଅ", "OTP দিয়া",
    ],
    "urgency": [
        "abhi", "turant", "jaldi", "immediately", "right now", "urgent",
        "warna", "nahi toh", "last chance", "family ko mat batao",
        "तुरंत करो", "जल्दी करो", "turant karo", "এখনই", "உடனே",
        "వెంటనే", "ತಕ್ಷಣ", "ഉടനടി", "तत्काळ", "તરત", "ਤੁਰੰਤ", "ତୁରନ୍ତ",
    ],
    "reward_lottery": [
        "lottery", "jeeta hai", "jackpot", "lucky draw", "processing fee",
        "custom charges", "parcel pakda", "customs mein", "parcel release fee",
        "duty fee", "इनाम मिला है", "लॉटरी निकली", "पार्सल पकड़ा", "কাস্টমসে",
        "পার্সেল ধরা পড়েছে", "லாட்டரி", "లాటరీ", "ಲಾಟರಿ", "ലോട്ടറി",
    ],
    "investment_scam": [
        "investment", "trading tips", "stock tips", "crypto", "bitcoin",
        "guaranteed return", "paisa double", "telegram group", "insider tips",
        "दुगना होगा", "गारंटीड रिटर्न", "দুগুণ হবে", "இரட்டிப்பு", "రెట్టింపు",
    ],
    "job_scams": [
        "job confirm", "registration fee", "training fee", "consultancy fee",
        "backdoor entry", "job ke liye deposit", "offer letter fee",
        "नौकरी के लिए फीस", "வேலைக்கு கட்டணம்", "ఉద్యోగానికి ఫీజు",
    ],
    "utility_threat": [
        "electricity connection", "bijli kat", "meter replace", "connection band",
        "insurance expire", "emi bounce", "cibil score", "बिजली कटेगी",
        "कनेक्शन बंद", "বিজুলি কাটবে", "மின்வெட்டு", "కరెంట్ కట్",
    ],
}

# ---- family_emergency: combination rule (v3.1) ----
DISTRESS = [
    "hospital", "icu", "operation", "blood", "emergency", "accident",
    "chikitsalaya", "chikitsalya", "aspatal", "hospital mein",
    "हॉस्पिटल", "चिकित्सालय", "अस्पताल", "दुर्घटना", "एक्सीडेंट",
    "ऑपरेशन", "हॉस्पिटल में", "ভর্তি", "হাসপাতাল", "accident ho gaya",
    "மருத்துவமனை", "ఆసుపత్రి", "ಆಸ್ಪತ್ರೆ", "ആശുപത്രി", "ਹਸਪਤਾਲ",
    "હોસ્પિટલ", "ଡାକ୍ତରଖାନା", "চিকিৎসালয়",
]
MONEY_URGENCY = [
    "paisa", "paise", "bhejo", "transfer", "send money", "immediately",
    "right now", "urgent", "abhi", "turant", "jaldi", "warna", "nahi toh",
    "पैसे", "भेजो", "तुरंत", "जल्दी", "टাকা", "পাঠাও", "এখনই", "பணம்",
    "அனுப்பு", "డబ్బు", "పంపించు", "ಹಣ", "ಕಳುಹಿಸು", "പണം", "അയക്കൂ",
    "OTP", "उधार",
]
STRONG_FAMILY = [
    "kidnap", "ransom", "hostage", "अपहरण", "फिरौती", "কিডন্যাপ",
    "கடত்தல்", "కిడ్నాప్", "ಅಪಹರಣ", "തട്ടിക്കൊണ്ടുപോകുക",
]

ADVISORY = {
    "digital_arrest": "Police/CBI never arrest over a call or ask money. Hang up; call the station's official number.",
    "family_emergency": "Possible fake-emergency script. Hang up and call your family member's own number directly.",
    "upi_otp": "No real bank/UPI employee ever asks for OTP, PIN, or a transfer to a new account.",
    "urgency": "Manufactured urgency is a pressure tactic - real institutions give you time.",
    "reward_lottery": "You never win a lottery you never entered. Never pay a 'fee' to receive a prize or release a parcel.",
    "investment_scam": "Guaranteed returns do not exist. Verify investments only through SEBI-registered channels.",
    "job_scams": "No real employer asks for a fee to give you a job.",
    "utility_threat": "Government agencies never demand instant payment over a call. Check the official app/site.",
}


def scan(text):
    t = " " + str(text).lower() + " "
    hits = {}
    distress = [w for w in DISTRESS if w in t]
    money = [w for w in MONEY_URGENCY if w in t]
    strong = [w for w in STRONG_FAMILY if w in t]
    if strong or (distress and money):
        hits["family_emergency"] = strong + distress + money
    for cat, phrases in SCAM_PATTERNS.items():
        found = [p for p in phrases if p in t]
        if found:
            hits[cat] = found

    scam_cats = [c for c in hits if c != "urgency"]
    n_phrases = sum(len(v) for v in hits.values())
    has_urgency = "urgency" in hits
    score = 0
    if scam_cats or has_urgency:
        score = 30 * len(scam_cats) + 8 * n_phrases
        if has_urgency and scam_cats:
            score += 25
    score = min(100, score)
    top = max(scam_cats, key=lambda c: len(hits[c])) if scam_cats else (
        "urgency" if has_urgency else None)
    return {
        "score": score,
        "level": "HIGH" if score >= 70 else ("MEDIUM" if score >= 40 else "LOW"),
        "categories": list(hits.keys()),
        "matched": {c: hits[c] for c in hits},
        "advisory": ADVISORY.get(top, None),
    }
