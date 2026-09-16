import type { Identifier } from './shared';
type Internal = { marker: 'internal' };
export interface Node { id: Identifier; next?: Node; }
export type Event = { kind: 'created'; node: Node } | { kind: 'deleted'; id: Identifier };
export type Envelope<T> = { value: T; metadata?: Internal };
export type Payload = Envelope<Event>;
