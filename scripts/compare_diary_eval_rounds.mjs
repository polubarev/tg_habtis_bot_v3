import fs from 'node:fs';
import path from 'node:path';

const base = path.resolve('docs/evals/2026-10-22');
const read = file => JSON.parse(fs.readFileSync(file, 'utf8'));
const cohorts = [base, path.join(base, 'budget-round'), path.join(base, 'sonnet-terra')];
const models = [
  ['anthropic/claude-sonnet-5.5', 'Claude Sonnet 5.5', 2],
  ['google/gemini-3.8-flash', 'Gemini 3.8 Flash', 1],
  ['openai/gpt-5.6-terra', 'GPT-5.6 Terra', 2],
  ['qwen/qwen3.8-flash', 'Qwen3.8 Flash', 0],
  ['mistralai/mistral-large-4-0', 'Mistral Large 4', 1],
  ['openai/gpt-6-luna', 'GPT-6 Luna', 0],
  ['deepseek/deepseek-v4-pro-0813', 'DeepSeek V4 Pro', 1],
  ['anthropic/claude-haiku-5.5', 'Claude Haiku 5.5', 1],
];
const sources = models.map(([id, name, cohort]) => {
  const root = cohorts[cohort];
  const rows = fs.readFileSync(path.join(root, 'main/responses.jsonl'), 'utf8').trim().split('\n').map(JSON.parse);
  const latest = [...new Map(rows.map(r => [`${r.model}|${r.repeat}|${r.caseId}|${r.phase}|${r.turn}`, r])).values()];
  const calls = latest.filter(r => r.model === id && r.phase === 'unified' && r.caseId !== 'long_diary' && r.status === 'ok' && r.assessment.schemaErrors.length === 0);
  const reviews = read(path.join(root, 'manual-review.json')).reviews;
  const finals = read(path.join(root, 'main/review-key.json')).flatMap(group => group.records.filter(r => r.model === id).map(r => ({ ...r, ...reviews[group.id], reviewId: group.id })));
  return { id, name, cohort, calls, finals };
});
const callKey = r => `${r.caseId}|${r.repeat}|${r.turn}`;
const finalKey = r => `${r.case}|${r.repeat}`;
const commonCalls = sources[0].calls.map(callKey).filter(key => sources.every(s => s.calls.some(r => callKey(r) === key)));
const commonFinals = sources[0].finals.map(finalKey).filter(key => sources.every(s => s.finals.some(r => finalKey(r) === key)));
const comparisons = sources.map(s => {
  const calls = s.calls.filter(r => commonCalls.includes(callKey(r)));
  const finals = s.finals.filter(r => commonFinals.includes(finalKey(r)));
  const latency = calls.map(r => r.latencyMs).sort((a, b) => a - b);
  return { id: s.id, name: s.name, cohort: s.cohort + 1, comparableShortCalls: calls.length, comparableFinals: finals.length, substantiveIssues: finals.filter(r => r.scores.includes(0)).length, minorIssues: finals.filter(r => !r.scores.includes(0) && r.scores.includes(1)).length, costPer100CallsUsd: calls.reduce((n, r) => n + (r.billedCostUsd || 0), 0) / calls.length * 100, medianLatencySeconds: latency[Math.ceil(latency.length / 2) - 1] / 1000 };
});
const gemini = comparisons.find(c => c.id === 'google/gemini-3.8-flash');
for (const c of comparisons) c.costRelativeToGemini = c.costPer100CallsUsd / gemini.costPer100CallsUsd;
const qualitySorted = [...comparisons].sort((a, b) => a.substantiveIssues - b.substantiveIssues || a.minorIssues - b.minorIssues);
let rank = 0;
let previous;
qualitySorted.forEach((c, index) => {
  const metric = `${c.substantiveIssues}|${c.minorIssues}`;
  if (metric !== previous) rank = index + 1;
  c.qualityRank = rank;
  previous = metric;
});
const output = { note: 'Same available short calls and final case/repeat pairs across all eight models. Current Gemini uses round 2, not pooled double weighting. Ranking is descriptive: substantive manual issues first, minor issues second. Price/speed are separate. Missing calls, refusals and long-text outcomes remain in source reports and are not successes. Sonnet/Terra evaluation is incomplete because OpenRouter account credits ran out.', actualModelsTested: models.length, incompleteModels: ['anthropic/claude-sonnet-5.5', 'openai/gpt-5.6-terra'], totalRealCalls: cohorts.reduce((n, root) => n + read(path.join(root, 'totals.json')).totalCallsIncludingSmoke, 0), commonCalls, commonFinals, comparisons: qualitySorted };
fs.writeFileSync(path.join(base, 'comparison.json'), JSON.stringify(output, null, 2));
const table = qualitySorted.map(c => `| ${c.qualityRank} | ${c.name} | ${c.substantiveIssues}/${c.comparableFinals} | ${c.minorIssues} | $${c.costPer100CallsUsd.toFixed(3)} | ${c.costRelativeToGemini.toFixed(2)}× | ${c.medianLatencySeconds.toFixed(1)} с |`).join('\n');
fs.writeFileSync(path.join(base, 'comparison.md'), `# Предварительное сравнение восьми моделей\n\nВсего ${output.totalRealCalls} реальных API-вызовов, включая неуспешные. Sonnet и Terra теперь проверены, но их раунд неполный: закончились общие кредиты OpenRouter (HTTP 402). Astra, Opus и Argon не тестировались. Прежняя таблица шести моделей сохранена в [comparison-six-models.md](comparison-six-models.md).\n\nДля одинакового сравнения оставлены ${commonFinals.length} конечных коротких заданий, доступных у всех восьми, и ${commonCalls.length} одинаковых успешных коротких шагов для цены и времени. Gemini взята из второго раунда; она не получает двойной вес за участие в обоих. Новое пересечение меньше старого, поэтому результаты рангов между версиями напрямую не сравниваются.\n\nРанжирование по качеству: сначала существенные замечания ручного чтения, затем небольшие. Это описательный рейтинг маленькой синтетической выборки, не статистическое доказательство превосходства. Ноль существенных замечаний не означает полного отсутствия потерь деталей.\n\n| Место | Модель | Существенные замечания / финалы | Небольшие замечания | Фактическая цена 100 коротких шагов | К Gemini | Медиана |\n|---|---|---:|---:|---:|---:|---:|\n${table}\n\nОдинаковое место означает ничью по этим критериям. Отказы, ошибки получения ответа и пропуски сюда не превращаются в успешные результаты: они отдельно видны в отчётах. У Gemini был content_filter на одном интимном сценарии; Mistral страдал от 429 и timeout. Длинные ответы и согласованность оценок описаны отдельно. Ручную оценку сделал сам автор fixtures, без независимого человеческого жюри.\n\nЦена — измерение конкретных ответов с фактическими кешем и reasoning, не актуальная универсальная ставка или прогноз для любой записи. У разных моделей разная токенизация, служебные затраты, кеширование и длина вывода. Sonnet измерялся без специально настроенного prompt caching; оптимизированная цена не проверялась.\n\nПолные данные: [первый раунд](report.md), [второй раунд](budget-round/report.md), [Sonnet и Terra](sonnet-terra/report.md), [общие числа](comparison.json).\n`);
console.log(JSON.stringify(output, null, 2));
