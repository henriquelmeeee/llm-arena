# TODO tem q arrumar erro q o topico "all" n vai no /all
# IDEIA no topico de coding, dar codigos que não tem problema e depois inventar um problema
# pra testar alucinação da IA
from flask import Flask, render_template, request, g, redirect, flash
from flask_cors import CORS
from flask_sqlalchemy import SQLAlchemy
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
import os, random, time
from itertools import combinations

app = Flask(__name__, template_folder="./static", static_folder="./static")
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URL', 'sqlite:///database.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)
app.secret_key = "SDAKldjsafhlkhRIOAUYRH9aiuhrfsad(y)"
CORS(app)

limiter = Limiter(
    app=app,
    key_func=get_remote_address,
    default_limits=["200000000 per day", "5000000000000 per hour"]
)

AIs = {
    0: "ChatGPT-4-Turbo",
    12: "ChatGPT-3.5-Turbo",      # specifically, the "raw" version (if you use poe.com to create the input)
    7: "ChatGPT-4o",
    8: "ChatGPT-4",
    25: "ChatGPT-4o-mini",

    1: "Claude-3.5-Sonnet",
    9: "Claude-3-Sonnet",
    10: "Claude-3-Opus",
    11: "Claude-3-Haiku",

    2: "Llama-3.1-8B",
    3: "Llama-3.1-70B",
    4: "Llama-3.1-405B",
    5: "Llama-3-70B",
    6: "Llama-3-8B",

    13: "Gemma-2-27B", # https://deepinfra.com/google/gemma-2-27b-it
    14: "Gemma-2-9B", # https://deepinfra.com/google/gemma-2-9b-it

    15: "Mixtral-8x22B-Instruct-v0.1",
    16: "Mixtral-8x7B-Instruct-v0.1",
    17: "Openchat-3.6-8b"
    # TODO add more here and update the HTML lists also
}

SUPPORTED_TOPICS = ["all", "following_instructions", "coding", "explaining", "resuming", "creative_writing", "data_analysis", "science", "history", "philosophy", "mathematics", "quantum_physics", "extreme"]

class Output(db.Model):
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    text = db.Column(db.Text, nullable=False)
    the_input = db.Column(db.String(50000), nullable=False)
    ai_id = db.Column(db.Integer, nullable=False)
    topic = db.Column(db.String(20), nullable=False)

class AI(db.Model):
    name = db.Column(db.String(64), nullable=False)
    id = db.Column(db.Integer, primary_key=True)
    description = db.Column(db.String(100), nullable=False)
    coding_votes = db.Column(db.Integer, default=0)
    resuming_votes = db.Column(db.Integer, default=0)
    creative_writing_votes = db.Column(db.Integer, default=0)
    data_analysis_votes = db.Column(db.Integer, default=0)
    science_votes = db.Column(db.Integer, default=0)
    history_votes = db.Column(db.Integer, default=0)
    philosophy_votes = db.Column(db.Integer, default=0)
    mathematics_votes = db.Column(db.Integer, default=0)
    quantum_physics_votes = db.Column(db.Integer, default=0)
    extreme_votes = db.Column(db.Integer, default=0)
    explaining_votes = db.Column(db.Integer, default=0)
    following_instruction_votes = db.Column(db.Integer, default=0)

class Pairs(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    ai1_id = db.Column(db.Integer, db.ForeignKey('ai.id'), nullable=False)
    ai2_id = db.Column(db.Integer, db.ForeignKey('ai.id'), nullable=False)
    ai1_votes = db.Column(db.Integer, default=0)
    ai2_votes = db.Column(db.Integer, default=0)

    __table_args__ = (db.UniqueConstraint('ai1_id', 'ai2_id'),)

from random import choices
display_counts = {ai_id: 0 for ai_id in AIs.keys()}


@app.route('/')
def index():
    return render_template('index.html')

@app.route("/<topic>/")
def select_output(topic):
    global display_counts

    if topic not in SUPPORTED_TOPICS:
        return "Invalid topic", 400

    if topic == "all":
        random_topic = random.choice([t for t in SUPPORTED_TOPICS if t != "all"])
    else:
        random_topic = topic

    # 1. Escolher todas as IAs que têm output para o tópico
    available_ai_ids = db.session.query(Output.ai_id).filter_by(topic=random_topic).distinct().all()
    print(available_ai_ids)
    available_ai_ids = [ai_id for (ai_id,) in available_ai_ids]

    if len(available_ai_ids) < 2:
        return "Not enough AIs with outputs for comparison", 404

    # Calcular pesos inversos à contagem de exibições
    weights = [1 / (display_counts[ai_id] + 1) for ai_id in available_ai_ids]

    try:
        # 2. Escolher o primeiro output aleatório
        first_ai_id = choices(available_ai_ids, weights=weights, k=1)[0]
        first_output = Output.query.filter_by(topic=random_topic, ai_id=first_ai_id).order_by(db.func.random()).first()

        if not first_output:
            raise Exception("No output found for the first AI")

        # 3. Tentar encontrar um segundo output com o mesmo the_input, mas de uma IA diferente
        second_output = Output.query.filter(
            Output.topic == random_topic,
            Output.the_input == first_output.the_input,
            Output.ai_id != first_ai_id,
            Output.ai_id.in_(available_ai_ids)
        ).order_by(db.func.random()).first()

        if not second_output:
            raise Exception("No matching output found for the second AI")

    except Exception as e:
        print(f"Exception occurred: {e}")
        # Se não der certo, pegar um output aleatório e outro de qualquer IA
        first_output = Output.query.filter_by(topic=random_topic).order_by(db.func.random()).first()
        
        if not first_output:
            return "No outputs available for this topic", 404

        second_output = Output.query.filter(
            Output.topic == random_topic,
            Output.the_input == first_output.the_input,
            Output.ai_id != first_output.ai_id
        ).order_by(db.func.random()).first()

        if not second_output:
            return "Unable to find a pair of outputs for comparison", 404

    # Atualizar as contagens de exibição
    display_counts[first_output.ai_id] += 1
    display_counts[second_output.ai_id] += 1

    # Obter os nomes das IAs
    ai1_name = AIs.get(first_output.ai_id, f"Unknown AI (ID: {first_output.ai_id})")
    ai2_name = AIs.get(second_output.ai_id, f"Unknown AI (ID: {second_output.ai_id})")

    print(f"AI 1: {ai1_name} (ID: {first_output.ai_id})")
    print(f"AI 2: {ai2_name} (ID: {second_output.ai_id})")
    first_output.text = first_output.text.replace("<", "˂").replace(">", "˃")
    second_output.text = second_output.text.replace("<", "˂").replace(">", "˃")

    return render_template('compare.html',
                           out1=first_output,
                           out2=second_output,
                           ai1_name=ai1_name,
                           ai2_name=ai2_name,
                           ai1_id=first_output.ai_id,
                           ai2_id=second_output.ai_id,
                           topic=random_topic)

@app.route("/select/")
@limiter.limit("1 per 2 seconds")
def select_preferred():
    ai1_id = request.args.get('ai1', type=int)
    ai2_id = request.args.get('ai2', type=int)
    ai1_rating = request.args.get('ai1_vote', type=int)
    ai2_rating = request.args.get('ai2_vote', type=int)
    topic = request.args.get('topic')

    if topic not in SUPPORTED_TOPICS:
        return "Invalid topic", 400

    if not all(0 <= rating <= 4 for rating in (ai1_rating, ai2_rating)):
        return "Invalid rating", 400

    pair = Pairs.query.filter(
        ((Pairs.ai1_id == ai1_id) & (Pairs.ai2_id == ai2_id)) |
        ((Pairs.ai1_id == ai2_id) & (Pairs.ai2_id == ai1_id))
    ).first()

    if not pair:
        return "Pair not found", 404

    def calculate_score(rating):
        score_map = {0: -2, 1: -1, 2: 1, 3: 2, 4: 3}
        return score_map[rating]

    ai1_score = calculate_score(ai1_rating)
    ai2_score = calculate_score(ai2_rating)

    ai1 = AI.query.get(ai1_id)
    ai2 = AI.query.get(ai2_id)

    if not ai1 or not ai2:
        return "AI not found", 404

    # Update votes for the specific topic
    for ai, score in [(ai1, ai1_score), (ai2, ai2_score)]:
        vote_attr = f"{topic}_votes"
        if hasattr(ai, vote_attr):
            current_votes = getattr(ai, vote_attr)
            setattr(ai, vote_attr, current_votes + score)
        else:
            return f"AI has no attr", 500

    # Update pair votes
    pair.ai1_votes += ai1_score
    pair.ai2_votes += ai2_score

    db.session.commit()

    return "Votes updated successfully", 200

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
        AI.resuming_votes,
        AI.explaining_votes,
        AI.creative_writing_votes,
        AI.data_analysis_votes,
        AI.science_votes,
        AI.history_votes,
        AI.philosophy_votes,
        AI.mathematics_votes,
        AI.quantum_physics_votes,
        AI.following_instruction_votes,
        AI.extreme_votes,
        (AI.coding_votes + AI.resuming_votes + AI.creative_writing_votes + 
         AI.data_analysis_votes + AI.science_votes + AI.history_votes + 
         AI.philosophy_votes + AI.explaining_votes + AI.following_instruction_votes + AI.mathematics_votes + AI.quantum_physics_votes + 
         AI.extreme_votes).label('total_votes')
    ).order_by(db.desc('total_votes')).all()

    formatted_stats = []
    for ai in stats:
        formatted_stats.append({
            'id': ai.id,
            'name': ai.name,
            'coding_votes': format_number(ai.coding_votes),
            'resuming_votes': format_number(ai.resuming_votes),
            'explaining_votes': format_number(ai.explaining_votes),
            'following_instruction_votes': format_number(ai.following_instruction_votes),
            'creative_writing_votes': format_number(ai.creative_writing_votes),
            'data_analysis_votes': format_number(ai.data_analysis_votes),
            'science_votes': format_number(ai.science_votes),
            'history_votes': format_number(ai.history_votes),
            'philosophy_votes': format_number(ai.philosophy_votes),
            'mathematics_votes': format_number(ai.mathematics_votes),
            'quantum_physics_votes': format_number(ai.quantum_physics_votes),
            'extreme_votes': format_number(ai.extreme_votes),
            'total_votes': format_number(ai.total_votes)
        })

    return render_template('statistics.html', stats=formatted_stats)

@app.route("/statistics/compare/")
def statistics_compare():
    all_pairs = db.session.query(Pairs).all()
    pairs_list = []

    for pair in all_pairs:
        ai1 = AI.query.get(pair.ai1_id)
        ai2 = AI.query.get(pair.ai2_id)
        
        pair_info = [
            pair.id,
            ai1.name,
            ai2.name,
            pair.ai1_votes,
            pair.ai2_votes,
            pair.ai1_votes + pair.ai2_votes
        ]
        
        pairs_list.append(pair_info)
    return render_template("statistics_compare.html", all_pairs=all_pairs)

def init_db():
    db.create_all()
    if not Output.query.first():
        pass
    if not AI.query.first():
        for ai_id, ai_name in AIs.items():
            db.session.add(AI(id=ai_id, description="aa", name=ai_name))
        db.session.commit()
    
    if not Pairs.query.first():
        ai_ids = list(AIs.keys())
        for ai1_id, ai2_id in combinations(ai_ids, 2):
            new_pair = Pairs(ai1_id=ai1_id, ai2_id=ai2_id)
            db.session.add(new_pair)
        db.session.commit()

admin_mode=False

@app.route('/admin/')
def add_entry_form():
    if admin_mode:
        return render_template('admin.html')

@app.route('/add_entry/', methods=['POST'])
def add_entry():
    if admin_mode:
        topic = request.form['topic']
        input_text = request.form['input']
        ai_id = int(request.form['ai'])
        output_text = request.form['output']

        if topic not in SUPPORTED_TOPICS:
            return "Invalid topic", 400
        
        # TODO FIXME Maybe we need to check if the AI ID is correct?

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
        try:
            from sqlalchemy import Column, Integer, text
        
            # Adiciona a nova coluna 'explaining_votes' com valor default 0
            with db.engine.connect() as conn:
                #conn.execute(text('ALTER TABLE ai ADD COLUMN explaining_votes INTEGER DEFAULT 0'))
                conn.execute(text('ALTER TABLE ai ADD COLUMN following_instruction_votes INTEGER DEFAULT 0'))
        except:
            pass
        init_db()
    app.run(debug=os.getenv('FLASK_DEBUG', 'False').lower() == 'true', port=80, host="0.0.0.0")
