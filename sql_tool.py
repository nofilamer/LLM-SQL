import sqlite3
import json
import os
from pydantic import BaseModel, Field
from openai import OpenAI

# Initialize OpenAI Client
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# --------------------------------------------------------------
# Define Response Model
# --------------------------------------------------------------
class QueryResponse(BaseModel):
    results: list[dict] = Field(
        description="The results of the SQL query.",
        default_factory=list
    )
    response: str = Field(
        description="A natural language response to the user's question."
    )

    class Config:
        json_schema_extra = {
            "required": ["results", "response"]  # Include both fields
        }

# --------------------------------------------------------------
# Function to Query SQLite Database
# --------------------------------------------------------------
def query_perfbench_db(query):
    """Executes a SQL query on the perfbench database and returns the results."""
    db_path = "/Users/nofilamer/LINUX-MACHINE/GITHUB/LLM-SQL/data/perfbench.db"
    
    print(f"\n--- Database Query ---")
    print(f"Executing SQL: {query}")
    print(f"Database: {db_path}")
    
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row  # Enable row factory for dict-like access
    cursor = conn.cursor()
    
    try:
        cursor.execute(query)
        columns = [description[0] for description in cursor.description]
        print(f"Columns: {columns}")
        
        raw_results = cursor.fetchall()
        print(f"Number of results: {len(raw_results)}")
        
        # Convert SQLite Row objects to dictionaries with column names
        results = [dict(zip(columns, row)) for row in raw_results]
        
        # Print a sample of results (first 2 and total count)
        result_sample = results[:2] if len(results) > 2 else results
        print(f"Sample results: {json.dumps(result_sample, indent=2)}")
        print(f"Total results: {len(results)}")
        
    except sqlite3.Error as e:
        print(f"SQL Error: {str(e)}")
        return {"error": str(e)}
    finally:
        conn.close()
    
    print("--- End Database Query ---\n")
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
    "Always respond in JSON format with the results of your query and a natural language explanation."
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
        "tools": tools
    }
    
    print("\n--- Debug: JSON Payload Sent to OpenAI ---\n")
    print(json.dumps(json_payload, indent=4))
    print("\n-------------------------------------------\n")
    
    # Step 1: Call OpenAI Chat Completion API
    completion = client.chat.completions.create(**json_payload)
    
    # Append the original message to conversation history
    messages.append(completion.choices[0].message)
    
    # Check if the model called any tools
    if hasattr(completion.choices[0].message, 'tool_calls') and completion.choices[0].message.tool_calls:
        print("\n--- LLM Tool Calls ---")
        for tool_call in completion.choices[0].message.tool_calls:
            name = tool_call.function.name
            args = json.loads(tool_call.function.arguments)
            
            # Print the tool call details
            print(f"\nTool: {name}")
            print(f"Arguments: {json.dumps(args, indent=2)}")
            
            # Call function and get result
            result = call_function(name, args)
            
            # Print the tool response
            print(f"Tool Response: {json.dumps(result, indent=2)}")
            
            # Append the tool response to conversation history
            messages.append(
                {"role": "tool", "tool_call_id": tool_call.id, "content": json.dumps(result)}
            )
        print("\n-----------------------")
    else:
        print("No tool calls were made by the model")
    
    # Convert messages for JSON serialization again
    json_serializable_messages = [
        msg.model_dump() if hasattr(msg, "model_dump") else msg for msg in messages
    ]
    
    # Print the conversation history with tool results
    print("\n--- Conversation History with Tool Results ---")
    for i, msg in enumerate(json_serializable_messages):
        role = msg.get("role", "unknown")
        content_preview = str(msg.get("content", ""))[:100] + "..." if len(str(msg.get("content", ""))) > 100 else msg.get("content", "")
        if role == "tool":
            print(f"Message {i} - {role}: [Tool Response] {content_preview}")
        else:
            print(f"Message {i} - {role}: {content_preview}")
    print("\n-------------------------------------------")
    
    # Step 3: Send Final Response to OpenAI
    completion_2 = client.chat.completions.create(
        model="gpt-4o",
        messages=json_serializable_messages,
        response_format={"type": "json_object"},
    )
    
    # Print the final response
    print("\n--- Final Response from OpenAI ---\n")
    # Try to parse and pretty-print JSON response
    try:
        response_json = json.loads(completion_2.choices[0].message.content)
        print(json.dumps(response_json, indent=2))
    except json.JSONDecodeError:
        # Fall back to raw content if not valid JSON
        print(completion_2.choices[0].message.content)
    print("\n-------------------------------------------\n")
    
    return completion_2.choices[0].message.content

# Define function to call the appropriate function based on name
def call_function(name, args):
    if name == "query_perfbench_db":
        return query_perfbench_db(**args)

# --------------------------------------------------------------
# Main Execution
# --------------------------------------------------------------
if __name__ == "__main__":
    # Run a specific user query
    user_query = "show me jobs that used more than 50000 MB of memory and ran the specjbb2015 benchmark"
    print("\n==================================================")
    print("EXECUTING QUERY: " + user_query)
    print("==================================================\n")
    result = run_query(user_query)
    
    # Uncomment to run all queries in sequence
    # for query in queries:
    #     print("\n==================================================")
    #     print("EXECUTING QUERY: " + query)
    #     print("==================================================\n")
    #     result = run_query(query)
    #     import time
    #     time.sleep(2)

