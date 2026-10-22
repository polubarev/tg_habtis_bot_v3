// Read-only credit diagnostics; never prints the credential, key label or key ID.
import fs from 'node:fs';
let key = process.env.OPENROUTER_API_KEY;
if (!key) {
  key = fs.readFileSync('.env', 'utf8').match(/^\s*OPENROUTER_API_KEY\s*=\s*(.*?)\s*$/m)?.[1];
  if (key && ((key.startsWith('"') && key.endsWith('"')) || (key.startsWith("'") && key.endsWith("'")))) key = key.slice(1, -1);
  else key = key?.replace(/\s+#.*$/, '').trim();
}
if (!key) throw new Error('OPENROUTER_API_KEY not configured');
await Promise.all(['key', 'credits'].map(async endpoint => {
  const response = await fetch(`https://openrouter.ai/api/v1/${endpoint}`, { headers: { Authorization: `Bearer ${key}` }, signal: AbortSignal.timeout(20_000), redirect: 'error' });
  const result = await response.json();
  console.log(JSON.stringify({ endpoint, status: response.status, remainingUsd: endpoint === 'key' ? result.data?.limit_remaining : result.data ? result.data.total_credits - result.data.total_usage : null, keyLimitUsd: endpoint === 'key' ? result.data?.limit : undefined }));
}));
