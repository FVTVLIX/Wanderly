import os
import json
import random
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
    openai_key = db.Column(db.String(200), nullable=True)
    anthropic_key = db.Column(db.String(200), nullable=True)
    gemini_key = db.Column(db.String(200), nullable=True)
    searches = db.relationship('SearchHistory', backref='author', lazy=True)
    saved_strategies = db.relationship('SavedStrategy', backref='author', lazy=True)
    trips = db.relationship('Trip', backref='author', lazy=True)

class SearchHistory(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    search_query = db.Column(db.Text, nullable=False)
    results = db.Column(db.Text, nullable=True) # Stores JSON string of search results
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
    return db.session.get(User, int(user_id))

# --- Configuration ---
from openai import OpenAI
from anthropic import Anthropic
import google.generativeai as genai

openai_client = None
anthropic_client = None
gemini_available = False

if os.getenv("OPENAI_API_KEY"):
    openai_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

if os.getenv("ANTHROPIC_API_KEY"):
    anthropic_client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

if os.getenv("GOOGLE_API_KEY"):
    genai.configure(api_key=os.getenv("GOOGLE_API_KEY"))
    gemini_available = True

# --- Encryption ---
from cryptography.fernet import Fernet

encryption_key = os.getenv("ENCRYPTION_KEY")
cipher_suite = Fernet(encryption_key) if encryption_key else None

def encrypt_value(value):
    """Encrypts a string value."""
    if not value or not cipher_suite:
        return value
    try:
        return cipher_suite.encrypt(value.encode()).decode()
    except Exception as e:
        print(f"Encryption error: {e}")
        return value

def decrypt_value(value):
    """Decrypts a string value."""
    if not value or not cipher_suite:
        return value
    try:
        return cipher_suite.decrypt(value.encode()).decode()
    except Exception:
        # If decryption fails, assume it's a legacy plain text key or invalid
        return value

# --- Helper Functions ---
def mock_generation():
    """Returns hardcoded detailed strategies for testing."""
    return [
        {
            "title": "Strategy 1: The 'Kitchen of Japan' Deep Dive",
            "summary": "Focus entirely on the Kansai region (Osaka, Kyoto, Nara) to maximize food and history while saving on transport.",
            "cost_breakdown": {
                "flights": "$2600",
                "lodging": "$800",
                "food": "$1000",
                "transport": "$300",
                "activities": "$300",
                "total": "$5000",
                "currency": "USD"
            },
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
            "cost_breakdown": {
                "flights": "$2400",
                "lodging": "$900",
                "food": "$800",
                "transport": "$600",
                "activities": "$300",
                "total": "$5000",
                "currency": "USD"
            },
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
            "cost_breakdown": {
                "flights": "$2400",
                "lodging": "$900",
                "food": "$700",
                "transport": "$700",
                "activities": "$300",
                "total": "$5000",
                "currency": "USD"
            },
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
    prompt = f"""
    You are a travel planning expert. Break down the following problem into 3 distinct high-level approaches or strategies. 
    Problem: {problem}. 
    
    Output strictly as a JSON list of objects. Each object must have:
    - 'title': string
    - 'summary': string (1-2 sentences)
    - 'cost_breakdown': object with keys: 'flights', 'lodging', 'food', 'transport', 'activities', 'total', 'currency'. Estimate costs realistically.
    - 'itinerary': list of objects, each with 'day' (int), 'title' (string), and 'activities' (list of {{'name', 'type' (food/history/other), 'description'}}).
    - 'locations': list of objects with 'name', 'lat' (float), 'lon' (float) for major cities visited.
    """

    content = None
    
    # Check for user-provided keys first
    user_gemini_key = decrypt_value(current_user.gemini_key) if current_user.is_authenticated and current_user.gemini_key else os.getenv("GOOGLE_API_KEY")
    user_openai_key = decrypt_value(current_user.openai_key) if current_user.is_authenticated and current_user.openai_key else os.getenv("OPENAI_API_KEY")
    user_anthropic_key = decrypt_value(current_user.anthropic_key) if current_user.is_authenticated and current_user.anthropic_key else os.getenv("ANTHROPIC_API_KEY")

    print(f"Keys available - Gemini: {bool(user_gemini_key)}, OpenAI: {bool(user_openai_key)}, Anthropic: {bool(user_anthropic_key)}")

    # 1. Try Google Gemini
    if user_gemini_key:
        try:
            print("Using Google Gemini...")
            genai.configure(api_key=user_gemini_key)
            model = genai.GenerativeModel('gemini-2.5-flash')
            response = model.generate_content(prompt, generation_config={"response_mime_type": "application/json"})
            content = response.text
            print("Gemini response received.")
        except Exception as e:
            print(f"Gemini error: {e}")
            content = None

    # 2. Try OpenAI
    if not content and user_openai_key:
        try:
            print("Using OpenAI...")
            client = OpenAI(api_key=user_openai_key)
            response = client.chat.completions.create(
                model="gpt-4-turbo",
                messages=[
                    {"role": "system", "content": "You are a helpful travel assistant that outputs only valid JSON."},
                    {"role": "user", "content": prompt}
                ],
                response_format={"type": "json_object"}
            )
            content = response.choices[0].message.content
            print("OpenAI response received.")
        except Exception as e:
            print(f"OpenAI error: {e}")
            content = None

    # 3. Try Anthropic
    if not content and user_anthropic_key:
        try:
            print("Using Anthropic (Haiku)...")
            client = Anthropic(api_key=user_anthropic_key)
            message = client.messages.create(
                model="claude-3-haiku-20240307",
                max_tokens=4000,
                temperature=0.7,
                system="You are a helpful travel assistant that outputs only valid JSON.",
                messages=[
                    {"role": "user", "content": prompt}
                ]
            )
            content = message.content[0].text
            print("Anthropic response received.")
        except Exception as e:
            print(f"Anthropic error: {e}")
            content = None

    if not content:
        print("No content generated from any provider.")
        return []

    try:
        # Clean up potential markdown formatting
        content = content.replace('```json', '').replace('```', '').strip()
        
        # Attempt to find the first '[' and last ']' to extract the list
        import re
        match = re.search(r'\[.*\]', content, re.DOTALL)
        if match:
            content = match.group(0)
        
        # Ensure it's a list
        try:
            data = json.loads(content)
        except json.JSONDecodeError:
            # Fallback: Try to fix common JSON errors (like trailing commas)
            # This is a simple heuristic; for production, a robust library like `json5` or `dirtyjson` is better.
            # Here we just try to remove trailing commas before closing brackets/braces
            content_fixed = re.sub(r',\s*([\]}])', r'\1', content)
            data = json.loads(content_fixed)
        
        if isinstance(data, dict):
            if 'strategies' in data and isinstance(data['strategies'], list):
                return data['strategies']
            # If the LLM returned a single strategy object, wrap it in a list
            if 'title' in data and 'summary' in data:
                return [data]
            return []
            
        if isinstance(data, list):
            # Filter out non-dict items
            return [item for item in data if isinstance(item, dict)]
            
        return []
    except Exception as e:
        print(f"Error parsing JSON: {e}")
        print(f"Raw content: {content}")
        return []

def critique_strategy_llm(strategy_content):
    try:
        strategy_str = json.dumps(strategy_content)
        prompt = f"Act as a harsh travel critic. Analyze this strategy: {strategy_str}. Evaluate feasibility, balance, and budget. Give a score 1-10. Output JSON with keys: 'critique', 'score'."

        content = None

        # Check for user-provided keys first
        user_gemini_key = decrypt_value(current_user.gemini_key) if current_user.is_authenticated and current_user.gemini_key else os.getenv("GOOGLE_API_KEY")
        user_openai_key = decrypt_value(current_user.openai_key) if current_user.is_authenticated and current_user.openai_key else os.getenv("OPENAI_API_KEY")
        user_anthropic_key = decrypt_value(current_user.anthropic_key) if current_user.is_authenticated and current_user.anthropic_key else os.getenv("ANTHROPIC_API_KEY")

        # 1. Try Google Gemini
        if user_gemini_key:
            try:
                genai.configure(api_key=user_gemini_key)
                model = genai.GenerativeModel('gemini-2.5-flash')
                response = model.generate_content(prompt, generation_config={"response_mime_type": "application/json"})
                content = response.text
            except Exception as e:
                print(f"Gemini critique error: {e}")
                content = None

        # 2. Try OpenAI
        if not content and user_openai_key:
            try:
                client = OpenAI(api_key=user_openai_key)
                response = client.chat.completions.create(
                    model="gpt-4-turbo",
                    messages=[
                        {"role": "system", "content": "You are a critic that outputs only valid JSON."},
                        {"role": "user", "content": prompt}
                    ],
                    response_format={"type": "json_object"}
                )
                content = response.choices[0].message.content
            except Exception as e:
                print(f"OpenAI critique error: {e}")
                content = None

        # 3. Try Anthropic
        if not content and user_anthropic_key:
            try:
                client = Anthropic(api_key=user_anthropic_key)
                message = client.messages.create(
                    model="claude-3-haiku-20240307",
                    max_tokens=1000,
                    temperature=0.7,
                    system="You are a critic that outputs only valid JSON.",
                    messages=[
                        {"role": "user", "content": prompt}
                    ]
                )
                content = message.content[0].text
            except Exception as e:
                print(f"Anthropic critique error: {e}")
                content = None

        if not content:
            return {"critique": "Could not generate critique.", "score": 0}
        
        content = content.replace('```json', '').replace('```', '').strip()
        return json.loads(content)

    except Exception as e:
        print(f"Error critiquing strategy: {e}")
        return {"critique": "Error generating critique.", "score": 0}

# --- Routes ---

@app.route('/')
def index():
    trending_searches = [
        {"label": "Kyoto", "query": "Kyoto in Spring"},
        {"label": "Iceland", "query": "Iceland Road Trip"},
        {"label": "Amalfi", "query": "Amalfi Coast Luxury"},
        {"label": "Tokyo", "query": "Tokyo Food Tour"},
        {"label": "Paris", "query": "Paris Romantic Getaway"},
        {"label": "Bali", "query": "Bali Wellness Retreat"},
        {"label": "New York", "query": "NYC Art & Culture"},
        {"label": "Patagonia", "query": "Patagonia Hiking Adventure"},
        {"label": "Santorini", "query": "Santorini Sunset Views"},
        {"label": "Cape Town", "query": "Cape Town Wine & Safari"},
        {"label": "Swiss Alps", "query": "Swiss Alps Ski Trip"},
        {"label": "Machu Picchu", "query": "Machu Picchu Trek"}
    ]
    # Select 4 random trending searches
    selected_trending = random.sample(trending_searches, 4)
    return render_template('index.html', trending=selected_trending)

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
    query = request.form.get('query')
    origin = request.form.get('origin')
    
    problem = query
    if origin:
        problem = f"{query} (Starting from {origin})"
    
    # 1. Generate Strategies (Mock or Real)
    # Check if ANY key is available (User or System)
    has_gemini = (current_user.is_authenticated and current_user.gemini_key) or os.getenv("GOOGLE_API_KEY")
    has_openai = (current_user.is_authenticated and current_user.openai_key) or os.getenv("OPENAI_API_KEY")
    has_anthropic = (current_user.is_authenticated and current_user.anthropic_key) or os.getenv("ANTHROPIC_API_KEY")
    
    use_mock = not (has_gemini or has_openai or has_anthropic)
    
    if use_mock:
        print("Using mock generation (no keys available).")
        strategies = mock_generation()
    else:
        print("Attempting LLM generation...")
        raw_strategies = generate_strategies_llm(problem)
        strategies = []
        for s in raw_strategies:
            if not isinstance(s, dict):
                continue
            critique_data = critique_strategy_llm(s)
            s['critique'] = critique_data.get('critique', 'No critique available.')
            s['score'] = critique_data.get('score', 0)
            strategies.append(s)
        
        if not strategies:
            print("LLM generation failed or returned empty. Falling back to mock data.")
            flash("AI generation failed. Showing example strategies instead.", "warning")
            strategies = mock_generation()
            
    # Sort by score
    strategies.sort(key=lambda x: x.get('score', 0), reverse=True)
    
    if current_user.is_authenticated:
        new_search = SearchHistory(
            search_query=problem, 
            results=json.dumps(strategies),
            user_id=current_user.id
        )
        db.session.add(new_search)
        db.session.commit()
        return redirect(url_for('show_results', search_id=new_search.id))
    else:
        # Fallback for anonymous users: render directly
        return render_template('results.html', problem=problem, strategies=strategies)

@app.route('/results/<int:search_id>')
@login_required
def show_results(search_id):
    search = SearchHistory.query.get_or_404(search_id)
    if search.author != current_user:
        return redirect(url_for('index'))
        
    strategies = json.loads(search.results) if search.results else []
    return render_template('results.html', problem=search.search_query, strategies=strategies)

@app.route('/profile')
@login_required
def profile():
    history = SearchHistory.query.filter_by(user_id=current_user.id).order_by(SearchHistory.timestamp.desc()).limit(10).all()
    saved_raw = SavedStrategy.query.filter_by(user_id=current_user.id).all()
    trips = Trip.query.filter_by(user_id=current_user.id).order_by(Trip.start_date.asc()).all()
    
    trips = Trip.query.filter_by(user_id=current_user.id).order_by(Trip.start_date.asc()).all()
    
    trips = Trip.query.filter_by(user_id=current_user.id).order_by(Trip.start_date.asc()).all()
    return render_template('profile.html', trips=trips, saved_strategies=saved_raw, search_history=history)

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
    
    # Extract location for image
    image_keyword = "travel"
    if parsed_content.get('locations') and len(parsed_content['locations']) > 0:
        image_keyword = parsed_content['locations'][0]['name']
    
    return render_template('strategy_details.html', strategy=strategy, details=parsed_content, image_keyword=image_keyword)

@app.route('/delete_strategy/<int:id>', methods=['POST'])
@login_required
def delete_strategy(id):
    strategy = SavedStrategy.query.get_or_404(id)
    if strategy.author != current_user:
        flash('You cannot delete this strategy.')
        return redirect(url_for('profile'))
    
    # Delete associated trips first
    # Unlink associated trips instead of deleting them
    associated_trips = Trip.query.filter_by(strategy_id=id).all()
    for trip in associated_trips:
        trip.strategy_id = None
    
    db.session.delete(strategy)
    db.session.commit()
    flash('Strategy deleted successfully.')
    return redirect(url_for('profile'))

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

@app.route('/delete_trip/<int:id>', methods=['POST'])
@login_required
def delete_trip(id):
    trip = Trip.query.get_or_404(id)
    if trip.user_id != current_user.id:
        flash('You cannot delete this trip.')
        return redirect(url_for('profile'))
    
    db.session.delete(trip)
    db.session.commit()
    flash('Trip cancelled successfully.')
    return redirect(url_for('profile'))

@app.route('/settings')
@login_required
def settings():
    print("Accessing settings page...")
    return render_template('settings.html')

@app.route('/update_api_keys', methods=['POST'])
@login_required
def update_api_keys():
    current_user.openai_key = encrypt_value(request.form.get('openai_key'))
    current_user.anthropic_key = encrypt_value(request.form.get('anthropic_key'))
    current_user.gemini_key = encrypt_value(request.form.get('gemini_key'))
    db.session.commit()
    flash('API Keys updated successfully.')
    return redirect(url_for('settings'))

@app.route('/verify_api_key', methods=['POST'])
@login_required
def verify_api_key():
    data = request.json
    provider = data.get('provider')
    # The key coming from the frontend might be the raw input (if testing before saving)
    # or it might be the saved encrypted key if we were to implement a "Test Saved Key" feature.
    # For now, this route is likely used by a "Test" button next to the input field, sending the raw input.
    # However, if we want to be safe, we can check.
    key = data.get('key')
    
    if not key:
        return jsonify({'status': 'error', 'message': 'No key provided'})

    try:
        if provider == 'gemini':
            genai.configure(api_key=key)
            model = genai.GenerativeModel('gemini-2.5-flash')
            # Simple generation test
            model.generate_content("Hello", generation_config={"max_output_tokens": 5})
            return jsonify({'status': 'success'})
            
        elif provider == 'openai':
            client = OpenAI(api_key=key)
            client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[{"role": "user", "content": "Hello"}],
                max_tokens=5
            )
            return jsonify({'status': 'success'})
            
        elif provider == 'anthropic':
            client = Anthropic(api_key=key)
            client.messages.create(
                model="claude-3-haiku-20240307",
                max_tokens=5,
                messages=[{"role": "user", "content": "Hello"}]
            )
            return jsonify({'status': 'success'})
            
        return jsonify({'status': 'error', 'message': 'Invalid provider'})
        
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)})

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True, port=5001)
