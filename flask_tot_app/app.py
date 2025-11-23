import os
import json
from datetime import datetime, timedelta
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from dotenv import load_dotenv
import openai

load_dotenv()

app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'dev-secret-key')
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///site.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'

# Configure OpenAI API key
openai.api_key = os.getenv("OPENAI_API_KEY")

# --- Models ---
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(150), unique=True, nullable=False)
    email = db.Column(db.String(150), unique=True, nullable=False)
    password = db.Column(db.String(150), nullable=False)
    searches = db.relationship('SearchHistory', backref='author', lazy=True)
    saved_strategies = db.relationship('SavedStrategy', backref='author', lazy=True)
    trips = db.relationship('Trip', backref='author', lazy=True)

class SearchHistory(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    search_query = db.Column(db.Text, nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)

class SavedStrategy(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    content = db.Column(db.Text, nullable=False) # Stores JSON string of the full strategy details
    critique = db.Column(db.Text, nullable=True)
    score = db.Column(db.Float, nullable=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    trips = db.relationship('Trip', backref='strategy', lazy=True)

class Trip(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    destination = db.Column(db.String(100), nullable=False)
    start_date = db.Column(db.DateTime, nullable=False)
    end_date = db.Column(db.DateTime, nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    strategy_id = db.Column(db.Integer, db.ForeignKey('saved_strategy.id'), nullable=True)

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# --- Helper Functions ---
def mock_generation():
    """Returns hardcoded detailed strategies for testing."""
    return [
        {
            "title": "Strategy 1: The 'Kitchen of Japan' Deep Dive",
            "summary": "Focus entirely on the Kansai region (Osaka, Kyoto, Nara) to maximize food and history while saving on transport.",
            "cost_breakdown": "Flights: $2600, Lodging: $800, Food: $1000, Transport: $300, Activities: $300",
            "itinerary": [
                {"day": 1, "title": "Arrival in Osaka", "activities": [{"name": "Dotonbori Street Food", "type": "food", "description": "Eat Takoyaki and Okonomiyaki."}]},
                {"day": 2, "title": "Kyoto History", "activities": [{"name": "Fushimi Inari Shrine", "type": "history", "description": "Hike the 1000 torii gates."}, {"name": "Nishiki Market", "type": "food", "description": "Kyoto's Kitchen."}]},
                {"day": 3, "title": "Nara Day Trip", "activities": [{"name": "Todai-ji Temple", "type": "history", "description": "See the Great Buddha and deer."}]}
            ],
            "locations": [{"name": "Osaka", "lat": 34.6937, "lon": 135.5023}, {"name": "Kyoto", "lat": 35.0116, "lon": 135.7681}],
            "critique": "Feasibility: 9/10. Smart logistical play. Balance: 10/10. Perfect marriage of interests. Budget: 6/10. Flights might blow the budget. Overall Score: 7.5/10",
            "score": 7.5
        },
        {
            "title": "Strategy 2: The 'Samurai & Seafood' Route",
            "summary": "Pair Tokyo with Kanazawa ('Little Kyoto') for a deep dive into Samurai culture and fresh seafood.",
            "cost_breakdown": "Flights: $2400, Lodging: $900, Food: $800, Transport: $600, Activities: $300",
            "itinerary": [
                {"day": 1, "title": "Tokyo Arrival", "activities": [{"name": "Shinjuku Omoide Yokocho", "type": "food", "description": "Yakitori alley dining."}]},
                {"day": 2, "title": "Tokyo Edo History", "activities": [{"name": "Edo-Tokyo Museum", "type": "history", "description": "Learn about the Samurai era."}]},
                {"day": 3, "title": "Travel to Kanazawa", "activities": [{"name": "Omicho Market", "type": "food", "description": "Fresh seafood bowls (Kaisendon)."}]}
            ],
            "locations": [{"name": "Tokyo", "lat": 35.6762, "lon": 139.6503}, {"name": "Kanazawa", "lat": 36.5613, "lon": 136.6562}],
            "critique": "Feasibility: 8/10. Good pace. Balance: 9/10. Strong history/food mix. Budget: 7/10. Hokuriku Arch Pass saves money. Overall Score: 8/10",
            "score": 8.0
        },
        {
            "title": "Strategy 3: The 'Golden Route' Express",
            "summary": "The classic Tokyo and Kyoto itinerary condensed for 7 days, using 'smart luxury' to stay on budget.",
            "cost_breakdown": "Flights: $2400, Lodging: $900, Food: $700, Transport: $700, Activities: $300",
            "itinerary": [
                {"day": 1, "title": "Tokyo Modern & Old", "activities": [{"name": "Meiji Shrine", "type": "history", "description": "Forest oasis in the city."}, {"name": "Harajuku Crepes", "type": "food", "description": "Famous sweet treat."}]},
                {"day": 2, "title": "Kyoto Temples", "activities": [{"name": "Kiyomizu-dera", "type": "history", "description": "Wooden stage temple."}]},
                {"day": 3, "title": "Shojin Ryori", "activities": [{"name": "Tenryu-ji Temple", "type": "food", "description": "Traditional Buddhist vegetarian lunch."}]}
            ],
            "locations": [{"name": "Tokyo", "lat": 35.6762, "lon": 139.6503}, {"name": "Kyoto", "lat": 35.0116, "lon": 135.7681}],
            "critique": "Feasibility: 7/10. A bit rushed. Balance: 8/10. Classic hits. Budget: 5/10. Shinkansen is pricey. Overall Score: 6.5/10",
            "score": 6.5
        }
    ]

def generate_strategies_llm(problem):
    try:
        prompt = f"""
        You are a travel planning expert. Break down the following problem into 3 distinct high-level approaches or strategies. 
        Problem: {problem}. 
        
        Output strictly as a JSON list of objects. Each object must have:
        - 'title': string
        - 'summary': string (1-2 sentences)
        - 'cost_breakdown': string (estimated costs)
        - 'itinerary': list of objects, each with 'day' (int), 'title' (string), and 'activities' (list of {{'name', 'type' (food/history/other), 'description'}}).
        - 'locations': list of objects with 'name', 'lat' (float), 'lon' (float) for major cities visited.
        """
        response = openai.ChatCompletion.create(
            model="gpt-4",
            messages=[{"role": "user", "content": prompt}]
        )
        content = response.choices[0].message.content
        return json.loads(content)
    except Exception as e:
        print(f"Error generating strategies: {e}")
        return []

def critique_strategy_llm(strategy_content):
    try:
        # strategy_content is now a dict, convert to string for the prompt
        strategy_str = json.dumps(strategy_content)
        prompt = f"Act as a harsh travel critic. Analyze this strategy: {strategy_str}. Evaluate feasibility, balance, and budget. Give a score 1-10. Output JSON with keys: 'critique', 'score'."
        response = openai.ChatCompletion.create(
            model="gpt-4",
            messages=[{"role": "user", "content": prompt}]
        )
        content = response.choices[0].message.content
        return json.loads(content)
    except Exception as e:
        print(f"Error critiquing strategy: {e}")
        return {"critique": "Error generating critique.", "score": 0}

# --- Routes ---

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')
        
        if User.query.filter_by(email=email).first():
            flash('Email already exists.')
            return redirect(url_for('register'))
            
        hashed_pw = generate_password_hash(password)
        new_user = User(username=username, email=email, password=hashed_pw)
        db.session.add(new_user)
        db.session.commit()
        login_user(new_user)
        return redirect(url_for('profile'))
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        user = User.query.filter_by(email=email).first()
        
        if user and check_password_hash(user.password, password):
            login_user(user)
            return redirect(url_for('profile'))
        else:
            flash('Login failed. Check email and password.')
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('index'))

@app.route('/analyze', methods=['POST'])
def analyze():
    problem = request.form.get('problem')
    
    if current_user.is_authenticated:
        new_search = SearchHistory(search_query=problem, user_id=current_user.id)
        db.session.add(new_search)
        db.session.commit()

    use_mock = not os.getenv("OPENAI_API_KEY")

    if use_mock:
        strategies = mock_generation()
    else:
        raw_strategies = generate_strategies_llm(problem)
        strategies = []
        for s in raw_strategies:
            critique_data = critique_strategy_llm(s) # Pass the dict directly
            s['critique'] = critique_data.get('critique')
            s['score'] = critique_data.get('score')
            strategies.append(s)

    return render_template('results.html', strategies=strategies, problem=problem)

@app.route('/profile')
@login_required
def profile():
    history = SearchHistory.query.filter_by(user_id=current_user.id).order_by(SearchHistory.timestamp.desc()).limit(10).all()
    saved_raw = SavedStrategy.query.filter_by(user_id=current_user.id).all()
    trips = Trip.query.filter_by(user_id=current_user.id).order_by(Trip.start_date.asc()).all()
    
    # Parse JSON content for display
    saved = []
    for s in saved_raw:
        try:
            s.parsed_content = json.loads(s.content)
            saved.append(s)
        except:
            continue

    return render_template('profile.html', history=history, saved=saved, trips=trips)

@app.route('/save_strategy', methods=['POST'])
@login_required
def save_strategy():
    data = request.json
    strategy_content = {
        "summary": data.get('summary'),
        "cost_breakdown": data.get('cost_breakdown'),
        "itinerary": data.get('itinerary'),
        "locations": data.get('locations')
    }
    
    new_strategy = SavedStrategy(
        title=data['title'],
        content=json.dumps(strategy_content),
        critique=data['critique'],
        score=data['score'],
        user_id=current_user.id
    )
    db.session.add(new_strategy)
    db.session.commit()
    return jsonify({'status': 'success'})

@app.route('/strategy/<int:id>')
@login_required
def strategy_details(id):
    strategy = SavedStrategy.query.get_or_404(id)
    if strategy.author != current_user:
        return redirect(url_for('profile'))
    
    parsed_content = json.loads(strategy.content)
    return render_template('strategy_details.html', strategy=strategy, details=parsed_content)

@app.route('/add_trip', methods=['POST'])
@login_required
def add_trip():
    destination = request.form.get('destination')
    start_date = datetime.strptime(request.form.get('start_date'), '%Y-%m-%d')
    strategy_id = request.form.get('strategy_id')
    
    end_date = None
    if request.form.get('end_date'):
        end_date = datetime.strptime(request.form.get('end_date'), '%Y-%m-%d')
    
    # If strategy is linked, calculate end date if missing, or use strategy title as destination if missing
    if strategy_id:
        strategy = SavedStrategy.query.get(strategy_id)
        if not destination:
            destination = strategy.title
        
        if not end_date:
            # Try to calculate duration from itinerary
            try:
                content = json.loads(strategy.content)
                days = len(content.get('itinerary', []))
                # Default to 7 days if itinerary is empty or parsing fails, otherwise use itinerary length
                duration = days if days > 0 else 7
                end_date = start_date + timedelta(days=duration)
            except:
                end_date = start_date + timedelta(days=7) # Fallback

        # Check if a trip for this strategy already exists for this user
        existing_trip = Trip.query.filter_by(user_id=current_user.id, strategy_id=strategy_id).first()
        if existing_trip:
            existing_trip.start_date = start_date
            existing_trip.end_date = end_date
            # We don't necessarily update destination as user might have customized it, 
            # but for consistency with "Change Date", we keep the destination or update it?
            # Let's keep the destination as is unless it's missing.
            db.session.commit()
            flash('Trip date updated successfully!')
            return redirect(url_for('profile'))

    if not end_date:
         end_date = start_date + timedelta(days=7) # Fallback for manual trips

    new_trip = Trip(
        destination=destination, 
        start_date=start_date, 
        end_date=end_date, 
        user_id=current_user.id,
        strategy_id=strategy_id
    )
    db.session.add(new_trip)
    db.session.commit()
    return redirect(url_for('profile'))

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True)
