# server.py
from mcp.server.fastmcp import FastMCP
from neo4j import GraphDatabase
import openai
import json
import re
import os
import dotenv

# Load environment variables from .env file
dotenv.load_dotenv()
NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687") 
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "password")  # Change this to your actual password
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "your_openai_api_key")  # Change this to your actual OpenAI API key

mcp = FastMCP()

def get_neo4j_driver():
    return GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))

def serialize_record(record):
    serialized = {}
    for key, value in record.items():
        try:
            if hasattr(value, "items"):
                serialized[key] = dict(value)
            elif hasattr(value, "properties"):
                serialized[key] = dict(value.items())
            else:
                serialized[key] = value
        except Exception:
            serialized[key] = str(value)
    return serialized

def enforce_make_rule(cypher_query: str) -> str:
    """
    Ensures that any cypher involving :Make follows:
    MATCH (m:Make)-[:MANUFACTURES]->(n:Name)
    """
    # If already compliant, do nothing
    if "MATCH (m:Make)-[:MANUFACTURES]->(n:Name)" in cypher_query:
        return cypher_query

    # If the pattern exists but is non-compliant, replace it
    if "MATCH" in cypher_query and ":Make" in cypher_query:
        cypher_query = re.sub(
            r"MATCH\s*\(([^:]*):Make\)",
            "MATCH (m:Make)-[:MANUFACTURES]->(n:Name)",
            cypher_query
        )
        # Ensure a RETURN clause exists if not present
        if "RETURN" not in cypher_query:
            cypher_query += " RETURN m.name, n.name"
    return cypher_query

@mcp.tool()
def query_neo4j_with_llm(natural_query: str, create_nodes: bool = False, row: dict = None) -> str:
    """Generates and executes a Cypher query using LLM and optionally creates nodes, printing output locally."""

    if create_nodes and row:
        try:
            driver = get_neo4j_driver()

            def execute_create_query(tx, query, params):
                result = tx.run(query, params)
                return [record.data() for record in result]

            create_query = """
                CREATE (n:Name {name: $name})
                CREATE (mk:Make {name: $make})
                CREATE (cc:CC {value: $cc})
                CREATE (year:Year {value: $year})
                CREATE (km:Kilometers {value: $km})
                CREATE (p:Place {name: $place})
                CREATE (lot:LotNumber {lot_number: $lot_number})
                CREATE (sp:StartPrice {amount: $start_price})
                CREATE (minPrice:MinPrice {amount: $predictedminbid})
                CREATE (maxPrice:MaxPrice {amount: $predictedmaxbid})

                CREATE (n)-[:HAS_CC]->(cc)
                CREATE (cc)-[:BELONGS_TO]->(n)
                CREATE (mk)-[:MANUFACTURES]->(n)
                CREATE (n)-[:HAS_YEAR]->(year)
                CREATE (year)-[:YEAR_OF]->(n)
                CREATE (n)-[:HAS_KM]->(km)
                CREATE (km)-[:KILOMETERS_OF]->(n)
                CREATE (lot)-[:HAS_PLACE]->(p)
                CREATE (p)-[:LOCATION_OF]->(lot)
                CREATE (lot)-[:ASSIGNED_TO]->(n)
                CREATE (n)-[:HAS_LOT]->(lot)
                CREATE (lot)-[:HAS_START_PRICE]->(sp)
                CREATE (sp)-[:START_PRICE_OF]->(lot)
                CREATE (lot)<-[:BID_MIN]-(minPrice)
                CREATE (minPrice)-[:BELONGS_TO_LOT]->(lot)
                CREATE (lot)<-[:BID_MAX]-(maxPrice)
                CREATE (maxPrice)-[:BELONGS_TO_LOT]->(lot)
            """

            params = {
                "name": row.get("name"),
                "make": row.get("make"),
                "cc": row.get("cc"),
                "year": row.get("year"),
                "km": row.get("km"),
                "place": row.get("place"),
                "lot_number": row.get("lot_number"),
                "start_price": row.get("start_price"),
                "predictedminbid": row.get("predictedminbid"),
                "predictedmaxbid": row.get("predictedmaxbid"),
            }

            with driver.session() as session:
                results = session.execute_write(execute_create_query, create_query, params)

            driver.close()
            formatted_results = [serialize_record(record) for record in results]
            print("Node Creation Output:")
            print(json.dumps(formatted_results, indent=2))
            return json.dumps({"result": formatted_results})

        except Exception as e:
            error_message = f"Error creating nodes: {e}"
            print(error_message)
            return json.dumps({"error": error_message})

    else:
        # Run query mode
        try:
            system_prompt = f"""
# Graph Schema:
(:CC)-[:BELONGS_TO]->(:Name)
(:Make)-[:MANUFACTURES]->(:Name)
(:Name)-[:HAS_YEAR]->(:Year)
(:Year)-[:YEAR_OF]->(:Name)
(:Name)-[:HAS_KM]->(:Kilometers)
(:Kilometers)-[:KILOMETERS_OF]->(:Name)
(:Name)-[:HAS_LOT]->(:LotNumber)
(:LotNumber)-[:ASSIGNED_TO]->(:Name)
(:LotNumber)-[:HAS_PLACE]->(:Place)
(:Place)-[:LOCATION_OF]->(:LotNumber)
(:LotNumber)-[:HAS_START_PRICE]->(:StartPrice)
(:StartPrice)-[:START_PRICE_OF]->(:LotNumber)
(:LotNumber)-[:BID_MIN]->(:MinPrice)
(:LotNumber)-[:BID_MAX]->(:MaxPrice)

You are an expert Cypher query generator. Your goal is to convert user questions into syntactically correct and semantically valid Cypher queries using the schema provided above. Follow these strict instructions:

GENERAL RULES:

1. Use **only the nodes and relationships explicitly defined in the schema**.
   - Do NOT create new node labels, properties, or relationships.
   - Respect the **direction** of relationships as defined.

2. Always use the **most direct path possible** between nodes, strictly following the schema.

3. If multiple valid paths exist, **prefer the one with fewer hops** that best matches user intent.

4. Include intermediate nodes **only when necessary** to maintain schema accuracy.

5. When returning node properties:
   - For price-related nodes (start price, min price, max price), return .amount only.
   - For all other nodes, return properties using their actual names:
     - :Name → .name
     - :Make → .name
     - :Year → .year
     - :Kilometers → .value
     - :LotNumber → .lot_number
     - :Place → .name
     - :CC → .value
     - :StartPrice → .amount
     - :MinPrice → .amount
     - :MaxPrice → .amount

   - Do NOT return entire nodes or metadata like labels or relationship names.
   - Example: RETURN n.value, s.amount or RETURN l.lot_number

6. Do NOT include explanations, markdown, or natural language—only return a JSON object with the "cypher" key.

SPECIAL RULES:

- For queries involving the **make** of a car:
   - Always use the exact structure: MATCH (m:Make)-[:MANUFACTURES]->(n:Name)
   - Variable m must always refer to :Make and n must refer to :Name throughout the entire query.
   - Do NOT reverse the direction or use alternate relationship names.
   - Do NOT use different variable names for :Make or :Name once m and n are assigned.

- Always **capitalize the first letter** of any provided string (e.g., make or model name).
   - If a user says "honda", you must convert it to "Honda" before inserting it into the Cypher query.
   - Apply this rule to all `name`, `make`, `place`, and similar string fields in MATCH filters.

COUNTING LOGIC:

- If the question involves counting **all cars** (e.g. "how many cars are there"):
   - Use: MATCH (n:Name)-[:HAS_LOT]->(l:LotNumber) RETURN COUNT(DISTINCT l) AS total_cars
- If the question involves counting **cars by model name**:
   - Use: MATCH (n:Name {{name: "<model_name>"}})-[:HAS_LOT]->(l:LotNumber) RETURN COUNT(DISTINCT l) AS total_cars
- If the question involves counting **cars by make**:
   - Use: MATCH (m:Make {{name: "<make_name>"}})-[:MANUFACTURES]->(n:Name)-[:HAS_LOT]->(l:LotNumber) RETURN COUNT(DISTINCT l) AS total_cars

TRAVERSAL GUIDELINES:

- All MATCH statements must follow the defined directions.
- Do NOT assume or infer relationships not explicitly defined in the schema.
- Do NOT jump across unrelated node types.

UNANSWERABLE QUESTIONS:

If the user’s question cannot be answered with the available schema, return this:
{{ "cypher": "" }}

STRICT OUTPUT FORMAT:

Only respond with a single valid JSON object. No commentary. No markdown. No explanation.
"""

            response = openai.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": natural_query}
                ],
                temperature=0
            )

            cypher_json = response.choices[0].message.content
            cypher_result = json.loads(cypher_json)
            cypher_query = cypher_result.get("cypher", "")

            if not cypher_query:
                return json.dumps({"result": "Query cannot be answered with the available schema."})

            cypher_query = enforce_make_rule(cypher_query)

            print("LLM Generated Cypher Query:")
            print(cypher_query)

            driver = get_neo4j_driver()

            def execute_read_query(tx, query):
                result = tx.run(query)
                return [serialize_record(record.data()) for record in result]

            with driver.session() as session:
                neo4j_results = session.execute_read(execute_read_query, cypher_query)

            driver.close()
            print("Neo4j Query Output:")
            print(json.dumps({"result": neo4j_results}, indent=2))
            return json.dumps({"result": neo4j_results})

        except Exception as e:
            error_message = f"Error: {e}"
            print(error_message)
            return json.dumps({"error": error_message})

if __name__ == "__main__":
    mcp.run(transport='sse')

