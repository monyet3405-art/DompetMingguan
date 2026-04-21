from flask import Flask, render_template, request, jsonify
import json
import os
from datetime import datetime, timedelta
from collections import defaultdict

app = Flask(__name__)

DATA_FILE = "data.json"

CATEGORIES = {
    "makan": {"icon": "🍔", "color": "#FFB347", "label": "Makan & Minum"},
    "transport": {"icon": "🚌", "color": "#87CEEB", "label": "Transport"},
    "jajan": {"icon": "🧋", "color": "#DDA0DD", "label": "Jajan"},
    "hiburan": {"icon": "🎮", "color": "#98FB98", "label": "Hiburan"},
    "belanja": {"icon": "🛍️", "color": "#FFB6C1", "label": "Belanja"},
    "lainnya": {"icon": "📦", "color": "#F0E68C", "label": "Lainnya"},
}


def load_data():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r") as f:
            return json.load(f)
    return {
        "weekly_budget": 200000,
        "weekly_target": 50000,
        "transactions": [],
        "current_week_start": get_week_start()
    }


def save_data(data):
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=2)


def get_week_start():
    today = datetime.now()
    monday = today - timedelta(days=today.weekday())
    return monday.strftime("%Y-%m-%d")


def get_week_transactions(data):
    week_start = data.get("current_week_start", get_week_start())
    week_start_dt = datetime.strptime(week_start, "%Y-%m-%d")
    week_end_dt = week_start_dt + timedelta(days=6)
    
    week_txns = []
    for txn in data["transactions"]:
        txn_date = datetime.strptime(txn["date"], "%Y-%m-%d")
        if week_start_dt <= txn_date <= week_end_dt:
            week_txns.append(txn)
    return week_txns


@app.route("/")
def index():
    return render_template("index.html", categories=CATEGORIES)


@app.route("/api/summary")
def get_summary():
    data = load_data()
    week_txns = get_week_transactions(data)
    
    total_spent = sum(t["amount"] for t in week_txns)
    weekly_budget = data["weekly_budget"]
    weekly_target = data["weekly_target"]
    
    remaining = weekly_budget - total_spent
    savings = max(0, remaining)
    percentage = min(100, round((total_spent / weekly_budget * 100) if weekly_budget > 0 else 0))
    
    # Status badge
    if percentage <= 50:
        status = {"label": "🌟 Hemat Banget!", "type": "hemat"}
    elif percentage <= 75:
        status = {"label": "⚠️ Hampir Boros!", "type": "hampir"}
    elif percentage <= 90:
        status = {"label": "😬 Hati-hati Nih!", "type": "hatihati"}
    else:
        status = {"label": "🚨 Uang Tipis!", "type": "kritis"}
    
    # Category breakdown
    cat_totals = defaultdict(float)
    for t in week_txns:
        cat_totals[t["category"]] += t["amount"]
    
    category_data = []
    for cat_key, info in CATEGORIES.items():
        amount = cat_totals.get(cat_key, 0)
        pct = round((amount / total_spent * 100) if total_spent > 0 else 0)
        category_data.append({
            "key": cat_key,
            "label": info["label"],
            "icon": info["icon"],
            "color": info["color"],
            "amount": amount,
            "percentage": pct
        })
    
    # Daily breakdown for chart (Mon-Sun)
    week_start = data.get("current_week_start", get_week_start())
    week_start_dt = datetime.strptime(week_start, "%Y-%m-%d")
    daily = []
    days = ["Sen", "Sel", "Rab", "Kam", "Jum", "Sab", "Min"]
    for i in range(7):
        d = week_start_dt + timedelta(days=i)
        d_str = d.strftime("%Y-%m-%d")
        day_total = sum(t["amount"] for t in week_txns if t["date"] == d_str)
        daily.append({"day": days[i], "amount": day_total})
    
    target_achieved = savings >= weekly_target
    
    return jsonify({
        "weekly_budget": weekly_budget,
        "weekly_target": weekly_target,
        "total_spent": total_spent,
        "remaining": remaining,
        "savings": savings,
        "percentage": percentage,
        "status": status,
        "categories": category_data,
        "daily": daily,
        "target_achieved": target_achieved,
        "week_start": week_start
    })


@app.route("/api/transactions")
def get_transactions():
    data = load_data()
    week_txns = get_week_transactions(data)
    week_txns_sorted = sorted(week_txns, key=lambda x: x["date"], reverse=True)
    
    enriched = []
    for t in week_txns_sorted:
        cat_info = CATEGORIES.get(t["category"], {})
        enriched.append({
            **t,
            "icon": cat_info.get("icon", "📦"),
            "color": cat_info.get("color", "#ccc"),
            "cat_label": cat_info.get("label", t["category"])
        })
    
    return jsonify({"transactions": enriched})


@app.route("/api/transactions", methods=["POST"])
def add_transaction():
    data = load_data()
    body = request.json
    
    if not body or not body.get("amount") or not body.get("category") or not body.get("description"):
        return jsonify({"error": "Data tidak lengkap"}), 400
    
    try:
        amount = float(body["amount"])
        if amount <= 0:
            raise ValueError
    except (ValueError, TypeError):
        return jsonify({"error": "Jumlah tidak valid"}), 400
    
    txn = {
        "id": str(int(datetime.now().timestamp() * 1000)),
        "amount": amount,
        "category": body["category"],
        "description": body["description"],
        "date": body.get("date", datetime.now().strftime("%Y-%m-%d")),
        "created_at": datetime.now().isoformat()
    }
    
    data["transactions"].append(txn)
    save_data(data)
    
    return jsonify({"success": True, "transaction": txn})


@app.route("/api/transactions/<txn_id>", methods=["DELETE"])
def delete_transaction(txn_id):
    data = load_data()
    data["transactions"] = [t for t in data["transactions"] if t["id"] != txn_id]
    save_data(data)
    return jsonify({"success": True})


@app.route("/api/settings", methods=["GET"])
def get_settings():
    data = load_data()
    return jsonify({
        "weekly_budget": data["weekly_budget"],
        "weekly_target": data["weekly_target"]
    })


@app.route("/api/settings", methods=["POST"])
def update_settings():
    data = load_data()
    body = request.json
    
    if "weekly_budget" in body:
        data["weekly_budget"] = float(body["weekly_budget"])
    if "weekly_target" in body:
        data["weekly_target"] = float(body["weekly_target"])
    
    save_data(data)
    return jsonify({"success": True})


@app.route("/api/reset-week", methods=["POST"])
def reset_week():
    data = load_data()
    data["current_week_start"] = get_week_start()
    save_data(data)
    return jsonify({"success": True})

import os
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
