# LLM-SQL

A Python tool that converts natural language queries into SQL commands, executes them against a SQLite database, and returns results in a user-friendly format.

## Features

- Natural language to SQL conversion using OpenAI's GPT models
- Direct execution of generated SQL against a local SQLite database
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

# Run the tool
python sql_tool.py
```

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

1. User submits a natural language query about the data
2. OpenAI's LLM converts the query to SQL via function calling
3. SQL executes against the SQLite database
4. Results are processed and returned in a user-friendly format

## Requirements

- Python 3.7+
- OpenAI API key
- Dependencies listed in `requirements.txt`

## License

MIT