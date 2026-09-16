"""Run fixture-only conformance cases against generated files in a test directory."""
import importlib.util
import json
import re
import sys
from pathlib import Path

from pydantic import ValidationError

request = json.load(sys.stdin)
root = Path(request["root"]).resolve()
model_path = (root / request["file"]).resolve()
model_path.relative_to(root)
assert re.fullmatch(r"model_[a-f0-9]{24}\.py", model_path.name)
assert re.fullmatch(r"Model[a-p]{20}", request["typeName"])
spec = importlib.util.spec_from_file_location("fixture_models", model_path)
module = importlib.util.module_from_spec(spec)
sys.modules["fixture_models"] = module
spec.loader.exec_module(module)
model = getattr(module, request["typeName"])
accepted = []
for value in request["valid"]:
    instance = model.model_validate_json(json.dumps(value), strict=True)
    serialized = instance.model_dump(mode="json", by_alias=True, exclude_unset=True)
    assert serialized == value, (serialized, value)
    accepted.append(serialized)
rejected = 0
for value in request["invalid"]:
    try:
        model.model_validate_json(json.dumps(value), strict=True)
    except ValidationError:
        rejected += 1
    else:
        raise AssertionError("Generated model accepted an invalid synthetic fixture")
print(json.dumps({"accepted": accepted, "rejected": rejected}))
