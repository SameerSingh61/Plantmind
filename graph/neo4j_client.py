"""AuraDB connection shared by ingestion, the trigger rules, and the
backend. Everything downstream talks to Neo4j through this module —
no other file should import the neo4j driver directly.
"""
import os

from dotenv import load_dotenv

load_dotenv()

from neo4j import GraphDatabase  # noqa: E402

_driver = None


def get_driver():
    global _driver
    if _driver is None:
        uri = os.environ["NEO4J_URI"]
        user = os.environ["NEO4J_USER"]
        password = os.environ["NEO4J_PASSWORD"]
        _driver = GraphDatabase.driver(uri, auth=(user, password))
    return _driver


def run(cypher: str, **params) -> list[dict]:
    """Runs a Cypher statement, returns a list of plain dicts. Neo4j Node/
    Relationship values in the result are converted to plain dicts of
    their properties (via dict(value)) so callers never touch the driver's
    own graph types."""
    driver = get_driver()
    database = os.environ.get("NEO4J_DATABASE", "neo4j")
    with driver.session(database=database) as session:
        result = session.run(cypher, **params)
        rows = []
        for record in result:
            row = {}
            for key, value in dict(record).items():
                row[key] = _convert(value)
            rows.append(row)
        return rows


def _convert(value):
    from neo4j.graph import Node, Relationship
    if isinstance(value, Node):
        d = dict(value)
        d["_labels"] = list(value.labels)
        return d
    if isinstance(value, Relationship):
        d = dict(value)
        d["_type"] = value.type
        return d
    if isinstance(value, list):
        return [_convert(v) for v in value]
    return value


def close():
    global _driver
    if _driver is not None:
        _driver.close()
        _driver = None
