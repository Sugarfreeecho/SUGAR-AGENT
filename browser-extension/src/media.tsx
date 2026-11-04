import React, { createContext, useContext, useEffect, useState } from 'react';
import { loopbackUrl } from './shared.mjs';
import {normalizeResourceReference} from './resource-links.mjs';
import { Dialog } from './Dialog';

export const MediaSession = createContext('');

export function relativeReference(source: string, basePath = '') {
  source = normalizeResourceReference(source).replace(/#L?\d+(?:[-:]L?\d+)?$/i, '').replace(/(\.[^\\/:#]+):\d+(?::\d+)?$/, '$1');
  if (!basePath || /^(?:[a-z][a-z0-9+.-]*:|[\/\\])/i.test(source)) return source;
  return basePath.replace(/[\\/][^\\/]*$/, '/') + source;
}

async function localReference(source: string, sessionId: string, endpoint: string) {
  const settings = (await chrome.storage.local.get('sugar.connection'))['sugar.connection'];
  if (!settings?.token || !sessionId) throw new Error('文件需要已连接的会话');
  const url = loopbackUrl(settings.baseUrl); url.pathname = endpoint; url.searchParams.set('session_id', sessionId);
  if (source.startsWith('question-image:')) {
    const [identity, question, index] = source.slice(15).split('/');
    url.pathname='/api/browser/v1/question-image';url.searchParams.set('interaction_id',identity);url.searchParams.set('question_id',question);url.searchParams.set('image_index',index);
  }
  else if (source.startsWith('attachment:')) url.searchParams.set('attachment_id', source.slice(11));
  else {
    const parsed = new URL(source, settings.baseUrl);
    const local = parsed.origin === new URL(settings.baseUrl).origin;
    if (local && parsed.pathname.startsWith('/api/attachments/')) url.searchParams.set('attachment_id', parsed.pathname.split('/').at(-1)!);
    else if (local && ['/api/workspace-media', '/api/workspace-image', '/api/workspace-file-text'].includes(parsed.pathname)) url.searchParams.set('rel', parsed.searchParams.get('rel') || '');
    else {
      if (/^(?:https?|javascript|blob|data):/i.test(source) || source.startsWith('//')) throw new Error('文件地址不在当前工作区');
      let path = source.replace(/^file:\/\//i, '');
      if (/^\/[A-Za-z]:\//.test(path)) path = path.slice(1);
      url.searchParams.set('rel', path);
    }
  }
  const response = await fetch(url.href, { credentials: 'omit', headers: { Authorization: 'Bearer ' + settings.token }, signal: AbortSignal.timeout(20000) });
  if (!response.ok) {
    const result = await response.json().catch(() => ({}));
    throw new Error(response.status === 404 ? '文件不存在，或后端尚未加载文件接口' : result.detail || result.error || '文件读取失败');
  }
  return response;
}

export async function fileSource(source: string, sessionId: string) {
  const response = await localReference(source, sessionId, '/api/browser/v1/files');
  if(response.headers.get('X-Resource-Type')==='directory') {
    const directory=await response.json();
    return {name:directory.name || directory.path,directory,blob:null,text:null,markdown:false,image:false};
  }
  const blob = await response.blob();
  const name = decodeURIComponent(response.headers.get('X-File-Name') || source.split(/[\\/]/).at(-1) || '文件');
  const textFile = /\.(?:md|markdown|txt|json|csv|log|py|js|mjs|ts|tsx|jsx|css|html?|xml|ya?ml|toml|ini|sh|ps1)$/i.test(name) || blob.type.startsWith('text/');
  return {name, blob, text: textFile ? await blob.text() : null, markdown: /\.(?:md|markdown)$/i.test(name),directory:null,image:blob.type.startsWith('image/')};
}

export async function imageDetails(source: string, sessionId: string): Promise<{url:string;size:number;type:string}> {
  if (/^data:image\/(png|jpeg|gif|webp);base64,/i.test(source)) {
    const type=source.slice(5,source.indexOf(';'));
    return {url:source,size:Math.max(0,Math.floor((source.length-source.indexOf(',')-1)*3/4)),type};
  }
  const settings = (await chrome.storage.local.get('sugar.connection'))['sugar.connection'];
  const remote = /^https?:\/\//i.test(source) && new URL(source).origin !== new URL(settings?.baseUrl || 'http://127.0.0.1:8192').origin;
  const response = remote ? await fetch(source, {credentials:'omit', referrerPolicy:'no-referrer', signal:AbortSignal.timeout(15000)}) : await localReference(source, sessionId, '/api/browser/v1/media');
  if (!response.ok || !response.headers.get('content-type')?.startsWith('image/')) throw new Error('图片暂时无法读取');
  const blob = await response.blob();
  if (blob.size > 20_000_000) throw new Error('图片大于 20 MB，请在主程序打开');
  return {url:URL.createObjectURL(blob),size:blob.size,type:blob.type};
}

export async function imageSource(source: string, sessionId: string): Promise<string> {
  return (await imageDetails(source, sessionId)).url;
}

function imageSizeText(bytes: unknown) {
  const value=Number(bytes || 0);
  if(!Number.isFinite(value) || value<=0) return '';
  if(value<1024) return value+' B';
  if(value<1048576) return (Math.round(value/102.4)/10)+' KB';
  if(value<1073741824) return (Math.round(value/104857.6)/10)+' MB';
  return (Math.round(value/107374182.4)/10)+' GB';
}

function imageFormatText(type: unknown) {
  const subtype=String(type || '').split('/').pop() || '';
  return subtype ? subtype.toUpperCase().replace('JPEG','JPG') : '';
}

export function AttachmentImage({ identity, source, alt = '会话图片' }: { identity: string; source?: string; alt?: string }) {
  const session = useContext(MediaSession), [src, setSrc] = useState(''), [error, setError] = useState('');
  useEffect(() => {
    let disposed = false, object = '';
    setSrc('');setError('');
    void imageSource(source || 'attachment:' + identity, session).then(value => {
      object = value; if (disposed) URL.revokeObjectURL(value); else setSrc(value);
    }).catch(reason => { if (!disposed) setError(reason.message); });
    return () => { disposed = true; if (object.startsWith('blob:')) URL.revokeObjectURL(object); };
  }, [identity, session, source]);
  return src ? <a href={src} target="_blank" rel="noreferrer"><img className="attachment-image" src={src} alt={alt} /></a> : <span className="secondary">{error || '正在读取图片…'}</span>;
}

export function MessageImage({ identity, meta }: { identity: string; meta?: Record<string, any> }) {
  const session = useContext(MediaSession);
  const [image, setImage] = useState<{url?:string;size?:number;type?:string;error?:string}>({});
  const [open, setOpen] = useState(false);
  useEffect(() => {
    let disposed = false, object = '';
    setImage({});setOpen(false);
    void imageDetails('attachment:' + identity, session).then(value => {
      object = value.url;
      if (disposed) { if (object.startsWith('blob:')) URL.revokeObjectURL(object); }
      else setImage(value);
    }).catch(reason => { if (!disposed) setImage({error:reason.message}); });
    return () => { disposed = true; if (object.startsWith('blob:')) URL.revokeObjectURL(object); };
  }, [identity, session]);
  if(image.error) return <span className="secondary">{image.error}</span>;
  const name = String(meta?.name || '图片');
  const details = [imageSizeText(meta?.bytes || image.size), imageFormatText(meta?.mediaType || image.type)].filter(Boolean).join(' · ');
  return <>
    <figure className="msg-attachment-card">
      <button type="button" className="msg-attachment-preview-trigger" aria-label={'放大查看 ' + name} title="点击放大查看" disabled={!image.url} onClick={() => setOpen(true)}>
        {image.url ? <img className="attachment-image msg-attachment-thumbnail" src={image.url} alt={name} /> : <span className="secondary">读取中…</span>}
      </button>
      <figcaption className="msg-attachment-copy"><span className="msg-attachment-name">{name}</span>{details && <small className="msg-attachment-meta">{details}</small>}</figcaption>
    </figure>
    {open && image.url && <Dialog label="图片预览" onClose={() => setOpen(false)}><div className="file-preview"><header><h2>{name}</h2><button type="button" onClick={() => setOpen(false)}>关闭</button></header><img className="file-preview-image" src={image.url} alt={name} /></div></Dialog>}
  </>;
}
