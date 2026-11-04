import test from 'node:test';
import assert from 'node:assert/strict';
import {Marked} from 'marked';
import {localResourceLinks} from '../src/resource-links.mjs';

const markdown=new Marked({extensions:[localResourceLinks]});
const inline=source=>markdown.lexer(source)[0].tokens;
test('the exact escaped directory link with Windows spaces is a clickable token',()=>{
  const source=String.raw`&#x20;[workspace/zen-gate-obsolete-20261030/]\(D:\AI\AI Agent\MyAgent Developer\workspace\zen-gate-obsolete-20261030)`;
  const link=inline(source).find(token=>token.type==='link');
  assert.ok(link);assert.equal(link.text,'workspace/zen-gate-obsolete-20261030/');
  assert.equal(link.href,'D:/AI/AI Agent/MyAgent Developer/workspace/zen-gate-obsolete-20261030');
  assert.match(markdown.parse(source),/<a href=/);
});
test('files and images retain spaces, Chinese and nested parentheses in their local destinations',()=>{
  for(const source of [
    String.raw`[文件](D:\AI\项目 (旧)\说明 文档.md)`,
    String.raw`[文件]\(<D:\AI\项目 (旧)\说明 文档.md>)`,
    String.raw`[文件](<D:\AI\项目 (旧)\说明 文档.md>)`,
  ])assert.equal(inline(source)[0].href,'D:/AI/项目 (旧)/说明 文档.md');
  const image=inline(String.raw`![截图]\(D:\AI\项目 (旧)\截图 1.png)`)[0];
  assert.equal(image.type,'image');assert.equal(image.href,'D:/AI/项目 (旧)/截图 1.png');
  assert.match(markdown.parse(String.raw`![截图]\(D:\AI\项目 (旧)\截图 1.png)`),/<img /);
  assert.equal(inline(String.raw`[报告]\(docs/报告 (最终).md)`)[0].href,'docs/报告 (最终).md');
});
test('ordinary links, code examples and fenced source keep normal Markdown behavior',()=>{
  assert.equal(inline('[链接](https://example.test/path?q=1)')[0].href,'https://example.test/path?q=1');
  const literal=String.raw`[文件]\(D:\AI\报告.md)`;
  assert.equal(inline('`'+literal+'`')[0].type,'codespan');
  const fence=markdown.lexer('```md\n'+literal+'\n```')[0];assert.equal(fence.type,'code');assert.equal(fence.text,literal);
  assert.equal(inline('[文档](docs/readme.md "标题")')[0].title,'标题');
  assert.equal(inline(String.raw`[危险]\(javascript:alert(1))`).some(token=>token.type==='link'),false);
  assert.equal(inline(String.raw`[网络]\(https://example.test/path)`).some(token=>token.type==='link' && token.text==='网络'),false);
});
