#!/usr/bin/env node
import * as path from 'node:path';
import { scan, type ScanOptions } from './inventory.js';
import { buildBundle, writeBundle } from './export.js';

const usage = `Usage: node dist/cli.js scan --root ID=/absolute/repository [--root ...] --out DIRECTORY
  --include PATH       Select a relative file/directory (repeatable; ID:PATH scopes to one root)
  --python EXECUTABLE  Python interpreter for static AST adapter (default: python3)
Default exclusions include dependencies, build output, docs, tests, fixtures, and symlinks.
Outputs are partial static contract inventories. No analyzed application code is executed.
Exit codes: 0 partial scan produced, 1 invocation/output error, 2 adapter/file failures.
`;

export function parseArgs(args: string[]): ScanOptions {
  if (args.shift() !== 'scan') throw new Error('Expected scan command');
  const options: ScanOptions = { roots: [], includes: [], python: 'python3', out: '' };
  while (args.length) {
    const flag = args.shift()!;
    const value = args.shift();
    if (!value || value.startsWith('--')) throw new Error(`Missing value for ${flag}`);
    if (flag === '--root') {
      const separator = value.indexOf('=');
      if (separator < 1) throw new Error('Root must use ID=/absolute/repository');
      options.roots.push({ id: value.slice(0, separator), root: path.resolve(value.slice(separator + 1)) });
    } else if (flag === '--include') options.includes.push(value);
    else if (flag === '--python') options.python = value;
    else if (flag === '--out') options.out = path.resolve(value);
    else throw new Error(`Unknown option: ${flag}`);
  }
  if (!options.roots.length || !options.out) throw new Error('--root and --out are required');
  for (const root of options.roots) if (path.resolve(root.root) === options.out) throw new Error('Output cannot replace a repository root');
  for (const include of options.includes) if (include.includes(':') && !options.roots.some(root => root.id === include.slice(0, include.indexOf(':')))) throw new Error('Include references an unknown repository ID');
  return options;
}

try {
  const args = process.argv.slice(2);
  if (!args.length || args.includes('--help')) process.stdout.write(usage);
  else {
    const options = parseArgs(args);
    const inventory = scan(options);
    const bundle = buildBundle(inventory);
    const output = writeBundle(bundle, options.out);
    process.stdout.write(JSON.stringify({ output, status: bundle.failed ? 'failed' : 'partial', repositories: inventory.repositories.length, declarations: inventory.declarations.length, operations: inventory.operations.length }) + '\n');
    process.exitCode = bundle.failed ? 2 : 0;
  }
} catch (error) {
  process.stderr.write(`contract-inventory: ${error instanceof Error ? error.message : 'scan failed'}\n`);
  process.exitCode = 1;
}
