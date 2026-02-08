# bedrock_test.py
import json, sys
import boto3

REGION = "eu-central-1"

br = boto3.client("bedrock-runtime", region_name=REGION)

def call_claude():
    body = {
        "messages": [
            {"role": "user", "content": [{"type": "text", "text": "Reply with exactly: ready"}]}
        ],
        "max_tokens": 100,
        "anthropic_version": "bedrock-2023-05-31"
    }
    resp = br.invoke_model(
        modelId="anthropic.claude-3-5-sonnet-20240620-v1:0",
        body=json.dumps(body)
    )
    data = json.loads(resp["body"].read().decode("utf-8"))
    # Anthropic returns an array under content; grab the text
    text = "".join(part.get("text","") for part in data["content"] if part.get("type")=="text")
    print("Claude says:", text)

def titan_embed():
    body = {
        "inputText": "The quick brown fox jumps over the lazy dog.",
        "dimensions": 1024  # safe default; Bedrock will choose if omitted
    }
    resp = br.invoke_model(
        modelId="amazon.titan-embed-text-v2:0",
        body=json.dumps(body)
    )
    data = json.loads(resp["body"].read().decode("utf-8"))
    vec = data.get("embedding") or data.get("embeddings", [{}])[0].get("embedding")
    print("Titan embedding length:", len(vec))

if __name__ == "__main__":
    try:
        call_claude()
        titan_embed()
        print("✓ Bedrock test complete.")
    except Exception as e:
        print("ERROR:", e)
        sys.exit(1)
