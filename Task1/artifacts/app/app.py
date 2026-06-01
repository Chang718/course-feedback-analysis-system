import json
import os
from pathlib import Path
from datetime import datetime

from flask import Flask, request, jsonify, send_from_directory

app = Flask(__name__)

DATA_PATH = Path(__file__).parent / "seed_feedback.json"


def get_runtime_options() -> dict:
    host = os.environ.get("FLASK_HOST", "0.0.0.0")
    port_str = os.environ.get("PORT", "5000")
    port = int(port_str)
    debug_str = os.environ.get("FLASK_DEBUG", "false").lower()
    debug = debug_str in ("true", "1", "yes")
    return {"host": host, "port": port, "debug": debug}


def load_feedback() -> list:
    if DATA_PATH.exists():
        with open(DATA_PATH, "r") as f:
            return json.load(f)
    return []


def save_feedback(feedback_list: list):
    with open(DATA_PATH, "w") as f:
        json.dump(feedback_list, f, indent=2)


def get_next_id(feedback_list: list) -> int:
    if not feedback_list:
        return 1
    return max(item["id"] for item in feedback_list) + 1


def validate_feedback_data(data: dict) -> str | None:
    required = ["course_name", "instructor_name", "rating", "category", "feedback_text"]
    missing = [field for field in required if field not in data or not data[field]]
    if missing:
        missing.sort()
        return f"Missing required fields: {', '.join(missing)}"
    # rating must be convertible to int and 1-5
    try:
        rating = int(data["rating"])
    except (ValueError, TypeError):
        return "rating must be an integer between 1 and 5"
    if rating < 1 or rating > 5:
        return "rating must be between 1 and 5"
    if data["category"] not in ["Teaching", "Assessment", "Materials", "Pace", "Engagement"]:
        return f"Invalid category. Must be one of: Teaching, Assessment, Materials, Pace, Engagement"
    return None


@app.route("/")
def index():
    return send_from_directory(app.root_path, "index.html")


@app.route("/generated_hero.png")
def hero_image():
    return send_from_directory(app.root_path, "generated_hero.png")


@app.route("/api/health", methods=["GET"])
def health():
    return jsonify({"status": "ok", "app": "course-feedback-analysis"})


@app.route("/api/feedback", methods=["GET"])
def get_feedback():
    feedback_list = load_feedback()
    return jsonify({"feedback": feedback_list})


@app.route("/api/feedback", methods=["POST"])
def post_feedback():
    data = request.get_json(force=True)
    error = validate_feedback_data(data)
    if error:
        return jsonify({"error": error}), 400

    feedback_list = load_feedback()
    new_id = get_next_id(feedback_list)
    rating = int(data["rating"])
    if rating >= 4:
        sentiment = "positive"
    elif rating == 3:
        sentiment = "neutral"
    else:
        sentiment = "negative"

    new_feedback = {
        "id": new_id,
        "course_name": data["course_name"],
        "instructor_name": data["instructor_name"],
        "rating": rating,
        "category": data["category"],
        "feedback_text": data["feedback_text"],
        "sentiment": sentiment,
        "created_at": datetime.utcnow().isoformat()
    }
    feedback_list.append(new_feedback)
    save_feedback(feedback_list)

    return jsonify({"message": "Feedback submitted successfully.", "feedback": new_feedback}), 201


@app.route("/api/summary", methods=["GET"])
def summary():
    feedback_list = load_feedback()
    total = len(feedback_list)
    if total == 0:
        return jsonify({
            "total_feedback": 0,
            "average_rating": 0,
            "positive_ratio": 0,
            "top_category": None,
            "category_counts": {}
        })

    ratings = [item["rating"] for item in feedback_list]
    avg_rating = round(sum(ratings) / total, 2)
    positive_count = sum(1 for r in ratings if r >= 4)
    positive_ratio = round((positive_count / total) * 100, 2)

    category_counts = {}
    for item in feedback_list:
        cat = item["category"]
        category_counts[cat] = category_counts.get(cat, 0) + 1
    top_category = max(category_counts, key=category_counts.get) if category_counts else None

    return jsonify({
        "total_feedback": total,
        "average_rating": avg_rating,
        "positive_ratio": positive_ratio,
        "top_category": top_category,
        "category_counts": category_counts
    })


if __name__ == "__main__":
    options = get_runtime_options()
    app.run(host=options["host"], port=options["port"], debug=options["debug"])
