import json, boto3

REGION = "eu-central-1"
br = boto3.client("bedrock-runtime", region_name=REGION)

def chat_titan(prompt: str):
    body = {
        "inputText": prompt,
        "textGenerationConfig": {
            "maxTokenCount": 200,
            "temperature": 0.3
        }
    }
    resp = br.invoke_model(
        modelId="amazon.titan-text-express-v1",
        body=json.dumps(body)
    )
    data = json.loads(resp["body"].read().decode("utf-8"))
    print("Titan Text says:", data["results"][0]["outputText"])

def titan_embed(text: str):
    body = {"inputText": text, "dimensions": 1024}
    resp = br.invoke_model(
        modelId="amazon.titan-embed-text-v1",   # using v1 to avoid extra gates
        body=json.dumps(body)
    )
    data = json.loads(resp["body"].read().decode("utf-8"))
    vec = data.get("embedding") or data.get("embeddings", [{}])[0].get("embedding")
    print("Titan embedding length:", len(vec))

if __name__ == "__main__":
    chat_titan("Reply with exactly: ready")
    titan_embed("The quick brown fox jumps over the lazy dog.")
    print("✓ Amazon models test complete.")
