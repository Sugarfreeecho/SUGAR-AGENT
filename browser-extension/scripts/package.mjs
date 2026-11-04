import { createRequire } from 'node:module';
import { createWriteStream } from 'node:fs';
import { mkdir, readdir, readFile, stat, writeFile } from 'node:fs/promises';
import { resolve, relative } from 'node:path';
import { createHash } from 'node:crypto';

const root = resolve(import.meta.dirname, '..');
const require = createRequire(resolve(root, '../plugins/browser-use/node/package.json'));
const { yazl } = require('playwright-core/lib/utilsBundle');
const manifest = JSON.parse(await readFile(resolve(root, 'dist/manifest.json'), 'utf8'));
const pkg = JSON.parse(await readFile(resolve(root, 'package.json'), 'utf8'));
if (manifest.version !== pkg.version) throw new Error('Build version does not match source; run npm run build');
const outputDir = resolve(root, '../outputs/browser-extension');
await mkdir(outputDir, { recursive: true });
const output = resolve(outputDir, `sugaragent-browser-${pkg.version}.zip`);
const zip = new yazl.ZipFile();
const files = [];
async function add(directory) {
  for (const name of (await readdir(directory)).sort()) {
    const path = resolve(directory, name);
    if ((await stat(path)).isDirectory()) await add(path);
    else if (!name.endsWith('.map')) {
      const entry = relative(resolve(root, 'dist'), path).replaceAll('\\', '/');
      zip.addFile(path, entry, { mtime: new Date('2026-01-01T00:00:00Z') });
      files.push(entry);
    }
  }
}
await add(resolve(root, 'dist'));
if (!files.includes('THIRD_PARTY_NOTICES.md') || !files.some(name => name.startsWith('licenses/'))) throw new Error('Build is missing third-party license notices');
const finished = new Promise((yes, no) => {
  const destination = createWriteStream(output);
  destination.on('close', yes); destination.on('error', no); zip.outputStream.on('error', no);
  zip.outputStream.pipe(destination);
});
zip.end();
await finished;
const sha256 = createHash('sha256').update(await readFile(output)).digest('hex');
await writeFile(output + '.sha256', `${sha256}  ${output.split(/[\\/]/).at(-1)}\n`);
console.log(JSON.stringify({ output, version: pkg.version, files: files.length, sha256 }, null, 2));
