export interface Child {
  name: string;
  enabled: boolean;
}

export interface TypescriptPayload {
  name: string;
  required_nullable: string | null;
  optional_name?: string;
  action: 'keep' | 'drop';
  child: Child;
  children: Child[];
  count: number;
}
