/** Versioned static-analysis adapter protocol. No adapter may import/execute target code. */
export type JsonSchema = Record<string, unknown>;
export type ExtractionStatus = 'resolved' | 'partial' | 'unsupported';
export interface Repository { id: string; root: string; revision: string; }
export interface ScanRequest {
  protocolVersion: 1;
  repository: Repository;
  /** POSIX paths relative to repository.root, explicitly selected by the coordinator. */
  files: string[];
}
export interface Evidence {
  file: string;
  line: number;
  symbol?: string;
  basis: 'declaration' | 'registration' | 'client-expectation' | 'runtime-validation' | 'serialization' | 'static-call';
}
export interface Declaration {
  id: string;
  name: string;
  kind: string;
  language: 'typescript' | 'python';
  exported: boolean;
  status: ExtractionStatus;
  evidence: Evidence[];
  schemaId?: string;
  gaps: string[];
}
export interface SchemaRecord {
  id: string;
  name: string;
  role: 'input' | 'output' | 'wire' | 'declaration';
  /** A conservative static projection; absence is preferable to fabricated constraints. */
  schema?: JsonSchema;
  dialect: string;
  status: ExtractionStatus;
  evidence: Evidence[];
  gaps: string[];
}
export interface HttpResponse {
  status: string;
  mediaType?: string;
  schemaId?: string;
}
export interface Operation {
  id: string;
  kind: 'http' | 'tool' | 'message' | 'storage';
  name: string;
  direction: 'inbound' | 'outbound' | 'internal';
  /** owning service/provider if established; never guess it from a type name. */
  owner?: string;
  method?: string;
  path?: string;
  server?: string;
  mounted?: boolean;
  requestSchemaId?: string;
  requestMediaType?: string;
  responses: HttpResponse[];
  status: ExtractionStatus;
  evidence: Evidence[];
  gaps: string[];
  /** Expressions and behavior facts, never credential values or example payloads. */
  details?: Record<string, unknown>;
}
export interface Relationship {
  source: string;
  target: string;
  kind: 'references' | 'calls' | 'registers' | 'validates' | 'serializes';
  evidence: Evidence[];
}
export interface Diagnostic {
  file?: string;
  line?: number;
  code: string;
  message: string;
}
export interface FileResult {
  path: string;
  status: 'examined' | 'failed' | 'unsupported';
}
export interface AdapterResult {
  protocolVersion: 1;
  adapter: { name: string; version: string; capabilities: string[]; limitations: string[] };
  declarations: Declaration[];
  schemas: SchemaRecord[];
  operations: Operation[];
  relationships: Relationship[];
  files: FileResult[];
  diagnostics: Diagnostic[];
}
