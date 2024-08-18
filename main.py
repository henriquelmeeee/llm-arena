from flask import Flask, render_template, request, g, redirect, flash
from flask_sqlalchemy import SQLAlchemy
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
import time
import os


app = Flask(__name__, template_folder="./static", static_folder="./static")
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URL', 'sqlite:///database.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)
app.secret_key = "SDAKldjsafhlkhRIOAUYRH9aiuhrfsad(y)"
limiter = Limiter(
    app=app,
    key_func=get_remote_address,
    default_limits=["200 per day", "50 per hour"]
)

AIs = {
    0: "ChatGPT-4-Turbo",
    1: "Claude-3.5-Sonnet",
    2: "Llama-3.1-8B",
    3: "Llama-3.1-70B",
    4: "Llama-3.1-405B",
    5: "Llama-3-70B",
    6: "Llama-3-8B"
}

# TODO support foreign_language_votes in DB
SUPPORTED_TOPICS = ["coding", "resumes", "foreign_language"]

class Output(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    text = db.Column(db.Text, nullable=False)
    the_input = db.Column(db.String(50000), nullable=False)
    ai_id = db.Column(db.Integer, nullable=False)
    topic = db.Column(db.String(20), nullable=False)

class AI(db.Model):
    name = db.Column(db.String(64), nullable=False)
    id = db.Column(db.Integer, primary_key=True)
    description = db.Column(db.String(100), nullable=False)
    portuguese_votes = db.Column(db.Integer, default=0)
    english_votes = db.Column(db.Integer, default=0)

@app.route('/')
def index():
    return render_template('index.html')

@app.route("/<topic>/")
def select_output(topic):
    if topic not in SUPPORTED_TOPICS:
        return "Invalid topic", 400

    random_output_1 = Output.query.filter_by(topic=topic).order_by(db.func.random()).first()
    if not random_output_1:
        return "No outputs found for the specified topic", 404
    random_output_2 = Output.query.filter_by(topic=topic, the_input=random_output_1.the_input).filter(Output.id != random_output_1.id).order_by(db.func.random()).first()
    
    if not random_output_2:
        return "Not enough outputs for comparison", 404

    return render_template('compare.html', out1=random_output_1, out2=random_output_2)

@app.route("/select/<topic_and_id>")
@limiter.limit("1 per 2 seconds")
def select_prefered(topic_and_id):
    try:
        topic, output_id = topic_and_id.split("_")
        output_id = int(output_id)
    except ValueError:
        return "Invalid input format", 400

    if topic not in SUPPORTED_TOPICS:
        return "Invalid topic", 400

    output = Output.query.get(output_id)
    if not output:
        return "Output not found", 404

    ai = AI.query.get(output.ai_id)
    if not ai:
        return "AI not found", 404

    if topic == "coding":
        ai.coding_votes += 1
    elif topic == "resumes":
        ai.resumes_votes += 1
    # foreign_language here and etc

    db.session.commit()

    return AIs[ai.id], 200

def format_number(num):
    if num < 1000:
        return str(num)
    elif num < 1000000:
        return f"{num/1000:.1f}k".rstrip('0').rstrip('.')
    elif num < 1000000000:
        return f"{num/1000000:.1f}m".rstrip('0').rstrip('.')
    else:
        return f"{num/1000000000:.1f}b".rstrip('0').rstrip('.')

from sqlalchemy import case, func

@app.route("/statistics/")
def statistics():
    stats = db.session.query(
        AI.id,
        AI.name,
        AI.coding_votes,
        AI.resumes_votes,
        (AI.coding_votes + AI.resumes_votes).label('total_votes')
    ).order_by((AI.coding_votes + AI.resumes_votes).desc()).all()

    formatted_stats = []
    for ai in stats:
        formatted_stats.append({
            'id': ai.id,
            'name': ai.name,
            'english_votes': format_number(ai.coding_votes),
            'portuguese_votes': format_number(ai.resumes_votes),
            'total_votes': format_number(ai.total_votes)
        })

    return render_template('statistics.html', stats=formatted_stats)

def init_db():
    db.create_all()
    if not Output.query.first():
        #db.session.add(Output(id=1, text='teste1', the_input='input1', ai_id=1, language='portuguese'))
        #db.session.add(Output(id=2, text='teste2', the_input='input1', ai_id=2, language='portuguese'))
        #db.session.commit()
        pass
    if not AI.query.first():
        for ai_id, ai_name in AIs.items():
            db.session.add(AI(id=ai_id, description="aa", name=ai_name))
        db.session.commit()

admin_mode=True

@app.route('/admin/')
def add_entry_form():
    if admin_mode:
        return render_template('admin.html')

@app.route('/add_entry', methods=['POST'])
def add_entry():
    topic = request.form['topic']
    input_text = request.form['input']
    ai_id = int(request.form['ai'])
    output_text = request.form['output']

    if topic not in SUPPORTED_TOPICS:
        return "Invalid topic", 400

    new_entry = Output(text=output_text, the_input=input_text, ai_id=ai_id, topic=topic)
    db.session.add(new_entry)
    db.session.commit()

    return redirect("/admin/")

@app.route("/suggest-specific-input/")
def suggest_specific_input():
    return render_template("suggest_specific_input.html")

class Suggestion(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    input_text = db.Column(db.Text, nullable=False)
    timestamp = db.Column(db.DateTime, default=db.func.current_timestamp())

@app.route("/add-suggest/", methods=["POST"])
@limiter.limit("5 per minute")
def add_suggest():
    input_suggestion = request.form.get('inputSuggestion')
    
    if not input_suggestion or input_suggestion.strip() == '':
        flash('Your suggestion needs to be valid.', 'error')
        return redirect("/suggest-specific-input/")
    
    new_suggestion = Suggestion(input_text=input_suggestion)
    db.session.add(new_suggestion)
    db.session.commit()
    
    flash('We got your suggestion. Thank you!', 'success')
    return redirect("/suggest-specific-input/")

if __name__ == '__main__':
    with app.app_context():
        init_db()
    app.run(debug=os.getenv('FLASK_DEBUG', 'False').lower() == 'true')
