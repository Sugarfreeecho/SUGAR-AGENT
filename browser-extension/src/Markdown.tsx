import React, { useContext, useEffect, useMemo, useRef, useState } from 'react';
import { imageSource, fileSource, relativeReference, MediaSession } from './media';
import { Dialog } from './Dialog';
import {Icon} from './Icon';
import {localResourceLinks} from './resource-links.mjs';
import { marked } from 'marked';
import DOMPurify from 'dompurify';
import katex from 'katex';
import hljs from 'highlight.js/lib/core';
import javascript from 'highlight.js/lib/languages/javascript';
import typescript from 'highlight.js/lib/languages/typescript';
import python from 'highlight.js/lib/languages/python';
import bash from 'highlight.js/lib/languages/bash';
import json from 'highlight.js/lib/languages/json';
import css from 'highlight.js/lib/languages/css';
import xml from 'highlight.js/lib/languages/xml';
import 'katex/dist/katex.min.css';

for (const [name, language] of Object.entries({ javascript, typescript, python, bash, json, css, xml })) hljs.registerLanguage(name, language);
const escapeHtml = (value: string) => value.replaceAll('&', '&amp;').replaceAll('<', '&lt;').replaceAll('>', '&gt;');
const attribute = (value: string) => escapeHtml(value).replaceAll('"', '&quot;');
const resourceName = (source:string) => {
  if(/^data:image\//i.test(source))return '图片.'+(source.match(/^data:image\/(\w+)/i)?.[1] || 'png');
  const name=source.replace(/[\\/]+$/,'').split(/[\\/]/).at(-1) || '文件';
  try{return decodeURIComponent(name);}catch{return name;}
};
marked.use({ renderer: { html: ({ text }) => escapeHtml(text), image: ({ href, text }) => `<a href="#" data-reference="${attribute(href)}" data-resource-image="true"><img data-source="${attribute(href)}" alt="${attribute(text)}"></a>`,
  link({href, tokens}) { return `<a href="${/^https?:/i.test(href) ? attribute(href) : '#'}" data-reference="${attribute(href)}">${this.parser.parseInline(tokens)}</a>`; }
}, extensions: [
  localResourceLinks,
  { name: 'blockMath', level: 'block', start: source => source.indexOf('$$'), tokenizer(source) {
    const match = /^\$\$\s*\n?([\s\S]+?)\n?\$\$(?:\n|$)/.exec(source);
    if (match) return { type: 'blockMath', raw: match[0], text: match[1] };
  }, renderer: token => katex.renderToString(token.text, { displayMode: true, throwOnError: false, trust: false }) },
  { name: 'inlineMath', level: 'inline', start: source => source.indexOf('$'), tokenizer(source) {
    const match = /^\$([^\n$]+?)\$(?!\d)/.exec(source);
    if (match) return { type: 'inlineMath', raw: match[0], text: match[1] };
  }, renderer: token => katex.renderToString(token.text, { displayMode: false, throwOnError: false, trust: false }) },
] });
let diagramQueue: Promise<unknown> = Promise.resolve();

export const RichMarkdown=React.memo(function RichMarkdown({ text, basePath = '' }: { text: string; basePath?: string }) {
  const root = useRef<HTMLDivElement>(null);
  const session = useContext(MediaSession);
  const [preview, setPreview] = useState<{name: string; source: string; text?: string | null; markdown?: boolean; image?:boolean;directory?:any;url?: string; error?: string} | null>(null);
  const previewEpoch = useRef(0);
  useEffect(() => () => { ++previewEpoch.current; }, []);
  useEffect(() => () => { if (preview?.url?.startsWith('blob:')) URL.revokeObjectURL(preview.url); }, [preview?.url]);
  async function openFile(source: string, image = false) {
    const epoch = ++previewEpoch.current;
    setPreview({name: resourceName(source), source});
    try {
      if(image || /\.(?:png|jpe?g|gif|webp|bmp|svg|ico|tiff?|avif)(?:[?#]|$)/i.test(source)) {
        const url=await imageSource(source,session);
        if(epoch!==previewEpoch.current){if(url.startsWith('blob:'))URL.revokeObjectURL(url);return;}
        setPreview({name:resourceName(source),source,image:true,url});return;
      }
      const file = await fileSource(source, session);
      if (epoch !== previewEpoch.current) return;
      setPreview({...file, source, ...(file.blob ? {url:URL.createObjectURL(file.blob)} : {})});
    } catch (error) { if (epoch === previewEpoch.current) setPreview({name:'无法打开文件', source, error:(error as Error).message}); }
  }
  const [themeRevision, setThemeRevision] = useState(0);
  useEffect(() => {
    const change = () => setThemeRevision(value => value + 1);
    const observer = new MutationObserver(change);
    observer.observe(document.documentElement, { attributes: true, attributeFilter: ['data-theme'] });
    const scheme = matchMedia('(prefers-color-scheme: dark)'); scheme.addEventListener('change', change);
    return () => { observer.disconnect(); scheme.removeEventListener('change', change); };
  }, []);
  const html = useMemo(() => DOMPurify.sanitize(marked.parse(text || '', { async: false, gfm: true }) as string,
    { FORBID_TAGS: ['iframe', 'form', 'input'] }), [text]);
  useEffect(() => {
    let disposed = false;
    const container = root.current;
    if (!container) return;
    for (const preview of container.querySelectorAll('.mermaid-preview')) preview.remove();
    for (const details of container.querySelectorAll('.diagram-source')) {
      const pre = details.querySelector('pre'); if (pre) details.replaceWith(pre);
    }
    const objects: string[] = [];
    for (const img of container.querySelectorAll<HTMLImageElement>('img[data-source]')) {
      void imageSource(relativeReference(img.dataset.source || '', basePath), session).then(value => {
        if (disposed) { if (value.startsWith('blob:')) URL.revokeObjectURL(value); return; }
        objects.push(value); img.src = value;
      }).catch(error => { if (!disposed) { const label = document.createElement('span'); label.className='media-error'; label.textContent=`${img.alt || '图片'}：${error.message}`; img.replaceWith(label); } });
    }
    for (const block of container.querySelectorAll<HTMLElement>('pre code')) {
      const language = [...block.classList].find(name => name.startsWith('language-'))?.slice(9);
      if (language && language !== 'mermaid' && hljs.getLanguage(language)) {
        block.innerHTML = hljs.highlight(block.textContent || '', { language }).value;
        block.classList.add('hljs');
      }
    }
    const timer = setTimeout(() => {
      for (const block of container.querySelectorAll<HTMLElement>('pre code.language-mermaid')) {
        const source = block.textContent || '';
        diagramQueue = diagramQueue.catch(() => {}).then(async () => {
          if (disposed || !block.isConnected) return;
          const mermaid = (await import('mermaid')).default;
          const dark = ['dark', 'purple'].includes(document.documentElement.dataset.theme || '') || (!document.documentElement.dataset.theme && matchMedia('(prefers-color-scheme: dark)').matches);
          mermaid.initialize({ startOnLoad: false, securityLevel: 'strict', theme: dark ? 'dark' : 'default', flowchart: { htmlLabels: false } });
          try {
            const result = await mermaid.render('diagram' + crypto.randomUUID().replaceAll('-', ''), source);
            if (disposed || !block.isConnected) return;
            const preview = document.createElement('div'); preview.className = 'mermaid-preview';
            preview.innerHTML = DOMPurify.sanitize(result.svg, { USE_PROFILES: { svg: true, svgFilters: true } });
            const pre = block.parentElement!;
            const details = document.createElement('details'); details.className = 'diagram-source';
            const summary = document.createElement('summary'); summary.textContent = 'Mermaid';
            pre.before(preview, details); details.append(summary, pre);
          } catch { /* Preserve the complete source when a diagram is incomplete or invalid. */ }
        });
      }
    }, 200);
    return () => { disposed = true; clearTimeout(timer); objects.filter(value => value.startsWith('blob:')).forEach(value => URL.revokeObjectURL(value)); };
  }, [html, session, themeRevision, basePath]);
  return <><div ref={root} className="markdown" dangerouslySetInnerHTML={{ __html: html }} onClick={event => {
    const anchor = (event.target as Element).closest('a');
    if (!anchor) return;
    event.preventDefault();
    const source = anchor.dataset.reference || anchor.getAttribute('href') || '';
    if (source.startsWith('#')) { if (source.length > 1) document.getElementById(source.slice(1))?.scrollIntoView(); return; }
    const image=anchor.dataset.resourceImage==='true';
    if (!image && /^https?:\/\//i.test(source) && !/\/api\/(?:workspace-(?:image|media|file-text)|attachments\/)/.test(source)) { void chrome.tabs.create({url:source}); return; }
    if (/^(?:javascript|blob):/i.test(source) || /^data:/i.test(source) && !(image && /^data:image\/(?:png|jpeg|gif|webp);base64,/i.test(source))) return;
    void openFile(relativeReference(source, basePath),image);
  }} />{preview && <Dialog label={preview.directory ? '文件夹预览' : preview.image ? '图片预览' : '文件预览'} onClose={() => {++previewEpoch.current; setPreview(null);}}><div className="file-preview"><header><h2>{preview.name}</h2><button onClick={() => {++previewEpoch.current; setPreview(null);}}>关闭</button></header>
    {preview.error ? <p className="file-preview-error" role="alert">{preview.error}</p> : preview.directory ? <><p className="directory-path">{preview.directory.path}</p><div className="directory-list">{preview.directory.parent && <button onClick={()=>void openFile(preview.directory.parent)}><Icon name="folder" size={15}/><span>上一级</span><Icon name="chevron" size={13}/></button>}{preview.directory.entries.map((entry:any)=><button key={entry.name} onClick={()=>void openFile(preview.directory.path.replace(/[\\/]+$/,'')+'/'+entry.name)}><Icon name={entry.type==='directory' ? 'folder' : 'attach'} size={15}/><span>{entry.name}</span><Icon name="chevron" size={13}/></button>)}{!preview.directory.entries.length && <p className="secondary">文件夹为空</p>}</div>{preview.directory.truncated && <p className="secondary">仅显示前 200 项。</p>}</> : preview.url ? <>{preview.image ? <img className="file-preview-image" src={preview.url} alt={preview.name}/> : preview.text !== null && preview.text !== undefined ? preview.markdown ? <RichMarkdown text={preview.text} basePath={preview.source} /> : <pre>{preview.text}</pre> : <p>此文件可下载后查看。</p>}<a href={preview.url} download={preview.name}>下载文件</a></> : <p className="secondary">正在读取文件…</p>}
  </div></Dialog>}</>;
});
