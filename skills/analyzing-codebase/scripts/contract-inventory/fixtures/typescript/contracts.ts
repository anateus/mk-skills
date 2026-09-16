import { z } from 'zod';
import { initContract } from '@ts-rest/core';
import { createExpressEndpoints } from '@ts-rest/express';
import axios from 'axios';
import type { Shared as ImportedShared } from './shared.js';
interface Internal { shared: ImportedShared; next?: Internal; tags: string[] }
export type State = 'ready' | 'done';
export const Input = z.object({ name: z.string().min(2), state: z.enum(['ready', 'done']).optional() }).refine(value => value.name !== 'blocked');
const c = initContract();
export const contract = c.router({
  list: { method: 'GET', path: '/widgets', responses: { 200: Input, 400: z.object({ error: z.string() }) } },
  create: { method: 'POST', path: '/widgets', body: Input, responses: { 201: Input, 422: z.object({ error: z.string() }) } },
  remove: { method: 'DELETE', path: '/widgets/:id', responses: { 204: null } },
}, { pathPrefix: '/v1' });
createExpressEndpoints(contract, handlers, app);
export const unmounted = c.router({ waiting: { method: 'GET', path: '/waiting', responses: { 200: z.string() } } });
fetch('https://provider.invalid/widgets?token=DO_NOT_EMIT', { method: 'POST', headers: { Authorization: 'SECRET_HEADER_SENTINEL' }, body: 'SECRET_BODY_SENTINEL' });
fetch(dynamicUrl);
const client = axios.create({ baseURL: 'https://provider.invalid' });
client.delete('/widgets/42');
function getWidget(url: string) { return fetch(url); }
getWidget('https://provider.invalid/widgets');
export const VAPI_TOOLS_MAP = { resolveTarget: resolveTarget, initiatePayment: paymentHandler };
export const TELNYX_TOOLS_BY_NAME = { resolveTarget: { handler: resolveTarget, assistantResult: 'none' } };
export const dynamicContract = c.router({ candidate: { method: runtimeMethod, path: '/dynamic', responses: { 200: z.string() } } });
export const toolsMap = { LEGACY_PROVIDER: { charge: paymentHandler } };
