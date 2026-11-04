import test from 'node:test';
import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';

test('extension icons use actual PNG bytes at each declared size, not a WebP renamed png',async()=>{
  const root=new URL('../public/',import.meta.url);
  const manifest=JSON.parse(await readFile(new URL('manifest.json',root),'utf8'));
  for(const [size,path] of [...Object.entries(manifest.icons),...Object.entries(manifest.action.default_icon),['256','icon.png']]){
    const file=await readFile(new URL(path,root));
    assert.equal(file.subarray(0,8).toString('hex'),'89504e470d0a1a0a',path+' is not PNG encoded');
    assert.equal(file.readUInt32BE(16),Number(size));assert.equal(file.readUInt32BE(20),Number(size));
  }
});
