// Read the raw UI module strings embedded in each Vite archive, without rewriting assets.
const fs = require('node:fs');
const path = require('node:path');
const { parseAst } = require('../../frontend/node_modules/rollup/dist/parseAst.js');
const manifest = JSON.parse(fs.readFileSync('.git/archived-stream-replay-work.json', 'utf8'));
for (const v of manifest.versions) {
  const source = fs.readFileSync(path.join(v.directory, 'site', v.js), 'utf8');
  const values = [];
  function walk(node) {
    if (!node || typeof node !== 'object') return;
    if (node.type === 'Literal' && typeof node.value === 'string' && node.value.length > 3000) values.push(node.value);
    if (node.type === 'TemplateLiteral' && node.expressions.length === 0) values.push(node.quasis.map(q => q.value.cooked).join(''));
    for (const value of Object.values(node)) {
      if (Array.isArray(value)) value.forEach(walk);
      else if (value && typeof value === 'object') walk(value);
    }
  }
  walk(parseAst(source));
  const probes = {
    scrolling: 'function newDomContext(', smooth: 'function createSmoothFollowController(',
    rendering: 'function createProcessFeedRow(', sse: 'async function consumeAgentSseResponse(',
    events: 'function renderEvent(',
  };
  const result = { version: v.version, modules: {} };
  for (const [name, marker] of Object.entries(probes)) {
    const module = values.find(value => value.includes(marker));
    if (!module) throw new Error(`${v.version}: missing ${name}`);
    fs.mkdirSync(path.join(v.directory, 'embedded'), { recursive: true });
    fs.writeFileSync(path.join(v.directory, 'embedded', name + '.js'), module);
    result.modules[name] = { characters: module.length, sha256: require('node:crypto').createHash('sha256').update(module).digest('hex') };
  }
  result.executionRecords = result.modules.rendering && fs.readFileSync(path.join(v.directory, 'embedded/rendering.js'), 'utf8').includes('function renderExecutionRecord(');
  result.innerSseConsumer = fs.readFileSync(path.join(v.directory, 'embedded/sse.js'), 'utf8').includes('async function consumeAgentSseResponseInner(');
  console.log(JSON.stringify(result));
}
