# rag/embeddings.py

import boto3
import json
import os
from dotenv import load_dotenv

load_dotenv()

bedrock = boto3.client(
    "bedrock-runtime",
    region_name=os.getenv("AWS_REGION")
)

MODEL_ID = "amazon.titan-embed-text-v1"


import time
from botocore.exceptions import ClientError

def embed(text: str) -> list[float]:
    """Convert text into vector embedding using Bedrock Titan with robust retry logic."""
    max_retries = 8
    base_delay = 2
    
    for attempt in range(max_retries):
        try:
            response = bedrock.invoke_model(
                modelId=MODEL_ID,
                body=json.dumps({"inputText": text})
            )
            result = json.loads(response["body"].read())
            return result["embedding"]
        except ClientError as e:
            if e.response["Error"]["Code"] == "ThrottlingException" and attempt < max_retries - 1:
                delay = base_delay * (2 ** attempt)
                print(f"Throttled. Retrying in {delay}s...")
                time.sleep(delay)
                continue
            raise e
        except Exception as e:
            if "ThrottlingException" in str(e) and attempt < max_retries - 1:
                delay = base_delay * (2 ** attempt)
                print(f"Throttled. Retrying in {delay}s...")
                time.sleep(delay)
                continue
            raise e
    
    raise RuntimeError("Max retries exceeded for Bedrock embedding.")