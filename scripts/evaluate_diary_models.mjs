// Real OpenRouter evaluation on synthetic data. Never sends real diary entries.
// node scripts/evaluate_diary_models.mjs --dry-run
// node scripts/evaluate_diary_models.mjs --output docs/evals/2026-10-22
import fs from 'node:fs';
import path from 'node:path';
import crypto from 'node:crypto';
import { cases, holdoutCases, fields, unifiedPrompt, baselinePrompt } from './diary_eval_cases.mjs';

const args = process.argv.slice(2);
const option = (name, fallback) => {
  const at = args.indexOf(name);
  return at < 0 ? fallback : args[at + 1];
};
const dryRun = args.includes('--dry-run');
const output = path.resolve(option('--output', 'docs/evals/2026-10-22'));
const repeats = Number(option('--repeats', '2'));
const concurrency = Number(option('--concurrency', '6'));
const maxCost = Number(option('--max-cost-usd', '3'));
const maxCalls = Number(option('--max-calls', '250'));
const providerMap = option('--provider-map', '') ? JSON.parse(fs.readFileSync(option('--provider-map', ''), 'utf8')) : {};
const modelIds = option('--models', 'google/gemini-3.8-flash,openai/gpt-6-luna,qwen/qwen3.8-flash').split(',');
const selectedCases = (option('--suite', 'main') === 'holdout' ? holdoutCases : cases).filter(c => !option('--case', '') || option('--case', '').split(',').includes(c.id));
if (!Number.isInteger(repeats) || repeats < 1 || !Number.isInteger(concurrency) || concurrency < 1 || !Number.isInteger(maxCalls) || maxCalls < 1 || !(maxCost > 0)) throw new Error('Invalid limits');
fs.mkdirSync(output, { recursive: true });
const habitSchema = { type: 'object', properties: fields, required: Object.keys(fields), additionalProperties: false };
const fullSchema = { type: 'object', properties: { diary: { type: 'string' }, habits: habitSchema }, required: ['diary', 'habits'], additionalProperties: false };
const snapshot = { cases: selectedCases, unifiedPrompt, baselinePrompt, habitSchema, fullSchema };
const digest = crypto.createHash('sha256').update(JSON.stringify(snapshot)).digest('hex');
const snapshotFile = path.join(output, 'fixtures.json');
if (fs.existsSync(snapshotFile) && JSON.parse(fs.readFileSync(snapshotFile, 'utf8')).sha256 !== digest) throw new Error('Fixture snapshot changed: use another output directory');
fs.writeFileSync(snapshotFile, JSON.stringify({ sha256: digest, ...snapshot }, null, 2));
for (const c of selectedCases) {
  for (const t of c.turns) {
    if (t.text.length > 30_000) throw new Error(`Fixture exceeds entry limit: ${c.id}`);
    if (Object.keys(t.expected).length !== Object.keys(fields).length) throw new Error('Incomplete expectation');
  }
}
const expectedCalls = modelIds.length * repeats * selectedCases.reduce((n, c) => n + 1 + c.turns.length, 0);
console.log(JSON.stringify({ dryRun, cases: selectedCases.length, models: modelIds, repeats, expectedCalls, longestInputUtf16: Math.max(...selectedCases.map(c => c.turns[0].text.length)), maxCostUsd: maxCost, fixtureSha256: digest }));
if (dryRun) process.exit(0);

// Load only the credential we need. Never log dotenv values or request headers.
function readKey() {
  if (process.env.OPENROUTER_API_KEY) return process.env.OPENROUTER_API_KEY;
  const dotenv = fs.readFileSync(path.resolve('.env'), 'utf8');
  const match = dotenv.match(/^\s*OPENROUTER_API_KEY\s*=\s*(.*?)\s*$/m);
  if (!match) throw new Error('OPENROUTER_API_KEY missing');
  let value = match[1];
  if ((value.startsWith('"') && value.endsWith('"')) || (value.startsWith("'") && value.endsWith("'"))) value = value.slice(1, -1);
  else value = value.replace(/\s+#.*$/, '').trim();
  if (!value) throw new Error('OPENROUTER_API_KEY empty');
  return value;
}
const apiKey = readKey();
const baseUrl = 'https://openrouter.ai/api/v1';
const metadataResponse = await fetch(`${baseUrl}/models`, { signal: AbortSignal.timeout(30_000), redirect: 'error' });
if (!metadataResponse.ok) throw new Error(`Metadata HTTP ${metadataResponse.status}`);
const catalog = await metadataResponse.json();
const modelMetadata = modelIds.map(id => {
  const model = catalog.data?.find(m => m.id === id);
  if (!model) throw new Error(`Unavailable model: ${id}`);
  if (!model.supported_parameters?.includes('structured_outputs')) throw new Error(`No structured output: ${id}`);
  return { id, name: model.name, pricing: model.pricing, supported_parameters: model.supported_parameters, context_length: model.context_length };
});
const recordsFile = path.join(output, 'responses.jsonl');
const records = fs.existsSync(recordsFile) ? fs.readFileSync(recordsFile, 'utf8').trim().split('\n').filter(Boolean).map(line => JSON.parse(line)) : [];
if (records.some(r => r.fixtureSha256 !== digest)) throw new Error('Results belong to another fixture snapshot');
const recordKey = r => `${r.model}|${r.repeat}|${r.caseId}|${r.phase}|${r.turn}`;
const successful = new Map(records.filter(r => r.status === 'ok').map(r => [recordKey(r), r]));
const filtered = new Map(records.filter(r => r.response?.choices?.[0]?.finish_reason === 'content_filter').map(r => [recordKey(r), r]));
const previousErrors = new Map(records.filter(r => r.status !== 'ok').map(r => [recordKey(r), r]));
let spent = records.reduce((sum, r) => sum + (r.budgetChargeUsd || 0), 0);
let reserved = 0;
let completed = 0;
let attempted = records.length;
const run = { startedAt: new Date().toISOString(), fixtureSha256: digest, repeats, concurrency, maxCostUsd: maxCost, maxCalls, providerMap, expectedCalls, modelMetadata, reasoningEffort: 'low', normalMaxTokens: 10_000, longMaxTokens: 24_000, baselineMaxTokens: 4_000, transport: 'OpenRouter chat/completions with strict JSON Schema; not production LangChain wrapper', baselineScope: 'Current extraction system prompt, first turn of every scenario', credentials: 'Environment or .env; never persisted' };
const priorRunFile = path.join(output, 'run.json');
if (records.length && fs.existsSync(priorRunFile)) {
  const priorRun = JSON.parse(fs.readFileSync(priorRunFile, 'utf8'));
  if (JSON.stringify(priorRun.providerMap || {}) !== JSON.stringify(providerMap)) throw new Error('Provider routing changed: use another output directory');
}
fs.writeFileSync(path.join(output, 'run.json'), JSON.stringify(run, null, 2));

function validateValue(value, schema, label, errors) {
  const types = Array.isArray(schema.type) ? schema.type : [schema.type];
  if (value === null) { if (!types.includes('null')) errors.push(`${label}: null`); return; }
  const type = Array.isArray(value) ? 'array' : typeof value;
  const valid = types.includes(type) || (type === 'number' && types.includes('integer') && Number.isInteger(value));
  if (!valid) { errors.push(`${label}: wrong type ${type}`); return; }
  if (typeof value === 'number' && ((schema.minimum !== undefined && value < schema.minimum) || (schema.maximum !== undefined && value > schema.maximum))) errors.push(`${label}: range`);
  if (schema.enum && !schema.enum.includes(value)) errors.push(`${label}: enum`);
  if (Array.isArray(value)) {
    value.forEach((item, i) => validateValue(item, schema.items, `${label}[${i}]`, errors));
    if (new Set(value).size !== value.length) errors.push(`${label}: duplicates`);
  }
}
function sameValue(actual, want) {
  if (Array.isArray(want)) return Array.isArray(actual) && actual.length === want.length && [...actual].sort().join('|') === [...want].sort().join('|');
  return actual === want;
}
export function assess(payload, fixture, phase, previousDiary) {
  const errors = [];
  if (!payload || typeof payload !== 'object' || Array.isArray(payload)) return { schemaErrors: ['Not an object'], fieldMatches: 0, fieldTotal: Object.keys(fields).length, mismatches: Object.keys(fields), checks: [] };
  const values = phase === 'baseline' ? payload : payload.habits;
  const rootKeys = phase === 'baseline' ? Object.keys(fields) : ['diary', 'habits'];
  for (const key of Object.keys(payload)) if (!rootKeys.includes(key)) errors.push(`Unexpected root ${key}`);
  if (phase !== 'baseline' && typeof payload.diary !== 'string') errors.push('diary: missing/string');
  if (!values || typeof values !== 'object' || Array.isArray(values)) errors.push('habits: missing/object');
  for (const key of Object.keys(values || {})) if (!Object.hasOwn(fields, key)) errors.push(`Unexpected habit ${key}`);
  const mismatches = [];
  for (const [key, schema] of Object.entries(fields)) {
    if (!Object.hasOwn(values || {}, key)) errors.push(`${key}: missing`);
    else validateValue(values[key], schema, key, errors);
    if (!sameValue(values?.[key], fixture.expected[key])) mismatches.push({ field: key, expected: fixture.expected[key], actual: Object.hasOwn(values || {}, key) ? values[key] : '__missing__' });
  }
  const checks = [];
  if (phase !== 'baseline' && typeof payload.diary === 'string') {
    const text = payload.diary;
    for (const fact of fixture.facts || []) checks.push({ id: `fact:${fact.id}`, pass: new RegExp(fact.pattern, 'iu').test(text) });
    for (const pattern of fixture.forbidden || []) checks.push({ id: `forbidden:${pattern}`, pass: !new RegExp(pattern, 'iu').test(text) });
    for (const item of fixture.order || []) {
      const before = text.search(new RegExp(item.before, 'iu'));
      const after = text.search(new RegExp(item.after, 'iu'));
      checks.push({ id: `order:${item.id}`, pass: before >= 0 && after >= 0 && before < after });
    }
    if (fixture.unchanged) checks.push({ id: 'unchanged', pass: text === previousDiary });
    if (fixture.empty) checks.push({ id: 'empty', pass: text === '' });
    checks.push({ id: 'no_update_marker', pass: !text.includes('[Update]') });
  }
  return { schemaErrors: errors, fieldMatches: Object.keys(fields).length - mismatches.length, fieldTotal: Object.keys(fields).length, mismatches, checks };
}

async function callModel(model, c, repeat, phase, index, messages, previousDiary) {
  const identity = { model: model.id, caseId: c.id, repeat, phase, turn: index };
  const cached = successful.get(recordKey(identity));
  if (cached) return cached;
  if (filtered.has(recordKey(identity))) return filtered.get(recordKey(identity));
  if (args.includes('--resume-short-errors') && c.long && previousErrors.has(recordKey(identity))) return previousErrors.get(recordKey(identity));
  const maxTokens = phase === 'baseline' ? 4_000 : c.long ? 24_000 : 10_000;
  const schema = phase === 'baseline' ? habitSchema : fullSchema;
  const body = { model: model.id, messages, response_format: { type: 'json_schema', json_schema: { name: phase === 'baseline' ? 'habit_extraction' : 'diary_entry', strict: true, schema } }, max_tokens: maxTokens, reasoning: { effort: 'low', exclude: true }, provider: { require_parameters: true, ...(providerMap[model.id] || {}) } };
  if (model.supported_parameters.includes('temperature')) body.temperature = 0.1;
  const upperInputTokens = messages.reduce((n, m) => n + Buffer.byteLength(m.content, 'utf8'), 0) + 2_000;
  const reservation = upperInputTokens * Number(model.pricing.prompt) + maxTokens * Number(model.pricing.completion);
  if (spent + reserved + reservation > maxCost || attempted >= maxCalls) {
    console.log(`Budget guard: skipped ${model.id}/${c.id}/${phase}/${index}`);
    return null;
  }
  reserved += reservation;
  attempted += 1;
  const started = performance.now();
  let record;
  try {
    const response = await fetch(`${baseUrl}/chat/completions`, { method: 'POST', redirect: 'error', headers: { Authorization: `Bearer ${apiKey}`, 'Content-Type': 'application/json', 'HTTP-Referer': 'https://habits-diary-bot.app', 'X-Title': 'Synthetic Diary Model Evaluation' }, body: JSON.stringify(body), signal: AbortSignal.timeout(c.long ? 240_000 : 120_000) });
    const rawBody = (await response.text()).replaceAll(apiKey, '[REDACTED]');
    let data;
    try { data = JSON.parse(rawBody); } catch { throw new Error(`Non-JSON HTTP ${response.status}: ${rawBody.slice(0, 800)}`); }
    const choice = data.choices?.[0];
    let payload = null;
    let parseError = null;
    if (typeof choice?.message?.content === 'string') {
      try { payload = JSON.parse(choice.message.content); } catch (e) { parseError = e.message; }
    } else parseError = 'Missing text content';
    const ok = response.ok && !data.error && choice?.finish_reason === 'stop' && payload !== null;
    const costKnown = typeof data.usage?.cost === 'number';
    const estimatedCost = data.usage ? (data.usage.prompt_tokens || 0) * Number(model.pricing.prompt) + (data.usage.completion_tokens || 0) * Number(model.pricing.completion) : null;
    record = { ...identity, fixtureSha256: digest, status: ok ? 'ok' : 'error', httpStatus: response.status, latencyMs: Math.round(performance.now() - started), request: body, response: data, payload, parseError, billedCostUsd: costKnown ? data.usage.cost : null, estimatedCostUsd: estimatedCost, budgetChargeUsd: costKnown ? data.usage.cost : reservation, assessment: ok ? assess(payload, c.turns[index], phase, previousDiary) : null };
  } catch (e) {
    record = { ...identity, fixtureSha256: digest, status: 'error', latencyMs: Math.round(performance.now() - started), request: body, error: { name: e.name, message: String(e.message).replaceAll(apiKey, '[REDACTED]') }, billedCostUsd: null, estimatedCostUsd: null, budgetChargeUsd: reservation };
  } finally { reserved -= reservation; }
  spent += record.budgetChargeUsd;
  records.push(record);
  fs.appendFileSync(recordsFile, JSON.stringify(record) + '\n');
  if (record.status === 'ok') successful.set(recordKey(record), record);
  completed += 1;
  if (completed % 5 === 0 || record.status !== 'ok') console.log(JSON.stringify({ completed, model: model.id, case: c.id, phase, turn: index + 1, status: record.status, fieldMatches: record.assessment?.fieldMatches, failedChecks: record.assessment?.checks.filter(x => !x.pass).map(x => x.id), seconds: record.latencyMs / 1000, budgetSpentUsd: Number(spent.toFixed(5)), error: record.response?.error?.message || record.error?.message }));
  return record;
}

const jobs = [];
for (let repeat = 1; repeat <= repeats; repeat += 1) {
  for (const c of selectedCases) {
    for (const model of modelMetadata) jobs.push(async () => {
      await callModel(model, c, repeat, 'baseline', 0, [
        { role: 'system', content: baselinePrompt },
        { role: 'user', content: `Language: ru\nSchema (user-defined fields with descriptions):\n${JSON.stringify(fields)}\nUser Raw record:\n${c.turns[0].text}\nReturn ONLY the structured JSON response matching the schema.` },
      ]);
      const messages = [{ role: 'system', content: unifiedPrompt }];
      let previousDiary;
      for (let index = 0; index < c.turns.length; index += 1) {
        messages.push({ role: 'user', content: c.turns[index].text });
        const record = await callModel(model, c, repeat, 'unified', index, [...messages], previousDiary);
        if (!record || record.status !== 'ok') break;
        previousDiary = record.payload.diary;
        messages.push({ role: 'assistant', content: JSON.stringify(record.payload) });
      }
    });
  }
}
let nextJob = 0;
await Promise.all(Array.from({ length: Math.min(concurrency, jobs.length) }, async () => {
  while (nextJob < jobs.length) {
    const job = jobs[nextJob++];
    await job();
  }
}));

const latest = new Map(records.map(r => [recordKey(r), r]));
const summary = [];
for (const model of modelMetadata) {
  for (const phase of ['baseline', 'unified']) {
    const all = [...latest.values()].filter(r => r.model === model.id && r.phase === phase);
    const ok = all.filter(r => r.status === 'ok');
    const checks = ok.flatMap(r => r.assessment.checks);
    const latencies = ok.map(r => r.latencyMs).sort((a, b) => a - b);
    const fieldMatches = ok.reduce((n, r) => n + r.assessment.fieldMatches, 0);
    const fieldTotal = ok.reduce((n, r) => n + r.assessment.fieldTotal, 0);
    summary.push({ model: model.id, phase, calls: all.length, successful: ok.length, schemaValid: ok.filter(r => r.assessment.schemaErrors.length === 0).length, perfectExtractionTurns: ok.filter(r => r.assessment.fieldMatches === r.assessment.fieldTotal).length, fieldMatches, fieldTotal, fieldAccuracy: fieldTotal ? fieldMatches / fieldTotal : null, checksPassed: checks.filter(c => c.pass).length, checksTotal: checks.length, medianLatencyMs: latencies.length ? latencies[Math.floor(latencies.length / 2)] : null, billedCostUsd: all.reduce((n, r) => n + (r.billedCostUsd || 0), 0), missingBillingCalls: all.filter(r => r.billedCostUsd === null).length, promptTokens: all.reduce((n, r) => n + (r.response?.usage?.prompt_tokens || 0), 0), completionTokens: all.reduce((n, r) => n + (r.response?.usage?.completion_tokens || 0), 0), reasoningTokens: all.reduce((n, r) => n + (r.response?.usage?.completion_tokens_details?.reasoning_tokens || 0), 0) });
  }
}
fs.writeFileSync(path.join(output, 'summary.json'), JSON.stringify({ finishedAt: new Date().toISOString(), fixtureSha256: digest, totalRecords: records.length, budgetChargeUsd: spent, summary }, null, 2));
console.log(JSON.stringify({ finished: true, summary }, null, 2));
