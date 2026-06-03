from flask import Flask, request, jsonify, send_from_directory
import json
import os
from pathlib import Path
from datetime import datetime

app = Flask(__name__)

DATA_PATH = Path(app.root_path) / 'seed_feedback.json'


def get_runtime_options():
    host = os.environ.get('FLASK_HOST', '0.0.0.0')
    port = int(os.environ.get('PORT', 5000))
    debug_env = os.environ.get('FLASK_DEBUG', '').lower()
    debug = debug_env in ('true', '1', 'yes')
    return {'host': host, 'port': port, 'debug': debug}


def load_feedback():
    if DATA_PATH.exists():
        with open(DATA_PATH, 'r') as f:
            return json.load(f)
    return []


def save_feedback(feedback_list):
    with open(DATA_PATH, 'w') as f:
        json.dump(feedback_list, f, indent=2)


def compute_sentiment(rating):
    if rating >= 4:
        return 'positive'
    elif rating == 3:
        return 'neutral'
    else:
        return 'negative'


@app.route('/')
def index():
    return send_from_directory(app.root_path, 'index.html')


@app.route('/generated_hero.png')
def hero_image():
    return send_from_directory(app.root_path, 'generated_hero.png')


@app.route('/api/health', methods=['GET'])
def health():
    return jsonify({'status': 'ok', 'app': 'course-feedback-analysis'})


@app.route('/api/feedback', methods=['GET'])
def get_feedback():
    feedback_list = load_feedback()
    return jsonify({'feedback': feedback_list})


@app.route('/api/feedback', methods=['POST'])
def post_feedback():
    feedback_list = load_feedback()
    data = request.get_json()
    if not data:
        return jsonify({'error': 'Invalid JSON'}), 400

    required_fields = ['course_name', 'instructor_name', 'rating', 'category', 'feedback_text']
    missing = [f for f in required_fields if f not in data]
    if missing:
        missing.sort()
        return jsonify({'error': f'Missing required fields: {", ".join(missing)}'}), 400

    # Convert rating to int
    try:
        rating = int(data['rating'])
    except (ValueError, TypeError):
        return jsonify({'error': 'Rating must be an integer'}), 400

    if not (1 <= rating <= 5):
        return jsonify({'error': 'Rating must be between 1 and 5'}), 400

    category = data['category']
    valid_categories = ['Teaching', 'Assessment', 'Materials', 'Pace', 'Engagement']
    if category not in valid_categories:
        return jsonify({'error': f'Invalid category. Must be one of {valid_categories}'}), 400

    # Assign id
    if feedback_list:
        new_id = max(fb['id'] for fb in feedback_list) + 1
    else:
        new_id = 1

    feedback_entry = {
        'id': new_id,
        'course_name': data['course_name'],
        'instructor_name': data['instructor_name'],
        'rating': rating,
        'category': category,
        'feedback_text': data['feedback_text'],
        'sentiment': compute_sentiment(rating),
        'created_at': datetime.utcnow().isoformat()
    }
    feedback_list.append(feedback_entry)
    save_feedback(feedback_list)

    return jsonify({'message': 'Feedback submitted successfully.', 'feedback': feedback_entry}), 201


@app.route('/api/summary', methods=['GET'])
def summary():
    feedback_list = load_feedback()
    total = len(feedback_list)
    if total == 0:
        return jsonify({
            'total_feedback': 0,
            'average_rating': 0,
            'positive_ratio': 0,
            'top_category': None,
            'category_counts': {}
        })

    avg_rating = sum(fb['rating'] for fb in feedback_list) / total
    positive_count = sum(1 for fb in feedback_list if fb['rating'] >= 4)
    positive_ratio = round((positive_count / total) * 100, 2)

    from collections import Counter
    category_counts = Counter(fb['category'] for fb in feedback_list)
    top_category = category_counts.most_common(1)[0][0] if category_counts else None

    return jsonify({
        'total_feedback': total,
        'average_rating': round(avg_rating, 2),
        'positive_ratio': positive_ratio,
        'top_category': top_category,
        'category_counts': dict(category_counts)
    })


if __name__ == '__main__':
    opts = get_runtime_options()
    app.run(host=opts['host'], port=opts['port'], debug=opts['debug'])
