#!/usr/bin/env node
// codex-run v2 — drives `codex app-server` (JSON-RPC 2.0-ish over stdio,
// newline-delimited JSON; the wire omits the "jsonrpc" field) instead of
// shelling out to `codex exec`. Gives per-turn sandbox policy, background
// jobs (status/wait/cancel), thread resume, and a raw event log.
//
// Protocol shapes verified against `codex app-server generate-json-schema`
// (codex-cli 0.154.0) and confirmed against real events.jsonl from live runs.

import { spawn } from "node:child_process";
import fs from "node:fs";
import path from "node:path";
import os from "node:os";
import crypto from "node:crypto";
import { fileURLToPath } from "node:url";

const SELF_PATH = fileURLToPath(import.meta.url);
const HOME = os.homedir();
const STATE_DIR = process.env.CODEX_RUN_STATE_DIR
  ? path.resolve(process.env.CODEX_RUN_STATE_DIR)
  : path.join(HOME, ".local", "state", "codex-run");
const JOBS_DIR = path.join(STATE_DIR, "jobs");
// Skill root (skills/delegating-to-codex), so `--preset <name>` can resolve
// against this checkout's presets/ regardless of cwd or how codex-run was
// invoked (symlinked into ~/.local/bin, run in place, etc).
const SKILL_DIR = path.resolve(path.dirname(SELF_PATH), "..");
const PRESETS_DIR = path.join(SKILL_DIR, "presets");

const USAGE = `codex-run -p prompt.md -o last.md [-C workdir] [-m model] [-e effort] [-s sandbox] [--net] [-w path]... [-c key=value]... [--preset name|path] [-r thread_id] [-l log] [-b] [--timeout secs]
codex-run status <job|thread_id>
codex-run wait <job|thread_id> [--timeout secs]
codex-run cancel <job|thread_id>
codex-run list
codex-run -h`;

function usageExit(msg) {
  if (msg) process.stderr.write(msg + "\n");
  process.stderr.write(USAGE + "\n");
  process.exit(2);
}

function nowIso() {
  return new Date().toISOString();
}

function ensureDirs() {
  fs.mkdirSync(JOBS_DIR, { recursive: true });
}

function jobPath(jobId) {
  return path.join(JOBS_DIR, `${jobId}.json`);
}

function readJob(jobId) {
  return JSON.parse(fs.readFileSync(jobPath(jobId), "utf8"));
}

function writeJobAtomic(job) {
  const p = jobPath(job.jobId);
  const tmp = p + ".tmp";
  fs.writeFileSync(tmp, JSON.stringify(job, null, 2));
  fs.renameSync(tmp, p);
}

function listJobs() {
  ensureDirs();
  const files = fs.readdirSync(JOBS_DIR).filter((f) => f.endsWith(".json") && !f.endsWith(".tmp"));
  const jobs = [];
  for (const f of files) {
    try {
      jobs.push(JSON.parse(fs.readFileSync(path.join(JOBS_DIR, f), "utf8")));
    } catch {
      // skip unreadable/partial job files
    }
  }
  jobs.sort((a, b) => (b.startedAt || "").localeCompare(a.startedAt || ""));
  return jobs;
}

// Resolve a "job|thread_id" argument to a job record (searches by jobId
// first, then by threadId across all job files — most recent wins).
function findJob(idOrThread) {
  ensureDirs();
  const direct = jobPath(idOrThread);
  if (fs.existsSync(direct)) return readJob(idOrThread);
  const jobs = listJobs();
  const match = jobs.find((j) => j.threadId === idOrThread);
  if (match) return match;
  return null;
}

function genJobId() {
  const d = new Date();
  const yyyymmdd = d.toISOString().slice(0, 10).replace(/-/g, "");
  const hex = crypto.randomBytes(3).toString("hex");
  return `cr-${yyyymmdd}-${hex}`;
}

// ---------------------------------------------------------------------------
// Minimal JSON-RPC-ish client for `codex app-server`.
// Wire messages are newline-delimited JSON. Requests/responses carry `id`;
// the `jsonrpc` field is omitted (confirmed on the wire, not just per spec).
// ---------------------------------------------------------------------------
class AppServerClient {
  constructor(cwd) {
    this.cwd = cwd;
    this.onNotification = null;
    this.onServerRequest = null;
    this.nextId = 1;
    this.pending = new Map();
    this.buffer = "";
    this.stderrBuf = "";
    this.exited = false;
    this.exitError = null;
    this._exitWaiters = [];
    this.rawLogFn = null;
  }

  start() {
    this.proc = spawn("codex", ["app-server"], {
      cwd: this.cwd,
      stdio: ["pipe", "pipe", "pipe"],
    });
    this.proc.stdout.setEncoding("utf8");
    this.proc.stderr.setEncoding("utf8");
    this.proc.stdout.on("data", (chunk) => this._handleChunk(chunk));
    this.proc.stderr.on("data", (chunk) => {
      this.stderrBuf += chunk;
    });
    this.proc.on("error", (err) => this._handleExit(err));
    this.proc.on("exit", (code, signal) => {
      const err =
        code === 0 || code === null
          ? null
          : new Error(`codex app-server exited (code=${code} signal=${signal}): ${this.stderrBuf.trim().slice(-2000)}`);
      this._handleExit(err);
    });
  }

  _handleChunk(chunk) {
    this.buffer += chunk;
    let idx;
    while ((idx = this.buffer.indexOf("\n")) !== -1) {
      const line = this.buffer.slice(0, idx);
      this.buffer = this.buffer.slice(idx + 1);
      if (line.trim()) this._handleLine(line);
    }
  }

  _handleLine(line) {
    let msg;
    try {
      msg = JSON.parse(line);
    } catch (e) {
      this._handleExit(new Error(`Failed to parse app-server line as JSON: ${e.message}`));
      return;
    }
    if (this.rawLogFn) this.rawLogFn(msg);
    if (msg.id !== undefined && msg.method) {
      // server-initiated request
      if (this.onServerRequest) this.onServerRequest(msg);
      return;
    }
    if (msg.id !== undefined) {
      const pending = this.pending.get(msg.id);
      if (!pending) return;
      this.pending.delete(msg.id);
      if (msg.error) pending.reject(new Error(msg.error.message || `request ${pending.method} failed`));
      else pending.resolve(msg.result ?? {});
      return;
    }
    if (msg.method && this.onNotification) this.onNotification(msg);
  }

  _handleExit(err) {
    if (this.exited) return;
    this.exited = true;
    this.exitError = err || null;
    for (const p of this.pending.values()) {
      p.reject(err || new Error("codex app-server connection closed"));
    }
    this.pending.clear();
    for (const w of this._exitWaiters) w();
    this._exitWaiters = [];
  }

  waitExit() {
    return new Promise((resolve) => {
      if (this.exited) return resolve();
      this._exitWaiters.push(resolve);
    });
  }

  send(method, params) {
    const id = this.nextId++;
    const payload = { id, method, params };
    return new Promise((resolve, reject) => {
      if (this.exited) return reject(this.exitError || new Error("codex app-server connection closed"));
      this.pending.set(id, { resolve, reject, method });
      this._write(payload);
    });
  }

  notify(method, params) {
    this._write({ method, params });
  }

  respond(id, result) {
    this._write({ id, result });
  }

  respondError(id, code, message) {
    this._write({ id, error: { code, message } });
  }

  _write(obj) {
    if (this.rawLogFn) this.rawLogFn(obj, true);
    this.proc.stdin.write(JSON.stringify(obj) + "\n");
  }
}

// ---------------------------------------------------------------------------
// CLI parsing
// ---------------------------------------------------------------------------
function parseArgs(argv) {
  const sub = argv[0] && !argv[0].startsWith("-") ? argv[0] : null;
  if (sub === "status" || sub === "wait" || sub === "cancel" || sub === "list") {
    const rest = argv.slice(1);
    const opts = { timeout: null };
    const positional = [];
    for (let i = 0; i < rest.length; i++) {
      const a = rest[i];
      if (a === "--timeout") opts.timeout = Number(rest[++i]);
      else positional.push(a);
    }
    return { sub, positional, opts };
  }
  if (argv.includes("-h") || argv.includes("--help")) return { sub: "help" };

  const o = {
    prompt: null,
    out: null,
    cwd: process.cwd(),
    model: "gpt-5.6-luna",
    effort: null,
    sandbox: "workspace-write",
    net: false,
    writableRoots: [],
    resumeThread: null,
    log: null,
    background: false,
    timeout: null,
    printPolicy: false,
    workerJobFile: null,
    configOverrides: [],
    preset: null,
    sandboxExplicit: false,
  };
  for (let i = 0; i < argv.length; i++) {
    const a = argv[i];
    switch (a) {
      case "-p":
        o.prompt = argv[++i];
        break;
      case "-o":
        o.out = argv[++i];
        break;
      case "-C":
        o.cwd = argv[++i];
        break;
      case "-m":
        o.model = argv[++i];
        break;
      case "-e":
        o.effort = argv[++i];
        break;
      case "-s":
        o.sandbox = argv[++i];
        o.sandboxExplicit = true;
        break;
      case "--net":
        o.net = true;
        break;
      case "-w":
        o.writableRoots.push(argv[++i]);
        break;
      case "-c":
      case "--config":
        o.configOverrides.push(argv[++i]);
        break;
      case "--preset":
        o.preset = argv[++i];
        break;
      case "-r":
        o.resumeThread = argv[++i];
        break;
      case "-l":
        o.log = argv[++i];
        break;
      case "-b":
        o.background = true;
        break;
      case "--timeout":
        o.timeout = Number(argv[++i]);
        break;
      case "--worker":
        o.workerJobFile = argv[++i];
        break;
      case "--print-policy":
        o.printPolicy = true;
        break;
      default:
        usageExit(`Unknown argument: ${a}`);
    }
  }
  return { sub: "run", opts: o };
}

// "none" sends no sandbox mode and no per-turn sandboxPolicy at all, so the
// thread falls through to Codex's permission-profile system (default_permissions
// + [permissions.<name>] in config, or supplied via -c). Codex ignores
// default_permissions whenever a legacy sandbox mode is present, which is why
// this has to be a distinct mode rather than a flag on top of workspace-write.
function validSandbox(s) {
  return s === "read-only" || s === "workspace-write" || s === "danger-full-access" || s === "none";
}

function buildSandboxPolicy(sandbox, net, writableRoots) {
  if (sandbox === "none") return null;
  if (sandbox === "danger-full-access") return { type: "dangerFullAccess" };
  if (sandbox === "read-only") return { type: "readOnly", networkAccess: !!net };
  return {
    type: "workspaceWrite",
    networkAccess: !!net,
    writableRoots,
    excludeSlashTmp: false,
    excludeTmpdirEnvVar: false,
  };
}

// Resolve `--preset <name|path>` to a JSON file: a bare name (no slash)
// resolves against this skill's presets/ directory; anything with a slash
// is a path, resolved relative to cwd. Loaded eagerly (not lazily) so a
// bad preset fails fast with rc 2, same as any other usage error.
function resolvePresetPath(nameOrPath) {
  if (nameOrPath.includes("/") || nameOrPath.includes(path.sep)) return path.resolve(nameOrPath);
  return path.join(PRESETS_DIR, `${nameOrPath}.json`);
}

function loadPresetFile(nameOrPath) {
  const filePath = resolvePresetPath(nameOrPath);
  let raw;
  try {
    raw = fs.readFileSync(filePath, "utf8");
  } catch (e) {
    usageExit(`preset not found: ${nameOrPath} (resolved ${filePath}): ${e.message}`);
  }
  let json;
  try {
    json = JSON.parse(raw);
  } catch (e) {
    usageExit(`invalid preset JSON: ${filePath}: ${e.message}`);
  }
  if (!json || typeof json !== "object" || Array.isArray(json)) {
    usageExit(`invalid preset: ${filePath} (expected a JSON object of config overrides)`);
  }
  return json;
}

// A preset is a plain object of dotted config keys (same shape -c produces),
// plus two pseudo-keys codex-run consumes itself and never forwards to
// Codex: `$sandbox` (picks the -s mode when the caller didn't pass -s) and
// `_comment`/`$anything` (documentation, stripped). Any `$`- or `_`-prefixed
// key is dropped from the merged config for the same reason.
function splitPresetConfig(preset) {
  let sandbox = null;
  const cfg = {};
  for (const [key, value] of Object.entries(preset)) {
    if (key === "$sandbox") {
      sandbox = value;
      continue;
    }
    if (key.startsWith("$") || key.startsWith("_")) continue;
    cfg[key] = value;
  }
  return { sandbox, cfg };
}

// The exec tool enforces the *thread's* sandbox, not the per-turn
// sandboxPolicy (observed: turn-level writableRoots were echoed back but
// index.lock writes were still denied). So writable roots and network go
// in as thread-level config overrides too; the turn policy stays for
// clients that do honor it.
//
// Merge order is preset first, then `-c` overrides, so a caller can use a
// preset as a base and override individual keys per run. `-c key=value`
// (same shape as codex's own -c: dotted config key, value parsed as JSON,
// falling back to the raw string), e.g.
//   -c features.network_proxy=true -c 'features.network_proxy.domains={"api.github.com":"allow"}'
function buildThreadConfig(sandboxPolicy, configOverrides = [], presetConfig = null) {
  const cfg = {};
  if (sandboxPolicy && sandboxPolicy.type === "workspaceWrite") {
    if (sandboxPolicy.writableRoots.length) cfg["sandbox_workspace_write.writable_roots"] = sandboxPolicy.writableRoots;
    if (sandboxPolicy.networkAccess) cfg["sandbox_workspace_write.network_access"] = true;
  }
  if (presetConfig) {
    for (const [key, value] of Object.entries(presetConfig)) cfg[key] = value;
  }
  for (const kv of configOverrides) {
    const eq = kv.indexOf("=");
    if (eq <= 0) usageExit(`bad -c override (want key=value): ${kv}`);
    const key = kv.slice(0, eq);
    const raw = kv.slice(eq + 1);
    let value;
    try {
      value = JSON.parse(raw);
    } catch {
      value = raw;
    }
    cfg[key] = value;
  }
  return Object.keys(cfg).length ? cfg : null;
}

// Compute the effective run policy (cwd, sandboxPolicy, thread-level config
// override) without touching the network or spawning codex. Shared by the
// real run path and `--print-policy` (a debug entry point so tests can
// assert this offline).
function computeEffectivePolicy(o) {
  const cwd = path.resolve(o.cwd);
  const writableRoots = o.writableRoots.map((p) => path.resolve(cwd, p));

  let sandbox = o.sandbox;
  let presetConfig = null;
  if (o.preset) {
    const preset = loadPresetFile(o.preset);
    const split = splitPresetConfig(preset);
    presetConfig = split.cfg;
    if (split.sandbox != null && !o.sandboxExplicit) sandbox = split.sandbox;
  }
  if (!validSandbox(sandbox)) usageExit(`invalid sandbox (from ${o.sandboxExplicit ? "-s" : "preset $sandbox"}): ${sandbox}`);

  const sandboxPolicy = buildSandboxPolicy(sandbox, o.net, writableRoots);
  const threadConfig = buildThreadConfig(sandboxPolicy, o.configOverrides || [], presetConfig);
  return { cwd, writableRoots, sandboxPolicy, threadConfig, sandbox };
}

// ---------------------------------------------------------------------------
// Logging helpers
// ---------------------------------------------------------------------------
function makeLogger(logPath) {
  const stream = fs.createWriteStream(logPath, { flags: "a" });
  return (line) => {
    stream.write(`[${nowIso()}] ${line}\n`);
  };
}

function makeEventLogger(eventsPath) {
  const stream = fs.createWriteStream(eventsPath, { flags: "a" });
  return (msg, isOutgoing) => {
    const rec = { ts: nowIso(), dir: isOutgoing ? "out" : "in", ...msg };
    stream.write(JSON.stringify(rec) + "\n");
  };
}

function shorten(text, limit = 200) {
  const s = String(text ?? "").trim().replace(/\s+/g, " ");
  return s.length <= limit ? s : s.slice(0, limit) + "…";
}

// ---------------------------------------------------------------------------
// Core turn runner — used by both foreground and background(worker) paths.
// Returns { status, error, threadId, turnId, agentMessages, sawAnyAgentMessage }
// ---------------------------------------------------------------------------
async function runTurn(o, job, log, logEvent) {
  const client = new AppServerClient(o.cwd);
  client.rawLogFn = logEvent;

  let resolveDone;
  const done = new Promise((res) => (resolveDone = res));
  let finished = false;
  let agentMessages = [];
  let threadId = job.threadId || null;
  let turnId = null;
  let sawAnyAgentMessage = false;

  function finish(result) {
    if (finished) return;
    finished = true;
    resolveDone(result);
  }

  client.onNotification = (msg) => {
    const p = msg.params || {};
    switch (msg.method) {
      case "thread/started":
        threadId = p.thread && p.thread.id;
        job.threadId = threadId;
        writeJobAtomic(job);
        log(`thread/started threadId=${threadId}`);
        break;
      case "turn/started":
        turnId = p.turn && p.turn.id;
        job.turnId = turnId;
        writeJobAtomic(job);
        log(`turn/started turnId=${turnId} threadId=${p.threadId}`);
        break;
      case "item/started":
        break; // no per-item log line needed on start; completed carries detail
      case "item/completed": {
        const item = p.item || {};
        if (item.type === "agentMessage") {
          sawAnyAgentMessage = true;
          agentMessages.push(item.text || "");
          log(`agentMessage: ${shorten(item.text)}`);
        } else if (item.type === "commandExecution") {
          log(`commandExecution: ${shorten(item.command, 300)} exit=${item.exitCode}`);
        } else if (item.type === "fileChange") {
          const paths = (item.changes || []).map((c) => c.path).join(", ");
          log(`fileChange: [${paths}] status=${item.status}`);
        }
        break;
      }
      case "turn/completed": {
        const t = p.turn || {};
        turnId = t.id || turnId;
        log(`turn/completed status=${t.status} turnId=${turnId}`);
        finish({ status: t.status });
        break;
      }
      case "error": {
        const e = p.error || {};
        log(`error: ${e.message}`);
        finish({ status: "failed", error: e.message });
        break;
      }
      case "warning":
        log(`warning: ${p.message}`);
        break;
      default:
        break;
    }
  };

  client.onServerRequest = (msg) => {
    // With approvalPolicy "never" these should not occur, but never hang.
    // Only commandExecution/fileChange approval requests take a
    // {decision: ...} result (schema: CommandExecutionApprovalDecision,
    // FileChangeApprovalDecision both include "decline"). item/permissions/
    // requestApproval expects {permissions, scope} instead, which codex-run
    // doesn't have an answer for, and future builds may add other server
    // request methods entirely — reply with a JSON-RPC method-not-found
    // error for anything we don't recognize rather than guessing a shape.
    if (msg.method === "item/commandExecution/requestApproval" || msg.method === "item/fileChange/requestApproval") {
      log(`server request (unexpected under approvalPolicy=never): ${msg.method} — declining`);
      client.respond(msg.id, { decision: "decline" });
    } else {
      log(`server request: unhandled method ${msg.method} — responding with method-not-found`);
      client.respondError(msg.id, -32601, `codex-run does not handle ${msg.method}`);
    }
  };

  client.start();
  const exitPromise = client.waitExit().then(() => {
    finish({ status: "failed", error: `app-server exited: ${client.exitError ? client.exitError.message : "unknown"}` });
  });

  try {
    const sandboxPolicy = o.sandboxPolicy;
    const config = o.threadConfig ?? null;

    await client.send("initialize", {
      clientInfo: { name: "codex-run", title: "codex-run", version: "2.0.0" },
      capabilities: null,
    });
    client.notify("initialized", {});

    if (o.resumeThread) {
      log(`thread/resume threadId=${o.resumeThread}`);
      const resp = await client.send("thread/resume", {
        threadId: o.resumeThread,
        cwd: o.cwd,
        model: o.model,
        approvalPolicy: "never",
        sandbox: o.sandbox === "none" ? null : o.sandbox,
        config,
      });
      threadId = (resp.thread && resp.thread.id) || o.resumeThread;
    } else {
      log(`thread/start cwd=${o.cwd} model=${o.model} sandbox=${o.sandbox}`);
      const resp = await client.send("thread/start", {
        cwd: o.cwd,
        model: o.model,
        approvalPolicy: "never",
        sandbox: o.sandbox === "none" ? null : o.sandbox,
        serviceName: "codex-run",
        ephemeral: false,
        config,
      });
      threadId = resp.thread && resp.thread.id;
    }
    job.threadId = threadId;
    writeJobAtomic(job);
    log(`sandboxPolicy=${JSON.stringify(sandboxPolicy)}`);

    const turnParams = {
      threadId,
      input: [{ type: "text", text: o.prompt }],
      model: o.model,
      approvalPolicy: "never",
      cwd: o.cwd,
    };
    if (sandboxPolicy) turnParams.sandboxPolicy = sandboxPolicy;
    if (o.effort) turnParams.effort = o.effort;

    const turnResp = await client.send("turn/start", turnParams);
    turnId = turnResp.turn && turnResp.turn.id;
    job.turnId = turnId;
    writeJobAtomic(job);

    // Wire up SIGTERM -> turn/interrupt for background worker cancellation.
    let interrupting = false;
    const onSigterm = async () => {
      if (interrupting) return;
      interrupting = true;
      log("SIGTERM received, sending turn/interrupt");
      try {
        await client.send("turn/interrupt", { threadId, turnId });
      } catch (e) {
        log(`turn/interrupt failed: ${e.message}`);
      }
      const timer = setTimeout(() => {
        log("turn/interrupt: no turn/completed within 15s, forcing interrupted state");
        finish({ status: "interrupted" });
      }, 15000);
      await done;
      clearTimeout(timer);
    };
    process.on("SIGTERM", onSigterm);

    const result = await Promise.race([done, exitPromise.then(() => done)]);
    process.removeListener("SIGTERM", onSigterm);

    return {
      status: result.status || "failed",
      error: result.error,
      threadId,
      turnId,
      agentMessages,
      sawAnyAgentMessage,
    };
  } finally {
    try {
      client.proc && client.proc.stdin.end();
      client.proc && client.proc.kill();
    } catch {
      // best-effort cleanup
    }
  }
}

function statusToRc(status) {
  if (status === "completed") return 0;
  if (status === "interrupted") return 130;
  if (status === "failed") return 1;
  return 3;
}

function printOneLiner(job) {
  const line = `exit=${job.rc} session=${job.threadId || ""} out=${job.out} log=${job.log} job=${job.jobId} status=${job.status}`;
  console.log(line);
  return line;
}

// ---------------------------------------------------------------------------
// Foreground / worker execution
// ---------------------------------------------------------------------------
async function execJob(o, job) {
  const log = makeLogger(job.log);
  const logEvent = makeEventLogger(job.events);

  job.status = "inProgress";
  job.startedAt = job.startedAt || nowIso();
  writeJobAtomic(job);

  let result;
  try {
    result = await runTurn(o, job, log, logEvent);
  } catch (e) {
    log(`fatal: ${e.message}`);
    result = { status: "failed", error: e.message, agentMessages: [], sawAnyAgentMessage: false };
  }

  const text = (result.agentMessages || []).join("\n\n");
  try {
    const tmp = o.out + ".tmp";
    fs.writeFileSync(tmp, text);
    fs.renameSync(tmp, o.out);
  } catch (e) {
    log(`failed to write output file: ${e.message}`);
  }
  if (!result.sawAnyAgentMessage) log("no agentMessage item arrived; output file is empty");

  job.threadId = result.threadId || job.threadId;
  job.turnId = result.turnId || job.turnId;
  job.status = result.status;
  job.rc = statusToRc(result.status);
  job.error = result.error || null;
  job.endedAt = nowIso();
  writeJobAtomic(job);
  log(`done status=${job.status} rc=${job.rc}`);
  return job;
}

async function runForeground(o) {
  if (!validSandbox(o.sandbox)) usageExit(`invalid -s sandbox: ${o.sandbox}`);

  const policy = computeEffectivePolicy(o);
  o.sandbox = policy.sandbox;

  if (o.printPolicy) {
    console.log(
      JSON.stringify(
        {
          cwd: policy.cwd,
          sandbox: o.sandbox,
          sandboxPolicy: policy.sandboxPolicy,
          threadConfig: policy.threadConfig,
        },
        null,
        2
      )
    );
    process.exit(0);
  }

  if (!o.prompt) usageExit("missing -p prompt.md");
  if (!fs.existsSync(o.prompt)) usageExit(`prompt file not found: ${o.prompt}`);

  o.cwd = policy.cwd;
  o.writableRoots = policy.writableRoots;
  o.sandboxPolicy = policy.sandboxPolicy;
  o.threadConfig = policy.threadConfig;

  if (!o.out) usageExit("missing -o out.md");
  o.out = path.resolve(o.out);
  const base = o.out.replace(/\.[^./]+$/, "");
  o.log = o.log ? path.resolve(o.log) : `${base}.log`;
  const events = `${base}.events.jsonl`;
  o.promptText = fs.readFileSync(o.prompt, "utf8");
  o.prompt = o.promptText;

  ensureDirs();
  const jobId = genJobId();
  const job = {
    jobId,
    pid: process.pid,
    cwd: o.cwd,
    threadId: null,
    turnId: null,
    model: o.model,
    sandbox: o.sandbox,
    out: o.out,
    log: o.log,
    events,
    status: "starting",
    rc: null,
    startedAt: nowIso(),
    endedAt: null,
    error: null,
    // Fields the detached worker needs to reconstruct run options from the
    // job file alone (it has no access to the parent's argv/closures).
    _promptText: o.promptText,
    _effort: o.effort || null,
    _sandboxPolicy: o.sandboxPolicy,
    _threadConfig: o.threadConfig,
    _resumeThread: o.resumeThread || null,
  };
  writeJobAtomic(job);

  if (o.background) {
    const jobFile = jobPath(jobId);
    const child = spawn(process.execPath, [SELF_PATH, "--worker", jobFile], {
      detached: true,
      stdio: ["ignore", fs.openSync(o.log, "a"), fs.openSync(o.log, "a")],
    });
    job.pid = child.pid;
    writeJobAtomic(job);
    child.unref();
    console.log(`job=${jobId} session=pending out=${o.out} log=${o.log}`);
    process.exit(0);
  }

  const finalJob = await execJob(o, job);
  printOneLiner(finalJob);
  process.exit(finalJob.rc);
}

async function runWorker(jobFile) {
  const job = JSON.parse(fs.readFileSync(jobFile, "utf8"));
  const o = {
    cwd: job.cwd,
    model: job.model,
    effort: job._effort || null,
    sandbox: job.sandbox,
    sandboxPolicy: job._sandboxPolicy,
    threadConfig: job._threadConfig ?? null,
    resumeThread: job._resumeThread || null,
    out: job.out,
    log: job.log,
    prompt: job._promptText,
  };
  const finalJob = await execJob(o, job);
  process.exit(finalJob.rc);
}

// ---------------------------------------------------------------------------
// status / wait / cancel / list
// ---------------------------------------------------------------------------
function isPidAlive(pid) {
  try {
    process.kill(pid, 0);
    return true;
  } catch {
    return false;
  }
}

function cmdStatus(idOrThread) {
  const job = findJob(idOrThread);
  if (!job) {
    console.error(`no such job or thread: ${idOrThread}`);
    process.exit(2);
  }
  printOneLiner(job);
  process.exit(job.rc === null ? 3 : job.rc);
}

async function cmdWait(idOrThread, timeoutSecs) {
  const start = Date.now();
  for (;;) {
    const job = findJob(idOrThread);
    if (!job) {
      console.error(`no such job or thread: ${idOrThread}`);
      process.exit(2);
    }
    if (job.status !== "starting" && job.status !== "inProgress") {
      printOneLiner(job);
      process.exit(job.rc);
    }
    if (timeoutSecs && (Date.now() - start) / 1000 > timeoutSecs) {
      console.error(`wait: timeout after ${timeoutSecs}s, job still ${job.status}`);
      process.exit(3);
    }
    await new Promise((r) => setTimeout(r, 1000));
  }
}

async function cmdCancel(idOrThread) {
  const job = findJob(idOrThread);
  if (!job) {
    console.error(`no such job or thread: ${idOrThread}`);
    process.exit(2);
  }
  if (job.status !== "starting" && job.status !== "inProgress") {
    console.error(`job ${job.jobId} already terminal (status=${job.status}); nothing to cancel`);
    printOneLiner(job);
    process.exit(job.rc);
  }
  if (!job.pid || !isPidAlive(job.pid)) {
    job.status = "interrupted";
    job.rc = 130;
    job.error = "worker process not found (stale); marked interrupted";
    job.endedAt = nowIso();
    writeJobAtomic(job);
    console.error(`worker pid ${job.pid} not alive; marked stale job as interrupted`);
    printOneLiner(job);
    process.exit(job.rc);
  }
  process.kill(job.pid, "SIGTERM");
  // Wait for the worker's SIGTERM handler to mark it terminal (up to ~16s).
  const start = Date.now();
  for (;;) {
    const j2 = findJob(idOrThread);
    if (j2 && j2.status !== "starting" && j2.status !== "inProgress") {
      printOneLiner(j2);
      process.exit(j2.rc);
    }
    if ((Date.now() - start) / 1000 > 20) {
      console.error("cancel: worker did not reach terminal state within 20s");
      process.exit(3);
    }
    await new Promise((r) => setTimeout(r, 500));
  }
}

function cmdList() {
  const jobs = listJobs();
  for (const j of jobs) {
    console.log(`${j.jobId} ${j.status} ${j.threadId || "-"} ${j.cwd} ${j.startedAt}`);
  }
  process.exit(0);
}

// ---------------------------------------------------------------------------
// Entry point
// ---------------------------------------------------------------------------
async function main() {
  const argv = process.argv.slice(2);
  const parsed = parseArgs(argv);

  if (parsed.sub === "help") {
    console.log(USAGE);
    process.exit(0);
  }
  if (parsed.sub === "list") return cmdList();
  if (parsed.sub === "status") {
    if (!parsed.positional[0]) usageExit("status requires a job or thread id");
    return cmdStatus(parsed.positional[0]);
  }
  if (parsed.sub === "wait") {
    if (!parsed.positional[0]) usageExit("wait requires a job or thread id");
    return cmdWait(parsed.positional[0], parsed.opts.timeout);
  }
  if (parsed.sub === "cancel") {
    if (!parsed.positional[0]) usageExit("cancel requires a job or thread id");
    return cmdCancel(parsed.positional[0]);
  }

  const o = parsed.opts;
  if (o.workerJobFile) return runWorker(o.workerJobFile);
  return runForeground(o);
}

main().catch((e) => {
  process.stderr.write(`codex-run: fatal: ${e && e.stack ? e.stack : e}\n`);
  process.exit(3);
});
