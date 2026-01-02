from __future__ import annotations
from pymongo import MongoClient
from pymongo.database import Database
from pymongo.collection import Collection
from typing import TypedDict

class MongoHandles(TypedDict):
    db: Database
    sessions: Collection
    turns: Collection

def connect_mongo(mongo_uri: str, db_name: str) -> MongoHandles:
    # Add SSL/TLS configuration for MongoDB Atlas
    client = MongoClient(
        mongo_uri,
        tls=True,
        tlsAllowInvalidCertificates=False,
        serverSelectionTimeoutMS=30000,
        connectTimeoutMS=20000,
        socketTimeoutMS=20000,
    )
    db = client[db_name]
    return {
        "db": db,
        "sessions": db["chat_sessions"],
        "turns": db["chat_turns"],
    }

def ensure_indexes(handles: MongoHandles) -> None:
    sessions = handles["sessions"]
    turns = handles["turns"]

    sessions.create_index([("updated_at", -1)])
    sessions.create_index([("status", 1), ("updated_at", -1)])

    turns.create_index([("session_id", 1), ("turn_index", 1)], unique=True)
    turns.create_index([("session_id", 1), ("created_at", -1)])
    turns.create_index([("outputs.compliance.result", 1)])
