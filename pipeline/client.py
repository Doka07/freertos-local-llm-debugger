import argparse
import json
import logging
import pathlib
import sys
from typing import Any, Dict, Optional
import httpx
import jsonschema

logging.basicConfig(level=logging.INFO, format="[%(asctime)s] %(levelname)s: %(message)s")
logger = logging.getLogger("diagnosis_client")

ROOT = pathlib.Path(__file__).parent.parent
SCHEMAS_DIR = ROOT / "schemas"
PROMPTS_DIR = ROOT / "prompts"

def load_schema(schema_name: str) -> Dict[str, Any]:
    with open(SCHEMAS_DIR / schema_name) as f:
        return json.load(f)

def load_system_prompt() -> str:
    with open(PROMPTS_DIR / "system_prompt_v1.txt") as f:
        return f.read()

def load_inference_config() -> Dict[str, Any]:
    with open(PROMPTS_DIR / "inference_config_v1.json") as f:
        return json.load(f)

def validate_evidence_pack(evidence_pack: Dict[str, Any], schema: Dict[str, Any]) -> None:
    jsonschema.validate(instance=evidence_pack, schema=schema)

def validate_verdict(verdict: Dict[str, Any], schema: Dict[str, Any]) -> None:
    jsonschema.validate(instance=verdict, schema=schema)

def query_model(
    evidence_pack: Dict[str, Any],
    api_base: str = "http://localhost:11434/v1",
    model: str = "qwen2.5-coder:14b",
    temperature: float = 0.0,
    seed: int = 42,
    timeout_s: float = 180.0,
    mock_response: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    verdict_schema = load_schema("verdict.schema.json")

    if mock_response is not None:
        logger.info("Using mock response for dry-run verification")
        validate_verdict(mock_response, verdict_schema)
        return mock_response

    system_prompt = load_system_prompt()
    user_content = json.dumps(evidence_pack)

    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"Analyze this FreeRTOS evidence pack and output a structured verdict:\n{user_content}"}
        ],
        "temperature": temperature,
        "seed": seed,
        "response_format": {
            "type": "json_schema",
            "json_schema": {
                "name": "DiagnosisVerdict",
                "schema": verdict_schema,
                "strict": True
            }
        }
    }

    url = f"{api_base.rstrip("/")}/chat/completions"
    logger.info(f"Dispatching query to {url} (model={model}, temp={temperature}, seed={seed})")

    with httpx.Client(timeout=timeout_s) as client:
        resp = client.post(url, json=payload)
        resp.raise_for_status()
        data = resp.json()

    raw_verdict_str = data["choices"][0]["message"]["content"]
    verdict = json.loads(raw_verdict_str)

    # Normalize percentage confidence if emitted as 0-100
    if verdict.get("confidence", 0.0) > 1.0:
        verdict["confidence"] = round(verdict["confidence"] / 100.0, 3)

    # Validate output against frozen schema
    validate_verdict(verdict, verdict_schema)
    return verdict

def main():
    parser = argparse.ArgumentParser(description="FreeRTOS LLM Diagnosis Client")
    parser.add_argument("--evidence", required=True, help="Path to evidence_pack.json")
    parser.add_argument("--output", help="Path to save verdict.json")
    parser.add_argument("--api-base", default="http://localhost:11434/v1", help="OpenAI-compatible base URL")
    parser.add_argument("--model", default="qwen2.5-coder:14b", help="Model tag")
    parser.add_argument("--mock-verdict", help="Path to mock verdict JSON for dry-run testing")
    parser.add_argument("--timeout", type=float, default=180.0, help="Inference timeout in seconds")
    args = parser.parse_args()

    evidence_schema = load_schema("evidence_pack.schema.json")
    with open(args.evidence) as f:
        evidence_pack = json.load(f)

    logger.info(f"Validating evidence package: {args.evidence}")
    validate_evidence_pack(evidence_pack, evidence_schema)

    mock_resp = None
    if args.mock_verdict:
        with open(args.mock_verdict) as f:
            mock_resp = json.load(f)

    verdict = query_model(
        evidence_pack=evidence_pack,
        api_base=args.api_base,
        model=args.model,
        timeout_s=args.timeout,
        mock_response=mock_resp
    )

    logger.info(f"Verdict generated successfully: failure_class={verdict["failure_class"]}, confidence={verdict["confidence"]}")
    if args.output:
        with open(args.output, "w") as f:
            json.dump(verdict, f, indent=2)
        logger.info(f"Saved verdict to {args.output}")
    else:
        print(json.dumps(verdict, indent=2))

if __name__ == "__main__":
    main()
