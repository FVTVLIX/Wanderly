# Wanderly: AI-Powered Travel Strategist 

> **"Where dreams become journeys, guided by the wisdom of the machine."**

Wanderly is not just another itinerary generator. It is a proof-of-concept application demonstrating the power of the **Tree of Thoughts (ToT)** framework applied to complex lifestyle planning. 

By leveraging Large Language Models (LLMs) like **Google Gemini**, **OpenAI GPT-4**, and **Anthropic Claude**, Wanderly breaks down the vague human desire to "travel somewhere" into concrete, analyzed, and scored strategic options.

---

## The Engine: Tree of Thoughts (ToT) Implementation

Traditional travel apps are linear: you input dates and a destination, and they output a list of hotels. Wanderly thinks differently. It treats travel planning as a **complex reasoning problem** requiring exploration, evaluation, and selection.

### 1. The "Branching" Phase (Generation)
When a user inputs a vague query (e.g., *"I want a food trip in Japan that isn't too expensive"*), Wanderly doesn't just guess one answer. It forks the problem into **three distinct strategic branches**.

*   **Strategy A:** A deep dive into a specific region (e.g., "The Kitchen of Japan: Osaka & Kyoto").
*   **Strategy B:** A thematic route (e.g., "Street Food & Samurai History").
*   **Strategy C:** A logistical optimization (e.g., "The Budget Rail Pass Route").

Each branch is fully fleshed out with unique itineraries, cost breakdowns, and logical reasoning for why it fits the user's request.

### 2. The "Harsh Critic" Phase (Evaluation)
Generating options is easy; evaluating them is hard. Wanderly employs a secondary agentic persona—**The Critic**—to rigorously grade each generated strategy.

This agent does not know which model generated the strategy. It evaluates purely on output quality based on three pillars:

*   **Feasibility :** Is the travel logistics realistic? Are the timelines too tight?
*   **Balance :** Does the itinerary mix activity types (food, history, relaxation) effectively, or is it monotonic?
*   **Budget :** Is the estimated cost breakdown realistic for the described activities and region?

### 3. The "Selection" Phase (Ranking)
The application aggregates the scores provided by The Critic (0-10 scale) and presents the strategies to the user ranked from highest to lowest quality. This ensures the user sees the most robust underlying reasoning first.

---

## Technical Architecture

Wanderly is built as a robust **Flask** application designed for extensibility and modular AI integration.

### Core Stack
*   **Backend:** Python / Flask
*   **Database:** SQLAlchemy (SQLite)
*   **Authentication:** Flask-Login
*   **Styling:** Custom CSS (No frameworks, pure "Raised by the Internet" aesthetic)

### AI Orchestration
The application implements a **Multi-Provider Fallback System**. It creates a resilient intelligence layer that ensures the app always functions, regardless of individual API outages or quota limits.

1.  **Primary:** Google Gemini (`gemini-2.5-flash`) - *Fast, cost-effective reasoning.*
2.  **Fallback 1:** OpenAI (`gpt-4-turbo`) - *High-fidelity complex reasoning.*
3.  **Fallback 2:** Anthropic Claude (`claude-3-haiku`) - *Creative and natural nuance.*

### Privacy & Security
*   **Bring Your Own Key (BYOK):** Users can input their own API keys in the dashboard.
*   **Encryption:** All API keys are encrypted at rest using `Fernet` symmetric encryption before being stored in the database. Keys are decrypted only at the moment of request generation.

---

## Getting Started

Follow these steps to run Wanderly locally on your machine.

### Prerequisites
*   Python 3.8+
*   pip

### Installation

1.  **Clone the repository**
    ```bash
    git clone https://github.com/FVTVLIX/wanderly.git
    cd wanderly
    ```

2.  **Create a virtual environment**
    ```bash
    python -m venv venv
    source venv/bin/activate  # On Windows: venv\Scripts\activate
    ```

3.  **Install dependencies**
    ```bash
    pip install -r requirements.txt
    ```

4.  **Set up environment variables**
    Copy the `.env.example` or create a `.env` file in the root directory:
    ```env
    ANTHROPIC_API_KEY=your_anthropic_key
    ENCRYPTION_KEY=your_generated_fernet_key
    # Optional System-wide Keys (Users can also provide their own)
    GOOGLE_API_KEY=your_gemini_key
    OPENAI_API_KEY=your_openai_key
    ```
    *Note: You can generate a Fernet key using `from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())`*

5.  **Initialize the database & Run**
    ```bash
    python app.py
    ```

6.  **Explore**
    Open your browser and navigate to `http://127.0.0.1:5001`.

---

This project was built to demonstrate that **agentic workflows**—where AI models criticize, iterate, and reason upon each other's work—produce significantly higher quality outcomes than simple prompt-response interactions.

**Wanderly: Think deeper. Travel better.**
