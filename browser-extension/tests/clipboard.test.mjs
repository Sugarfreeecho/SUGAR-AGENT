import test from 'node:test';
import assert from 'node:assert/strict';
import {clipboardFiles,mergeUploads} from '../src/clipboard.mjs';

test('pasted files are taken once even when both clipboard representations contain them',()=>{
  const image=new File(['png'],'截图.png',{type:'image/png'});
  const text=new File(['text'],'说明.txt',{type:'text/plain'});
  assert.deepEqual(clipboardFiles({files:[image,text],items:[{kind:'file',getAsFile:()=>image}]}),[image,text]);
});
test('file items are a fallback and normal text remains on the native paste path',()=>{
  const image=new File(['png'],'image.png',{type:'image/png'});
  assert.deepEqual(clipboardFiles({files:[],items:[{kind:'string'},{kind:'file',getAsFile:()=>image},{kind:'file',getAsFile:()=>null}]}),[image]);
  assert.deepEqual(clipboardFiles({items:[{kind:'string',type:'text/plain'}]}),[]);
});
test('pending upload receipts merge with stored drafts without duplication or losing prior attachments',()=>{
  const old={id:'one',name:'old.txt'},fresh={id:'two',name:'image.png'};
  assert.deepEqual(mergeUploads([old,fresh],[fresh]),[old,fresh]);
  assert.deepEqual(mergeUploads([old],[fresh]),[old,fresh]);
});
