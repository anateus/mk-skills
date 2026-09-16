import json
from pathlib import Path
from unittest.mock import patch
from datahub.ingestion.source.openapi import OpenApiSource, OpenApiConfig
from datahub.ingestion.source.schema.json_schema import JsonSchemaSource
from datahub.ingestion.api.common import PipelineContext
from datahub.metadata.schema_classes import SchemaMetadataClass, SubTypesClass

def response(field):
    return {"description":"synthetic", "content":{"application/json":{"schema":{"type":"object","properties":{field:{"type":"string"}}}}}}

spec={"openapi":"3.0.3","info":{"title":"Synthetic","version":"1"},"paths":{
    "/widgets":{"get":{"responses":{"200":response("readValue"),"400":response("errorValue")}},"post":{"responses":{"200":response("writeValue")}}},
    "/created":{"post":{"responses":{"201":response("createdValue")}}},
    "/removed":{"delete":{"responses":{"204":{"description":"removed"}}}}
}}
Path("synthetic.openapi.json").write_text(json.dumps(spec,indent=2)+"\n")
ctx=PipelineContext(run_id="offline-contract-probe")
with patch.object(OpenApiConfig,"get_swagger",return_value=spec), patch("requests.sessions.Session.request",side_effect=AssertionError("Network forbidden")) as http:
    source=OpenApiSource.create({"name":"synthetic","url":"https://invalid.example","swagger_file":"openapi.json","enable_api_calls_for_schema_extraction":False},ctx)
    units=list(source.get_workunits())
    schemas=[{"urn":u.get_urn(),"fields":[f.fieldPath for f in u.metadata.aspect.fields]} for u in units if isinstance(getattr(u.metadata,"aspect",None),SchemaMetadataClass)]
    dataset_urns=sorted({u.get_urn() for u in units if u.get_urn().startswith("urn:li:dataset:")})
    assert len(dataset_urns)==1 and "synthetic.widgets" in dataset_urns[0], dataset_urns
    assert len(schemas)==1, schemas
    assert [x for x in schemas[0]["fields"] if "readValue" in x], schemas
    assert not any("writeValue" in x or "errorValue" in x for x in schemas[0]["fields"]), schemas
    assert http.call_count==0
schema={"$schema":"http://json-schema.org/draft-07/schema#","$id":"https://schemas.example.invalid/synthetic/Message.json","title":"Message","type":"object","properties":{"kind":{"type":"string","enum":["created","deleted"]},"value":{"oneOf":[{"type":"string","minLength":2},{"type":"integer","minimum":0}]}},"required":["kind","value"],"additionalProperties":False}
Path("message.schema.json").write_text(json.dumps(schema,indent=2)+"\n")
with patch("requests.sessions.Session.request",side_effect=AssertionError("Network forbidden")):
    json_source=JsonSchemaSource.create({"path":str(Path("message.schema.json").resolve()),"platform":"contract-probe","env":"DEV"},PipelineContext(run_id="offline-schema-probe"))
    json_units=list(json_source.get_workunits())
    meta=next(u.metadata.aspect for u in json_units if isinstance(getattr(u.metadata,"aspect",None),SchemaMetadataClass))
    raw=meta.platformSchema.rawSchema
    assert json.loads(raw)==schema
    subtype=next(u.metadata.aspect.typeNames for u in json_units if isinstance(getattr(u.metadata,"aspect",None),SubTypesClass))
    result={"sdk":"1.7.0","openapi":{"fixtureOperations":4,"fixturePaths":3,"datasetCount":len(dataset_urns),"schemas":schemas,"httpRequests":http.call_count,"observed":"One dataset for shared path; GET schema wins over POST; POST 201 and DELETE 204 endpoints omitted."},"jsonSchema":{"rawSchemaPreserved":True,"fields":[f.fieldPath for f in meta.fields],"subtype":subtype},"scope":"Real SDK sources generating metadata workunits locally; no server or UI test."}
Path("datahub-results.json").write_text(json.dumps(result,indent=2)+"\n")
print(json.dumps(result,indent=2))
