#!/usr/bin/env python3
"""Conservative Python contract discovery. Target modules are parsed, never imported."""
import ast
import json
import sys
from pathlib import Path
from urllib.parse import quote, urlsplit

DIALECT = "https://json-schema.org/draft/2020-12/schema"
METHODS = {"get", "post", "put", "patch", "delete", "head", "options", "trace"}
CLIENTS = {"aiohttp.ClientSession", "httpx.Client", "httpx.AsyncClient", "requests.Session"}


def dotted(node):
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        parent = dotted(node.value)
        return parent + "." + node.attr if parent else ""
    return ""


def literal(node):
    return node.value if isinstance(node, ast.Constant) else None


def keywords(node):
    return {item.arg: item.value for item in node.keywords if item.arg}


def unwrap(node):
    return unwrap(node.value) if isinstance(node, ast.Await) else node


class Scanner:
    def __init__(self, request):
        self.repo = request["repository"]
        self.root = Path(self.repo["root"]).resolve()
        self.units = {}
        self.classes = {}
        self.functions = {}
        self.routers = {}
        self.includes = []
        self.result = {
            "protocolVersion": 1,
            "adapter": {
                "name": "python-ast", "version": "0.1.0",
                "capabilities": ["python-annotations", "pydantic-static", "fastapi-static-registration", "http-client-static-calls"],
                "limitations": [
                    "Target modules are never executed. Pydantic coercion, custom validators, serializers and version-dependent behavior are not exported.",
                    "FastAPI mounted means a static registration path to an app, not evidence of deployment or execution.",
                    "Dynamic imports, monkey patches, dependency injection, arbitrary wrappers and control flow are not resolved.",
                    "Only explicit selected files are examined; imported dependencies outside that selection remain unresolved.",
                ],
            },
            "declarations": [], "schemas": [], "operations": [], "relationships": [], "files": [], "diagnostics": [],
        }
        for file in sorted(set(request["files"])):
            self.read(file)
        self.index()

    def ident(self, file, symbol, kind):
        return self.repo["id"] + ":python:" + ":".join(quote(x, safe="") for x in [file, symbol, kind])

    def evidence(self, file, node, basis="declaration", symbol=None):
        evidence = {"file": file, "line": node.lineno, "basis": basis}
        if symbol:
            evidence["symbol"] = symbol
        return evidence

    def read(self, file):
        try:
            if Path(file).is_absolute() or ".." in Path(file).parts:
                raise ValueError("non-relative-path")
            path = (self.root / file).resolve()
            path.relative_to(self.root)
            if not file.endswith(".py"):
                self.result["files"].append({"path": file, "status": "unsupported"})
                return
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=file)
        except (OSError, ValueError, SyntaxError, UnicodeError):
            self.result["files"].append({"path": file, "status": "failed"})
            self.result["diagnostics"].append({"file": file, "code": "python-parse-failed", "message": "File could not be safely read and parsed; source and exception text omitted."})
            return
        parents = {child: parent for parent in ast.walk(tree) for child in ast.iter_child_nodes(parent)}
        aliases = {}
        for node in tree.body:
            if isinstance(node, ast.Import):
                for name in node.names:
                    aliases[name.asname or name.name.split(".")[0]] = name.name if name.asname else name.name.split(".")[0]
            elif isinstance(node, ast.ImportFrom):
                prefix = node.module or ""
                if node.level:
                    parts = file.removesuffix(".py").split("/")[:-node.level]
                    prefix = ".".join(parts + ([prefix] if prefix else []))
                for name in node.names:
                    aliases[name.asname or name.name] = prefix + "." + name.name
        self.units[file] = {"tree": tree, "parents": parents, "aliases": aliases}
        self.result["files"].append({"path": file, "status": "examined"})

    def scope(self, file, node):
        parents = self.units[file]["parents"]
        names = []
        while node in parents:
            node = parents[node]
            if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
                names.append(node.name)
        return ".".join(reversed(names))

    def name(self, file, node):
        value = dotted(node)
        head, dot, tail = value.partition(".")
        return self.units[file]["aliases"].get(head, head) + (dot + tail if dot else "")

    def conditional(self, file, node):
        parents = self.units[file]["parents"]
        while node in parents:
            node = parents[node]
            if isinstance(node, (ast.If, ast.For, ast.AsyncFor, ast.While, ast.Try)) or type(node).__name__ == "Match":
                return True
        return False

    def resolve(self, file, node, catalog):
        raw = dotted(node)
        scope = self.scope(file, node)
        while scope:
            if (file, scope + "." + raw) in catalog:
                return (file, scope + "." + raw)
            scope = scope.rpartition(".")[0]
        if (file, raw) in catalog:
            return (file, raw)
        name = self.name(file, node)
        matches = []
        for key in catalog:
            module = key[0].removesuffix(".py").replace("/", ".").removesuffix(".__init__")
            full = module + "." + key[1]
            if full == name or full.endswith("." + name):
                matches.append(key)
        return matches[0] if len(matches) == 1 else None

    def index(self):
        for file, unit in self.units.items():
            for node in ast.walk(unit["tree"]):
                if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
                    symbol = ".".join(filter(None, [self.scope(file, node), node.name]))
                    catalog = self.classes if isinstance(node, ast.ClassDef) else self.functions
                    if (file, symbol) in catalog:
                        self.result["diagnostics"].append({"file": file, "line": node.lineno, "code": "shadowed-python-symbol", "message": "Multiple declarations share a symbol; only the last indexed declaration is represented."})
                    catalog[file, symbol] = node
        self.models = {key for key, node in self.classes.items() if any(self.name(key[0], base) in {"pydantic.BaseModel", "pydantic.RootModel", "typing.TypedDict", "typing_extensions.TypedDict"} for base in node.bases)}
        while True:
            inherited = {key for key, node in self.classes.items() if any(self.resolve(key[0], base, self.classes) in self.models for base in node.bases)}
            if inherited <= self.models:
                break
            self.models |= inherited

    def annotation(self, file, node, gaps):
        if node is None:
            gaps.append("missing-type-annotation")
            return {}
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            try:
                return self.annotation(file, ast.parse(node.value, mode="eval").body, gaps)
            except SyntaxError:
                gaps.append("unresolved-forward-annotation")
                return {}
        if isinstance(node, ast.Constant) and node.value is None:
            return {"type": "null"}
        primitives = {"str": "string", "int": "integer", "float": "number", "bool": "boolean", "None": "null"}
        name = self.name(file, node)
        if name in primitives:
            return {"type": primitives[name]}
        if name in {"typing.Any", "Any", "object"}:
            gaps.append("unconstrained-python-type")
            return {}
        key = self.resolve(file, node, self.classes)
        if key in self.models:
            return {"$ref": self.ident(*key, "schema")}
        if isinstance(node, ast.BinOp) and isinstance(node.op, ast.BitOr):
            return {"anyOf": [self.annotation(file, node.left, gaps), self.annotation(file, node.right, gaps)]}
        if isinstance(node, ast.Subscript):
            kind = self.name(file, node.value).split(".")[-1]
            parts = node.slice.elts if isinstance(node.slice, ast.Tuple) else [node.slice]
            if kind in {"Optional", "Union"}:
                schemas = [self.annotation(file, part, gaps) for part in parts]
                if kind == "Optional":
                    schemas.append({"type": "null"})
                return {"anyOf": schemas}
            if kind in {"Annotated", "Required", "NotRequired"}:
                if kind == "Annotated":
                    gaps.append("annotated-metadata-not-exported")
                return self.annotation(file, parts[0], gaps)
            if kind in {"list", "List", "Sequence", "set", "Set", "frozenset"}:
                schema = {"type": "array", "items": self.annotation(file, parts[0], gaps)}
                if kind in {"set", "Set", "frozenset"}:
                    schema["uniqueItems"] = True
                return schema
            if kind in {"dict", "Dict", "Mapping"} and len(parts) == 2:
                if self.name(file, parts[0]) != "str":
                    gaps.append("non-string-mapping-keys")
                return {"type": "object", "additionalProperties": self.annotation(file, parts[1], gaps)}
            if kind == "Literal":
                values = [literal(part) for part in parts]
                if all(isinstance(part, ast.Constant) and isinstance(part.value, (str, int, float, bool, type(None))) for part in parts):
                    return {"enum": values}
        gaps.append("unresolved-or-unsupported-annotation")
        return {}

    def add_schema(self, file, symbol, node, schema, gaps, role="declaration"):
        id_ = self.ident(file, symbol, "schema")
        self.result["schemas"].append({"id": id_, "name": symbol, "role": role, "dialect": DIALECT, "schema": {"$schema": DIALECT, "$id": id_, **schema}, "status": "partial" if gaps else "resolved", "evidence": [self.evidence(file, node, symbol=symbol)], "gaps": sorted(set(gaps))})
        return id_

    def declarations(self):
        for (file, symbol), node in sorted(self.classes.items()):
            gaps = []
            declaration = {"id": self.ident(file, symbol, "declaration"), "name": symbol, "kind": "python-class", "language": "python", "exported": not node.name.startswith("_"), "status": "unsupported", "evidence": [self.evidence(file, node, symbol=symbol)], "gaps": gaps}
            if (file, symbol) not in self.models:
                gaps.append("non-model-class-schema-unsupported")
                self.result["declarations"].append(declaration)
                continue
            typed_dict = any(self.name(file, base).endswith("TypedDict") for base in node.bases)
            declaration["kind"] = "typed-dict" if typed_dict else "pydantic-model"
            if not typed_dict:
                gaps.append("pydantic-runtime-semantics-not-exported")
            properties, required = {}, []
            for base in node.bases:
                if self.resolve(file, base, self.classes) in self.models:
                    gaps.append("inherited-fields-not-flattened")
            for member in node.body:
                if isinstance(member, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    for decorator in member.decorator_list:
                        target = decorator.func if isinstance(decorator, ast.Call) else decorator
                        tail = self.name(file, target).split(".")[-1]
                        if "validator" in tail or "serializer" in tail or tail == "computed_field":
                            gaps.append("custom-" + tail + "-not-exported")
                if isinstance(member, (ast.Assign, ast.AnnAssign)):
                    targets = member.targets if isinstance(member, ast.Assign) else [member.target]
                    if any(dotted(target) == "model_config" for target in targets):
                        gaps.append("model-config-not-exported")
                if not isinstance(member, ast.AnnAssign) or not isinstance(member.target, ast.Name) or member.target.id.startswith("_") or member.target.id == "model_config":
                    continue
                field_name = member.target.id
                annotation = member.annotation
                if isinstance(annotation, ast.Subscript) and self.name(file, annotation.value).endswith("ClassVar"):
                    continue
                field_schema = self.annotation(file, annotation, gaps)
                is_required = member.value is None or (isinstance(member.value, ast.Constant) and member.value.value is Ellipsis)
                if typed_dict:
                    is_required = not any(kw.arg == "total" and literal(kw.value) is False for kw in node.keywords)
                    if isinstance(annotation, ast.Subscript):
                        kind = self.name(file, annotation.value).split(".")[-1]
                        if kind in {"Required", "NotRequired"}:
                            is_required = kind == "Required"
                if isinstance(member.value, ast.Call) and self.name(file, member.value.func) in {"pydantic.Field", "Field"}:
                    args = keywords(member.value)
                    default = args.get("default", member.value.args[0] if member.value.args else None)
                    is_required = "default_factory" not in args and (default is None or (isinstance(default, ast.Constant) and default.value is Ellipsis))
                    for alias in {"alias", "validation_alias", "serialization_alias"} & args.keys():
                        gaps.append("field-" + alias.replace("_", "-") + "-requires-wire-projection")
                        alias_value = literal(args[alias])
                        if isinstance(alias_value, str):
                            field_schema["x-python-" + alias.replace("_", "-")] = alias_value
                    for key, mapped in {"gt": "exclusiveMinimum", "ge": "minimum", "lt": "exclusiveMaximum", "le": "maximum", "multiple_of": "multipleOf"}.items():
                        value = literal(args.get(key))
                        if isinstance(value, (int, float)) and not isinstance(value, bool):
                            field_schema[mapped] = value
                    for key in set(args) - {"default", "default_factory", "gt", "ge", "lt", "le", "multiple_of", "alias", "validation_alias", "serialization_alias", "description", "title", "examples"}:
                        gaps.append("field-constraint-not-exported:" + key)
                properties[field_name] = field_schema
                if is_required:
                    required.append(field_name)
            schema = {"type": "object", "properties": properties}
            if required:
                schema["required"] = required
            declaration["schemaId"] = self.add_schema(file, symbol, node, schema, gaps)
            declaration["status"] = "partial" if gaps else "resolved"
            declaration["gaps"] = sorted(set(gaps))
            self.result["declarations"].append(declaration)
        for file, unit in self.units.items():
            for node in unit["tree"].body:
                target = None
                if isinstance(node, ast.AnnAssign) and self.name(file, node.annotation).split(".")[-1] == "TypeAlias":
                    target = node.target
                if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.value, ast.Call) and self.name(file, node.value.func).split(".")[-1] in {"NewType", "TypedDict", "TypeVar", "NamedTuple"}:
                    target = node.targets[0]
                if isinstance(target, ast.Name):
                    self.result["declarations"].append({"id": self.ident(file, target.id, "declaration"), "name": target.id, "kind": "python-type-alias", "language": "python", "exported": not target.id.startswith("_"), "status": "unsupported", "evidence": [self.evidence(file, node, symbol=target.id)], "gaps": ["type-alias-or-functional-type-not-exported"]})

    def router_key(self, file, node):
        return self.resolve(file, node, self.routers)

    def registration(self):
        for file, unit in self.units.items():
            for node in ast.walk(unit["tree"]):
                if isinstance(node, ast.Assign) and isinstance(node.value, ast.Call):
                    kind = self.name(file, node.value.func)
                    if kind not in {"fastapi.FastAPI", "fastapi.APIRouter"}:
                        continue
                    for target in node.targets:
                        if isinstance(target, ast.Name):
                            scope = self.scope(file, node)
                            symbol = ".".join(filter(None, [scope, target.id]))
                            prefix = keywords(node.value).get("prefix")
                            self.routers[file, symbol] = {"prefix": "" if prefix is None else literal(prefix), "app": kind == "fastapi.FastAPI", "node": node, "scope": scope}
        for file, unit in self.units.items():
            for node in ast.walk(unit["tree"]):
                if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == "include_router":
                    parent = self.router_key(file, node.func.value)
                    child_node = node.args[0] if node.args else keywords(node).get("router")
                    child = self.router_key(file, child_node)
                    prefix_node = keywords(node).get("prefix")
                    prefix = "" if prefix_node is None else literal(prefix_node)
                    if parent and child:
                        self.includes.append((parent, child, prefix, file, node))
                    else:
                        self.result["diagnostics"].append({"file": file, "line": node.lineno, "code": "unresolved-router-registration", "message": "Router registration could not be resolved in selected files."})

    def mounts(self, key, visited=None):
        visited = set() if visited is None else visited
        if key in visited:
            return []
        router = self.routers[key]
        prefix = router["prefix"]
        if router["app"]:
            # A factory-local app alone is only a declaration. Require a module call.
            active = not router["scope"]
            if not active:
                for node in self.units[key[0]]["tree"].body:
                    value = node.value if isinstance(node, (ast.Assign, ast.Expr)) else None
                    if isinstance(value, ast.Call) and dotted(value.func) == router["scope"]:
                        active = True
            return [(prefix, [])] if active else []
        paths = []
        for parent, child, extra, file, node in self.includes:
            if child == key:
                for parent_path, evidence in self.mounts(parent, visited | {key}):
                    path = parent_path + extra + prefix if all(isinstance(x, str) for x in [parent_path, extra, prefix]) else None
                    paths.append((path, evidence + [self.evidence(file, node, "registration")]))
        return paths

    def routes(self):
        for (file, symbol), node in sorted(self.functions.items()):
            for ordinal, decorator in enumerate(node.decorator_list):
                if not isinstance(decorator, ast.Call) or not isinstance(decorator.func, ast.Attribute) or decorator.func.attr not in METHODS:
                    continue
                router_key = self.router_key(file, decorator.func.value)
                if router_key is None:
                    continue
                args = keywords(decorator)
                route = literal(decorator.args[0]) if decorator.args else literal(args.get("path"))
                mounts = self.mounts(router_key)
                mounted = bool(mounts)
                if not mounts:
                    mounts = [(self.routers[router_key]["prefix"], [])]
                for mount_index, (prefix, registration) in enumerate(mounts):
                    gaps = ["fastapi-implicit-responses-and-dependencies-not-exported", "query-path-header-and-cookie-parameters-not-exported"]
                    if not mounted:
                        gaps.append("no-static-app-registration")
                    op = {"id": self.ident(file, symbol + ":" + str(ordinal) + ":" + str(mount_index), "operation"), "name": symbol, "kind": "http", "direction": "inbound", "method": decorator.func.attr.upper(), "mounted": mounted, "responses": [], "status": "partial", "evidence": [self.evidence(file, decorator, "declaration", symbol)] + registration, "gaps": gaps}
                    conditional_registration = any(self.conditional(edge_file, edge_node) for _, _, _, edge_file, edge_node in self.includes if any(item["file"] == edge_file and item["line"] == edge_node.lineno for item in registration))
                    if self.conditional(file, decorator) or self.conditional(router_key[0], self.routers[router_key]["node"]) or conditional_registration:
                        op.pop("mounted")
                        gaps.append("conditional-registration-not-evaluated")
                    if isinstance(prefix, str) and isinstance(route, str):
                        op["path"] = prefix + route
                    else:
                        gaps.append("dynamic-route-path-or-prefix")
                    status_node = args.get("status_code")
                    status = 200 if status_node is None else literal(status_node)
                    response = {"status": str(status)} if isinstance(status, int) and 100 <= status <= 599 else None
                    if response is None:
                        gaps.append("dynamic-response-status")
                    response_annotation = args.get("response_model", node.returns)
                    has_response_type = response_annotation is not None and not (isinstance(response_annotation, ast.Constant) and response_annotation.value is None)
                    if response and has_response_type:
                        response_gaps = []
                        schema = self.annotation(file, response_annotation, response_gaps)
                        if status not in {204, 304}:
                            response["schemaId"] = self.add_schema(file, symbol + ":response:" + str(ordinal), node, schema, response_gaps, "output")
                            if "response_class" not in args:
                                response["mediaType"] = "application/json"
                        else:
                            gaps.append("bodyless-status-with-response-annotation")
                        gaps.extend(response_gaps)
                    if response:
                        op["responses"].append(response)
                    body_params = [arg for arg in node.args.args + node.args.kwonlyargs if self.resolve(file, arg.annotation, self.classes) in self.models]
                    if len(body_params) == 1:
                        key = self.resolve(file, body_params[0].annotation, self.classes)
                        op["requestSchemaId"] = self.ident(*key, "schema")
                        op["requestMediaType"] = "application/json"
                        gaps.append("parameter-binding-and-dependency-overrides-not-resolved")
                    elif len(body_params) > 1:
                        gaps.append("multiple-model-body-parameters-not-composed")
                    if any(key.startswith("response_model_") or key in {"response_class", "responses", "dependencies"} for key in args):
                        gaps.append("response-serialization-or-route-options-not-exported")
                    op["gaps"] = sorted(set(gaps))
                    self.result["operations"].append(op)

    def client(self, file, node, seen=None):
        node = unwrap(node)
        seen = set() if seen is None else seen
        if node is None or id(node) in seen:
            return False
        seen = seen | {id(node)}
        if self.name(file, node) in {"requests", "httpx", "aiohttp"}:
            return True
        if isinstance(node, ast.Call):
            if self.name(file, node.func) in CLIENTS:
                return True
            key = self.resolve(file, node.func, self.functions)
            if key:
                annotation = self.functions[key].returns
                return self.name(key[0], annotation) in CLIENTS
        scope = self.scope(file, node)
        name = dotted(node)
        if not name:
            return False
        for candidate in ast.walk(self.units[file]["tree"]):
            if self.scope(file, candidate) != scope:
                continue
            if isinstance(candidate, ast.Assign) and any(dotted(target) == name for target in candidate.targets):
                if self.client(file, candidate.value, seen):
                    return True
            if isinstance(candidate, ast.AnnAssign) and dotted(candidate.target) == name:
                if self.name(file, candidate.annotation) in CLIENTS or self.client(file, candidate.value, seen):
                    return True
            if isinstance(candidate, ast.arg) and candidate.arg == name and self.name(file, candidate.annotation) in CLIENTS:
                return True
            if isinstance(candidate, ast.withitem) and dotted(candidate.optional_vars) == name and self.client(file, candidate.context_expr, seen):
                return True
        return False

    def clients(self):
        for file, unit in self.units.items():
            for node in ast.walk(unit["tree"]):
                if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
                    continue
                if node.func.attr not in METHODS | {"request"} or not self.client(file, node.func.value):
                    continue
                args = keywords(node)
                general = node.func.attr == "request"
                method = literal(node.args[0]) if general and node.args else literal(args.get("method")) if general else node.func.attr.upper()
                url_node = node.args[1 if general else 0] if len(node.args) > (1 if general else 0) else args.get("url")
                gaps = ["client-call-is-not-provider-guarantee", "response-status-and-schema-unresolved"]
                scope = self.scope(file, node)
                op = {"id": self.ident(file, scope + ":" + str(node.lineno) + ":" + str(node.col_offset), "operation"), "name": scope or "module-client-call", "kind": "http", "direction": "outbound", "responses": [], "status": "partial", "evidence": [self.evidence(file, node, "static-call", scope)], "gaps": gaps}
                if isinstance(method, str) and method.lower() in METHODS:
                    op["method"] = method.upper()
                else:
                    gaps.append("dynamic-http-method")
                url = literal(url_node)
                if isinstance(url, str):
                    parsed = urlsplit(url)
                    if parsed.scheme in {"http", "https"} and parsed.netloc and not parsed.username and not parsed.password:
                        op["server"] = parsed.scheme + "://" + parsed.netloc
                        op["path"] = parsed.path or "/"
                        if parsed.query or parsed.fragment:
                            gaps.append("query-or-fragment-values-omitted")
                    elif url.startswith("/") and not url.startswith("//"):
                        op["path"] = parsed.path
                        gaps.append("base-url-unresolved")
                    else:
                        gaps.append("url-unresolved-or-sensitive")
                else:
                    gaps.append("dynamic-url-unresolved")
                if "json" in args:
                    op["requestMediaType"] = "application/json"
                    gaps.append("request-body-schema-unresolved")
                if "headers" in args or "auth" in args:
                    gaps.append("authentication-and-header-values-not-exported")
                # Preserve only option names/booleans, never expressions or payloads.
                dumps = []
                for candidate in ast.walk(unit["tree"]):
                    if self.scope(file, candidate) == scope and isinstance(candidate, ast.Call) and isinstance(candidate.func, ast.Attribute) and candidate.func.attr in {"model_dump", "model_dump_json"}:
                        options = {key: literal(value) for key, value in keywords(candidate).items() if key in {"by_alias", "exclude_none", "exclude_unset", "exclude_defaults"} and isinstance(literal(value), bool)}
                        dumps.append({"method": candidate.func.attr, "options": options, "association": "same-scope-only"})
                        op["evidence"].append(self.evidence(file, candidate, "serialization"))
                if dumps:
                    op["details"] = {"nearbySerialization": dumps}
                    gaps.append("serialization-options-require-wire-projection;call-association-unresolved")
                self.result["operations"].append(op)

    def run(self):
        self.declarations()
        self.registration()
        self.routes()
        self.clients()
        # Multiple route decorators can share the same response schema.
        self.result["schemas"] = list({schema["id"]: schema for schema in self.result["schemas"]}.values())
        for schema in self.result["schemas"]:
            def references(value):
                if isinstance(value, dict):
                    if "$ref" in value:
                        yield value["$ref"]
                    for child in value.values():
                        yield from references(child)
                elif isinstance(value, list):
                    for child in value:
                        yield from references(child)
            for target in sorted(set(references(schema["schema"]))):
                self.result["relationships"].append({"source": schema["id"], "target": target, "kind": "references", "evidence": schema["evidence"]})
        for operation in self.result["operations"]:
            ids = ([operation["requestSchemaId"]] if "requestSchemaId" in operation else []) + [response["schemaId"] for response in operation["responses"] if "schemaId" in response]
            for target in sorted(set(ids)):
                self.result["relationships"].append({"source": operation["id"], "target": target, "kind": "references", "evidence": operation["evidence"]})
        return self.result


def main():
    try:
        request = json.load(sys.stdin)
        if not isinstance(request, dict) or request.get("protocolVersion") != 1:
            raise ValueError("protocol")
        repo = request.get("repository")
        if not isinstance(repo, dict) or any(not isinstance(repo.get(key), str) or not repo[key] for key in ["id", "root", "revision"]):
            raise ValueError("repository")
        if not isinstance(request.get("files"), list) or any(not isinstance(file, str) for file in request["files"]):
            raise ValueError("files")
        json.dump(Scanner(request).run(), sys.stdout, sort_keys=True, allow_nan=False)
        sys.stdout.write("\n")
    except (ValueError, TypeError, KeyError, RecursionError):
        print("Invalid scan request or unsupported recursive input; no target code executed.", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
