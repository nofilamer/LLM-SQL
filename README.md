# LLM-SQL Web UI

A web application that converts natural language queries into SQL commands, executes them against a SQLite database, and presents results through a modern web interface.

## Features

- Natural language to SQL conversion using OpenAI's GPT models
- Direct execution of generated SQL against a local SQLite database
- Modern web interface for query input and result visualization
- Structured data validation with Pydantic
- Secure query handling with parameterized queries
- JSON-formatted responses for easy integration

## Quick Start

```bash
# Clone the repository
git clone https://github.com/username/LLM-SQL.git
cd LLM-SQL

# Create and activate virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Set your OpenAI API key
export OPENAI_API_KEY=your_key_here  # On Windows: set OPENAI_API_KEY=your_key_here

# Run the web application
uvicorn sql_tool:app --reload
```

Once the server is running, open your web browser and navigate to `http://localhost:8000` to access the web interface.

## Database Schema

The included example database (`data/perfbench.db`) contains a `perf_data` table with the following structure:

```sql
CREATE TABLE perf_data (
    jobid TEXT PRIMARY KEY,
    date DATE NOT NULL,
    useremail TEXT NOT NULL,
    vcpu INTEGER,
    mem INTEGER,
    capacitygroup TEXT,
    containers INTEGER,
    benchmarks TEXT NOT NULL,
    benchmarkcontext TEXT,
    result TEXT
);
```

## How It Works

1. User submits a natural language query through the web interface
2. OpenAI's LLM converts the query to SQL via function calling
3. SQL executes against the SQLite database
4. Results are processed and displayed in a user-friendly format on the web page

## Requirements

- Python 3.7+
- OpenAI API key
- Dependencies listed in `requirements.txt`:
  - FastAPI
  - Uvicorn
  - OpenAI
  - Pydantic
  - Python-dotenv
  - Jinja2
  - Requests
  - IPykernel

## License

MIT