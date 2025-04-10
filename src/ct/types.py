from pydantic import BaseModel
from datetime import datetime, timezone
from typing import Optional, List
import numpy as np


class LLMError(Exception):
    def __init__(self, message, exception = None):
        super().__init__(message)
        self.exception = exception

class LLMAPIResponseError(LLMError):
    def __init__(self, response, message, exception=None):
        super().__init__(message, exception)
        self.response = response

class CallMetadata(BaseModel):
    provider : str        # Provider name
    model : str           # Model name
    operation : str       # Type of operation
    duration : float      # Request duration in seconds
    input_tokens : Optional[int]    # Number of tokens in the input prompt
    output_tokens : Optional[int]   # Number of tokens in the generated response
    timestamp : datetime  # Response timestamp in UTC

def call_metadata(
        provider : str,
        model : str,
        operation : str,
        duration : float,
        input_tokens : Optional[int],
        output_tokens : Optional[int],
) -> CallMetadata:
    return CallMetadata(
        provider=provider,
        model=model,
        operation=operation,
        duration=duration,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        timestamp=datetime.now(timezone.utc),
    )

class TextMetadata(BaseModel):
    source : str
    reference : str

class Text(BaseModel):
    content : str
    metadata : TextMetadata

type Chunks = List[Text]

type Question = Text

type Vector = np.ndarray