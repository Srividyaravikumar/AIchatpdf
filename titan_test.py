# save as titan_test.py and run: python titan_test.py
import json, boto3
br = boto3.client("bedrock-runtime", region_name="eu-central-1")
body = {"inputText": "hello world", "dimensions": 1024}
resp = br.invoke_model(modelId="amazon.titan-embed-text-v2:0", body=json.dumps(body))
print("OK:", len(json.loads(resp["body"].read().decode())["embedding"]))
