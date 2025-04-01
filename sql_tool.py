import sqlite3
import json
import os
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field
from openai import OpenAI
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import uvicorn
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Initialize OpenAI Client
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# Initialize FastAPI app
app = FastAPI(title="LLM SQL Query Tool")

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Create templates and static directories if they don't exist
os.makedirs("templates", exist_ok=True)
os.makedirs("static", exist_ok=True)

# Create templates directory
templates = Jinja2Templates(directory="templates")


# --------------------------------------------------------------
# Define Request and Response Models
# --------------------------------------------------------------
class QueryRequest(BaseModel):
    query: str = Field(..., description="The natural language query to execute")


class QueryResponse(BaseModel):
    results: List[Dict[str, Any]] = Field(
        description="The results of the SQL query.", default_factory=list
    )
    response: str = Field(
        description="A natural language response to the user's question."
    )
    sql_query: Optional[str] = Field(
        description="The SQL query that was executed.", default=None
    )

    class Config:
        json_schema_extra = {"required": ["results", "response"]}


# --------------------------------------------------------------
# Function to Query SQLite Database
# --------------------------------------------------------------
def query_perfbench_db(query):
    """Executes a SQL query on the perfbench database and returns the results."""
    # Try multiple paths to find the database
    possible_paths = [
        os.path.join(
            os.path.dirname(os.path.abspath(__file__)), "data", "perfbench.db"
        ),
        os.path.join(os.getcwd(), "data", "perfbench.db"),
        "/Users/nofilamer/LINUX-MACHINE/GITHUB/LLM-SQL/data/perfbench.db",  # Original path from the code
    ]

    # Find the first path that exists
    db_path = None
    for path in possible_paths:
        if os.path.exists(path):
            db_path = path
            break

    if db_path is None:
        raise FileNotFoundError("Could not find perfbench.db database file")

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row  # Enable row factory for dict-like access
    cursor = conn.cursor()

    try:
        cursor.execute(query)
        columns = [description[0] for description in cursor.description]

        raw_results = cursor.fetchall()

        # Convert SQLite Row objects to dictionaries with column names
        results = [dict(zip(columns, row)) for row in raw_results]

    except sqlite3.Error as e:
        return {"error": str(e)}
    finally:
        conn.close()

    return {"results": results}


# --------------------------------------------------------------
# Define Tool (Function) for OpenAI
# --------------------------------------------------------------
tools = [
    {
        "type": "function",
        "function": {
            "name": "query_perfbench_db",
            "description": "Query the perfbench database using a SQL statement.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string"},
                },
                "required": ["query"],
                "additionalProperties": False,
            },
            "strict": True,
        },
    }
]

# --------------------------------------------------------------
# Define System Prompt with Database Schema
# --------------------------------------------------------------
system_prompt = (
    "You are a helpful assistant for querying benchmark results. "
    "If the question is not relevant to the benchmark results, respond with 'I don't know.' "
    "The database schema is as follows: "
    "CREATE TABLE perf_data ("
    "jobid TEXT PRIMARY KEY, "
    "date DATE NOT NULL, "
    "useremail TEXT NOT NULL, "
    "vcpu INTEGER, "
    "mem INTEGER, "
    "capacitygroup TEXT, "
    "containers INTEGER, "
    "benchmarks TEXT NOT NULL, "
    "benchmarkcontext TEXT, "
    "result TEXT);"
    "Always respond in JSON format with the following structure exactly: "
    '{ "results": [...array of result objects...], "response": "natural language explanation" }'
)


# --------------------------------------------------------------
# Define User Query Function
# --------------------------------------------------------------
def run_query(user_query):
    """Run a natural language query against the database using LLM."""
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_query + " Return the results in JSON format."},
    ]

    # Convert messages for JSON serialization
    json_serializable_messages = [
        msg.model_dump() if hasattr(msg, "model_dump") else msg for msg in messages
    ]

    # Prepare JSON payload
    json_payload = {
        "model": "gpt-4o",
        "messages": json_serializable_messages,
        "response_format": {"type": "json_object"},
        "tools": tools,
    }

    executed_sql_query = None

    # Step 1: Call OpenAI Chat Completion API
    completion = client.chat.completions.create(**json_payload)

    # Append the original message to conversation history
    messages.append(completion.choices[0].message)

    # Check if the model called any tools
    if (
        hasattr(completion.choices[0].message, "tool_calls")
        and completion.choices[0].message.tool_calls
    ):
        for tool_call in completion.choices[0].message.tool_calls:
            name = tool_call.function.name
            args = json.loads(tool_call.function.arguments)

            # Record the SQL query
            if name == "query_perfbench_db" and "query" in args:
                executed_sql_query = args["query"]

            # Call function and get result
            result = call_function(name, args)

            # Append the tool response to conversation history
            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": json.dumps(result),
                }
            )

    # Convert messages for JSON serialization again
    json_serializable_messages = [
        msg.model_dump() if hasattr(msg, "model_dump") else msg for msg in messages
    ]

    # Step 3: Send Final Response to OpenAI
    completion_2 = client.chat.completions.create(
        model="gpt-4o",
        messages=json_serializable_messages,
        response_format={"type": "json_object"},
    )

    # Parse the response
    try:
        response_json = json.loads(completion_2.choices[0].message.content)

        # Handle key naming differences (explanation → response)
        if "explanation" in response_json and "response" not in response_json:
            response_json["response"] = response_json.pop("explanation")

        # Make sure the response field exists
        if "response" not in response_json:
            if "result" in response_json:
                response_json["response"] = response_json.pop("result")
            else:
                response_json["response"] = "Query completed successfully."

        # Make sure results field exists and is a list
        if "results" not in response_json:
            response_json["results"] = []

        # Add the SQL query to the response
        response_json["sql_query"] = executed_sql_query
        return response_json
    except json.JSONDecodeError:
        return {
            "results": [],
            "response": "Error processing results",
            "sql_query": executed_sql_query,
        }


# Define function to call the appropriate function based on name
def call_function(name, args):
    if name == "query_perfbench_db":
        return query_perfbench_db(**args)


# --------------------------------------------------------------
# FastAPI Routes
# --------------------------------------------------------------
@app.get("/")
async def root(request: Request):
    """Serve the main HTML page"""
    return templates.TemplateResponse("index.html", {"request": request})


@app.post("/api/query", response_model=QueryResponse)
async def query(request: QueryRequest):
    """API endpoint to process natural language queries"""
    try:
        result = run_query(request.query)

        # Log the response for debugging
        print(f"API Response: {json.dumps(result, indent=2)}")

        # Make sure required fields exist before returning
        if "response" not in result:
            result["response"] = "Query executed successfully."
        if "results" not in result:
            result["results"] = []

        return result
    except Exception as e:
        import traceback

        print(f"Error processing query: {str(e)}")
        print(traceback.format_exc())
        raise HTTPException(status_code=500, detail=str(e))


# Create index.html template
index_html = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>LLM SQL Query Tool</title>
    <style>
        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            line-height: 1.6;
            color: #333;
            max-width: 1200px;
            margin: 0 auto;
            padding: 20px;
            background-color: #f9f9f9;
        }
        h1 {
            color: #2c3e50;
            text-align: center;
            margin-bottom: 20px;
        }
        .container {
            background-color: white;
            padding: 25px;
            border-radius: 8px;
            box-shadow: 0 2px 10px rgba(0, 0, 0, 0.1);
        }
        .query-container {
            margin-bottom: 20px;
        }
        #query {
            width: 100%;
            padding: 12px;
            border: 1px solid #ddd;
            border-radius: 4px;
            font-size: 16px;
            box-sizing: border-box;
        }
        #submit {
            background-color: #3498db;
            color: white;
            border: none;
            padding: 12px 24px;
            border-radius: 4px;
            cursor: pointer;
            font-size: 16px;
            transition: background-color 0.3s;
            margin-top: 10px;
        }
        #submit:hover {
            background-color: #2980b9;
        }
        .results {
            margin-top: 30px;
        }
        .response-text {
            background-color: #f8f9fa;
            padding: 15px;
            border-left: 4px solid #3498db;
            margin-bottom: 20px;
            border-radius: 4px;
        }
        table {
            width: 100%;
            border-collapse: collapse;
            margin-bottom: 20px;
        }
        th, td {
            padding: 12px 15px;
            text-align: left;
            border-bottom: 1px solid #ddd;
        }
        th {
            background-color: #f2f2f2;
            font-weight: bold;
        }
        tr:hover {
            background-color: #f5f5f5;
        }
        .sql-query {
            background-color: #f0f0f0;
            padding: 15px;
            border-radius: 4px;
            font-family: monospace;
            white-space: pre-wrap;
            margin-bottom: 20px;
            overflow-x: auto;
        }
        .loading {
            text-align: center;
            margin: 20px 0;
            display: none;
        }
        .spinner {
            border: 4px solid #f3f3f3;
            border-top: 4px solid #3498db;
            border-radius: 50%;
            width: 30px;
            height: 30px;
            animation: spin 2s linear infinite;
            margin: 0 auto;
        }
        @keyframes spin {
            0% { transform: rotate(0deg); }
            100% { transform: rotate(360deg); }
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>LLM SQL Query Tool</h1>
        
        <div class="query-container">
            <p>Ask a question about the benchmark data:</p>
            <textarea id="query" rows="4" placeholder="e.g., What are the top 5 jobs with the highest number of containers?"></textarea>
            <button id="submit">Run Query</button>
        </div>
        
        <div class="loading">
            <div class="spinner"></div>
            <p>Processing your query...</p>
        </div>
        
        <div class="results" id="results" style="display: none;">
            <h2>Results</h2>
            
            <h3>SQL Query</h3>
            <div class="sql-query" id="sql-query"></div>
            
            <h3>Response</h3>
            <div class="response-text" id="response-text"></div>
            
            <h3>Data</h3>
            <div id="table-container"></div>
        </div>
    </div>

    <script>
        document.getElementById('submit').addEventListener('click', async () => {
            const queryText = document.getElementById('query').value.trim();
            
            if (!queryText) {
                alert('Please enter a query');
                return;
            }
            
            // Show loading indicator
            document.querySelector('.loading').style.display = 'block';
            document.getElementById('results').style.display = 'none';
            
            try {
                const response = await fetch('/api/query', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify({ query: queryText })
                });
                
                if (!response.ok) {
                    throw new Error('Network response was not ok');
                }
                
                const data = await response.json();
                
                // Hide loading indicator
                document.querySelector('.loading').style.display = 'none';
                
                // Show results section
                document.getElementById('results').style.display = 'block';
                
                // Display SQL query
                const sqlQueryElement = document.getElementById('sql-query');
                sqlQueryElement.textContent = data.sql_query || 'No SQL query was executed';
                
                // Display natural language response
                const responseTextElement = document.getElementById('response-text');
                responseTextElement.textContent = data.response;
                
                // Create table for results
                const tableContainer = document.getElementById('table-container');
                tableContainer.innerHTML = '';
                
                if (data.results && data.results.length > 0) {
                    const table = document.createElement('table');
                    
                    // Create table header
                    const thead = document.createElement('thead');
                    const headerRow = document.createElement('tr');
                    
                    Object.keys(data.results[0]).forEach(key => {
                        const th = document.createElement('th');
                        th.textContent = key;
                        headerRow.appendChild(th);
                    });
                    
                    thead.appendChild(headerRow);
                    table.appendChild(thead);
                    
                    // Create table body
                    const tbody = document.createElement('tbody');
                    
                    data.results.forEach(result => {
                        const row = document.createElement('tr');
                        
                        Object.values(result).forEach(value => {
                            const td = document.createElement('td');
                            td.textContent = value;
                            row.appendChild(td);
                        });
                        
                        tbody.appendChild(row);
                    });
                    
                    table.appendChild(tbody);
                    tableContainer.appendChild(table);
                } else {
                    tableContainer.textContent = 'No results found';
                }
                
            } catch (error) {
                console.error('Error:', error);
                document.querySelector('.loading').style.display = 'none';
                alert('An error occurred while processing your query');
            }
        });
    </script>
</body>
</html>
"""


# --------------------------------------------------------------
# Create template files on startup
# --------------------------------------------------------------
def create_template_files():
    with open("templates/index.html", "w") as f:
        f.write(index_html)


# Mount static files
app.mount("/static", StaticFiles(directory="static"), name="static")

# --------------------------------------------------------------
# Main Execution
# --------------------------------------------------------------
if __name__ == "__main__":
    # Create template files
    create_template_files()

    # Check database connection
    try:
        # Try multiple paths to find the database
        possible_paths = [
            os.path.join(
                os.path.dirname(os.path.abspath(__file__)), "data", "perfbench.db"
            ),
            os.path.join(os.getcwd(), "data", "perfbench.db"),
            "/Users/nofilamer/LINUX-MACHINE/GITHUB/LLM-SQL/data/perfbench.db",  # Original path from the code
        ]

        # Find the first path that exists
        db_path = None
        for path in possible_paths:
            if os.path.exists(path):
                db_path = path
                print(f"Found database at: {db_path}")
                break

        if db_path is None:
            print("WARNING: Could not find perfbench.db database file")
        else:
            # Test the connection
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM perf_data")
            count = cursor.fetchone()[0]
            conn.close()
            print(f"Successfully connected to database. Found {count} records.")
    except Exception as e:
        print(f"WARNING: Failed to connect to database: {str(e)}")

    # Check OpenAI API key
    if not os.getenv("OPENAI_API_KEY"):
        print("WARNING: OPENAI_API_KEY environment variable is not set")
    else:
        print("OpenAI API key found in environment variables")

    # Start the server
    print("\n==================================================")
    print("LLM SQL QUERY API RUNNING")
    print("==================================================\n")
    print("Access the web interface at: http://localhost:8000")
    uvicorn.run(app, host="0.0.0.0", port=8000)
