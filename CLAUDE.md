# LLM-SQL Development Guide

## Environment Setup
```bash
# Create and activate Python virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Run the main tool (requires OpenAI API key)
export OPENAI_API_KEY=your_key_here  # On Windows: set OPENAI_API_KEY=your_key_here
python sql_tool.py
```

## Project Structure
- `sql_tool.py`: Main script for LLM-powered SQL query generation
- `data/perfbench.db`: SQLite database with benchmark performance data
- `requirements.txt`: Project dependencies

## Database Schema
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

## Code Style Guidelines
- **Imports**: Standard library → third-party → local modules
- **Formatting**: Follow PEP 8 (4-space indentation, 79-char line limit)
- **Comments**: Use section dividers with `# -----` for code organization
- **Types**: Use Pydantic models for data structures and validation
- **Error Handling**: Catch specific exceptions (e.g., `sqlite3.Error`)
- **Naming**: Use snake_case for functions/variables, PascalCase for classes

## Best Practices
- Use parameterized queries to prevent SQL injection
- Structure LLM prompts with clear system instructions
- Process SQLite results as dictionaries with column names
- Make functions reusable with clear documentation
- Keep API keys in environment variables, never hardcode
- Use function calling pattern for LLM-database interaction