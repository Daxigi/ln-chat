from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from datetime import datetime

class User(BaseModel):
    username: str
    email: Optional[str] = None
    full_name: Optional[str] = None
    disabled: Optional[bool] = None

class QueryResult(BaseModel):
    success: bool
    query: Optional[str] = None
    results: Optional[List[Dict[str, Any]]] = None
    error: Optional[str] = None
    execution_time: Optional[float] = None

class ChatMessage(BaseModel):
    role: str  # 'user' o 'assistant'
    content: str
    timestamp: datetime = datetime.now()
    metadata: Optional[Dict[str, Any]] = None

class TrainingData(BaseModel):
    id: str
    type: str  # 'ddl', 'documentation', 'sql'
    content: Dict[str, Any]
    created_at: datetime

