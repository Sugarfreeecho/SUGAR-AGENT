var Pn=Object.defineProperty;var Ln=(t,e,n)=>e in t?Pn(t,e,{enumerable:!0,configurable:!0,writable:!0,value:n}):t[e]=n;var L=(t,e,n)=>Ln(t,typeof e!="symbol"?e+"":e,n);import"./modulepreload-polyfill-B5Qt9EMX.js";(function(t){var e=104857600,n=200*1024*1024,r='<svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M3 7a2 2 0 0 1 2-2h4l2 2h8a2 2 0 0 1 2 2v9a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V7z"></path></svg>';function s(){if(!document.getElementById("myagent-path-picker-styles")){var o=document.createElement("style");o.id="myagent-path-picker-styles",o.textContent='.path-input-row{display:flex;align-items:stretch;gap:.35rem;width:100%;}.path-input-row>.ip,.path-input-row>.tx,.path-input-row>input[type="text"],.path-input-row>input:not([type]){flex:1;min-width:0;}.path-browse-btn{flex-shrink:0;width:2.35rem;padding:0;border:1px solid var(--border-glass,rgba(255,255,255,.08));border-radius:var(--radius-sm,8px);background:var(--surface-glass2,rgba(40,40,60,.94));color:var(--text-secondary,#a6adc8);cursor:pointer;display:inline-flex;align-items:center;justify-content:center;transition:color .18s,border-color .18s,background .18s;}.path-browse-btn:hover{color:var(--text-primary,#cdd6f4);border-color:var(--border-brand-accent,rgba(124,111,247,.35));background:rgba(108,92,231,.12);}.path-browse-btn:disabled{opacity:.45;cursor:not-allowed;}.path-browse-btn--ghost{background:transparent;border-color:transparent;box-shadow:none;width:2.1rem;}.path-browse-btn--ghost:hover{background:rgba(108,92,231,.1);border-color:transparent;color:var(--accent-2,#d4b8fc);}.input-wrapper .path-browse-btn--ghost{align-self:center;margin-right:-.15rem;}.input-wrapper.is-drag-over{border-color:rgba(203,166,247,.62);box-shadow:0 0 0 3px rgba(203,166,247,.12),0 0 28px rgba(139,92,246,.18);}.input-wrapper.is-file-uploading{border-color:rgba(99,102,241,.52);}.chat-upload-status{box-sizing:border-box;width:100%;margin:.38rem 0 0;padding:.42rem .58rem;border:1px solid rgba(99,102,241,.22);border-radius:10px;background:rgba(99,102,241,.08);color:var(--text-secondary,#a6adc8);font-size:.72rem;}.chat-upload-status-row{display:flex;align-items:center;gap:.5rem;}.chat-upload-status-label{flex:1;min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;}.chat-upload-cancel{flex:none;border:0;background:transparent;color:var(--accent-2,#d4b8fc);font:inherit;font-weight:700;cursor:pointer;padding:.08rem .2rem;}.chat-upload-cancel:hover{color:var(--text-primary,#fff);}.chat-upload-progress{height:4px;margin-top:.36rem;border-radius:999px;overflow:hidden;background:rgba(255,255,255,.1);}.chat-upload-progress-bar{display:block;width:0;height:100%;border-radius:inherit;background:linear-gradient(90deg,#6366f1,#a78bfa);transition:width .12s linear;}.workspace-file-popover{position:fixed;display:none;z-index:260;width:min(46rem,calc(100vw - 1.2rem));height:min(44rem,82vh);max-height:min(44rem,82vh);border:1px solid rgba(203,166,247,.24);border-radius:14px;background:linear-gradient(145deg,rgba(31,31,49,.88),rgba(19,20,31,.78));box-shadow:0 24px 70px rgba(0,0,0,.38),0 0 0 1px rgba(255,255,255,.045) inset,0 0 34px rgba(139,92,246,.16);overflow:hidden;backdrop-filter:blur(22px);-webkit-backdrop-filter:blur(22px);}.workspace-file-popover:before{content:"";position:absolute;inset:0;pointer-events:none;background:radial-gradient(circle at 18% 0%,rgba(203,166,247,.18),transparent 30%),radial-gradient(circle at 92% 18%,rgba(99,102,241,.16),transparent 28%);}.workspace-file-popover.is-open{display:flex;flex-direction:column;}.workspace-file-search{position:relative;width:100%;box-sizing:border-box;border:0;border-bottom:1px solid rgba(255,255,255,.08);background:rgba(255,255,255,.055);color:var(--text-primary,#cdd6f4);padding:.56rem .72rem;font:inherit;font-size:.78rem;outline:none;}.workspace-file-search::placeholder{color:var(--text-muted,#6c7086);}.workspace-file-list{position:relative;flex:1;min-height:0;overflow:auto;padding:.36rem .38rem .2rem;}.workspace-file-item{width:100%;display:grid;grid-template-columns:1.05rem minmax(0,1fr) auto;gap:.2rem .38rem;align-items:center;text-align:left;border:0;border-radius:8px;background:transparent;color:var(--text-secondary,#a6adc8);padding:.22rem .36rem;cursor:pointer;font:inherit;font-size:.74rem;}.workspace-file-item:hover,.workspace-file-item.is-active{background:rgba(139,92,246,.13);color:var(--text-primary,#cdd6f4);}.workspace-file-item.is-selected{background:rgba(99,102,241,.18);color:var(--text-primary,#cdd6f4);}.workspace-file-check{width:.82rem;height:.82rem;border:1px solid rgba(203,166,247,.38);border-radius:4px;display:inline-flex;align-items:center;justify-content:center;color:#fff;font-size:.62rem;line-height:1;background:transparent;}.workspace-file-item.is-selected .workspace-file-check{background:linear-gradient(135deg,#6366f1,#a78bfa);border-color:transparent;color:#fff;}.workspace-file-dir-row{grid-template-columns:1.05rem minmax(0,1fr) auto;color:var(--text-primary,#cdd6f4);font-weight:650;}.workspace-file-dir-row .workspace-file-tree{grid-column:2/3;}.workspace-file-file-row{grid-template-columns:1.05rem minmax(0,1fr) auto;}.workspace-file-tree{min-width:0;display:flex;align-items:center;gap:.24rem;}.workspace-file-indent{flex:0 0 auto;width:var(--indent,0);}.workspace-file-chevron{width:.8rem;min-width:.8rem;color:var(--text-muted,#6c7086);font-size:.72rem;text-align:center;border:0;background:transparent;padding:0;cursor:pointer;}.workspace-file-icon{position:relative;width:.98rem;min-width:.98rem;height:.74rem;margin-top:.04rem;border-radius:3px;border:1px solid rgba(203,166,247,.28);background:linear-gradient(135deg,rgba(203,166,247,.18),rgba(99,102,241,.1));box-shadow:inset 0 .12rem .26rem rgba(255,255,255,.08);}.workspace-file-icon:before{content:"";position:absolute;left:.06rem;right:.06rem;top:.12rem;height:.16rem;border-radius:999px;background:rgba(203,166,247,.34);}.workspace-file-icon:after{content:"";position:absolute;left:.06rem;right:.06rem;bottom:.11rem;height:.24rem;border-radius:2px;background:rgba(99,102,241,.16);}.workspace-file-icon.is-file{width:.82rem;min-width:.82rem;height:1rem;margin-top:0;border-radius:3px;background:transparent;border:1.5px solid rgba(166,173,200,.58);box-shadow:none;color:var(--text-muted,#6c7086);}.workspace-file-icon.is-file:before{left:auto;right:-1.5px;top:-1.5px;width:.3rem;height:.3rem;border:0;border-left:1.5px solid rgba(166,173,200,.58);border-bottom:1.5px solid rgba(166,173,200,.58);border-radius:0 3px 0 3px;background:var(--surface-glass2,rgba(40,40,60,.94));}.workspace-file-icon.is-file:after{display:none;}.workspace-file-icon.is-folder-svg{width:1rem;min-width:1rem;height:1rem;margin-top:0;border:0;background:transparent;box-shadow:none;color:var(--text-muted,#6c7086);display:inline-flex;align-items:center;justify-content:center;}.workspace-file-icon.is-folder-svg:before,.workspace-file-icon.is-folder-svg:after{display:none;}.workspace-file-icon.is-folder-svg svg{width:1rem;height:1rem;display:block;}.workspace-file-icon.is-image{border-color:rgba(45,212,191,.72);}.workspace-file-icon.is-image:after{display:block;left:.12rem;right:.12rem;bottom:.15rem;height:.24rem;clip-path:polygon(0 100%,38% 38%,56% 66%,76% 24%,100% 100%);background:rgba(45,212,191,.72);}.workspace-file-icon.is-audio{border-color:rgba(251,191,36,.76);}.workspace-file-icon.is-audio:after{display:block;left:.17rem;right:auto;bottom:.18rem;width:.36rem;height:.4rem;border-radius:0;background:rgba(251,191,36,.76);clip-path:polygon(0 32%,45% 32%,100% 0,100% 100%,45% 68%,0 68%);}.workspace-file-name{min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;font-size:.74rem;}.workspace-file-dir{grid-column:2/-1;color:var(--text-muted,#6c7086);font-size:.68rem;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;}.workspace-file-meta{color:var(--text-muted,#6c7086);font-size:.68rem;white-space:nowrap;}.workspace-file-footer{position:relative;display:flex;align-items:center;justify-content:space-between;gap:.5rem;padding:.42rem .52rem;border-top:1px solid rgba(255,255,255,.08);background:rgba(255,255,255,.035);font-size:.72rem;color:var(--text-muted,#6c7086);}.workspace-file-outside{flex-shrink:0;border:1px solid rgba(203,166,247,.24);border-radius:8px;padding:.28rem .58rem;background:rgba(203,166,247,.1);color:var(--text-primary,#cdd6f4);font:inherit;font-size:.7rem;font-weight:700;cursor:pointer;transition:background .16s,border-color .16s,color .16s;}.workspace-file-outside:hover{background:rgba(203,166,247,.18);border-color:rgba(203,166,247,.42);color:#fff;}.workspace-file-insert{border:0;border-radius:8px;padding:.34rem .62rem;background:linear-gradient(135deg,#6366f1,#8b5cf6);color:#fff;font-size:.72rem;font-weight:700;cursor:pointer;}.workspace-file-insert:disabled{opacity:.45;cursor:not-allowed;}.workspace-file-empty{padding:1rem;text-align:center;color:var(--text-muted,#6c7086);font-size:.78rem;}.theme-light .workspace-file-popover{background:linear-gradient(145deg,rgba(255,255,255,.93),rgba(244,247,252,.86));box-shadow:0 24px 64px rgba(31,35,52,.16),0 0 28px rgba(99,102,241,.12);}.theme-light .workspace-file-search,.theme-light .workspace-file-footer{background:rgba(34,40,58,.035);}',document.head.appendChild(o)}}async function i(o,m,g){var w=typeof AbortController<"u"?new AbortController:null,v=w?setTimeout(function(){w.abort()},5e4):null,C;try{C=await fetch("/api/pick-path",{method:"POST",headers:{"Content-Type":"application/json"},credentials:"same-origin",body:JSON.stringify({kind:o||"directory",initial:m||"",multiple:!!g}),signal:w?w.signal:void 0})}finally{v&&clearTimeout(v)}var I=await C.json().catch(function(){return{ok:!1,error:"请求失败"}});if(!C.ok||!I.ok){if(I&&I.cancelled)return null;var d=I&&I.error||"无法打开选择对话框";if(/取消|cancelled|800704c7|2147023673/i.test(d))return null;throw new Error(d)}return g?Array.isArray(I.paths)?I.paths:I.path?[I.path]:[]:I.path||null}async function f(o,m,g,w,v){o.disabled=!0;try{var C=await i(m,g||"",!!v);w&&w(C)}catch{return}finally{o.disabled=!1}}function a(o){var m=String(o||"").trim();return m?((m.charAt(0)==='"'&&m.charAt(m.length-1)==='"'||m.charAt(0)==="'"&&m.charAt(m.length-1)==="'")&&(m=m.slice(1,-1)),'"'+m.replace(/"/g,'\\"')+'"'):""}function h(o){var m=String(o||"").toLowerCase().split(".").pop()||"";return/^(png|jpe?g|gif|webp|bmp|svg|tiff?|ico|avif)$/.test(m)?"is-image":/^(mp3|wav|flac|aac|m4a|ogg|oga|opus|wma|aiff?)$/.test(m)?"is-audio":""}function l(o,m){var g=o.selectionStart,w=o.selectionEnd,v=o.value.slice(0,g),C=o.value.slice(w),I=String(m||"");v.length&&!/\s$/.test(v)&&(I=" "+I),C.length&&!/^\s/.test(C)&&(I=I+" "),o.value=v+I+C;var d=v.length+I.length;o.selectionStart=o.selectionEnd=d,o.dispatchEvent(new Event("input",{bubbles:!0})),o.focus()}function u(o){var m=Array.prototype.slice.call(o||[]).filter(Boolean),g=0;if(m.forEach(function(w){var v=Number(w&&w.size||0);if(v>e)throw new Error("文件“"+String(w&&w.name||"未命名文件")+"”超过 "+S(e)+" 限制。");g+=Math.max(0,v)}),g>n)throw new Error("本次上传总大小超过 "+S(n)+" 限制。");return m}function T(o,m){var g;try{g=u(o)}catch(v){return Promise.reject(v)}if(!g.length)return Promise.resolve([]);m=m||{};var w=new FormData;return g.forEach(function(v){w.append("files",v,v.name||"upload.bin")}),new Promise(function(v,C){var I=new XMLHttpRequest;I.open("POST","/api/upload-chat-files",!0),I.withCredentials=!0,I.timeout=600*1e3,I.upload&&typeof m.onProgress=="function"&&(I.upload.onprogress=function(d){m.onProgress(d.loaded||0,d.lengthComputable?d.total:0)}),typeof m.registerAbort=="function"&&m.registerAbort(function(){I.abort()}),I.onload=function(){var d;try{d=JSON.parse(I.responseText||"{}")}catch{d={ok:!1,error:"上传失败"}}if(I.status<200||I.status>=300||!d.ok){C(new Error(d&&d.error||"上传失败"));return}v(Array.isArray(d.files)?d.files:[])},I.onerror=function(){C(new Error("上传失败：网络连接异常。"))},I.ontimeout=function(){C(new Error("上传超时，请重试。"))},I.onabort=function(){var d=new Error("上传已取消。");d.name="AbortError",C(d)},I.send(w)})}function S(o){return o=Number(o||0),!isFinite(o)||o<=0?"":o<1024?o+" B":o<1024*1024?Math.round(o/102.4)/10+" KB":o<1024*1024*1024?Math.round(o/104857.6)/10+" MB":Math.round(o/1073741824e-1)/10+" GB"}async function F(o,m,g){var w=[];o?w.push("q="+encodeURIComponent(o)):m&&w.push("dir="+encodeURIComponent(m));var v="/api/workspace-files"+(w.length?"?"+w.join("&"):""),C=await fetch(v,{credentials:"same-origin",signal:g}),I=await C.json().catch(function(){return{ok:!1,error:"读取工作区文件失败"}});if(!C.ok||!I.ok)throw new Error(I&&I.error||"读取工作区文件失败");return Array.isArray(I.files)?I.files:[]}function E(){try{return typeof currentSessionId<"u"?String(currentSessionId||""):""}catch{return""}}function N(o,m,g){if(m){var w=E();if(g&&w&&g!==w){try{if(typeof persistInputDraft=="function"){var v="";typeof draftBySession<"u"&&Object.prototype.hasOwnProperty.call(draftBySession,g)?v=String(draftBySession[g]||""):typeof readStoredInputDraft=="function"&&(v=String(readStoredInputDraft(g)||"")),persistInputDraft(g,v.trim()?v+" "+m:m);return}}catch{}return}l(o,m)}}function ne(o,m,g){var w=E();return T(m,g).then(function(v){var C=Array.isArray(o._myAgentStructuredAttachments)?o._myAgentStructuredAttachments.slice():[];v.forEach(function(d){!d||!d.path||C.some(function(B){return B.path===d.path})||C.push({path:d.path,name:d.name||"",size:Number(d.size||0)})}),o._myAgentStructuredAttachments=C;var I=v.map(function(d){return a(d.path||d.rel||d.name)}).join(" ");N(o,I,w)})}function te(o){return Array.isArray(o&&o._myAgentStructuredAttachments)?o._myAgentStructuredAttachments.slice():[]}function ue(o){o&&(o._myAgentStructuredAttachments=[])}function X(o,m){console.error("chat file upload failed:",m),o.dispatchEvent(new CustomEvent("myagent:file-paste-error",{bubbles:!0,detail:{message:String(m&&m.message||m||"上传失败")}}))}function re(o,m){var g=o.closest?o.closest(".input-wrapper"):null;m?o.dataset.fileUploadBusy="1":delete o.dataset.fileUploadBusy,g&&(g.classList.toggle("is-file-uploading",!!m),m?g.setAttribute("aria-busy","true"):g.removeAttribute("aria-busy")),o.dispatchEvent(new CustomEvent("myagent:file-upload-state",{bubbles:!0,detail:{busy:!!m}}))}function ye(o,m){var g=o.closest?o.closest(".input-wrapper"):null,w=document.createElement("div");w.className="chat-upload-status",w.setAttribute("role","status"),w.innerHTML='<div class="chat-upload-status-row"><span class="chat-upload-status-label"></span><button type="button" class="chat-upload-cancel">取消</button></div><div class="chat-upload-progress" role="progressbar" aria-valuemin="0" aria-valuemax="100" aria-valuenow="0"><span class="chat-upload-progress-bar"></span></div>';var v=m.length;return w.querySelector(".chat-upload-status-label").textContent="正在上传 "+v+" 个文件… 0%",g&&g.parentNode&&g.parentNode.insertBefore(w,g.nextSibling),w}function W(o,m){var g;try{g=u(m)}catch(O){return X(o,O),Promise.reject(O)}if(!g.length)return Promise.resolve();if(o._myAgentActiveUpload){var w=new Error("已有文件正在上传，请等待完成或先取消。");return X(o,w),Promise.reject(w)}var v=ye(o,g),C=v.querySelector(".chat-upload-status-label"),I=v.querySelector(".chat-upload-progress"),d=v.querySelector(".chat-upload-progress-bar"),B=v.querySelector(".chat-upload-cancel"),U=null,H=o._myAgentActiveUpload={};return re(o,!0),B.addEventListener("click",function(){B.disabled=!0,C.textContent="正在取消上传…",U&&U()}),ne(o,g,{registerAbort:function(O){U=O},onProgress:function(O,Z){if(o._myAgentActiveUpload===H){var J=Z>0?Math.min(100,Math.round(O*100/Z)):0;C.textContent="正在上传 "+g.length+" 个文件… "+J+"%",d.style.width=J+"%",I.setAttribute("aria-valuenow",String(J))}}}).catch(function(O){throw(!O||O.name!=="AbortError")&&X(o,O),O}).finally(function(){o._myAgentActiveUpload===H&&(delete o._myAgentActiveUpload,re(o,!1)),v.parentNode&&v.parentNode.removeChild(v)})}function V(o){var m=o&&o.clipboardData;if(!m)return[];var g=[],w=Array.prototype.slice.call(m.items||[]);return w.forEach(function(v){if(!(!v||v.kind!=="file"||typeof v.getAsFile!="function")){var C=v.getAsFile();C&&g.push(C)}}),g.length||(g=Array.prototype.slice.call(m.files||[]).filter(Boolean)),g.map(function(v,C){if(String(v&&v.name||"").trim())return v;var I=String(v&&v.type||"").split("/")[1]||"bin";I=I.replace(/[^a-z0-9.+-]/gi,"")||"bin";var d="clipboard-"+Date.now()+"-"+(C+1)+"."+I;try{return new File([v],d,{type:v.type||"application/octet-stream",lastModified:Date.now()})}catch{return v}})}function qe(o){var m=o&&o.clipboardData;if(!m||typeof m.getData!="function")return!1;try{return String(m.getData("text/plain")||"").trim().length>0}catch{return!1}}function fn(o){!o||o.dataset.filePasteBound==="1"||(o.dataset.filePasteBound="1",o.addEventListener("paste",function(m){if(!qe(m)){var g=V(m);g.length&&(m.preventDefault(),W(o,g).catch(function(){}))}}))}function mn(o,m){var g=document.createElement("div");g.className="workspace-file-popover",g.setAttribute("aria-hidden","true"),g.innerHTML='<input class="workspace-file-search" type="text" autocomplete="off" spellcheck="false" placeholder="搜索工作区文件"><div class="workspace-file-list" role="listbox"></div><div class="workspace-file-footer"><span class="workspace-file-count">未选择文件</span><button type="button" class="workspace-file-outside">选择工作目录外文件</button></div>',document.body.appendChild(g);var w=g.querySelector(".workspace-file-search"),v=g.querySelector(".workspace-file-list"),C=g.querySelector(".workspace-file-count"),I=g.querySelector(".workspace-file-outside"),d={items:[],visible:[],active:0,open:!1,debounce:null,controller:null,selected:Object.create(null),expanded:Object.create(null),loadedDirs:Object.create(null),itemMap:Object.create(null)};function B(){var c=o.closest?o.closest(".input-wrapper"):o,p=c.getBoundingClientRect(),b=8,k=Math.min(Math.max(p.width,520),window.innerWidth-16),y=Math.max(8,Math.min(p.left,window.innerWidth-k-8)),P=document.querySelector(".titlebar"),x=P?P.getBoundingClientRect().bottom:44,A=parseFloat(getComputedStyle(document.documentElement).fontSize||"16")||16,M=Math.min(44*A,window.innerHeight*.82),j=Math.max(1,p.top-x-b),D=Math.min(M,j),ee=p.top-D-b;if(D<96){var ae=Math.max(1,window.innerHeight-p.bottom-b-8);D=Math.min(M,ae),ee=p.bottom+b}g.style.left=y+"px",g.style.top=Math.max(x,ee)+"px",g.style.width=k+"px",g.style.height=Math.max(1,Math.floor(D))+"px",g.style.maxHeight=Math.max(1,Math.floor(D))+"px"}function U(){var c=Object.keys(d.selected).length;C.textContent=c?"已选择 "+c+" 项":"未选择文件",v.querySelectorAll(".workspace-file-item").forEach(function(p){var b=p.getAttribute("data-path-key")||"",k=!!d.selected[b];p.classList.toggle("is-selected",k);var y=p.querySelector(".workspace-file-check");y&&(y.textContent=k?"✓":"")})}function H(c){var p=v.querySelectorAll(".workspace-file-item");if(!p.length){d.active=0;return}d.active=Math.max(0,Math.min(c,p.length-1));for(var b=0;b<p.length;b++)p[b].classList.toggle("is-active",b===d.active),p[b].setAttribute("aria-selected",b===d.active?"true":"false");var k=p[d.active];k&&typeof k.scrollIntoView=="function"&&k.scrollIntoView({block:"nearest"})}function O(){d.open=!1,g.classList.remove("is-open"),g.setAttribute("aria-hidden","true"),d.debounce&&clearTimeout(d.debounce),d.controller&&d.controller.abort()}function Z(c){return c&&(c.path||c.rel||c.name)||""}function J(c){return a(Z(c))}function Sn(c,p){var b=Z(c);if(!b)return!1;var k=String(c&&c.rel||"");return p.indexOf(J(c))>=0||p.indexOf(b)>=0||k&&p.indexOf(a(k))>=0||k&&p.indexOf(k)>=0}function bn(c,p){c=String(c||""),p=String(p||"");for(var b=0;b<c.length&&b<p.length&&c.charAt(b)===p.charAt(b);)b++;for(var k=c.length-1,y=p.length-1;k>=b&&y>=b&&c.charAt(k)===p.charAt(y);)k--,y--;return p.slice(b,y+1).trim()}function yn(c,p){if(p){var b=String(o.value||"");if(!(b.indexOf(p)>=0)){var k=o.value;l(o,p);var y=bn(k,o.value);c&&y&&(c._inputToken=y)}}}function wn(c,p){if(!p&&!c)return;var b=String(o.value||""),k=[];function y(x){x=String(x||"").trim(),x&&k.indexOf(x)<0&&k.push(x)}y(c&&c._inputToken),y(p),y(c&&c.path),y(c&&c.rel),y(c&&c.path&&a(c.path)),y(c&&c.rel&&a(c.rel));var P=b;k.sort(function(x,A){return A.length-x.length}).forEach(function(x){var A=x.replace(/[.*+?^${}()|[\]\\]/g,"\\$&"),M=new RegExp("(?:^|\\s)"+A+"(?=\\s|$)","g");P=P.replace(M,function(j){return j.charAt(0)&&/\s/.test(j.charAt(0))?" ":""})}),P=P.replace(/[ \t]{2,}/g," ").trim(),P!==b&&(o.value=P,o.selectionStart=o.selectionEnd=o.value.length,o.dispatchEvent(new Event("input",{bubbles:!0})))}function pe(c){if(c){var p=Z(c);if(p){var b=J(c);if(d.selected[p]){var k=d.selected[p];delete d.selected[p],wn(k,b)}else d.selected[p]=c,yn(c,b);U()}}}function Ue(){var c=String(o.value||"");Object.keys(d.selected).forEach(function(p){var b=d.selected[p];Sn(b,c)||delete d.selected[p]})}function In(){Ue(),U()}o.addEventListener("input",In),I&&I.addEventListener("click",function(c){c.preventDefault(),c.stopPropagation(),typeof m=="function"&&m()});function He(){var c=String(t.__WORK_DIR__||"workspace"),p=c.split(/[\\/]+/).filter(Boolean);return p[p.length-1]||"workspace"}function je(c,p,b){return{type:"dir",name:c,rel:p,root:!!b,path:"",dirs:Object.create(null),files:[],children:[],loaded:!1}}function xn(c,p){var b=String(c&&c.path||""),k=String(p||"").replace(/\//g,"\\");return b&&k&&b.toLowerCase().slice(-k.length)===k.toLowerCase()?b.slice(0,Math.max(0,b.length-k.length)).replace(/[\\/]+$/,""):String(t.__WORK_DIR__||"").replace(/[\\/]+$/,"")}function Ge(c,p){var b=String(c||"").replace(/[\\/]+$/,""),k=String(p||"").replace(/[\\/]+/g,"/");if(!k)return b;var y=b.indexOf("\\")>=0?"\\":"/";return b?b+y+k.replace(/\//g,y):k}function se(c){return{kind:"directory",name:c.name||c.rel||He(),rel:c.rel||"",path:c.path||Ge(String(t.__WORK_DIR__||""),c.rel||"")}}function kn(c){var p=je(He(),"",!0);p.path=String(t.__WORK_DIR__||"").replace(/[\\/]+$/,""),p.loaded=!!d.loadedDirs.__root__;function b(y,P){for(var x=p,A=[],M=0;M<y.length;M++)A.push(y[M]),x.dirs[y[M]]||(x.dirs[y[M]]=je(y[M],A.join("/"),!1),x.dirs[y[M]].path=Ge(P||p.path,A.join("/"))),x=x.dirs[y[M]],x.loaded=!!d.loadedDirs[x.rel||"__root__"];return x}(c||[]).forEach(function(y){var P=String(y.rel||y.path||y.name||"").replace(/\\/g,"/"),x=P.split("/").filter(Boolean);if(x.length){var A=xn(y,P);if(!p.path&&A&&(p.path=A),y.kind==="directory"){var M=b(x,A||p.path);M.name=y.name||M.name,M.path=y.path||M.path;return}var j=b(x.slice(0,-1),A||p.path);j.files.push({type:"file",name:y.name||x[x.length-1]||P,rel:P,item:y})}});function k(y){var P=Object.keys(y.dirs).map(function(x){return y.dirs[x]}).sort(function(x,A){return x.name.localeCompare(A.name,void 0,{sensitivity:"base"})});P.forEach(k),y.files.sort(function(x,A){return x.name.localeCompare(A.name,void 0,{sensitivity:"base"})}),y.children=P.concat(y.files)}return k(p),p}function $e(c,p,b){if(!(!c||c.type!=="dir")){b=Number(b||0);var k=c.rel||"__root__";p?d.expanded[k]=!0:typeof d.expanded[k]>"u"&&(d.expanded[k]=b===0),p&&c.children.forEach(function(y){y.type==="dir"&&$e(y,p,b+1)})}}function Cn(c){var p=[];function b(k,y){p.push({type:"dir",node:k,depth:y}),d.expanded[k.rel||"__root__"]&&k.children.forEach(function(P){P.type==="dir"?b(P,y+1):p.push({type:"file",node:P,depth:y+1})})}return b(c,0),p}function Tn(c){return String(c&&(c.kind||"file")||"file")+":"+String(c&&(c.rel||c.path||c.name)||"")}function ze(c){(c||[]).forEach(function(p){var b=Tn(p);b!==":"&&(d.itemMap[b]=p)}),d.items=Object.keys(d.itemMap).map(function(p){return d.itemMap[p]}),d.items.sort(function(p,b){return String(p.rel||"").localeCompare(String(b.rel||""),void 0,{sensitivity:"base"})})}function En(c){if(c){var p=c.rel||"__root__";d.expanded[p]=!d.expanded[p],Q(d.items,!1),d.expanded[p]&&!w.value&&!d.loadedDirs[p]&&An(c.rel||"")}}function Q(c,p,b){if(Ue(),d.items=(c||[]).slice().sort(function(y,P){return String(y.rel||"").localeCompare(String(P.rel||""),void 0,{sensitivity:"base"})}),v.innerHTML="",d.visible=[],p){v.innerHTML='<div class="workspace-file-empty">加载中</div>';return}if(b){v.innerHTML='<div class="workspace-file-empty">'+String(b)+"</div>";return}if(!d.items.length){v.innerHTML='<div class="workspace-file-empty">没有匹配文件</div>';return}var k=kn(d.items);$e(k,!!w.value),d.visible=Cn(k),d.visible.forEach(function(y,P){var x=y.node,A=document.createElement("button");A.type="button",A.className="workspace-file-item "+(y.type==="dir"?"workspace-file-dir-row":"workspace-file-file-row"),A.setAttribute("role","option"),A.setAttribute("data-row-index",String(P)),A.setAttribute("data-path-key",y.type==="dir"?se(x).path||se(x).rel||se(x).name||"":x.item.path||x.item.rel||x.item.name||"");var M=document.createElement("div");M.className="workspace-file-tree";var j=document.createElement("span");j.className="workspace-file-indent",j.style.setProperty("--indent",Math.min(y.depth,10)*.86+"rem");var D=document.createElement("span");D.className="workspace-file-chevron",D.textContent=y.type==="dir"?d.expanded[x.rel||"__root__"]?"▾":"▸":"",y.type==="dir"?(D.setAttribute("aria-label",d.expanded[x.rel||"__root__"]?"折叠文件夹":"展开文件夹"),D.setAttribute("role","button"),D.addEventListener("click",function(ie){ie.preventDefault(),ie.stopPropagation(),En(x)})):D.setAttribute("tabindex","-1");var ee=document.createElement("span");ee.className="workspace-file-icon"+(y.type==="file"?" is-file "+h(x.item&&x.item.name):" is-folder-svg"),y.type==="dir"&&(ee.innerHTML=r);var ae=document.createElement("div");ae.className="workspace-file-name",ae.textContent=x.name||x.rel||"";var Ie=document.createElement("div");Ie.className="workspace-file-meta",Ie.textContent=y.type==="dir"?"":S(x.item.size),M.appendChild(j),M.appendChild(D),M.appendChild(ee),M.appendChild(ae);var Qe=document.createElement("span");Qe.className="workspace-file-check",A.appendChild(Qe),A.appendChild(M),A.appendChild(Ie),A.addEventListener("mouseenter",function(){H(P)}),A.addEventListener("click",function(ie){ie.preventDefault(),ie.stopPropagation(),y.type==="dir"?pe(se(x)):pe(x.item)}),v.appendChild(A)}),H(0),U()}function We(){var c=w.value||"";d.controller&&d.controller.abort(),d.controller=typeof AbortController<"u"?new AbortController:null,Q(d.items,!0),F(c,"",d.controller?d.controller.signal:void 0).then(function(p){d.open&&(c?Q(p,!1):(d.loadedDirs.__root__=!0,ze(p),Q(d.items,!1)))}).catch(function(p){p&&p.name==="AbortError"||d.open&&Q([],!1,p&&p.message||"读取失败")})}function An(c){var p=c||"__root__";d.loadedDirs[p]||(d.loadedDirs[p]=!0,F("",c||"",void 0).then(function(b){!d.open||w.value||(ze(b),Q(d.items,!1))}).catch(function(){delete d.loadedDirs[p]}))}function _n(){d.debounce&&clearTimeout(d.debounce),d.debounce=setTimeout(We,120)}function Ve(){if(d.open){B();try{w.focus(),w.select()}catch{}return}d.open=!0,g.classList.add("is-open"),g.setAttribute("aria-hidden","false"),w.value="",d.expanded=Object.create(null),d.loadedDirs=Object.create(null),d.itemMap=Object.create(null),d.items=[],Q([],!0),B(),We(),setTimeout(function(){B();try{w.focus()}catch{}},0)}function Rn(){d.open?O():Ve()}return w.addEventListener("input",_n),w.addEventListener("keydown",function(c){if(c.key==="ArrowDown")c.preventDefault(),H(d.active+1);else if(c.key==="ArrowUp")c.preventDefault(),H(d.active-1);else if(c.key==="Enter"){c.preventDefault();var p=d.visible[d.active];p&&p.type==="dir"?pe(se(p.node)):p&&p.type==="file"&&pe(p.node.item)}else c.key==="Escape"&&(c.preventDefault(),O(),o.focus())}),document.addEventListener("click",function(c){d.open&&(g.contains(c.target)||O())}),window.addEventListener("resize",function(){d.open&&B()}),window.addEventListener("scroll",function(){d.open&&B()},!0),{panel:g,open:Ve,close:O,toggle:Rn}}function De(o,m,g){if(!o||o.dataset.pathBrowseWrapped==="1")return o;s();var w=document.createElement("div");w.className="path-input-row";var v=o.parentNode;if(!v)return o;v.insertBefore(w,o),w.appendChild(o);var C=document.createElement("button");C.type="button",C.className="path-browse-btn",C.innerHTML=r;var I=g||"浏览路径";return C.setAttribute("aria-label",I),typeof bindUiHoverTip=="function"?(C.setAttribute("data-ui-tip",I),C.removeAttribute("title"),bindUiHoverTip(C)):C.title=I,C.addEventListener("click",function(d){d.stopPropagation();var B=o.getAttribute("data-path-kind")||m;B!=="file"&&B!=="directory"&&(B="directory"),f(C,B,o.value||"",function(U){if(U){var H=Array.isArray(U)?U[0]||"":String(U);H&&(o.value=H,o.dispatchEvent(new Event("input",{bubbles:!0})),o.dispatchEvent(new Event("change",{bubbles:!0})))}})}),w.appendChild(C),o.dataset.pathBrowseWrapped="1",o}function hn(o){var m=o.closest?o.closest(".input-wrapper"):o;!m||m.dataset.fileDropBound==="1"||(m.dataset.fileDropBound="1",["dragenter","dragover"].forEach(function(g){m.addEventListener(g,function(w){!w.dataTransfer||!w.dataTransfer.files||!w.dataTransfer.files.length||(w.preventDefault(),m.classList.add("is-drag-over"))})}),["dragleave","drop"].forEach(function(g){m.addEventListener(g,function(){m.classList.remove("is-drag-over")})}),m.addEventListener("drop",function(g){!g.dataTransfer||!g.dataTransfer.files||!g.dataTransfer.files.length||(g.preventDefault(),W(o,g.dataTransfer.files).catch(function(){}))}))}function vn(o,m){if(!(!o||!m)){s(),hn(m),fn(m),o.classList.add("path-browse-btn","path-browse-btn--ghost"),o.innerHTML=r,o.setAttribute("aria-label","工作区文件"),o.setAttribute("data-ui-tip","工作区文件"),o.dataset.silentPickerUnavailable="1",o.removeAttribute("title");var g=document.createElement("input");g.type="file",g.multiple=!0,g.style.display="none",g.setAttribute("aria-hidden","true"),document.body.appendChild(g),g.addEventListener("change",function(){var v=g.files;!v||!v.length||(o.disabled=!0,W(m,v).catch(function(){}).finally(function(){g.value="",o.disabled=!1}))});var w=mn(m,function(){g.click()});o.addEventListener("click",function(v){if(v.stopPropagation(),v.preventDefault(),v.altKey){g.click();return}if(!v.shiftKey){w.toggle();return}var C=t&&typeof t.__WORK_DIR__=="string"?t.__WORK_DIR__:"";f(o,"file",C,function(I){var d=Array.isArray(I)?I:I?[I]:[];d.length&&l(m,d.map(function(B){return a(B)}).join(" "))},!1)})}}function we(o){o=o||document;for(var m=o.querySelectorAll("[data-path-kind]"),g=0;g<m.length;g++){var w=m[g],v=w.getAttribute("data-path-kind");(v==="file"||v==="directory")&&De(w,v)}}t.MyAgentPathPicker={pickPath:i,wrapInputWithBrowse:De,attachChatPicker:vn,uploadChatFiles:T,insertUploadedFiles:ne,startChatFileUpload:W,clipboardFilesFromEvent:V,clipboardHasUsableText:qe,chatAttachments:te,clearChatAttachments:ue,scan:we},document.readyState==="loading"?document.addEventListener("DOMContentLoaded",function(){we(document)}):we(document)})(typeof window<"u"?window:globalThis);const Mn="modulepreload",Fn=function(t){return"/"+t},Ke={},nn=function(e,n,r){let s=Promise.resolve();if(n&&n.length>0){let f=function(l){return Promise.all(l.map(u=>Promise.resolve(u).then(T=>({status:"fulfilled",value:T}),T=>({status:"rejected",reason:T}))))};document.getElementsByTagName("link");const a=document.querySelector("meta[property=csp-nonce]"),h=(a==null?void 0:a.nonce)||(a==null?void 0:a.getAttribute("nonce"));s=f(n.map(l=>{if(l=Fn(l),l in Ke)return;Ke[l]=!0;const u=l.endsWith(".css"),T=u?'[rel="stylesheet"]':"";if(document.querySelector(`link[href="${l}"]${T}`))return;const S=document.createElement("link");if(S.rel=u?"stylesheet":Mn,u||(S.as="script"),S.crossOrigin="",S.href=l,h&&S.setAttribute("nonce",h),document.head.appendChild(S),u)return new Promise((F,E)=>{S.addEventListener("load",F),S.addEventListener("error",()=>E(new Error(`Unable to preload CSS for ${l}`)))})}))}function i(f){const a=new Event("vite:preloadError",{cancelable:!0});if(a.payload=f,window.dispatchEvent(a),!a.defaultPrevented)throw f}return s.then(f=>{for(const a of f||[])a.status==="rejected"&&i(a.reason);return e().catch(i)})};function _e(){return{async:!1,breaks:!1,extensions:null,gfm:!0,hooks:null,pedantic:!1,renderer:null,silent:!1,tokenizer:null,walkTokens:null}}var Y=_e();function tn(t){Y=t}var de={exec:()=>null};function _(t,e=""){let n=typeof t=="string"?t:t.source;const r={replace:(s,i)=>{let f=typeof i=="string"?i:i.source;return f=f.replace(q.caret,"$1"),n=n.replace(s,f),r},getRegex:()=>new RegExp(n,e)};return r}var q={codeRemoveIndent:/^(?: {1,4}| {0,3}\t)/gm,outputLinkReplace:/\\([\[\]])/g,indentCodeCompensation:/^(\s+)(?:```)/,beginningSpace:/^\s+/,endingHash:/#$/,startingSpaceChar:/^ /,endingSpaceChar:/ $/,nonSpaceChar:/[^ ]/,newLineCharGlobal:/\n/g,tabCharGlobal:/\t/g,multipleSpaceGlobal:/\s+/g,blankLine:/^[ \t]*$/,doubleBlankLine:/\n[ \t]*\n[ \t]*$/,blockquoteStart:/^ {0,3}>/,blockquoteSetextReplace:/\n {0,3}((?:=+|-+) *)(?=\n|$)/g,blockquoteSetextReplace2:/^ {0,3}>[ \t]?/gm,listReplaceTabs:/^\t+/,listReplaceNesting:/^ {1,4}(?=( {4})*[^ ])/g,listIsTask:/^\[[ xX]\] /,listReplaceTask:/^\[[ xX]\] +/,anyLine:/\n.*\n/,hrefBrackets:/^<(.*)>$/,tableDelimiter:/[:|]/,tableAlignChars:/^\||\| *$/g,tableRowBlankLine:/\n[ \t]*$/,tableAlignRight:/^ *-+: *$/,tableAlignCenter:/^ *:-+: *$/,tableAlignLeft:/^ *:-+ *$/,startATag:/^<a /i,endATag:/^<\/a>/i,startPreScriptTag:/^<(pre|code|kbd|script)(\s|>)/i,endPreScriptTag:/^<\/(pre|code|kbd|script)(\s|>)/i,startAngleBracket:/^</,endAngleBracket:/>$/,pedanticHrefTitle:/^([^'"]*[^\s])\s+(['"])(.*)\2/,unicodeAlphaNumeric:/[\p{L}\p{N}]/u,escapeTest:/[&<>"']/,escapeReplace:/[&<>"']/g,escapeTestNoEncode:/[<>"']|&(?!(#\d{1,7}|#[Xx][a-fA-F0-9]{1,6}|\w+);)/,escapeReplaceNoEncode:/[<>"']|&(?!(#\d{1,7}|#[Xx][a-fA-F0-9]{1,6}|\w+);)/g,unescapeTest:/&(#(?:\d+)|(?:#x[0-9A-Fa-f]+)|(?:\w+));?/ig,caret:/(^|[^\[])\^/g,percentDecode:/%25/g,findPipe:/\|/g,splitPipe:/ \|/,slashPipe:/\\\|/g,carriageReturn:/\r\n|\r/g,spaceLine:/^ +$/gm,notSpaceStart:/^\S*/,endingNewline:/\n$/,listItemRegex:t=>new RegExp(`^( {0,3}${t})((?:[	 ][^\\n]*)?(?:\\n|$))`),nextBulletRegex:t=>new RegExp(`^ {0,${Math.min(3,t-1)}}(?:[*+-]|\\d{1,9}[.)])((?:[ 	][^\\n]*)?(?:\\n|$))`),hrRegex:t=>new RegExp(`^ {0,${Math.min(3,t-1)}}((?:- *){3,}|(?:_ *){3,}|(?:\\* *){3,})(?:\\n+|$)`),fencesBeginRegex:t=>new RegExp(`^ {0,${Math.min(3,t-1)}}(?:\`\`\`|~~~)`),headingBeginRegex:t=>new RegExp(`^ {0,${Math.min(3,t-1)}}#`),htmlBeginRegex:t=>new RegExp(`^ {0,${Math.min(3,t-1)}}<(?:[a-z].*>|!--)`,"i")},Bn=/^(?:[ \t]*(?:\n|$))+/,Nn=/^((?: {4}| {0,3}\t)[^\n]+(?:\n(?:[ \t]*(?:\n|$))*)?)+/,On=/^ {0,3}(`{3,}(?=[^`\n]*(?:\n|$))|~{3,})([^\n]*)(?:\n|$)(?:|([\s\S]*?)(?:\n|$))(?: {0,3}\1[~`]* *(?=\n|$)|$)/,ce=/^ {0,3}((?:-[\t ]*){3,}|(?:_[ \t]*){3,}|(?:\*[ \t]*){3,})(?:\n+|$)/,qn=/^ {0,3}(#{1,6})(?=\s|$)(.*)(?:\n+|$)/,Re=/(?:[*+-]|\d{1,9}[.)])/,rn=/^(?!bull |blockCode|fences|blockquote|heading|html|table)((?:.|\n(?!\s*?\n|bull |blockCode|fences|blockquote|heading|html|table))+?)\n {0,3}(=+|-+) *(?:\n+|$)/,sn=_(rn).replace(/bull/g,Re).replace(/blockCode/g,/(?: {4}| {0,3}\t)/).replace(/fences/g,/ {0,3}(?:`{3,}|~{3,})/).replace(/blockquote/g,/ {0,3}>/).replace(/heading/g,/ {0,3}#{1,6}/).replace(/html/g,/ {0,3}<[^\n>]+>\n/).replace(/\|table/g,"").getRegex(),Dn=_(rn).replace(/bull/g,Re).replace(/blockCode/g,/(?: {4}| {0,3}\t)/).replace(/fences/g,/ {0,3}(?:`{3,}|~{3,})/).replace(/blockquote/g,/ {0,3}>/).replace(/heading/g,/ {0,3}#{1,6}/).replace(/html/g,/ {0,3}<[^\n>]+>\n/).replace(/table/g,/ {0,3}\|?(?:[:\- ]*\|)+[\:\- ]*\n/).getRegex(),Pe=/^([^\n]+(?:\n(?!hr|heading|lheading|blockquote|fences|list|html|table| +\n)[^\n]+)*)/,Un=/^[^\n]+/,Le=/(?!\s*\])(?:\\.|[^\[\]\\])+/,Hn=_(/^ {0,3}\[(label)\]: *(?:\n[ \t]*)?([^<\s][^\s]*|<.*?>)(?:(?: +(?:\n[ \t]*)?| *\n[ \t]*)(title))? *(?:\n+|$)/).replace("label",Le).replace("title",/(?:"(?:\\"?|[^"\\])*"|'[^'\n]*(?:\n[^'\n]+)*\n?'|\([^()]*\))/).getRegex(),jn=_(/^( {0,3}bull)([ \t][^\n]+?)?(?:\n|$)/).replace(/bull/g,Re).getRegex(),Se="address|article|aside|base|basefont|blockquote|body|caption|center|col|colgroup|dd|details|dialog|dir|div|dl|dt|fieldset|figcaption|figure|footer|form|frame|frameset|h[1-6]|head|header|hr|html|iframe|legend|li|link|main|menu|menuitem|meta|nav|noframes|ol|optgroup|option|p|param|search|section|summary|table|tbody|td|tfoot|th|thead|title|tr|track|ul",Me=/<!--(?:-?>|[\s\S]*?(?:-->|$))/,Gn=_("^ {0,3}(?:<(script|pre|style|textarea)[\\s>][\\s\\S]*?(?:</\\1>[^\\n]*\\n+|$)|comment[^\\n]*(\\n+|$)|<\\?[\\s\\S]*?(?:\\?>\\n*|$)|<![A-Z][\\s\\S]*?(?:>\\n*|$)|<!\\[CDATA\\[[\\s\\S]*?(?:\\]\\]>\\n*|$)|</?(tag)(?: +|\\n|/?>)[\\s\\S]*?(?:(?:\\n[ 	]*)+\\n|$)|<(?!script|pre|style|textarea)([a-z][\\w-]*)(?:attribute)*? */?>(?=[ \\t]*(?:\\n|$))[\\s\\S]*?(?:(?:\\n[ 	]*)+\\n|$)|</(?!script|pre|style|textarea)[a-z][\\w-]*\\s*>(?=[ \\t]*(?:\\n|$))[\\s\\S]*?(?:(?:\\n[ 	]*)+\\n|$))","i").replace("comment",Me).replace("tag",Se).replace("attribute",/ +[a-zA-Z:_][\w.:-]*(?: *= *"[^"\n]*"| *= *'[^'\n]*'| *= *[^\s"'=<>`]+)?/).getRegex(),an=_(Pe).replace("hr",ce).replace("heading"," {0,3}#{1,6}(?:\\s|$)").replace("|lheading","").replace("|table","").replace("blockquote"," {0,3}>").replace("fences"," {0,3}(?:`{3,}(?=[^`\\n]*\\n)|~{3,})[^\\n]*\\n").replace("list"," {0,3}(?:[*+-]|1[.)]) ").replace("html","</?(?:tag)(?: +|\\n|/?>)|<(?:script|pre|style|textarea|!--)").replace("tag",Se).getRegex(),$n=_(/^( {0,3}> ?(paragraph|[^\n]*)(?:\n|$))+/).replace("paragraph",an).getRegex(),Fe={blockquote:$n,code:Nn,def:Hn,fences:On,heading:qn,hr:ce,html:Gn,lheading:sn,list:jn,newline:Bn,paragraph:an,table:de,text:Un},Ye=_("^ *([^\\n ].*)\\n {0,3}((?:\\| *)?:?-+:? *(?:\\| *:?-+:? *)*(?:\\| *)?)(?:\\n((?:(?! *\\n|hr|heading|blockquote|code|fences|list|html).*(?:\\n|$))*)\\n*|$)").replace("hr",ce).replace("heading"," {0,3}#{1,6}(?:\\s|$)").replace("blockquote"," {0,3}>").replace("code","(?: {4}| {0,3}	)[^\\n]").replace("fences"," {0,3}(?:`{3,}(?=[^`\\n]*\\n)|~{3,})[^\\n]*\\n").replace("list"," {0,3}(?:[*+-]|1[.)]) ").replace("html","</?(?:tag)(?: +|\\n|/?>)|<(?:script|pre|style|textarea|!--)").replace("tag",Se).getRegex(),zn={...Fe,lheading:Dn,table:Ye,paragraph:_(Pe).replace("hr",ce).replace("heading"," {0,3}#{1,6}(?:\\s|$)").replace("|lheading","").replace("table",Ye).replace("blockquote"," {0,3}>").replace("fences"," {0,3}(?:`{3,}(?=[^`\\n]*\\n)|~{3,})[^\\n]*\\n").replace("list"," {0,3}(?:[*+-]|1[.)]) ").replace("html","</?(?:tag)(?: +|\\n|/?>)|<(?:script|pre|style|textarea|!--)").replace("tag",Se).getRegex()},Wn={...Fe,html:_(`^ *(?:comment *(?:\\n|\\s*$)|<(tag)[\\s\\S]+?</\\1> *(?:\\n{2,}|\\s*$)|<tag(?:"[^"]*"|'[^']*'|\\s[^'"/>\\s]*)*?/?> *(?:\\n{2,}|\\s*$))`).replace("comment",Me).replace(/tag/g,"(?!(?:a|em|strong|small|s|cite|q|dfn|abbr|data|time|code|var|samp|kbd|sub|sup|i|b|u|mark|ruby|rt|rp|bdi|bdo|span|br|wbr|ins|del|img)\\b)\\w+(?!:|[^\\w\\s@]*@)\\b").getRegex(),def:/^ *\[([^\]]+)\]: *<?([^\s>]+)>?(?: +(["(][^\n]+[")]))? *(?:\n+|$)/,heading:/^(#{1,6})(.*)(?:\n+|$)/,fences:de,lheading:/^(.+?)\n {0,3}(=+|-+) *(?:\n+|$)/,paragraph:_(Pe).replace("hr",ce).replace("heading",` *#{1,6} *[^
]`).replace("lheading",sn).replace("|table","").replace("blockquote"," {0,3}>").replace("|fences","").replace("|list","").replace("|html","").replace("|tag","").getRegex()},Vn=/^\\([!"#$%&'()*+,\-./:;<=>?@\[\]\\^_`{|}~])/,Qn=/^(`+)([^`]|[^`][\s\S]*?[^`])\1(?!`)/,on=/^( {2,}|\\)\n(?!\s*$)/,Kn=/^(`+|[^`])(?:(?= {2,}\n)|[\s\S]*?(?:(?=[\\<!\[`*_]|\b_|$)|[^ ](?= {2,}\n)))/,be=/[\p{P}\p{S}]/u,Be=/[\s\p{P}\p{S}]/u,ln=/[^\s\p{P}\p{S}]/u,Yn=_(/^((?![*_])punctSpace)/,"u").replace(/punctSpace/g,Be).getRegex(),dn=/(?!~)[\p{P}\p{S}]/u,Xn=/(?!~)[\s\p{P}\p{S}]/u,Zn=/(?:[^\s\p{P}\p{S}]|~)/u,Jn=/\[[^[\]]*?\]\((?:\\.|[^\\\(\)]|\((?:\\.|[^\\\(\)])*\))*\)|`[^`]*?`|<[^<>]*?>/g,cn=/^(?:\*+(?:((?!\*)punct)|[^\s*]))|^_+(?:((?!_)punct)|([^\s_]))/,et=_(cn,"u").replace(/punct/g,be).getRegex(),nt=_(cn,"u").replace(/punct/g,dn).getRegex(),un="^[^_*]*?__[^_*]*?\\*[^_*]*?(?=__)|[^*]+(?=[^*])|(?!\\*)punct(\\*+)(?=[\\s]|$)|notPunctSpace(\\*+)(?!\\*)(?=punctSpace|$)|(?!\\*)punctSpace(\\*+)(?=notPunctSpace)|[\\s](\\*+)(?!\\*)(?=punct)|(?!\\*)punct(\\*+)(?!\\*)(?=punct)|notPunctSpace(\\*+)(?=notPunctSpace)",tt=_(un,"gu").replace(/notPunctSpace/g,ln).replace(/punctSpace/g,Be).replace(/punct/g,be).getRegex(),rt=_(un,"gu").replace(/notPunctSpace/g,Zn).replace(/punctSpace/g,Xn).replace(/punct/g,dn).getRegex(),st=_("^[^_*]*?\\*\\*[^_*]*?_[^_*]*?(?=\\*\\*)|[^_]+(?=[^_])|(?!_)punct(_+)(?=[\\s]|$)|notPunctSpace(_+)(?!_)(?=punctSpace|$)|(?!_)punctSpace(_+)(?=notPunctSpace)|[\\s](_+)(?!_)(?=punct)|(?!_)punct(_+)(?!_)(?=punct)","gu").replace(/notPunctSpace/g,ln).replace(/punctSpace/g,Be).replace(/punct/g,be).getRegex(),at=_(/\\(punct)/,"gu").replace(/punct/g,be).getRegex(),it=_(/^<(scheme:[^\s\x00-\x1f<>]*|email)>/).replace("scheme",/[a-zA-Z][a-zA-Z0-9+.-]{1,31}/).replace("email",/[a-zA-Z0-9.!#$%&'*+/=?^_`{|}~-]+(@)[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?(?:\.[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?)+(?![-_])/).getRegex(),ot=_(Me).replace("(?:-->|$)","-->").getRegex(),lt=_("^comment|^</[a-zA-Z][\\w:-]*\\s*>|^<[a-zA-Z][\\w-]*(?:attribute)*?\\s*/?>|^<\\?[\\s\\S]*?\\?>|^<![a-zA-Z]+\\s[\\s\\S]*?>|^<!\\[CDATA\\[[\\s\\S]*?\\]\\]>").replace("comment",ot).replace("attribute",/\s+[a-zA-Z:_][\w.:-]*(?:\s*=\s*"[^"]*"|\s*=\s*'[^']*'|\s*=\s*[^\s"'=<>`]+)?/).getRegex(),me=/(?:\[(?:\\.|[^\[\]\\])*\]|\\.|`[^`]*`|[^\[\]\\`])*?/,dt=_(/^!?\[(label)\]\(\s*(href)(?:(?:[ \t]*(?:\n[ \t]*)?)(title))?\s*\)/).replace("label",me).replace("href",/<(?:\\.|[^\n<>\\])+>|[^ \t\n\x00-\x1f]*/).replace("title",/"(?:\\"?|[^"\\])*"|'(?:\\'?|[^'\\])*'|\((?:\\\)?|[^)\\])*\)/).getRegex(),pn=_(/^!?\[(label)\]\[(ref)\]/).replace("label",me).replace("ref",Le).getRegex(),gn=_(/^!?\[(ref)\](?:\[\])?/).replace("ref",Le).getRegex(),ct=_("reflink|nolink(?!\\()","g").replace("reflink",pn).replace("nolink",gn).getRegex(),Ne={_backpedal:de,anyPunctuation:at,autolink:it,blockSkip:Jn,br:on,code:Qn,del:de,emStrongLDelim:et,emStrongRDelimAst:tt,emStrongRDelimUnd:st,escape:Vn,link:dt,nolink:gn,punctuation:Yn,reflink:pn,reflinkSearch:ct,tag:lt,text:Kn,url:de},ut={...Ne,link:_(/^!?\[(label)\]\((.*?)\)/).replace("label",me).getRegex(),reflink:_(/^!?\[(label)\]\s*\[([^\]]*)\]/).replace("label",me).getRegex()},Te={...Ne,emStrongRDelimAst:rt,emStrongLDelim:nt,url:_(/^((?:ftp|https?):\/\/|www\.)(?:[a-zA-Z0-9\-]+\.?)+[^\s<]*|^email/,"i").replace("email",/[A-Za-z0-9._+-]+(@)[a-zA-Z0-9-_]+(?:\.[a-zA-Z0-9-_]*[a-zA-Z0-9])+(?![-_])/).getRegex(),_backpedal:/(?:[^?!.,:;*_'"~()&]+|\([^)]*\)|&(?![a-zA-Z0-9]+;$)|[?!.,:;*_'"~)]+(?!$))+/,del:/^(~~?)(?=[^\s~])((?:\\.|[^\\])*?(?:\\.|[^\s~\\]))\1(?=[^~]|$)/,text:/^([`~]+|[^`~])(?:(?= {2,}\n)|(?=[a-zA-Z0-9.!#$%&'*+\/=?_`{\|}~-]+@)|[\s\S]*?(?:(?=[\\<!\[`*~_]|\b_|https?:\/\/|ftp:\/\/|www\.|$)|[^ ](?= {2,}\n)|[^a-zA-Z0-9.!#$%&'*+\/=?_`{\|}~-](?=[a-zA-Z0-9.!#$%&'*+\/=?_`{\|}~-]+@)))/},pt={...Te,br:_(on).replace("{2,}","*").getRegex(),text:_(Te.text).replace("\\b_","\\b_| {2,}\\n").replace(/\{2,\}/g,"*").getRegex()},ge={normal:Fe,gfm:zn,pedantic:Wn},oe={normal:Ne,gfm:Te,breaks:pt,pedantic:ut},gt={"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"},Xe=t=>gt[t];function G(t,e){if(e){if(q.escapeTest.test(t))return t.replace(q.escapeReplace,Xe)}else if(q.escapeTestNoEncode.test(t))return t.replace(q.escapeReplaceNoEncode,Xe);return t}function Ze(t){try{t=encodeURI(t).replace(q.percentDecode,"%")}catch{return null}return t}function Je(t,e){var i;const n=t.replace(q.findPipe,(f,a,h)=>{let l=!1,u=a;for(;--u>=0&&h[u]==="\\";)l=!l;return l?"|":" |"}),r=n.split(q.splitPipe);let s=0;if(r[0].trim()||r.shift(),r.length>0&&!((i=r.at(-1))!=null&&i.trim())&&r.pop(),e)if(r.length>e)r.splice(e);else for(;r.length<e;)r.push("");for(;s<r.length;s++)r[s]=r[s].trim().replace(q.slashPipe,"|");return r}function le(t,e,n){const r=t.length;if(r===0)return"";let s=0;for(;s<r&&t.charAt(r-s-1)===e;)s++;return t.slice(0,r-s)}function ft(t,e){if(t.indexOf(e[1])===-1)return-1;let n=0;for(let r=0;r<t.length;r++)if(t[r]==="\\")r++;else if(t[r]===e[0])n++;else if(t[r]===e[1]&&(n--,n<0))return r;return n>0?-2:-1}function en(t,e,n,r,s){const i=e.href,f=e.title||null,a=t[1].replace(s.other.outputLinkReplace,"$1");r.state.inLink=!0;const h={type:t[0].charAt(0)==="!"?"image":"link",raw:n,href:i,title:f,text:a,tokens:r.inlineTokens(a)};return r.state.inLink=!1,h}function mt(t,e,n){const r=t.match(n.other.indentCodeCompensation);if(r===null)return e;const s=r[1];return e.split(`
`).map(i=>{const f=i.match(n.other.beginningSpace);if(f===null)return i;const[a]=f;return a.length>=s.length?i.slice(s.length):i}).join(`
`)}var he=class{constructor(t){L(this,"options");L(this,"rules");L(this,"lexer");this.options=t||Y}space(t){const e=this.rules.block.newline.exec(t);if(e&&e[0].length>0)return{type:"space",raw:e[0]}}code(t){const e=this.rules.block.code.exec(t);if(e){const n=e[0].replace(this.rules.other.codeRemoveIndent,"");return{type:"code",raw:e[0],codeBlockStyle:"indented",text:this.options.pedantic?n:le(n,`
`)}}}fences(t){const e=this.rules.block.fences.exec(t);if(e){const n=e[0],r=mt(n,e[3]||"",this.rules);return{type:"code",raw:n,lang:e[2]?e[2].trim().replace(this.rules.inline.anyPunctuation,"$1"):e[2],text:r}}}heading(t){const e=this.rules.block.heading.exec(t);if(e){let n=e[2].trim();if(this.rules.other.endingHash.test(n)){const r=le(n,"#");(this.options.pedantic||!r||this.rules.other.endingSpaceChar.test(r))&&(n=r.trim())}return{type:"heading",raw:e[0],depth:e[1].length,text:n,tokens:this.lexer.inline(n)}}}hr(t){const e=this.rules.block.hr.exec(t);if(e)return{type:"hr",raw:le(e[0],`
`)}}blockquote(t){const e=this.rules.block.blockquote.exec(t);if(e){let n=le(e[0],`
`).split(`
`),r="",s="";const i=[];for(;n.length>0;){let f=!1;const a=[];let h;for(h=0;h<n.length;h++)if(this.rules.other.blockquoteStart.test(n[h]))a.push(n[h]),f=!0;else if(!f)a.push(n[h]);else break;n=n.slice(h);const l=a.join(`
`),u=l.replace(this.rules.other.blockquoteSetextReplace,`
    $1`).replace(this.rules.other.blockquoteSetextReplace2,"");r=r?`${r}
${l}`:l,s=s?`${s}
${u}`:u;const T=this.lexer.state.top;if(this.lexer.state.top=!0,this.lexer.blockTokens(u,i,!0),this.lexer.state.top=T,n.length===0)break;const S=i.at(-1);if((S==null?void 0:S.type)==="code")break;if((S==null?void 0:S.type)==="blockquote"){const F=S,E=F.raw+`
`+n.join(`
`),N=this.blockquote(E);i[i.length-1]=N,r=r.substring(0,r.length-F.raw.length)+N.raw,s=s.substring(0,s.length-F.text.length)+N.text;break}else if((S==null?void 0:S.type)==="list"){const F=S,E=F.raw+`
`+n.join(`
`),N=this.list(E);i[i.length-1]=N,r=r.substring(0,r.length-S.raw.length)+N.raw,s=s.substring(0,s.length-F.raw.length)+N.raw,n=E.substring(i.at(-1).raw.length).split(`
`);continue}}return{type:"blockquote",raw:r,tokens:i,text:s}}}list(t){let e=this.rules.block.list.exec(t);if(e){let n=e[1].trim();const r=n.length>1,s={type:"list",raw:"",ordered:r,start:r?+n.slice(0,-1):"",loose:!1,items:[]};n=r?`\\d{1,9}\\${n.slice(-1)}`:`\\${n}`,this.options.pedantic&&(n=r?n:"[*+-]");const i=this.rules.other.listItemRegex(n);let f=!1;for(;t;){let h=!1,l="",u="";if(!(e=i.exec(t))||this.rules.block.hr.test(t))break;l=e[0],t=t.substring(l.length);let T=e[2].split(`
`,1)[0].replace(this.rules.other.listReplaceTabs,te=>" ".repeat(3*te.length)),S=t.split(`
`,1)[0],F=!T.trim(),E=0;if(this.options.pedantic?(E=2,u=T.trimStart()):F?E=e[1].length+1:(E=e[2].search(this.rules.other.nonSpaceChar),E=E>4?1:E,u=T.slice(E),E+=e[1].length),F&&this.rules.other.blankLine.test(S)&&(l+=S+`
`,t=t.substring(S.length+1),h=!0),!h){const te=this.rules.other.nextBulletRegex(E),ue=this.rules.other.hrRegex(E),X=this.rules.other.fencesBeginRegex(E),re=this.rules.other.headingBeginRegex(E),ye=this.rules.other.htmlBeginRegex(E);for(;t;){const W=t.split(`
`,1)[0];let V;if(S=W,this.options.pedantic?(S=S.replace(this.rules.other.listReplaceNesting,"  "),V=S):V=S.replace(this.rules.other.tabCharGlobal,"    "),X.test(S)||re.test(S)||ye.test(S)||te.test(S)||ue.test(S))break;if(V.search(this.rules.other.nonSpaceChar)>=E||!S.trim())u+=`
`+V.slice(E);else{if(F||T.replace(this.rules.other.tabCharGlobal,"    ").search(this.rules.other.nonSpaceChar)>=4||X.test(T)||re.test(T)||ue.test(T))break;u+=`
`+S}!F&&!S.trim()&&(F=!0),l+=W+`
`,t=t.substring(W.length+1),T=V.slice(E)}}s.loose||(f?s.loose=!0:this.rules.other.doubleBlankLine.test(l)&&(f=!0));let N=null,ne;this.options.gfm&&(N=this.rules.other.listIsTask.exec(u),N&&(ne=N[0]!=="[ ] ",u=u.replace(this.rules.other.listReplaceTask,""))),s.items.push({type:"list_item",raw:l,task:!!N,checked:ne,loose:!1,text:u,tokens:[]}),s.raw+=l}const a=s.items.at(-1);if(a)a.raw=a.raw.trimEnd(),a.text=a.text.trimEnd();else return;s.raw=s.raw.trimEnd();for(let h=0;h<s.items.length;h++)if(this.lexer.state.top=!1,s.items[h].tokens=this.lexer.blockTokens(s.items[h].text,[]),!s.loose){const l=s.items[h].tokens.filter(T=>T.type==="space"),u=l.length>0&&l.some(T=>this.rules.other.anyLine.test(T.raw));s.loose=u}if(s.loose)for(let h=0;h<s.items.length;h++)s.items[h].loose=!0;return s}}html(t){const e=this.rules.block.html.exec(t);if(e)return{type:"html",block:!0,raw:e[0],pre:e[1]==="pre"||e[1]==="script"||e[1]==="style",text:e[0]}}def(t){const e=this.rules.block.def.exec(t);if(e){const n=e[1].toLowerCase().replace(this.rules.other.multipleSpaceGlobal," "),r=e[2]?e[2].replace(this.rules.other.hrefBrackets,"$1").replace(this.rules.inline.anyPunctuation,"$1"):"",s=e[3]?e[3].substring(1,e[3].length-1).replace(this.rules.inline.anyPunctuation,"$1"):e[3];return{type:"def",tag:n,raw:e[0],href:r,title:s}}}table(t){var f;const e=this.rules.block.table.exec(t);if(!e||!this.rules.other.tableDelimiter.test(e[2]))return;const n=Je(e[1]),r=e[2].replace(this.rules.other.tableAlignChars,"").split("|"),s=(f=e[3])!=null&&f.trim()?e[3].replace(this.rules.other.tableRowBlankLine,"").split(`
`):[],i={type:"table",raw:e[0],header:[],align:[],rows:[]};if(n.length===r.length){for(const a of r)this.rules.other.tableAlignRight.test(a)?i.align.push("right"):this.rules.other.tableAlignCenter.test(a)?i.align.push("center"):this.rules.other.tableAlignLeft.test(a)?i.align.push("left"):i.align.push(null);for(let a=0;a<n.length;a++)i.header.push({text:n[a],tokens:this.lexer.inline(n[a]),header:!0,align:i.align[a]});for(const a of s)i.rows.push(Je(a,i.header.length).map((h,l)=>({text:h,tokens:this.lexer.inline(h),header:!1,align:i.align[l]})));return i}}lheading(t){const e=this.rules.block.lheading.exec(t);if(e)return{type:"heading",raw:e[0],depth:e[2].charAt(0)==="="?1:2,text:e[1],tokens:this.lexer.inline(e[1])}}paragraph(t){const e=this.rules.block.paragraph.exec(t);if(e){const n=e[1].charAt(e[1].length-1)===`
`?e[1].slice(0,-1):e[1];return{type:"paragraph",raw:e[0],text:n,tokens:this.lexer.inline(n)}}}text(t){const e=this.rules.block.text.exec(t);if(e)return{type:"text",raw:e[0],text:e[0],tokens:this.lexer.inline(e[0])}}escape(t){const e=this.rules.inline.escape.exec(t);if(e)return{type:"escape",raw:e[0],text:e[1]}}tag(t){const e=this.rules.inline.tag.exec(t);if(e)return!this.lexer.state.inLink&&this.rules.other.startATag.test(e[0])?this.lexer.state.inLink=!0:this.lexer.state.inLink&&this.rules.other.endATag.test(e[0])&&(this.lexer.state.inLink=!1),!this.lexer.state.inRawBlock&&this.rules.other.startPreScriptTag.test(e[0])?this.lexer.state.inRawBlock=!0:this.lexer.state.inRawBlock&&this.rules.other.endPreScriptTag.test(e[0])&&(this.lexer.state.inRawBlock=!1),{type:"html",raw:e[0],inLink:this.lexer.state.inLink,inRawBlock:this.lexer.state.inRawBlock,block:!1,text:e[0]}}link(t){const e=this.rules.inline.link.exec(t);if(e){const n=e[2].trim();if(!this.options.pedantic&&this.rules.other.startAngleBracket.test(n)){if(!this.rules.other.endAngleBracket.test(n))return;const i=le(n.slice(0,-1),"\\");if((n.length-i.length)%2===0)return}else{const i=ft(e[2],"()");if(i===-2)return;if(i>-1){const a=(e[0].indexOf("!")===0?5:4)+e[1].length+i;e[2]=e[2].substring(0,i),e[0]=e[0].substring(0,a).trim(),e[3]=""}}let r=e[2],s="";if(this.options.pedantic){const i=this.rules.other.pedanticHrefTitle.exec(r);i&&(r=i[1],s=i[3])}else s=e[3]?e[3].slice(1,-1):"";return r=r.trim(),this.rules.other.startAngleBracket.test(r)&&(this.options.pedantic&&!this.rules.other.endAngleBracket.test(n)?r=r.slice(1):r=r.slice(1,-1)),en(e,{href:r&&r.replace(this.rules.inline.anyPunctuation,"$1"),title:s&&s.replace(this.rules.inline.anyPunctuation,"$1")},e[0],this.lexer,this.rules)}}reflink(t,e){let n;if((n=this.rules.inline.reflink.exec(t))||(n=this.rules.inline.nolink.exec(t))){const r=(n[2]||n[1]).replace(this.rules.other.multipleSpaceGlobal," "),s=e[r.toLowerCase()];if(!s){const i=n[0].charAt(0);return{type:"text",raw:i,text:i}}return en(n,s,n[0],this.lexer,this.rules)}}emStrong(t,e,n=""){let r=this.rules.inline.emStrongLDelim.exec(t);if(!r||r[3]&&n.match(this.rules.other.unicodeAlphaNumeric))return;if(!(r[1]||r[2]||"")||!n||this.rules.inline.punctuation.exec(n)){const i=[...r[0]].length-1;let f,a,h=i,l=0;const u=r[0][0]==="*"?this.rules.inline.emStrongRDelimAst:this.rules.inline.emStrongRDelimUnd;for(u.lastIndex=0,e=e.slice(-1*t.length+i);(r=u.exec(e))!=null;){if(f=r[1]||r[2]||r[3]||r[4]||r[5]||r[6],!f)continue;if(a=[...f].length,r[3]||r[4]){h+=a;continue}else if((r[5]||r[6])&&i%3&&!((i+a)%3)){l+=a;continue}if(h-=a,h>0)continue;a=Math.min(a,a+h+l);const T=[...r[0]][0].length,S=t.slice(0,i+r.index+T+a);if(Math.min(i,a)%2){const E=S.slice(1,-1);return{type:"em",raw:S,text:E,tokens:this.lexer.inlineTokens(E)}}const F=S.slice(2,-2);return{type:"strong",raw:S,text:F,tokens:this.lexer.inlineTokens(F)}}}}codespan(t){const e=this.rules.inline.code.exec(t);if(e){let n=e[2].replace(this.rules.other.newLineCharGlobal," ");const r=this.rules.other.nonSpaceChar.test(n),s=this.rules.other.startingSpaceChar.test(n)&&this.rules.other.endingSpaceChar.test(n);return r&&s&&(n=n.substring(1,n.length-1)),{type:"codespan",raw:e[0],text:n}}}br(t){const e=this.rules.inline.br.exec(t);if(e)return{type:"br",raw:e[0]}}del(t){const e=this.rules.inline.del.exec(t);if(e)return{type:"del",raw:e[0],text:e[2],tokens:this.lexer.inlineTokens(e[2])}}autolink(t){const e=this.rules.inline.autolink.exec(t);if(e){let n,r;return e[2]==="@"?(n=e[1],r="mailto:"+n):(n=e[1],r=n),{type:"link",raw:e[0],text:n,href:r,tokens:[{type:"text",raw:n,text:n}]}}}url(t){var n;let e;if(e=this.rules.inline.url.exec(t)){let r,s;if(e[2]==="@")r=e[0],s="mailto:"+r;else{let i;do i=e[0],e[0]=((n=this.rules.inline._backpedal.exec(e[0]))==null?void 0:n[0])??"";while(i!==e[0]);r=e[0],e[1]==="www."?s="http://"+e[0]:s=e[0]}return{type:"link",raw:e[0],text:r,href:s,tokens:[{type:"text",raw:r,text:r}]}}}inlineText(t){const e=this.rules.inline.text.exec(t);if(e){const n=this.lexer.state.inRawBlock;return{type:"text",raw:e[0],text:e[0],escaped:n}}}},$=class Ee{constructor(e){L(this,"tokens");L(this,"options");L(this,"state");L(this,"tokenizer");L(this,"inlineQueue");this.tokens=[],this.tokens.links=Object.create(null),this.options=e||Y,this.options.tokenizer=this.options.tokenizer||new he,this.tokenizer=this.options.tokenizer,this.tokenizer.options=this.options,this.tokenizer.lexer=this,this.inlineQueue=[],this.state={inLink:!1,inRawBlock:!1,top:!0};const n={other:q,block:ge.normal,inline:oe.normal};this.options.pedantic?(n.block=ge.pedantic,n.inline=oe.pedantic):this.options.gfm&&(n.block=ge.gfm,this.options.breaks?n.inline=oe.breaks:n.inline=oe.gfm),this.tokenizer.rules=n}static get rules(){return{block:ge,inline:oe}}static lex(e,n){return new Ee(n).lex(e)}static lexInline(e,n){return new Ee(n).inlineTokens(e)}lex(e){e=e.replace(q.carriageReturn,`
`),this.blockTokens(e,this.tokens);for(let n=0;n<this.inlineQueue.length;n++){const r=this.inlineQueue[n];this.inlineTokens(r.src,r.tokens)}return this.inlineQueue=[],this.tokens}blockTokens(e,n=[],r=!1){var s,i,f;for(this.options.pedantic&&(e=e.replace(q.tabCharGlobal,"    ").replace(q.spaceLine,""));e;){let a;if((i=(s=this.options.extensions)==null?void 0:s.block)!=null&&i.some(l=>(a=l.call({lexer:this},e,n))?(e=e.substring(a.raw.length),n.push(a),!0):!1))continue;if(a=this.tokenizer.space(e)){e=e.substring(a.raw.length);const l=n.at(-1);a.raw.length===1&&l!==void 0?l.raw+=`
`:n.push(a);continue}if(a=this.tokenizer.code(e)){e=e.substring(a.raw.length);const l=n.at(-1);(l==null?void 0:l.type)==="paragraph"||(l==null?void 0:l.type)==="text"?(l.raw+=`
`+a.raw,l.text+=`
`+a.text,this.inlineQueue.at(-1).src=l.text):n.push(a);continue}if(a=this.tokenizer.fences(e)){e=e.substring(a.raw.length),n.push(a);continue}if(a=this.tokenizer.heading(e)){e=e.substring(a.raw.length),n.push(a);continue}if(a=this.tokenizer.hr(e)){e=e.substring(a.raw.length),n.push(a);continue}if(a=this.tokenizer.blockquote(e)){e=e.substring(a.raw.length),n.push(a);continue}if(a=this.tokenizer.list(e)){e=e.substring(a.raw.length),n.push(a);continue}if(a=this.tokenizer.html(e)){e=e.substring(a.raw.length),n.push(a);continue}if(a=this.tokenizer.def(e)){e=e.substring(a.raw.length);const l=n.at(-1);(l==null?void 0:l.type)==="paragraph"||(l==null?void 0:l.type)==="text"?(l.raw+=`
`+a.raw,l.text+=`
`+a.raw,this.inlineQueue.at(-1).src=l.text):this.tokens.links[a.tag]||(this.tokens.links[a.tag]={href:a.href,title:a.title});continue}if(a=this.tokenizer.table(e)){e=e.substring(a.raw.length),n.push(a);continue}if(a=this.tokenizer.lheading(e)){e=e.substring(a.raw.length),n.push(a);continue}let h=e;if((f=this.options.extensions)!=null&&f.startBlock){let l=1/0;const u=e.slice(1);let T;this.options.extensions.startBlock.forEach(S=>{T=S.call({lexer:this},u),typeof T=="number"&&T>=0&&(l=Math.min(l,T))}),l<1/0&&l>=0&&(h=e.substring(0,l+1))}if(this.state.top&&(a=this.tokenizer.paragraph(h))){const l=n.at(-1);r&&(l==null?void 0:l.type)==="paragraph"?(l.raw+=`
`+a.raw,l.text+=`
`+a.text,this.inlineQueue.pop(),this.inlineQueue.at(-1).src=l.text):n.push(a),r=h.length!==e.length,e=e.substring(a.raw.length);continue}if(a=this.tokenizer.text(e)){e=e.substring(a.raw.length);const l=n.at(-1);(l==null?void 0:l.type)==="text"?(l.raw+=`
`+a.raw,l.text+=`
`+a.text,this.inlineQueue.pop(),this.inlineQueue.at(-1).src=l.text):n.push(a);continue}if(e){const l="Infinite loop on byte: "+e.charCodeAt(0);if(this.options.silent){console.error(l);break}else throw new Error(l)}}return this.state.top=!0,n}inline(e,n=[]){return this.inlineQueue.push({src:e,tokens:n}),n}inlineTokens(e,n=[]){var a,h,l;let r=e,s=null;if(this.tokens.links){const u=Object.keys(this.tokens.links);if(u.length>0)for(;(s=this.tokenizer.rules.inline.reflinkSearch.exec(r))!=null;)u.includes(s[0].slice(s[0].lastIndexOf("[")+1,-1))&&(r=r.slice(0,s.index)+"["+"a".repeat(s[0].length-2)+"]"+r.slice(this.tokenizer.rules.inline.reflinkSearch.lastIndex))}for(;(s=this.tokenizer.rules.inline.anyPunctuation.exec(r))!=null;)r=r.slice(0,s.index)+"++"+r.slice(this.tokenizer.rules.inline.anyPunctuation.lastIndex);for(;(s=this.tokenizer.rules.inline.blockSkip.exec(r))!=null;)r=r.slice(0,s.index)+"["+"a".repeat(s[0].length-2)+"]"+r.slice(this.tokenizer.rules.inline.blockSkip.lastIndex);let i=!1,f="";for(;e;){i||(f=""),i=!1;let u;if((h=(a=this.options.extensions)==null?void 0:a.inline)!=null&&h.some(S=>(u=S.call({lexer:this},e,n))?(e=e.substring(u.raw.length),n.push(u),!0):!1))continue;if(u=this.tokenizer.escape(e)){e=e.substring(u.raw.length),n.push(u);continue}if(u=this.tokenizer.tag(e)){e=e.substring(u.raw.length),n.push(u);continue}if(u=this.tokenizer.link(e)){e=e.substring(u.raw.length),n.push(u);continue}if(u=this.tokenizer.reflink(e,this.tokens.links)){e=e.substring(u.raw.length);const S=n.at(-1);u.type==="text"&&(S==null?void 0:S.type)==="text"?(S.raw+=u.raw,S.text+=u.text):n.push(u);continue}if(u=this.tokenizer.emStrong(e,r,f)){e=e.substring(u.raw.length),n.push(u);continue}if(u=this.tokenizer.codespan(e)){e=e.substring(u.raw.length),n.push(u);continue}if(u=this.tokenizer.br(e)){e=e.substring(u.raw.length),n.push(u);continue}if(u=this.tokenizer.del(e)){e=e.substring(u.raw.length),n.push(u);continue}if(u=this.tokenizer.autolink(e)){e=e.substring(u.raw.length),n.push(u);continue}if(!this.state.inLink&&(u=this.tokenizer.url(e))){e=e.substring(u.raw.length),n.push(u);continue}let T=e;if((l=this.options.extensions)!=null&&l.startInline){let S=1/0;const F=e.slice(1);let E;this.options.extensions.startInline.forEach(N=>{E=N.call({lexer:this},F),typeof E=="number"&&E>=0&&(S=Math.min(S,E))}),S<1/0&&S>=0&&(T=e.substring(0,S+1))}if(u=this.tokenizer.inlineText(T)){e=e.substring(u.raw.length),u.raw.slice(-1)!=="_"&&(f=u.raw.slice(-1)),i=!0;const S=n.at(-1);(S==null?void 0:S.type)==="text"?(S.raw+=u.raw,S.text+=u.text):n.push(u);continue}if(e){const S="Infinite loop on byte: "+e.charCodeAt(0);if(this.options.silent){console.error(S);break}else throw new Error(S)}}return n}},ve=class{constructor(t){L(this,"options");L(this,"parser");this.options=t||Y}space(t){return""}code({text:t,lang:e,escaped:n}){var i;const r=(i=(e||"").match(q.notSpaceStart))==null?void 0:i[0],s=t.replace(q.endingNewline,"")+`
`;return r?'<pre><code class="language-'+G(r)+'">'+(n?s:G(s,!0))+`</code></pre>
`:"<pre><code>"+(n?s:G(s,!0))+`</code></pre>
`}blockquote({tokens:t}){return`<blockquote>
${this.parser.parse(t)}</blockquote>
`}html({text:t}){return t}heading({tokens:t,depth:e}){return`<h${e}>${this.parser.parseInline(t)}</h${e}>
`}hr(t){return`<hr>
`}list(t){const e=t.ordered,n=t.start;let r="";for(let f=0;f<t.items.length;f++){const a=t.items[f];r+=this.listitem(a)}const s=e?"ol":"ul",i=e&&n!==1?' start="'+n+'"':"";return"<"+s+i+`>
`+r+"</"+s+`>
`}listitem(t){var n;let e="";if(t.task){const r=this.checkbox({checked:!!t.checked});t.loose?((n=t.tokens[0])==null?void 0:n.type)==="paragraph"?(t.tokens[0].text=r+" "+t.tokens[0].text,t.tokens[0].tokens&&t.tokens[0].tokens.length>0&&t.tokens[0].tokens[0].type==="text"&&(t.tokens[0].tokens[0].text=r+" "+G(t.tokens[0].tokens[0].text),t.tokens[0].tokens[0].escaped=!0)):t.tokens.unshift({type:"text",raw:r+" ",text:r+" ",escaped:!0}):e+=r+" "}return e+=this.parser.parse(t.tokens,!!t.loose),`<li>${e}</li>
`}checkbox({checked:t}){return"<input "+(t?'checked="" ':"")+'disabled="" type="checkbox">'}paragraph({tokens:t}){return`<p>${this.parser.parseInline(t)}</p>
`}table(t){let e="",n="";for(let s=0;s<t.header.length;s++)n+=this.tablecell(t.header[s]);e+=this.tablerow({text:n});let r="";for(let s=0;s<t.rows.length;s++){const i=t.rows[s];n="";for(let f=0;f<i.length;f++)n+=this.tablecell(i[f]);r+=this.tablerow({text:n})}return r&&(r=`<tbody>${r}</tbody>`),`<table>
<thead>
`+e+`</thead>
`+r+`</table>
`}tablerow({text:t}){return`<tr>
${t}</tr>
`}tablecell(t){const e=this.parser.parseInline(t.tokens),n=t.header?"th":"td";return(t.align?`<${n} align="${t.align}">`:`<${n}>`)+e+`</${n}>
`}strong({tokens:t}){return`<strong>${this.parser.parseInline(t)}</strong>`}em({tokens:t}){return`<em>${this.parser.parseInline(t)}</em>`}codespan({text:t}){return`<code>${G(t,!0)}</code>`}br(t){return"<br>"}del({tokens:t}){return`<del>${this.parser.parseInline(t)}</del>`}link({href:t,title:e,tokens:n}){const r=this.parser.parseInline(n),s=Ze(t);if(s===null)return r;t=s;let i='<a href="'+t+'"';return e&&(i+=' title="'+G(e)+'"'),i+=">"+r+"</a>",i}image({href:t,title:e,text:n,tokens:r}){r&&(n=this.parser.parseInline(r,this.parser.textRenderer));const s=Ze(t);if(s===null)return G(n);t=s;let i=`<img src="${t}" alt="${n}"`;return e&&(i+=` title="${G(e)}"`),i+=">",i}text(t){return"tokens"in t&&t.tokens?this.parser.parseInline(t.tokens):"escaped"in t&&t.escaped?t.text:G(t.text)}},Oe=class{strong({text:t}){return t}em({text:t}){return t}codespan({text:t}){return t}del({text:t}){return t}html({text:t}){return t}text({text:t}){return t}link({text:t}){return""+t}image({text:t}){return""+t}br(){return""}},z=class Ae{constructor(e){L(this,"options");L(this,"renderer");L(this,"textRenderer");this.options=e||Y,this.options.renderer=this.options.renderer||new ve,this.renderer=this.options.renderer,this.renderer.options=this.options,this.renderer.parser=this,this.textRenderer=new Oe}static parse(e,n){return new Ae(n).parse(e)}static parseInline(e,n){return new Ae(n).parseInline(e)}parse(e,n=!0){var s,i;let r="";for(let f=0;f<e.length;f++){const a=e[f];if((i=(s=this.options.extensions)==null?void 0:s.renderers)!=null&&i[a.type]){const l=a,u=this.options.extensions.renderers[l.type].call({parser:this},l);if(u!==!1||!["space","hr","heading","code","table","blockquote","list","html","paragraph","text"].includes(l.type)){r+=u||"";continue}}const h=a;switch(h.type){case"space":{r+=this.renderer.space(h);continue}case"hr":{r+=this.renderer.hr(h);continue}case"heading":{r+=this.renderer.heading(h);continue}case"code":{r+=this.renderer.code(h);continue}case"table":{r+=this.renderer.table(h);continue}case"blockquote":{r+=this.renderer.blockquote(h);continue}case"list":{r+=this.renderer.list(h);continue}case"html":{r+=this.renderer.html(h);continue}case"paragraph":{r+=this.renderer.paragraph(h);continue}case"text":{let l=h,u=this.renderer.text(l);for(;f+1<e.length&&e[f+1].type==="text";)l=e[++f],u+=`
`+this.renderer.text(l);n?r+=this.renderer.paragraph({type:"paragraph",raw:u,text:u,tokens:[{type:"text",raw:u,text:u,escaped:!0}]}):r+=u;continue}default:{const l='Token with "'+h.type+'" type was not found.';if(this.options.silent)return console.error(l),"";throw new Error(l)}}}return r}parseInline(e,n=this.renderer){var s,i;let r="";for(let f=0;f<e.length;f++){const a=e[f];if((i=(s=this.options.extensions)==null?void 0:s.renderers)!=null&&i[a.type]){const l=this.options.extensions.renderers[a.type].call({parser:this},a);if(l!==!1||!["escape","html","link","image","strong","em","codespan","br","del","text"].includes(a.type)){r+=l||"";continue}}const h=a;switch(h.type){case"escape":{r+=n.text(h);break}case"html":{r+=n.html(h);break}case"link":{r+=n.link(h);break}case"image":{r+=n.image(h);break}case"strong":{r+=n.strong(h);break}case"em":{r+=n.em(h);break}case"codespan":{r+=n.codespan(h);break}case"br":{r+=n.br(h);break}case"del":{r+=n.del(h);break}case"text":{r+=n.text(h);break}default:{const l='Token with "'+h.type+'" type was not found.';if(this.options.silent)return console.error(l),"";throw new Error(l)}}}return r}},Ce,fe=(Ce=class{constructor(t){L(this,"options");L(this,"block");this.options=t||Y}preprocess(t){return t}postprocess(t){return t}processAllTokens(t){return t}provideLexer(){return this.block?$.lex:$.lexInline}provideParser(){return this.block?z.parse:z.parseInline}},L(Ce,"passThroughHooks",new Set(["preprocess","postprocess","processAllTokens"])),Ce),ht=class{constructor(...t){L(this,"defaults",_e());L(this,"options",this.setOptions);L(this,"parse",this.parseMarkdown(!0));L(this,"parseInline",this.parseMarkdown(!1));L(this,"Parser",z);L(this,"Renderer",ve);L(this,"TextRenderer",Oe);L(this,"Lexer",$);L(this,"Tokenizer",he);L(this,"Hooks",fe);this.use(...t)}walkTokens(t,e){var r,s;let n=[];for(const i of t)switch(n=n.concat(e.call(this,i)),i.type){case"table":{const f=i;for(const a of f.header)n=n.concat(this.walkTokens(a.tokens,e));for(const a of f.rows)for(const h of a)n=n.concat(this.walkTokens(h.tokens,e));break}case"list":{const f=i;n=n.concat(this.walkTokens(f.items,e));break}default:{const f=i;(s=(r=this.defaults.extensions)==null?void 0:r.childTokens)!=null&&s[f.type]?this.defaults.extensions.childTokens[f.type].forEach(a=>{const h=f[a].flat(1/0);n=n.concat(this.walkTokens(h,e))}):f.tokens&&(n=n.concat(this.walkTokens(f.tokens,e)))}}return n}use(...t){const e=this.defaults.extensions||{renderers:{},childTokens:{}};return t.forEach(n=>{const r={...n};if(r.async=this.defaults.async||r.async||!1,n.extensions&&(n.extensions.forEach(s=>{if(!s.name)throw new Error("extension name required");if("renderer"in s){const i=e.renderers[s.name];i?e.renderers[s.name]=function(...f){let a=s.renderer.apply(this,f);return a===!1&&(a=i.apply(this,f)),a}:e.renderers[s.name]=s.renderer}if("tokenizer"in s){if(!s.level||s.level!=="block"&&s.level!=="inline")throw new Error("extension level must be 'block' or 'inline'");const i=e[s.level];i?i.unshift(s.tokenizer):e[s.level]=[s.tokenizer],s.start&&(s.level==="block"?e.startBlock?e.startBlock.push(s.start):e.startBlock=[s.start]:s.level==="inline"&&(e.startInline?e.startInline.push(s.start):e.startInline=[s.start]))}"childTokens"in s&&s.childTokens&&(e.childTokens[s.name]=s.childTokens)}),r.extensions=e),n.renderer){const s=this.defaults.renderer||new ve(this.defaults);for(const i in n.renderer){if(!(i in s))throw new Error(`renderer '${i}' does not exist`);if(["options","parser"].includes(i))continue;const f=i,a=n.renderer[f],h=s[f];s[f]=(...l)=>{let u=a.apply(s,l);return u===!1&&(u=h.apply(s,l)),u||""}}r.renderer=s}if(n.tokenizer){const s=this.defaults.tokenizer||new he(this.defaults);for(const i in n.tokenizer){if(!(i in s))throw new Error(`tokenizer '${i}' does not exist`);if(["options","rules","lexer"].includes(i))continue;const f=i,a=n.tokenizer[f],h=s[f];s[f]=(...l)=>{let u=a.apply(s,l);return u===!1&&(u=h.apply(s,l)),u}}r.tokenizer=s}if(n.hooks){const s=this.defaults.hooks||new fe;for(const i in n.hooks){if(!(i in s))throw new Error(`hook '${i}' does not exist`);if(["options","block"].includes(i))continue;const f=i,a=n.hooks[f],h=s[f];fe.passThroughHooks.has(i)?s[f]=l=>{if(this.defaults.async)return Promise.resolve(a.call(s,l)).then(T=>h.call(s,T));const u=a.call(s,l);return h.call(s,u)}:s[f]=(...l)=>{let u=a.apply(s,l);return u===!1&&(u=h.apply(s,l)),u}}r.hooks=s}if(n.walkTokens){const s=this.defaults.walkTokens,i=n.walkTokens;r.walkTokens=function(f){let a=[];return a.push(i.call(this,f)),s&&(a=a.concat(s.call(this,f))),a}}this.defaults={...this.defaults,...r}}),this}setOptions(t){return this.defaults={...this.defaults,...t},this}lexer(t,e){return $.lex(t,e??this.defaults)}parser(t,e){return z.parse(t,e??this.defaults)}parseMarkdown(t){return(n,r)=>{const s={...r},i={...this.defaults,...s},f=this.onError(!!i.silent,!!i.async);if(this.defaults.async===!0&&s.async===!1)return f(new Error("marked(): The async option was set to true by an extension. Remove async: false from the parse options object to return a Promise."));if(typeof n>"u"||n===null)return f(new Error("marked(): input parameter is undefined or null"));if(typeof n!="string")return f(new Error("marked(): input parameter is of type "+Object.prototype.toString.call(n)+", string expected"));i.hooks&&(i.hooks.options=i,i.hooks.block=t);const a=i.hooks?i.hooks.provideLexer():t?$.lex:$.lexInline,h=i.hooks?i.hooks.provideParser():t?z.parse:z.parseInline;if(i.async)return Promise.resolve(i.hooks?i.hooks.preprocess(n):n).then(l=>a(l,i)).then(l=>i.hooks?i.hooks.processAllTokens(l):l).then(l=>i.walkTokens?Promise.all(this.walkTokens(l,i.walkTokens)).then(()=>l):l).then(l=>h(l,i)).then(l=>i.hooks?i.hooks.postprocess(l):l).catch(f);try{i.hooks&&(n=i.hooks.preprocess(n));let l=a(n,i);i.hooks&&(l=i.hooks.processAllTokens(l)),i.walkTokens&&this.walkTokens(l,i.walkTokens);let u=h(l,i);return i.hooks&&(u=i.hooks.postprocess(u)),u}catch(l){return f(l)}}}onError(t,e){return n=>{if(n.message+=`
Please report this to https://github.com/markedjs/marked.`,t){const r="<p>An error occurred:</p><pre>"+G(n.message+"",!0)+"</pre>";return e?Promise.resolve(r):r}if(e)return Promise.reject(n);throw n}}},K=new ht;function R(t,e){return K.parse(t,e)}R.options=R.setOptions=function(t){return K.setOptions(t),R.defaults=K.defaults,tn(R.defaults),R};R.getDefaults=_e;R.defaults=Y;R.use=function(...t){return K.use(...t),R.defaults=K.defaults,tn(R.defaults),R};R.walkTokens=function(t,e){return K.walkTokens(t,e)};R.parseInline=K.parseInline;R.Parser=z;R.parser=z.parse;R.Renderer=ve;R.TextRenderer=Oe;R.Lexer=$;R.lexer=$.lex;R.Tokenizer=he;R.Hooks=fe;R.parse=R;R.options;R.setOptions;R.use;R.walkTokens;R.parseInline;z.parse;$.lex;const vt=`// Lightweight UI internationalisation. The UI is rendered by several legacy
// modules, so translations are applied at the DOM boundary (including nodes
// added later) instead of coupling every renderer to a framework.
const LS_UI_LANGUAGE = 'myagent-language';
const UI_TRANSLATIONS_EN = {
    '自优化通用智能平台': 'Self-optimizing general intelligence platform',
    '界面设置': 'Interface settings', '新建会话': 'New session', '新建对话': 'New chat', '切换语言': 'Switch language', '切换为英文': 'Switch to English', '切换为中文': 'Switch to Chinese',
    '会话列表': 'Session list', '拖动调整侧栏宽度': 'Drag to resize sidebar', '聊天': 'Chat',
    '选择或新建会话': 'Select or create a session', '展开 Subagent 面板': 'Expand Subagent panel',
    '当前计划': 'Current plan', 'Goal 与当前计划': 'Goal and current plan', '清除计划': 'Clear plan', '清除当前计划': 'Clear current plan',
    '消息': 'Messages', '历史记录': 'History', '折叠计划面板': 'Collapse plan panel',
    '折叠历史面板': 'Collapse history panel', '折叠 Goal 与计划面板': 'Collapse Goal and plan panel', '继续综合子任务': 'Continue synthesizing subtasks',
    '撤销': 'Undo', '说说你想做什么…（Shift/Ctrl+Enter换行）': 'What would you like to do? (Shift/Ctrl+Enter for a new line)', 'Agent运行中，输入后续任务': 'Agent is running; enter a follow-up task', '点击\`立即发送\`插入提示': 'Click \`Send now\` to insert the prompt', '选择文件': 'Choose file',
    '选择 Skill': 'Select Skill', '发送 / 停止': 'Send / Stop', '发送': 'Send', '停止': 'Stop',
    '模型': 'Model', '正在加载模型配置': 'Loading model configuration', '模型配置': 'Model configuration',
    '操作提示': 'Notifications', '已复制': 'Copied', '提示': 'Notice', '取消': 'Cancel', '确定': 'Confirm',
    '暂停': 'Pause', '继续': 'Resume', '增加预算并继续': 'Add budget and resume', '无限制': 'Unlimited', '分钟': 'min',
    '进行中': 'Active', '已暂停': 'Paused', '已完成': 'Completed', '已阻塞': 'Blocked', '已取消': 'Cancelled',
    'Token 预算已耗尽': 'Token budget exhausted', '连续运行失败': 'Consecutive run failures', '手动暂停': 'Paused manually',
    'Judge 解析连续失败': 'Repeated Judge parse failures', 'Judge 调用连续失败': 'Repeated Judge call failures',
    '最近 Judge': 'Latest Judge',
    '续跑': 'continuations', '失败': 'failures',
    '请输入要增加的 Token 预算': 'Enter the additional Token budget', '预算必须是大于 0 的整数。': 'The budget must be a positive integer.',
    'Goal 操作失败': 'Goal action failed',
    '已消耗': 'used', '用时': 'elapsed', '小时': 'h', '分': 'm', '秒': 's', '连续失败': 'consecutive failures',
    '连续失败表示 Goal 执行中连续以失败或错误结束的运行次数（包括初始执行和自动续跑）；任一轮成功完成后会归零。': 'Consecutive failures count Goal runs that ended with failure or error, including the initial run and automatic continuations; a successful run resets the count.',
    '最近错误': 'Latest error',
    'Goal 操作': 'Goal actions', '统计信息': 'Statistics', '开始 Goal': 'Start Goal', '暂停 Goal': 'Pause Goal',
    '编辑 Goal': 'Edit Goal', '删除 Goal': 'Delete Goal', '请输入新的 Goal 内容': 'Enter the new Goal objective',
    '编辑 Goal 内容': 'Edit Goal', '支持多行编辑，保存后会立即同步到当前会话。': 'Edit multiple lines and save changes directly to the current session.',
    'Goal 内容': 'Goal objective', 'Ctrl/Cmd + Enter 保存': 'Ctrl/Cmd + Enter to save', '保存修改': 'Save changes',
    '结果审核': 'Review result', 'Goal 结果审核': 'Goal result review',
    '核对目标与 Judge 结论，再决定是否通过或继续执行。': 'Review the Goal and Judge conclusion, then approve it or continue execution.',
    '当前 Goal 描述': 'Current Goal description', '本次 Judge 结果': 'Judge result',
    '审核通过': 'Approve', '继续 Goal 任务': 'Continue Goal',
    'Goal 描述不能为空。': 'Goal description cannot be empty.',
    '正在保存审核结果…': 'Saving review…', '审核结果保存失败。': 'Failed to save the review.',
    '修改已保存，可继续编辑或选择审核结果。': 'Changes saved. You can keep editing or choose a review outcome.',
    '该结果已审核通过。': 'This result has been approved.',
    '确认删除 Goal': 'Delete Goal?', '删除后当前 Goal 将从此会话中移除。此操作不会删除历史审计事件。': 'The current Goal will be removed from this session. Historical audit events will be retained.',
    '确认删除': 'Delete',
    '关闭': 'Close', '语言': 'Language', '中文': 'Chinese', '英文': 'English',
    '字体大小': 'Font size', '小号': 'Small', '标准': 'Default', '大号': 'Large',
    '界面风格': 'Appearance', '深色': 'Dark', '浅色（默认）': 'Light (default)',
    '会话目录': 'Session list', '会话目录风格': 'Session list style', '会话目录显示模式': 'Session list display mode',
    '紧凑': 'Compact', '详细': 'Detailed', '环境与 API': 'Environment & API', '高级设置': 'Advanced settings',
    '编辑完整 .env，保存后立即写回磁盘（部分项需重启服务）。': 'Edit the complete .env file. Changes are saved to disk immediately (some require a service restart).',
    '如需帮助或反馈，请联系GitHub @sugarfreeecho': 'For help or feedback, contact @sugarfreeecho on GitHub.',
    '运行诊断': 'Diagnostics', '执行状态看板': 'Execution dashboard',
    '更多操作': 'More actions', '更多': 'More', '删除': 'Delete', '置顶': 'Pin', '取消置顶': 'Unpin',
    '归档': 'Archive', '取消归档': 'Unarchive', '删除会话': 'Delete session', '此操作不可恢复': 'This action cannot be undone',
    '未命名': 'Untitled', '重新加载': 'Reload', '加载中...': 'Loading...', '加载中…': 'Loading…',
    '生成中': 'Generating', '任务失败，点击查看': 'Task failed — click to view', '有新回复，点击查看': 'New response — click to view',
    '追问': 'Follow up', '立即发送': 'Send now', '撤回': 'Withdraw', '待发送': 'Pending', '发送中': 'Sending',
    '打断': 'Interrupt', '追加': 'Append', '追问发送模式': 'Follow-up mode', '已追加，等待下一轮': 'Appended, waiting for the next round',
    '已发送': 'Sent', '提交中': 'Submitting', '撤回中': 'Withdrawing', '已接收，等待插入': 'Received, waiting to insert',
    '正在接管当前任务': 'Taking over the current task', '选择 Skill ': 'Select Skill ', '清空': 'Clear',
    '当前没有已注册 Skill': 'No registered skills', '正在加载 Skill': 'Loading skills',
    'MCP 工具': 'MCP Tools', '正在加载 MCP 工具': 'Loading MCP tools', '当前没有已注册的 MCP 工具': 'No registered MCP tools', 'MCP 工具加载失败': 'Failed to load MCP tools',
    'Hooks': 'Hooks', 'Plugins': 'Plugins', '正在加载扩展': 'Loading extensions', '当前没有已注册 Hook': 'No registered hooks', '当前没有已发现插件': 'No plugins found', '扩展加载失败': 'Failed to load extensions', '无': 'None',
    '加载详情中…': 'Loading details…', '知道了': 'Got it', '允许执行': 'Allow', '拒绝': 'Deny',
    '需要确认': 'Confirmation required', '任务已中断': 'Task interrupted', '已请求停止当前任务': 'Stop requested',
    '展开': 'Expand', '收起': 'Collapse', '复制': 'Copy', '导出': 'Export', '导出选项': 'Export options', '导出图片': 'Export image', '导出文本': 'Export text', '改写': 'Rewrite', '重试': 'Retry'
};
Object.assign(UI_TRANSLATIONS_EN, {
    // Todo / goal panel
    '已完成': 'Completed', '进行中': 'In progress', '待处理': 'Pending', '已暂停': 'Paused', '已阻塞': 'Blocked', '已取消': 'Cancelled',
    '无限制': 'Unlimited', '分钟': 'min', '续跑': 'Continue run', '增加预算并继续': 'Increase budget and continue',
    '继续': 'Continue', 'Token 预算已耗尽': 'Token budget exhausted', '连续运行失败': 'Consecutive run failures', '手动暂停': 'Paused manually',
    '请输入要增加的 Token 预算': 'Enter additional Token budget', '预算必须是大于 0 的整数。': 'Budget must be an integer greater than 0.',
    'Goal 操作失败': 'Goal operation failed', '目标操作失败': 'Goal operation failed', '待办事项': 'Todo items',
    '规划': 'Plan', '计划': 'Plan', '清除当前计划': 'Clear current plan',
    // Runtime status lines
    '正在思考中...': 'Thinking...', '正在重连': 'Reconnecting', '任务已中断': 'Task interrupted',
    '展开执行过程高度': 'Expand process height', '收起执行过程高度': 'Collapse process height',
    'Goal 自动续跑开始': 'Goal auto-continuation started', '任务已恢复，流程重启': 'Task restored; restarting workflow',
    '已请求停止当前任务': 'Stop requested for the current task', '解析事件失败': 'Failed to parse event',
    '验证': 'Verification', '正在根据对话更新要点': 'Updating key points from the conversation',
    '上下文窗口已满，开始压缩': 'Context window full; starting compression', '上下文压缩已完成': 'Context compression completed',
    '上下文摘要': 'Context summary', '要点': 'Key points', '历史/旧版事件': 'History/legacy event',
    '立即发送': 'Send now', '追问发送模式': 'Follow-up send mode', '打断': 'Interrupt', '追加': 'Append', '撤回': 'Withdraw',
    '撤回中': 'Withdrawing', '提交中': 'Submitting', '已追加，等待下一轮': 'Appended, waiting for the next round',
    '已接收，等待插入': 'Received, waiting to insert', '正在接管当前任务': 'Taking over the current task', '发送中': 'Sending', '已发送': 'Sent', '待发送': 'Pending send',
    '已选择 Skill：': 'Activated Skill: ', '激活 Skill：': 'Activated Skill: ', '追问接管已保留，等待发送通道释放。': 'Follow-up takeover retained; waiting for the send channel to become available.',
    '请求失败': 'Request failed', '撤销失败，请重试。': 'Undo failed. Please try again.'
});
Object.assign(UI_TRANSLATIONS_EN, {
    '新会话': 'New session', '停止 <span class="loader">': 'Stop <span class="loader">', '加载会话': 'Load session',
    '取消置顶': 'Unpin', '取消归档': 'Unarchive', '删除会话': 'Delete session', '此操作不可恢复': 'This action cannot be undone',
    '无法同步服务器。': 'Could not sync with the server.', '当前没有选中的会话。': 'No session is currently selected.',
    '消息定位索引无效，可能需要刷新当前会话。': 'The message index is invalid. Refresh the current session.',
    '服务端拒绝清空整个会话。': 'The server rejected clearing the entire session.',
    '服务端裁剪历史失败，可能是历史索引已变化或会话文件暂时不一致。': 'The server could not trim history; the index may have changed or the session file may be inconsistent.',
    '原因：': 'Reason: ', '无法改写': 'Cannot rewrite', '改写内容不能为空。': 'Rewrite content cannot be empty.',
    '生成中不可操作': 'Unavailable while generating', '当前会话仍在生成。请等待完成或停止后再修改历史。': 'This session is still generating. Wait for completion or stop it before editing history.',
    '无法删除该条': 'Cannot delete this message', '消息索引异常，已阻止清空整个会话。请刷新后再试。': 'The message index is invalid; clearing the session was blocked. Refresh and try again.',
    '删除消息': 'Delete message', '将同步到服务器': 'Will sync to server', '确定删除本条及之后的所有对话内容吗？': 'Delete this message and all following conversation content?',
    '同步失败': 'Sync failed', '删除未生效。': 'The deletion was not applied.', '无法改写该条': 'Cannot rewrite this message',
    '该消息尚未与服务器索引对齐，请刷新当前会话后再试。': 'This message is not aligned with the server index. Refresh the session and try again.',
    '无法分支': 'Cannot fork', '该回答尚未与服务器同步，请刷新页面后重试。': 'This response is not synced with the server. Refresh and try again.',
    '创建分支会话': 'Create fork session', '原会话不会被修改': 'The original session will not be modified',
    '问题': 'Question', '已完成': 'Completed', '进行中': 'In progress', '未开始': 'Not started',
    '折叠文件夹': 'Collapse folder', '展开文件夹': 'Expand folder', '下载保存 Mermaid 流程图为图片': 'Download Mermaid diagram as image',
    '调用工具': 'Tool calls', '次': 'times', '轮': 'rounds', '分': 'm', '秒': 's',
    '工具调用生成中...': 'Preparing tool call...', '执行中...': 'Running...', '执行结果': 'Result',
    '平均': 'Average', '累计': 'Total', '占比': 'Share', '暂无数据': 'No data', '暂无执行统计': 'No execution statistics',
    '暂无子事件': 'No sub-events', '无用户消息': 'No user message', '成功': 'Success', '会话数': 'Sessions',
    'LLM 请求': 'LLM requests', 'LLM API 流累计': 'Cumulative LLM API stream', 'Run 总耗时（墙钟）': 'Run wall-clock total', '平均首 token': 'Average first token',
    '累计输入 token': 'Cumulative input tokens', '累计输出 token': 'Cumulative output tokens', '工具调用总数': 'Total tool calls',
    '累计网络流量': 'Cumulative network traffic', 'LLM API 流耗时': 'LLM API stream duration', '首 token': 'First token',
    '输入 token': 'Input tokens', '输出 token': 'Output tokens', '上下文长度': 'Context length', '工具调用': 'Tool calls',
    '网络等待': 'Network wait', '网络流量': 'Network traffic', '时间': 'Time', '执行轮次': 'Execution round',
    '模型': 'Model', '会话': 'Session', '运行 ID': 'Run ID', 'Session ID': 'Session ID', '当前会话筛选': 'Current session filter',
    '所有会话': 'All sessions', '累计总值': 'Cumulative totals', '平均首 token': 'Average first token'
});
Object.assign(UI_TRANSLATIONS_EN, {
    // Session navigation and lifecycle
    '置顶目录': 'Pinned', '归档目录': 'Archived', '刷新归档目录': 'Refresh archived sessions',
    '加载归档目录': 'Load archived sessions', '加载更多': 'Load more', '今天': 'Today', '昨天': 'Yesterday', '近7天': 'Last 7 days',
    '近14天': 'Last 14 days', '加载会话': 'Load session', '加载会话列表失败': 'Failed to load sessions',
    '加载历史消息失败': 'Failed to load message history', '创建新会话失败': 'Failed to create session',
    '未选择会话': 'No session selected', '暂无提问': 'No questions yet', '打开工作目录': 'Open workspace',
    '打开会话目录': 'Open session folder', '确定删除会话': 'Delete this session',

    // Subagents
    '后台运行': 'Running in background', '运行中': 'Running', '完成': 'Completed', '失败': 'Failed',
    '已中断': 'Interrupted', '缺少 final 结果': 'Missing final result', '查看输出': 'View output',
    '放大显示': 'Expand view', '在浮窗内全屏显示': 'Show full-size in overlay', '无 Subagent': 'No subagents',
    '(暂无事件)': '(No events yet)', '(暂无 final 结果)': '(No final result)', '(无输出)': '(No output)',
    '删除 Subagent': 'Delete subagent', '删除失败': 'Deletion failed',
    '将删除该 subagent 的会话记录、过程卡片及其嵌套子任务。该操作不可撤销。': 'This will delete the subagent session, process card, and nested subtasks. This cannot be undone.',
    '无法删除该 Subagent，请稍后重试。': 'Could not delete this subagent. Please try again later.',
    '继续任务': 'Continue task', '继续中…': 'Continuing…', '等待主任务完成': 'Waiting for main task',

    // Model and skill controls
    '默认方案': 'Default profile', '未命名方案': 'Unnamed profile', '未加载模型配置': 'Model configuration not loaded',
    '没有可用模型配置': 'No model configurations available', '没有启用的模型配置': 'No enabled model profiles',
    '暂无已保存模型配置，可到模型配置页中保存': 'No saved model configurations. Save one on the model configuration page.',
    '请稍候': 'Please wait', '模型配置加载失败': 'Failed to load model configuration', '切换失败': 'Switch failed',
    'Skill 加载失败': 'Failed to load skills', '启用': 'Enable', '禁用': 'Disable',
    '模型配置启停失败': 'Failed to change model profile status', 'Skill 启停失败': 'Failed to change Skill status',

    // Messages, history and composer
    '开始一段新的对话': 'Start a new conversation',
    '在左侧侧栏新建或选择会话。Enter 发送，Ctrl+Enter / Shift+Enter 换行。': 'Create or select a session in the sidebar. Press Enter to send; Ctrl+Enter or Shift+Enter for a new line.',
    '分支': 'Fork', '创建分支': 'Create fork', '创建失败': 'Creation failed',
    '将在当前回答之后创建独立分支会话。分支点之前的内容与原会话相同，可在分支中继续提问且不影响原会话。': 'A separate fork session will be created after this response. Earlier messages remain the same, and continuing in the fork will not affect the original session.',
    '创建分支未生效。': 'The fork was not created.', '工具': 'Tool', '执行过程': 'Execution process',
    '本段过程已折叠': 'This process section is collapsed', '信息': 'Info', '错误': 'Error', '回复': 'Response',
    '思考': 'Reasoning', '压缩': 'Compression', '裁剪': 'Trim', '要点': 'Key points', '状态': 'Status',
    '工具调用生成中...': 'Preparing tool call...', '执行中...': 'Running...', '执行结果': 'Result',
    '正在思考中...': 'Thinking...', '正在重连': 'Reconnecting', '验证': 'Verification',
    'Mermaid 无法解析此图': 'Mermaid could not render this diagram',
    'Mermaid 流程图放大预览': 'Expanded Mermaid diagram preview', '关闭放大预览': 'Close expanded preview',
    '下载保存 Mermaid 流程图为图片': 'Download Mermaid diagram as an image', '下载图片': 'Download image',
    '放大显示 Mermaid 流程图': 'Expand Mermaid diagram', '点击查看图片': 'Click to view image',
    '移除文件路径': 'Remove file path', '响应异常': 'Invalid response', '已调用系统打开文件': 'Asked the system to open the file',
    '无法打开文件': 'Could not open file', '无法连接服务': 'Could not connect to the service',
    '取消改写': 'Cancel rewrite', '已截断历史，可撤销恢复': 'History truncated; you can undo to restore it',
    '已填入输入框，可撤销': 'Inserted into the input; you can undo',
    '改写待生效：发送消息后才会截断历史并发送；点此取消改写。': 'Rewrite pending: history will be truncated only when the message is sent. Click here to cancel.',
    '无法定位该条': 'Could not locate this message',

    // File picker
    '请求失败': 'Request failed', '无法打开选择对话框': 'Could not open the file picker', '上传失败': 'Upload failed',
    '正在取消上传…': 'Cancelling upload…', '上传已取消。': 'Upload cancelled.',
    '上传失败：网络连接异常。': 'Upload failed: network connection error.', '上传超时，请重试。': 'Upload timed out. Please try again.',
    '已有文件正在上传，请等待完成或先取消。': 'A file upload is already in progress. Wait for it to finish or cancel it first.',
    '本次上传总大小超过 200 MB 限制。': 'The total upload exceeds the 200 MB limit.',
    '读取工作区文件失败': 'Failed to read workspace files', '搜索工作区文件': 'Search workspace files',
    '未选择文件': 'No files selected', '选择工作目录外文件': 'Choose a file outside the workspace',
    '加载中': 'Loading', '没有匹配文件': 'No matching files', '折叠文件夹': 'Collapse folder',
    '展开文件夹': 'Expand folder', '读取失败': 'Failed to read', '浏览路径': 'Browse path', '工作区文件': 'Workspace files',

    // Confirmations, recovery and errors
    '粘贴文件失败': 'Failed to paste file', '文件上传失败': 'File upload failed', '无法保存剪贴板中的文件或图片。': 'Could not save the file or image from the clipboard.',
    '无法上传所选文件或剪贴板中的图片。': 'Could not upload the selected file or clipboard image.',
    '截断失败': 'Truncation failed', '无法同步服务器，改写未生效。': 'Could not sync with the server; the rewrite was not applied.',
    '撤销失败，请重试。': 'Undo failed. Please try again.', '检测到上次运行未完成，正在自动恢复任务…': 'The previous run was incomplete. Restoring it automatically…',
    '恢复实时流失败': 'Failed to restore the live stream', '续接失败': 'Failed to continue',
    '追问插入失败': 'Failed to insert follow-up', '追问已被接收，无法撤回': 'The follow-up was accepted and can no longer be withdrawn'
});
Object.assign(UI_TRANSLATIONS_EN, {
    'Agent Team（实验功能）': 'Agent Team (experimental)',
    'Agent Team 功能开关': 'Agent Team feature switch',
    '关闭（默认）': 'Off (default)', '启用': 'Enable',
    '正在读取状态…': 'Reading status…', '管理当前会话团队': 'Manage current session team',
    '当前会话团队控制面板': 'Current session team control panel',
    '刷新': 'Refresh', '请求关停': 'Request shutdown', '完成关停': 'Complete shutdown',
    '当前会话还没有团队。': 'This session does not have a team yet.',
    '团队名称（可选）': 'Team name (optional)', '创建团队': 'Create team',
    '成员': 'Members', '共享任务': 'Shared tasks', '权限请求': 'Permission requests',
    '持久成员由 Agent 调用 team(action="spawn_member") 创建和派工。': 'The agent creates and dispatches persistent members with team(action="spawn_member").',
    '新任务标题': 'New task title', '添加任务': 'Add task',
    '允许一次': 'Allow once', '暂无成员': 'No members', '暂无任务': 'No tasks',
    '暂无权限请求': 'No permission requests', '请先选择或新建一个会话。': 'Select or create a session first.',
    '当前页面正在查看较早历史，且未能恢复最新历史尾部。请重试。': 'This page is viewing older history and could not restore the latest tail. Please try again.'
});
Object.assign(UI_TRANSLATIONS_EN, {
    // Human-in-the-loop cards and banners
    '待处理的人机交互': 'Pending human interactions', 'Agent 正在等待你处理': 'Agent is waiting for your input',
    '待处理事项': 'Pending items', '全局待办': 'Global pending', '当前会话': 'Current session', '立即处理': 'Handle now',
    '安全审批': 'Safety approval', '需要你的回答': 'Your response is required', '确认下一步': 'Confirm next step',
    '等待中': 'Waiting', '待回答': 'Waiting for answer', '待审批': 'Waiting for approval', '已处理': 'Processed', '已过期': 'Expired', '可多选': 'Select multiple', '单选': 'Select one',
    '查看预览': 'View preview', '其他': 'Other', '其他答案': 'Other answer', '输入你的答案…': 'Enter your answer…', '取消提问': 'Cancel question', '不回答': 'Skip answering',
    '上一步': 'Back', '下一步': 'Next', '返回修改': 'Edit answers', '确认回答': 'Review answers', '提交答案': 'Submit answers', '正在提交…': 'Submitting…', '正在取消…': 'Cancelling…', '正在处理…': 'Processing…',
    '请选择一个选项。': 'Select an option.', '请至少选择一个选项。': 'Select at least one option.', '请输入其他答案。': 'Enter the other answer.', '请完成当前问题后再提交。': 'Complete the current question before submitting.',
    '发送新消息并取消当前问题？': 'Send a new message and cancel the current question?', '取消问题并发送': 'Cancel question and send', '返回回答问题': 'Return to question',
    'Agent 主动提问': 'Agent questions', 'Agent 主动提问功能开关': 'Agent question feature toggle',
    '已启用；Agent 可在确实需要选择时暂停并向你提问。': 'Enabled; the Agent may pause and ask when your choice is required.',
    '已关闭；Agent 不会创建结构化提问卡片。': 'Disabled; the Agent will not create structured question cards.',
    '取消失败：': 'Cancellation failed: ', '提交失败：': 'Submission failed: ', '处理失败：': 'Failed to process: ',
    '是否允许 Agent 执行此操作？': 'Allow Agent to perform this action?', '工具': 'Tool', '始终允许': 'Always allow',
    '允许一次': 'Allow once', '本任务内允许相同请求': 'Allow identical requests in this task', '始终允许此类操作': 'Always allow this kind of operation', '拒绝执行': 'Deny execution', '已取消': 'Cancelled', '该请求已取消。': 'This request was cancelled.', '该请求已过期。': 'This request expired.',
    '你已拒绝本次操作。': 'You denied this action.', '你已允许同类操作。': 'You allowed similar actions.', '你已允许本次操作。': 'You allowed this action.', '已回答': 'Answered',
    // Session grouping and subagent continuation
    '刷新归档目录': 'Refresh archived sessions', '加载归档目录': 'Load archived sessions', '加载更多': 'Load more', '加载中...': 'Loading...',
    '个子任务已完成，点击继续让主 Agent 综合子任务结果（不会自动续跑）。': ' subtasks completed. Click continue to let the main Agent synthesize their results (no automatic continuation).',
    '个子任务结果尚未纳入上方回答，点击补充综合。': ' subtask results are not included in the answer above. Click to add a synthesis.',
    // Agent Team and subagent controls
    '任务': 'Tasks', '会话': 'Sessions', '成员 · ': ' members · ', '允许一次': 'Allow once', '拒绝': 'Deny',
    '暂无任务': 'No tasks', '暂无成员': 'No members', '暂无权限请求': 'No permission requests',
    '请让 Agent 使用 team spawn_member': 'Ask the Agent to use team spawn_member', '收起 Subagent 面板': 'Collapse Subagent panel',
    '展开查看执行过程': 'Expand to view execution process', '退出全屏': 'Exit full screen', '停止': 'Stop',
    // Dashboard-specific labels and errors
    '请求至首 token': 'Request to first token', 'Transport 总耗时': 'Total transport duration', '请求流量': 'Request traffic',
    '响应流量（估算）': 'Estimated response traffic', '加载失败': 'Load failed',
    // File picker dynamic errors
    '无法打开选择对话框': 'Could not open the file picker', '上传失败：网络连接异常。': 'Upload failed: network connection error.',
    '上传超时，请重试。': 'Upload timed out. Please try again.', '上传已取消。': 'Upload cancelled.',
    '已有文件正在上传，请等待完成或先取消。': 'A file upload is already in progress. Wait for it to finish or cancel it first.',
    '读取工作区文件失败': 'Failed to read workspace files', '没有匹配文件': 'No matching files', '浏览路径': 'Browse path',
    '工作区文件': 'Workspace files', '选择工作目录外文件': 'Choose a file outside the workspace', '未选择文件': 'No files selected',
    '正在取消上传…': 'Cancelling upload…', '读取失败': 'Failed to read', '取消失败': 'Cancellation failed',
    '文件上传失败': 'File upload failed', '无法上传所选文件或剪贴板中的图片。': 'Could not upload the selected file or clipboard image.',
    '当前没有选中的会话。': 'No session is currently selected.', '未选择会话': 'No session selected', '暂无提问': 'No questions yet',
    '消息索引异常，已阻止从错误位置清空会话。请刷新后再试。': 'The message index is invalid; clearing from the wrong position was blocked. Refresh and try again.',
    '消息索引异常，已阻止清空整个会话。请刷新后再试。': 'The message index is invalid; clearing the session was blocked. Refresh and try again.',
    '当前会话仍在生成。请等待完成或停止后再修改历史。': 'This session is still generating. Wait for completion or stop it before editing history.',
    '本段过程已折叠': 'This process section is collapsed', '未找到可保存的 Final 卡片': 'No Final card is available to save',
    'Final 卡片图片生成失败': 'Failed to generate the Final card image', 'Final 卡片图片保存失败': 'Failed to save the Final card image',
    '当前浏览器不支持复制文本': 'This browser does not support copying text', '无法完成复制或保存': 'Could not copy or save', '无法完成导出': 'Could not export',
    '至少选择复制文本或保存图片中的一项。': 'Select at least one of copy text or save image.', '图片已保存': 'Image saved', 'Markdown 已导出': 'Markdown exported',
    '复制选项': 'Copy options', '打开会话目录': 'Open session folder', '打开工作目录': 'Open workspace',
    '知道了': 'Got it', '已请求打开': 'Open requested', '无法定位该条': 'Could not locate this message'
});
Object.assign(UI_TRANSLATIONS_EN, {
    '文件上传失败': 'File upload failed', '无法上传所选文件或剪贴板中的图片。': 'Could not upload the selected file or clipboard image.',
    '正在保存…': 'Saving…', '正在读取状态…': 'Reading status…', '读取失败：': 'Failed to read: ',
    '已关闭；现有 task/subagent 行为不受影响。': 'Disabled; existing task/subagent behavior is unchanged.',
    '已启用；Agent Team 入口和团队运行时可用。': 'Enabled; the Agent Team entry point and runtime are available.',
    '没有可用模型配置': 'No model configurations available', '没有启用的模型配置': 'No enabled model profiles',
    '模型配置加载失败': 'Failed to load model configuration', '正在加载模型配置': 'Loading model configuration',
    '模型配置切换失败: ': 'Failed to switch model configuration: ', '模型配置启停失败: ': 'Failed to change model profile status: ',
    '模型配置加载失败: ': 'Failed to load model configuration: ', '上下文窗口：': 'Context window: ', '接口类型：': 'Interface type: ',
    '最大输出：': 'Maximum output: ', '能力：': 'Capabilities: ', '状态：': 'Status: ', '可用': 'Available', '未就绪': 'Not ready', '未设置': 'Not set',
    '加载subagent历史失败:': 'Failed to load subagent history:', '加载详情中…': 'Loading details…', '加载失败: ': 'Load failed: ',
    '暂无事件': 'No events yet', '暂无 final 结果': 'No final result', '无 Subagent': 'No subagents',
    '任务失败，点击查看': 'Task failed — click to view', '有新回复，点击查看': 'New response — click to view',
    'Agent 请求执行操作': 'Agent requests permission to perform an action', '请选择操作': 'Choose an action', '复制文本': 'Copy text', '保存图片': 'Save image', '执行': 'Run',
    '原因：': 'Reason: ', '找不到可保存的 Final 卡片': 'No Final card is available to save', '操作失败': 'Operation failed', '确认': 'Confirm',
    '加载会话状态快照失败，回退至旧接口': 'Failed to load the session state snapshot; falling back to the legacy endpoint', '归档失败': 'Archive failed', '置顶失败': 'Pin failed', '重命名失败': 'Rename failed',
    '加载更早记录': 'Load earlier records', '加载更早消息': 'Load earlier messages', '保存失败：': 'Save failed: '
});
Object.assign(UI_TRANSLATIONS_EN, {
    // Agent runtime status events (including compression and recovery)
    '本机网络已恢复，正在继续任务…': 'The local network is back; continuing the task…',
    '本机仍处于离线状态，Agent 正在沉睡并等待网络恢复…': 'The local machine is still offline; the Agent is sleeping until the network recovers…',
    '检测到同会话仍有未结束的上下文压缩，等待其完成后再继续 ReAct。': 'An unfinished context compression was detected for this session; waiting for it to finish before continuing ReAct.',
    '当前上下文无需进一步裁剪或摘要': 'The current context needs no further trimming or summarization',
    '对话已摘要，关键信息已写入 key_context': 'Conversation summarized; key information written to key_context',
    '子任务结果已返回，正在纳入当前回答': 'Subtask results returned; incorporating them into the current response',
    '安全确认': 'Safety confirmation', '用户已允许': 'User allowed', '用户已拒绝执行（已跳过）。': 'User denied execution (skipped).',
    '任务已由用户中断。': 'Task interrupted by the user.', '任务已由用户中断（父会话）。': 'Task interrupted by the user (parent session).',
    '任务因 Agent 停止、重启或运行中断而暂停，可在服务恢复后继续。': 'The task was paused because the Agent stopped, restarted, or was interrupted; it can continue after the service recovers.',
    '执行已由 Hook 暂停：': 'Execution paused by a Hook: ', '执行已由 Stop Hook 暂停：': 'Execution paused by a Stop Hook: ',
    '模型未输出最终内容': 'The model did not produce a final response', '检测到连续重复行为': 'Consecutive repeated behavior detected',
    '已插入强制提醒': 'A mandatory reminder was inserted', '已终止任务': 'Task terminated',
    '自动应急截断': 'Automatic emergency truncation', '待办更新失败：': 'Todo update failed: ', 'subagent 执行异常：': 'Subagent execution error: ',
    'MCP 调用异常：': 'MCP call error: ', '未知工具：': 'Unknown tool: ', '工具执行异常：': 'Tool execution error: ',
    '编辑说明不能为空': 'Edit instructions cannot be empty', '缺少 edit_instruction': 'Missing edit_instruction', '无效 mode': 'Invalid mode',
    '请稍候': 'Please wait', '本轮执行步骤已达到最大迭代次数。Goal 模式会自动开始下一轮；普通会话可以手动继续任务。': 'This run reached the maximum number of iterations. Goal mode will start the next round automatically; regular sessions can be continued manually.',
    '将执行的大致命令如下，请确认是否允许：': 'The approximate command to run is below. Confirm whether to allow it:', 'run_shell（放宽工作区）': 'run_shell (relaxed workspace)',
    '确认网络下载': 'Confirm network download', '将把远程文件写入工作区指定路径。': 'The remote file will be written to the specified workspace path.', 'URL：': 'URL:', '保存为（工作区内）：': 'Save as (inside workspace):', '（未指定）': '(not specified)',
    '无法继续任务': 'Unable to continue the task', '无法发送': 'Unable to send', '截断失败': 'Truncation failed',
    'Hook 请求确认': 'Hook requests confirmation', '网络连接失败': 'Network connection failed', 'API 认证失败': 'API authentication failed',
    '访问被拒绝': 'Access denied', '模型或接口不可用': 'Model or interface unavailable', '请求频率超限': 'Request rate limit exceeded',
    '请求参数错误': 'Invalid request parameters', '内容被拦截': 'Content blocked', '服务器错误': 'Server error', 'LLM 调用异常': 'LLM call failed',
    '无法连接到 API 服务器。': 'Could not connect to the API server.', 'API Key 无效或已过期。': 'The API key is invalid or expired.',
    '当前地区不支持或 API Key 被风控。': 'The current region is unsupported or the API key was restricted.',
    '请求的模型不支持当前能力（如图像输入）。': 'The requested model does not support this capability (such as image input).',
    '已重试 3 次，均因速率限制失败。': 'All three retries failed due to rate limiting.', '请求体格式不符合 API 要求。': 'The request body format does not meet the API requirements.',
    '输入内容触发了安全审核。': 'The input triggered a safety review.', '发生未知错误。': 'An unknown error occurred.',
    '请检查网络连接、当前 model profile 的 API Base URL、VPN/代理设置。': 'Check the network connection, the current model profile API base URL, and VPN/proxy settings.',
    '请检查当前 model profile 中的 API Key 是否正确。': 'Check that the API key in the current model profile is correct.',
    '请新建 API Key，或检查服务地区限制。': 'Create a new API key or check regional service restrictions.',
    '请检查模型名称是否正确，或换一个支持该能力的模型。': 'Check the model name or switch to a model that supports this capability.',
    '请稍等片刻再试，或降低请求频率；Token Plan 用户可考虑升级套餐。': 'Wait a moment and try again, or reduce the request rate; Token Plan users may consider upgrading.',
    '请检查消息格式、必填字段、模型名称是否正确。': 'Check the message format, required fields, and model name.',
    '请避免敏感或违规内容，修改后重试。': 'Avoid sensitive or disallowed content, then try again.',
    '请稍后重试；若持续出现请联系 API 服务商。': 'Try again later; contact the API provider if the issue persists.',
    '请先检查模型配置，或到 GitHub 提交 issue 反馈。': 'Check the model configuration first, or report the issue on GitHub.',
    '（无来源文本，未生成 summary）': '(No source text; no summary generated)', '本机网络已断开': 'The local network is disconnected',
    '进入沉睡状态并等待网络恢复': 'entering sleep until the network recovers', '模型输出在完整工具调用后达到长度上限；已保留并执行完整调用，未完成片段已丢弃。': 'The model output reached the length limit after a complete tool call; the complete call was retained and executed, and the unfinished fragment was discarded.',
    '工具执行异常: ': 'Tool execution error: ', '已清理临时文件': 'Cleaned up temporary files', '已移入 .trash': 'moved to .trash',
    '后台 Subagent 已完成': 'Background subagent completed', 'LLM 调用失败': 'LLM call failed', '模型输出达到输出 token 上限': 'Model output reached the output-token limit',
    '达到最大迭代次数': 'Reached the maximum iteration count', 'ReAct 已达到轮次上限': 'ReAct reached the iteration limit'
});
Object.assign(UI_TRANSLATIONS_EN, {
    // Permission mode selector & security settings
    '权限': 'Permissions',
    '请求批准': 'Ask for approval',
    '替我审批': 'Approve for me',
    '完全访问权限': 'Full access',
    '不受限制': 'Unrestricted',
    '应用层受限': 'App-restricted',
    '应用层受限，越界和高风险操作由你审批': 'App-restricted; out-of-bounds and high-risk actions are reviewed by you',
    '相同应用层边界，由独立审查 Agent 审批': 'Same app-level boundary; approved by an independent review agent',
    '无应用限制、无审批，以当前用户执行': 'No app-level restrictions or approvals; runs as the current user',
    '更改权限': 'Change permissions',
    'Agent 的操作应如何获得审批？': 'How should Agent actions be approved?',
    '工作区内自动执行；联网、出项目、永久删除等会先问你': 'Runs automatically inside the workspace; asks before using the internet, going outside the project, or permanently deleting',
    '低风险自动放行，高风险仍转给你确认': 'Automatically approves low-risk actions and asks you to confirm high-risk ones',
    '关闭限制与审批，Agent 拥有你的全部权限': 'Turns off restrictions and approvals; the agent has all of your permissions',
    '自动审查中：审查 Agent 正在核对你的任务意图与请求风险。': 'Auto-reviewing: a reviewer agent is checking this request against your task intent.',
    '自动审批已批准': 'Auto-review approved',
    '自动审批已拒绝': 'Auto-review denied',
    '自动审查不可用（已转人工确认）': 'Auto-review unavailable (switched to manual review)',
    '可人工覆盖本次请求（只此一次，不沉淀规则）': 'You can override this once for this exact request (this time only; no rule is saved)',
    '允许工作区外处理（写/删/Shell）': 'Allow outside-workspace handling (write/delete/shell)',
    '工作区外处理权限': 'Outside-workspace handling',
    '开启后，写、删除和 Shell 在工作区外的操作不再逐次询问；破坏性/动态命令、网络和凭据导出仍按原规则。': 'When on, write/delete/shell operations outside the workspace no longer ask each time; destructive/dynamic commands, network, and credential export still follow the existing rules.',
    '已开启：写/删/Shell 工作区外操作自动放行。': 'Enabled: outside-workspace write/delete/shell run automatically.',
    '已关闭：工作区外操作恢复逐次审批。': 'Disabled: outside-workspace operations ask again.',
    '开启工作区外处理权限？': 'Enable outside-workspace handling?',
    '开启后，Agent 可在工作区外执行写入、删除和 Shell 操作而不再逐次询问。破坏性/动态命令、网络、凭据导出与安全策略篡改仍会被拦截或审批。': 'When enabled, the agent may write, delete, and run shell commands outside the workspace without asking each time. Destructive/dynamic commands, network, credential export, and policy tampering are still blocked or approved.',
    '确认开启': 'Enable',
    '完全访问已开启：Agent 可以直接读写文件、执行命令和联网，不再逐项询问。重启后依然有效，直到你手动切回“请求批准”。': 'Full access is on: the agent can read and write files, run commands, and use the network without asking each time. It stays on after restart until you switch back to "Ask for approval".',
    '完全访问已开启；Agent 可读写文件、执行命令和联网，不会自动关闭。': 'Full access is on; the agent can access files, run commands, and use the network. It will not turn off by itself.',
    '警告：完全访问已开启，Agent 可直接操作文件、终端和网络，重启后不会自动关闭，直到你手动切换。': 'Warning: Full access is on. The agent can directly use files, terminal, and network, and it stays on after restart until you switch back.',
    '仅在信任 Agent 时才建议开启': 'Only enable this when you trust the agent.',
    '完全访问开启后，Agent 可以直接读写文件、执行命令和联网，不再逐项征求你的同意。它拥有你当前账号能做的权限，可能会读取凭据、修改系统或删除文件。此设置对所有会话生效，重启后也不会自动关闭，直到你手动切回“请求批准”。是否继续？': 'With full access, the agent can read and write files, run commands, and use the network without asking each time. It has the permissions your current account has, so it could read credentials, modify the system, or delete files. This applies to all sessions and stays on after restart until you switch back to "Ask for approval". Continue?',
    '确认切换': 'Switch now',
    '确认清除': 'Clear now',
    '切换权限失败': 'Failed to switch permissions',
    '请求批准 / 替我审批 / 完全访问均可直接切换；完全访问切换时会单独警告': 'Ask for approval / Approve for me / Full access can be switched directly; Full access shows an extra warning',
    '权限规则（始终允许 / 必问 / 拒绝）': 'Permission rules (Always allow / Always ask / Deny)',
    '规则类型': 'Rule type',
    '规则行为': 'Rule behavior',
    '清除本会话规则': 'Clear session rules',
    '正在读取…': 'Loading…',
    'Shell 命令': 'Shell command',
    '读取': 'Read',
    '写入': 'Write',
    '网络': 'Network',
    '联网搜索': 'Web search',
    '允许': 'Allow',
    '必问': 'Always ask',
    '添加规则': 'Add rule',
    '网页抓取预批准域名（web_fetch 免审批）': 'Pre-approved domains for web fetch (web_fetch without approval)',
    '仅作用于只读的 web_fetch；web_download 与 Shell 联网不受影响。每行一个域名，留空表示仅用内置清单。': 'Applies only to read-only web_fetch; web_download and shell networking are unaffected. One domain per line; leave empty to use only the built-in list.',
    '保存': 'Save',
    '权限模式': 'Permission mode',
    '预批准域名操作': 'Pre-approved domain actions',
    '暂无长期规则。审批时选择“始终允许此类操作”会自动添加。': 'No persistent rules yet. Choosing "Always allow this kind of operation" while approving will add one automatically.',
    '未选择会话。': 'No session selected.',
    '清除当前会话的所有权限规则？用户级“始终允许”规则不受影响。': 'Clear all permission rules for the current session? User-level "Always allow" rules are unaffected.',
    '规则已删除。': 'Rule deleted.',
    '删除失败：': 'Failed to delete: ',
    '清除失败：': 'Failed to clear: ',
    '添加失败：': 'Failed to add: ',
    '·本会话': '· Session',
    '·项目': '· Project',
});
const UI_I18N_ATTRS = ['aria-label', 'data-ui-tip', 'title', 'placeholder'];
// These nodes contain user-, model-, or runtime-authored text. Translating them
// mutates conversation content instead of localizing UI chrome.
const UI_I18N_CONTENT_SELECTOR = [
    '.message',
    '.feed-chunk-scroller',
    '.process-brief-item',
    '.followup-queue-text',
    '.session-name',
    '.session-last-query',
    '#chat-goal-objective',
    '.todo-plan-item > span:last-child',
    '.human-question-text',
    '.human-option-label',
    '.human-option-description',
    '.human-option-preview pre',
    '.human-review-label',
    '.human-review-value',
    '.human-approval-subtitle',
    '.human-approval-message',
    '.human-terminal-answer',
    '.subagent-card-name',
    '.subagent-card-summary',
    '.subagent-output-content',
    '.subagent-block-body',
    '.subagent-block-preview',
    '.skill-picker-option-desc',
    '[data-i18n-skip]',
].join(',');
const uiI18nTextOriginal = new WeakMap();
const uiI18nAttrOriginal = new WeakMap();
const uiI18nRuntimeOriginal = new WeakMap();
var uiLanguage = localStorage.getItem(LS_UI_LANGUAGE) === 'en' ? 'en' : 'zh-CN';
var uiI18nObserver = null;

function translateUiString(value) {
    if (uiLanguage !== 'en') return value;
    var exact = UI_TRANSLATIONS_EN[value];
    if (exact) return exact;
    return String(value)
        .replace(/^更早 (\\d+) 轮对话$/, 'Earlier $1 conversations')
        .replace(/^(\\d+) \\/ (\\d+) 已完成$/, '$1 / $2 completed')
        .replace(/^(\\d+) \\/ (\\d+) 完成$/, '$1 / $2 completed')
        .replace(/^(\\d+)分钟$/, '$1 min')
        .replace(/^(\\d+) 分钟$/, '$1 min')
        .replace(/^已加载 (\\d+) 个自定义域名（内置清单始终生效）。$/, '$1 custom domain(s) loaded (the built-in list always applies).')
        .replace(/^已保存 (\\d+) 个自定义域名，新会话立即生效。$/, '$1 custom domain(s) saved; new sessions take effect immediately.')
        .replace(/^已清除本会话规则（(\\d+) 条）。$/, 'Session rules cleared ($1).')
        .replace(/^已选择 (\\d+) 个 Skill$/, '$1 skills selected')
        .replace(/^已选择 (\\d+) 项$/, '$1 items selected')
        .replace(/^正在上传 (\\d+) 个文件… (\\d+)%$/, 'Uploading $1 files… $2%')
        .replace(/预估上下文 token：选择会话并加载或发送消息后显示。分母为压缩摘要阈值。/g, 'Estimated context tokens; shown after selecting a session and loading or sending a message. The denominator is the compression-summary threshold.')
        .replace(/tokens（约 ([\\d.]+)%，超出门限 ([\\d.]+)%）。预估进入模型的上下文规模，含历史与系统提示；分母为当前 model profile 中触发压缩摘要的上下文门限。/g, 'tokens (about $1%; $2% over the limit). Estimated context size sent to the model, including history and system prompts; the denominator is the compression threshold for the current model profile.')
        .replace(/tokens（约 ([\\d.]+)%）。预估进入模型的上下文规模，含历史与系统提示；分母为当前 model profile 中触发压缩摘要的上下文门限。/g, 'tokens (about $1%). Estimated context size sent to the model, including history and system prompts; the denominator is the compression threshold for the current model profile.')
        .replace(/（当前约占上下文窗口 ([^）]+)）/g, ' (currently about $1 of the context window)')
        .replace(/模型配置：/g, 'Model configuration: ')
        .replace(/模型 ID：/g, 'Model ID: ')
        .replace(/接口类型：/g, 'Interface type: ')
        .replace(/上下文窗口：/g, 'Context window: ')
        .replace(/最大输出：/g, 'Maximum output: ')
        .replace(/思考强度：/g, 'Thinking effort: ')
        .replace(/能力：/g, 'Capabilities: ')
        .replace(/状态：/g, 'Status: ')
        .replace(/Skill：/g, 'Skill: ')
        .replace(/描述：/g, 'Description: ')
        .replace(/(\\d+) 个待处理请求/g, '$1 pending requests')
        .replace(/约 (\\d+(?:\\.\\d+)?)%/g, 'about $1%')
        .replace(/超出门限 (\\d+(?:\\.\\d+)?)%/g, '$1% over the limit')
        .replace(/工具调用生成中\\.\\.\\./g, 'Preparing tool call...')
        .replace(/执行中\\.\\.\\./g, 'Running...')
        .replace(/执行结果/g, 'Result')
        .replace(/生成中\\.\\.\\./g, 'Generating...')
        .replace(/(\\d+) 个待处理请求/g, '$1 pending requests')
        .replace(/(\\d+) 个问题待确认/g, '$1 questions awaiting confirmation')
        .replace(/(\\d+) 个问题/g, '$1 questions')
        .replace(/(\\d+) 个审批/g, '$1 approvals')
        .replace(/文件“(.+)”超过 (.+) 限制。/g, 'File “$1” exceeds the $2 limit.')
        .replace(/本次上传总大小超过 (.+) 限制。/g, 'The total upload exceeds the $1 limit.')
        .replace(/正在上传 (\\d+) 个文件… (\\d+)%/g, 'Uploading $1 files… $2%')
        .replace(/^(\\d+) 个子任务已完成，点击继续让主 Agent 综合子任务结果（不会自动续跑）。$/g, '$1 subtasks completed. Click continue to let the main Agent synthesize their results (no automatic continuation).')
        .replace(/^(\\d+) 个子任务结果尚未纳入上方回答，点击补充综合。$/g, '$1 subtask results are not included in the answer above. Click to add a synthesis.')
        .replace(/^提交失败：(.+)$/g, 'Submission failed: $1')
        .replace(/^取消失败：(.+)$/g, 'Cancellation failed: $1')
        .replace(/^处理失败：(.+)$/g, 'Failed to process: $1')
        .replace(/^切换会话加载失败：?(.+)$/g, 'Failed to load the session: $1')
        .replace(/^切换会话失败：?(.+)$/g, 'Failed to switch session: $1')
        .replace(/^加载会话消息失败：?(.+)$/g, 'Failed to load session messages: $1')
        .replace(/^加载会话列表失败：?(.+)$/g, 'Failed to load the session list: $1')
        .replace(/^创建新会话失败：?(.+)$/g, 'Failed to create a new session: $1')
        .replace(/^删除会话失败：?(.+)$/g, 'Failed to delete the session: $1')
        .replace(/^刷新会话摘要失败：?(.+)$/g, 'Failed to refresh the session summary: $1')
        .replace(/^加载更早(?:消息|记录)失败：?(.+)$/g, 'Failed to load earlier messages: $1')
        .replace(/^预加载下一批归档目录失败：?(.+)$/g, 'Failed to preload the next archived sessions: $1')
        .replace(/^重命名失败：?(.+)$/g, 'Rename failed: $1')
        .replace(/^归档失败：?(.+)$/g, 'Archive failed: $1')
        .replace(/^置顶失败：?(.+)$/g, 'Pin failed: $1')
        .replace(/^问题 (\\d+)$/g, 'Question $1')
        .replace(/^问题 #(\\d+)$/g, 'Question #$1')
        .replace(/（事件索引 (\\d+)）/g, ' (event index $1)')
        .replace(/^保存失败：(.+)$/g, 'Save failed: $1')
        .replace(/^Skill 加载失败：(.+)$/g, 'Failed to load Skill: $1')
        .replace(/^MCP 工具加载失败：(.+)$/g, 'Failed to load MCP tools: $1')
        .replace(/^扩展加载失败：(.+)$/g, 'Failed to load extensions: $1')
        .replace(/^异步截断失败：?(.+)$/g, 'Asynchronous truncation failed: $1')
        .replace(/^续接 subagent 失败：?(.+)$/g, 'Failed to continue subagent: $1')
        .replace(/^检测到上次运行未完成，正在自动恢复任务…$/g, 'The previous run was incomplete; restoring the task automatically…')
        .replace(/^检测到 (?:系统睡眠|Agent 进程暂停)约 (\\d+) 秒，任务已恢复$/g, 'A system sleep or Agent process pause of about $1 seconds was detected; the task resumed')
        .replace(/^未能加载到对应的用户提问（可能索引不一致）。可刷新页面或使用「更早 (.+) 轮对话」手动分页。$/g, 'Could not load the corresponding user question (the index may be inconsistent). Refresh the page or use “Earlier $1 conversations” to paginate manually.')
        .replace(/^【安全确认】用户已允许：(.+)$/g, '[Safety confirmation] User allowed: $1')
        .replace(/^【安全确认】用户已拒绝执行（已跳过）。\\s*(.+)$/g, '[Safety confirmation] User denied execution (skipped): $1')
        .replace(/^任务已由用户中断（父会话）$/g, 'Task interrupted by the user (parent session)')
        .replace(/^任务已由用户中断$/g, 'Task interrupted by the user')
        .replace(/^任务因 Agent 停止、重启或运行中断而暂停，可在服务恢复后继续$/g, 'The task was paused because the Agent stopped, restarted, or was interrupted; it can continue after the service recovers')
        .replace(/^执行已由 Stop Hook 暂停：(.+)$/g, 'Execution paused by a Stop Hook: $1')
        .replace(/^执行已由 Hook 暂停：(.+)$/g, 'Execution paused by a Hook: $1')
        .replace(/^Stop Hook 在 (\\d+) 次检查后仍阻止结束：(.+)$/g, 'Stop Hook still blocked completion after $1 checks: $2')
        .replace(/^模型未输出最终内容，正在重试（(\\d+)\\/(\\d+)）$/g, 'The model did not produce a final response; retrying ($1/$2)')
        .replace(/^检测到连续重复行为（(\\d+)次），已插入强制提醒$/g, 'Consecutive repeated behavior detected ($1 times); a mandatory reminder was inserted')
        .replace(/^检测到连续重复行为，已终止任务。最近输出：(.+)$/g, 'Consecutive repeated behavior detected; task terminated. Recent output: $1')
        .replace(/^子任务结果已返回，正在纳入当前回答$/g, 'Subtask results returned; incorporating them into the current response')
        .replace(/^待办更新失败：(.+)$/g, 'Todo update failed: $1')
        .replace(/^subagent 执行异常：(.+)$/g, 'Subagent execution error: $1')
        .replace(/^MCP 调用异常：(.+)$/g, 'MCP call error: $1')
        .replace(/^未知工具：(.+)$/g, 'Unknown tool: $1')
        .replace(/^工具执行异常：(.+)$/g, 'Tool execution error: $1')
        .replace(/^工具执行异常:\\s*(.+)$/g, 'Tool execution error: $1')
        .replace(/^Todo 计划已连续 (\\d+) 轮未更新，已插入更新提醒$/g, 'The Todo plan has not been updated for $1 rounds; an update reminder was inserted')
        .replace(/^检测到本机网络已断开，Agent 进入沉睡状态并等待网络恢复…$/g, 'The local network is disconnected; the Agent is sleeping until it recovers…')
        .replace(/^网络连接失败，正在重连（第 (\\d+) 次，(.+)s 后重试）\\.\\.\\.$/g, 'Network connection failed; reconnecting (attempt $1, retrying in $2s)…')
        .replace(/^LLM 调用失败 \\[([^\\]]+)\\] (.+)：(.+)\\n(.+)$/g, 'LLM call failed [$1] $2: $3\\n$4')
        .replace(/^模型输出在完整工具调用后达到长度上限；已保留并执行完整调用，未完成片段已丢弃。$/g, 'The model output reached the length limit after a complete tool call; the complete call was retained and executed, and the unfinished fragment was discarded.')
        .replace(/^模型输出达到 max_tokens\\/max_output_tokens 上限，工具调用可能被截断。请调大输出窗口，或把长文件写入拆成更小的步骤后重试。$/g, 'Model output reached the max_tokens/max_output_tokens limit; tool calls may be truncated. Increase the output window, or split long-file writes into smaller steps and retry.')
        .replace(/^模型输出达到输出 token 上限，已丢弃半截工具调用并重试（(\\d+)\\/(\\d+)）$/g, 'Model output reached the output-token limit; the incomplete tool call was discarded and retried ($1/$2)')
        .replace(/^已清理临时文件 (\\d+) 个（已移入 \\.trash）$/g, 'Cleaned up $1 temporary files (moved to .trash)')
        .replace(/^\\[后台 Subagent 已完成\\]/g, '[Background subagent completed]')
        .replace(/^无效的 mode：(.+?)；仅支持 compact、edit_key_context。$/g, 'Invalid mode: $1; only compact and edit_key_context are supported.')
        .replace(/^自动应急截断已重试 (\\d+) 次仍可能超过整包阈值；将直接请求主模型。可新建会话或调低环境变量 CONTEXT_WINDOW（当前 (.+)）$/g, 'Automatic emergency truncation may still exceed the full-package threshold after $1 retries; requesting the main model directly. Create a new session or lower CONTEXT_WINDOW (current: $2).')
        .replace(/网络连接失败/g, 'Network connection failed')
        .replace(/API 认证失败/g, 'API authentication failed')
        .replace(/访问被拒绝/g, 'Access denied')
        .replace(/模型或接口不可用/g, 'Model or interface unavailable')
        .replace(/请求频率超限/g, 'Request rate limit exceeded')
        .replace(/请求参数错误/g, 'Invalid request parameters')
        .replace(/内容被拦截/g, 'Content blocked')
        .replace(/服务器错误/g, 'Server error')
        .replace(/LLM 调用异常/g, 'LLM call failed')
        .replace(/无法连接到 API 服务器。/g, 'Could not connect to the API server.')
        .replace(/API Key 无效或已过期。/g, 'The API key is invalid or expired.')
        .replace(/当前地区不支持或 API Key 被风控。/g, 'The current region is unsupported or the API key was restricted.')
        .replace(/请求的模型不支持当前能力（如图像输入）。/g, 'The requested model does not support this capability (such as image input).')
        .replace(/已重试 3 次，均因速率限制失败。/g, 'All three retries failed due to rate limiting.')
        .replace(/请求体格式不符合 API 要求。/g, 'The request body format does not meet the API requirements.')
        .replace(/输入内容触发了安全审核。/g, 'The input triggered a safety review.')
        .replace(/发生未知错误。/g, 'An unknown error occurred.')
        .replace(/^已选 (\\d+) \\/ 共 (\\d+)$/, '$1 selected / $2 total')
        .replace(/^已选 (\\d+) \\/ 已启用 (\\d+) \\/ 共 (\\d+)$/, '$1 selected / $2 enabled / $3 total')
        .replace(/^共 (\\d+)$/, '$1 total')
        .replace(/已启用/g, 'Enabled')
        .replace(/已禁用/g, 'Disabled')
        .replace(/暂无描述/g, 'No description')
        .replace(/未就绪/g, 'Not ready')
        .replace(/可用/g, 'Available')
        .replace(/未设置/g, 'Not set')
        .replace(/^加载失败: (.+)$/, 'Failed to load: $1')
        .replace(/^请求失败: (.+)$/, 'Request failed: $1')
        .replace(/^无法打开：(.+)$/, 'Could not open: $1')
        .replace(/^移除 (.+)$/, 'Remove $1')
        .replace(/^确定删除会话「(.+)」吗？其中的消息与记录将被移除。$/, 'Delete session “$1”? Its messages and records will be removed.')
        .replace(/^工具 (\\d+) 次$/, '$1 tool calls')
        .replace(/^失败 (\\d+) 次$/, '$1 failures')
        .replace(/工具\\s*(\\d+)\\s*次/g, '$1 tool calls')
        .replace(/失败\\s*(\\d+)\\s*次/g, '$1 failures')
        .replace(/(\\d+)\\s*分\\s*(\\d+)\\s*秒/g, '$1m $2s')
        .replace(/^(\\d+) 轮$/, '$1 rounds')
        .replace(/^(\\d+)分(\\d+)秒$/, '$1m $2s')
        .replace(/^调用工具 (.+) (\\d+)次$/, 'Called tool $1 $2 times')
        .replace(/^检测到系统睡眠约 (\\d+) 秒，任务已恢复$/, 'System sleep detected for about $1 seconds; task resumed')
        .replace(/^检测到 Agent 进程暂停约 (\\d+) 秒，任务已恢复$/, 'Agent process pause detected for about $1 seconds; task resumed')
        .replace(/^会话 (.+)$/, 'Session $1')
        .replace(/(\\d+)\\s*成员/g, '$1 members')
        .replace(/(\\d+)\\s*任务/g, '$1 tasks')
        .replace(/^模型配置切换失败: (.+)$/, 'Failed to switch model configuration: $1')
        .replace(/^模型配置启停失败: (.+)$/, 'Failed to change model profile status: $1')
        .replace(/^Skill 启停失败：(.+)$/, 'Failed to change Skill status: $1')
        .replace(/^续接失败: (.+)$/, 'Failed to continue: $1')
        .replace(/^恢复实时流失败: (.+)$/, 'Failed to restore live stream: $1')
        .replace(/^追问插入失败: (.+)$/, 'Failed to insert follow-up: $1')
        .replace(/^追问已被接收，无法撤回: (.+)$/, 'The follow-up was accepted and cannot be withdrawn: $1')
        .replace(/^验证：(.+)$/, 'Verification: $1')
        .replace(/【上下文窗口已满，开始压缩】/g, '[Context window full; starting compression]')
        .replace(/【上下文压缩已完成】/g, '[Context compression completed]')
        .replace(/【上下文摘要】/g, '[Context summary]')
        .replace(/【上下文裁剪】/g, '[Context trimming]')
        .replace(/【要点】/g, '[Key points]')
        .replace(/上下文窗口已满，开始压缩/g, 'Context window full; starting compression')
        .replace(/上下文压缩已完成/g, 'Context compression completed')
        .replace(/正在进行上下文裁剪以控制 token（可能需数秒，请稍候）…/g, 'Trimming context to control tokens (this may take a few seconds; please wait)…')
        .replace(/摘要模型仍在生成或等待响应中，请稍候…/g, 'The summary model is still generating or waiting for a response; please wait…')
        .replace(/模型仍在更新要点或等待响应中，请稍候…/g, 'The model is still updating key points or waiting for a response; please wait…')
        .replace(/已完成上下文裁剪与摘要以控制长度/g, 'Context trimming and summarization completed to control length')
        .replace(/已完成上下文裁剪以控制长度/g, 'Context trimming completed to control length')
        .replace(/正在分析上下文并准备本地裁剪…/g, 'Analyzing context and preparing local trimming…')
        .replace(/正在执行本地裁剪与微压…/g, 'Performing local trimming and micro-compression…')
        .replace(/已对非关键信息进行裁剪/g, 'Non-critical information trimmed')
        .replace(/正在收敛较早段落中的 ReAct 过程…/g, 'Consolidating ReAct steps in earlier sections…')
        .replace(/已对较早段落中的思考过程进行裁剪/g, 'Reasoning in earlier sections trimmed')
        .replace(/裁剪后仍超限，开始生成历史摘要…/g, 'Still over the limit after trimming; generating a history summary…')
        .replace(/没有足够可摘要的历史前缀，已转入截尾兜底。/g, 'Not enough history prefix to summarize; switching to tail truncation fallback.')
        .replace(/没有足够可摘要的历史前缀，继续尝试更窄尾窗…/g, 'Not enough history prefix to summarize; trying a narrower tail window…')
        .replace(/可摘要历史不足，已丢弃更早对话（保留至多约半窗 token 的尾部）。/g, 'Not enough history to summarize; discarded earlier messages and kept up to roughly half a window of recent tokens.')
        .replace(/可摘要历史不足；对话已在半窗预算内未再截断。/g, 'Not enough history to summarize; the conversation was not truncated further within the half-window budget.')
        .replace(/摘要输出格式重试后仍无效，已改用摘录兜底。/g, 'The summary output remained invalid after retries; using an excerpt fallback.')
        .replace(/第 (\\d+) 次摘要输出格式无效，已丢弃并准备重试…/g, 'Summary output for attempt $1 was invalid, discarded, and will be retried…')
        .replace(/摘要模型调用失败，已改用摘录兜底：/g, 'Summary model call failed; using an excerpt fallback: ')
        .replace(/流程异常，已切换为失败兜底截尾。/g, 'The process encountered an error; switched to the failure fallback truncation.')
        .replace(/当前上下文无需进一步裁剪或摘要/g, 'The current context needs no further trimming or summarization')
        .replace(/正在进行上下文裁剪（可能需数秒，请稍候）…/g, 'Trimming context (this may take a few seconds; please wait)…')
        .replace(/第 (\\d+) 轮：正在生成历史摘要与要点…/g, 'Round $1: generating history summary and key points…')
        .replace(/第 (\\d+) 轮摘要完成/g, 'Round $1 summary completed')
        .replace(/第 (\\d+) 轮要点已写入/g, 'Key points for round $1 written')
        .replace(/正在根据编辑说明更新要点…/g, 'Updating key points from the edit instructions…')
        .replace(/已按说明更新要点/g, 'Key points updated according to the instructions')
        .replace(/完成 (\\d+) 轮历史摘要；完成关键 信息、经验与结论 的记录/g, 'Completed $1 rounds of history summarization; recorded key information, experience, and conclusions')
        .replace(/本轮未能继续缩小本地上下文，已转入安全兜底。/g, 'This round could not reduce local context further; switched to safe fallback.')
        .replace(/已完成配置的 (\\d+) 轮且尚未达到压缩比，继续进行增量摘要…/g, 'Completed the configured $1 rounds without reaching the compression ratio; continuing incremental summarization…')
        .replace(/连续摘要未再缩小本地上下文（已尝试 (\\d+) 轮）/g, 'Repeated summarization did not reduce local context further (tried $1 rounds)')
        .replace(/摘要未达到目标压缩比（已尝试 (\\d+) 轮）/g, 'Summary did not reach the target compression ratio (tried $1 rounds)')
        .replace(/已转入安全兜底截尾。/g, 'Switched to safe fallback truncation.')
        .replace(/对话已在半窗预算内未再截断。/g, 'The conversation was not truncated further within the half-window budget.')
        .replace(/上下文已按策略完成裁剪/g, 'Context trimmed according to policy')
        .replace(/对话已摘要，关键信息已写入 key_context/g, 'Conversation summarized; key information written to key_context')
        .replace(/\\[系统通知：/g, '[System notice: ')
        .replace(/\\[压缩失败，保留截断原文片段\\]/g, '[Compression failed; retaining a truncated excerpt]')
        .replace(/检测到同会话仍有未结束的上下文压缩，等待其完成后再继续 ReAct。/g, 'An unfinished context compression was detected for this session; waiting for it to finish before continuing ReAct.')
        .replace(/已按 CONTEXT_COMPRESS_FAILURE_MAX_TOKENS（与压缩失败兜底同款）裁剪对话尾部并继续本步/g, 'The conversation tail was trimmed using CONTEXT_COMPRESS_FAILURE_MAX_TOKENS (same as the compression-failure fallback), then this step continued')
        .replace(/上下文已截尾（Conversation truncated）；更早内容请查本会话目录。/g, 'Context truncated (Conversation truncated); see the session directory for earlier content.')
        .replace(/上下文已截尾（Conversation truncated），保留约半窗 token 尾部。/g, 'Context truncated (Conversation truncated), keeping roughly the last half-window of tokens.')
        .replace(/已完成上下文裁剪与摘要/g, 'Context trimming and summarization completed')
        .replace(/已完成上下文裁剪/g, 'Context trimming completed')
        .replace(/【自动·长度策略】/g, '[Automatic length policy]')
        .replace(/(\\d+)\\s*轮/g, '$1 rounds')
        .replace(/正在根据对话更新要点/g, 'Updating key points from the conversation')
        .replace(/正在思考中\\.\\.\\./g, 'Thinking...')
        .replace(/正在重连/g, 'Reconnecting')
        .replace(/^\\[历史\\/旧版事件\\] (.+)$/, '[History/legacy event] $1')
        .replace(/^(?:已选择|激活) Skill：(.+)$/, function (_, skills) {
            return 'Activated Skill: ' + String(skills || '').replace(/、/g, ', ');
        })
        .replace(/^追问暂未发出（发送通道繁忙），已保留待重试: (.+)$/, 'Follow-up not sent (send channel busy); retained for retry: $1')
        .replace(/^追问降级发送未成功，已保留待重试: (.+)$/, 'Fallback follow-up send failed; retained for retry: $1')
        .replace(/^思·/, 'Reasoning · ')
        .replace(/^答·/, 'Response · ')
        .replace(/^平均 (.+)$/, 'Average $1')
        .replace(/^累计 (.+)$/, 'Total $1')
        .replace(/^占本阶段 (.+)$/, 'Share of phase $1')
        .replace(/^(.+) 次 LLM 请求$/, '$1 LLM requests')
        .replace(/^(.+) 个模型。$/, '$1 models.')
        .replace(/^\\.\\.\\. \\[中间省略 (\\d+) 行\\] \\.\\.\\.$/, '... [$1 lines omitted] ...')
        .replace(/^\\.\\.\\. \\[中间省略约 (\\d+) 字符\\] \\.\\.\\.$/, '... [about $1 characters omitted] ...');
}

function translateUiNode(root) {
    if (!root) return;
    var elements = [];
    if (root.nodeType === Node.ELEMENT_NODE) elements.push(root);
    if (root.querySelectorAll) elements = elements.concat(Array.from(root.querySelectorAll('*')));
    elements.forEach(function (el) {
        if (el.closest && el.closest('.sidebar-brand-sub')) return;
        if (el.matches && (
            el.matches(UI_I18N_CONTENT_SELECTOR)
            || (el.closest && el.closest(UI_I18N_CONTENT_SELECTOR))
        )) return;
        if (el.matches('script,style,code,pre,[contenteditable="true"]')) return;
        var originals = uiI18nAttrOriginal.get(el) || {};
        UI_I18N_ATTRS.forEach(function (attr) {
            if (!el.hasAttribute(attr)) return;
            if (!(attr in originals)) originals[attr] = el.getAttribute(attr);
            el.setAttribute(attr, uiLanguage === 'en' ? translateUiString(originals[attr]) : originals[attr]);
        });
        uiI18nAttrOriginal.set(el, originals);
        Array.from(el.childNodes).forEach(function (node) {
            if (node.nodeType !== Node.TEXT_NODE || !node.nodeValue.trim()) return;
            if (!uiI18nTextOriginal.has(node)) uiI18nTextOriginal.set(node, node.nodeValue);
            var original = uiI18nTextOriginal.get(node);
            var trimmed = original.trim();
            var translated = uiLanguage === 'en' ? translateUiString(trimmed) : trimmed;
            node.nodeValue = original.replace(trimmed, translated);
        });
    });
}

// Runtime-owned process rows are kept separate from model/user content. Store
// their source text so toggling back to Chinese always restores the original,
// even when the row was updated while English was active.
function setUiRuntimeText(el, original) {
    if (!el) return;
    var source = String(original == null ? '' : original);
    uiI18nRuntimeOriginal.set(el, source);
    el.setAttribute('data-ui-runtime-text', '1');
    el.textContent = uiLanguage === 'en' ? translateUiString(source) : source;
}

function getUiRuntimeText(el) {
    if (!el) return '';
    var source = uiI18nRuntimeOriginal.get(el);
    return source == null ? String(el.textContent || '') : source;
}

// Final cards normally contain arbitrary model output and must never be
// translated.  These are the narrow, system-generated terminal messages that
// are emitted as an assistant final event and therefore need the same runtime
// localization as process/status rows.
function isUiRuntimeFinalText(value) {
    var source = String(value == null ? '' : value).trim();
    if (!source) return false;
    return /^任务已由用户中断(?:（父会话）)?。?$/.test(source)
        || /^任务因 Agent 停止、重启或运行中断而暂停/.test(source)
        || /^执行已由 (?:Hook|Stop Hook) 暂停：/.test(source)
        || /^Stop Hook 在 \\d+ 次检查后仍阻止结束：/.test(source)
        || /^检测到连续重复行为，已终止任务。最近输出：/.test(source)
        || /^本轮执行步骤已达到最大迭代次数。/.test(source)
        || /^(?:Token 预算已耗尽|连续运行失败|ReAct 已达到轮次上限|手动暂停)$/.test(source)
        || /^LLM 调用失败 \\[[^\\]]+\\] /.test(source)
        || /^模型输出达到 max_tokens\\/max_output_tokens 上限，/.test(source)
        || /^模型输出达到输出 token 上限，/.test(source)
        || /^模型输出在完整工具调用后达到长度上限；/.test(source);
}

function translateRuntimeUiNodes(root) {
    if (!root || !root.querySelectorAll) return;
    var nodes = [];
    if (root.nodeType === Node.ELEMENT_NODE && root.hasAttribute('data-ui-runtime-text')) nodes.push(root);
    nodes = nodes.concat(Array.from(root.querySelectorAll('[data-ui-runtime-text]')));
    nodes.forEach(function (el) {
        var source = uiI18nRuntimeOriginal.get(el);
        if (source != null) el.textContent = uiLanguage === 'en' ? translateUiString(source) : source;
    });
}

function applyUiLanguage(language, persist) {
    uiLanguage = language === 'en' ? 'en' : 'zh-CN';
    document.documentElement.lang = uiLanguage;
    document.documentElement.setAttribute('data-language', uiLanguage);
    document.title = uiLanguage === 'en' ? 'General Agent · Intelligent Chat' : 'General Agent · 智能会话';
    if (persist) localStorage.setItem(LS_UI_LANGUAGE, uiLanguage);
    if (uiI18nObserver) uiI18nObserver.disconnect();
    translateUiNode(document.body);
    translateRuntimeUiNodes(document.body);
    var languageButton = document.getElementById('sidebar-language-btn');
    if (languageButton) {
        languageButton.setAttribute('aria-label', uiLanguage === 'en' ? 'Switch to Chinese' : '切换为英文');
        languageButton.setAttribute('title', uiLanguage === 'en' ? 'Switch language' : '切换语言');
    }
    if (uiI18nObserver) uiI18nObserver.observe(document.body, { childList: true, subtree: true });
    document.dispatchEvent(new CustomEvent('myagent:language-change', { detail: { language: uiLanguage } }));
}

function initUiI18n() {
    uiI18nObserver = new MutationObserver(function (mutations) {
        mutations.forEach(function (mutation) {
            mutation.addedNodes.forEach(function (node) {
                if (node.nodeType === Node.ELEMENT_NODE) translateUiNode(node);
                else if (node.nodeType === Node.TEXT_NODE && node.parentElement) translateUiNode(node.parentElement);
            });
            if (mutation.type === 'characterData' && mutation.target.parentElement) {
                var textNode = mutation.target;
                var current = textNode.nodeValue || '';
                var original = uiI18nTextOriginal.get(textNode);
                if (!original || !original.trim()) {
                    original = current;
                    uiI18nTextOriginal.set(textNode, original);
                }
                var trimmed = original.trim();
                var translated = uiLanguage === 'en' ? translateUiString(trimmed) : trimmed;
                var nextValue = original.replace(trimmed, translated);
                if (nextValue !== current) textNode.nodeValue = nextValue;
            }
        });
    });
    applyUiLanguage(uiLanguage, false);
}
initUiI18n();
`,St=`// ═══════════════════════════════════════════════════════════
// General Agent · 智能会话 — 完整逻辑
// ═══════════════════════════════════════════════════════════

const chatContainer = document.getElementById('chat-container');
const messageInput = document.getElementById('message-input');
const sendBtn = document.getElementById('send-btn');
const pickPathBtn = document.getElementById('pick-path-btn');
if (window.MyAgentPathPicker && pickPathBtn && messageInput) {
    MyAgentPathPicker.attachChatPicker(pickPathBtn, messageInput);
}
if (messageInput) {
    messageInput.addEventListener('myagent:file-upload-state', function () {
        if (typeof setSendButtonState === 'function') setSendButtonState();
    });
    messageInput.addEventListener('myagent:file-paste-error', function (event) {
        const detail = event && event.detail ? event.detail : {};
        if (typeof showUiAlert === 'function') {
            showUiAlert({
                title: '文件上传失败',
                message: String(detail.message || '无法上传所选文件或剪贴板中的图片。'),
                variant: 'error',
            });
        }
    });
}
const sessionsList = document.getElementById('sessions-list');
const newSessionBtn = document.getElementById('new-session-btn');
const offscreenRoot = document.getElementById('session-offscreen-buffers');

const LS_UI_FONT = 'myagent-font-level';
const LS_UI_THEME = 'myagent-theme';
const LS_SESSION_LIST_MODE = 'myagent-session-list-mode';
/** 三档字号（rem 基准）：相对此前整体收紧一档（原大→现中、原中→现小） */
/** 三档 root 字号(px)：在「降一档」基准上整体 ×1.2 */
const UI_FONT_PX = [14, 16, 17];
var settingsModalKeyHandler = null;
var agentTeamFeatureSaving = false;
var askUserFeatureSaving = false;

function setAgentTeamFeatureUi(enabled, options) {
    options = options || {};
    var off = document.getElementById('settings-agent-team-off');
    var on = document.getElementById('settings-agent-team-on');
    var status = document.getElementById('settings-agent-team-status');
    var manage = document.getElementById('settings-agent-team-manage');
    var known = typeof enabled === 'boolean';
    if (off) {
        off.classList.toggle('is-active', known && !enabled);
        off.disabled = !!options.busy;
    }
    if (on) {
        on.classList.toggle('is-active', known && enabled);
        on.disabled = !!options.busy;
    }
    if (status) {
        status.classList.toggle('is-error', !!options.error);
        if (options.message) status.textContent = options.message;
        else if (options.busy) status.textContent = '正在保存…';
        else if (enabled) status.textContent = '已启用；Agent Team 入口和团队运行时可用。';
        else if (known) status.textContent = '已关闭；现有 task/subagent 行为不受影响。';
        else status.textContent = '正在读取状态…';
    }
    if (manage) manage.disabled = !known || !enabled || !!options.busy;
}

async function refreshAgentTeamFeature() {
    setAgentTeamFeatureUi(null, { busy: agentTeamFeatureSaving });
    try {
        var response = await fetch('/api/features/agent-team', { cache: 'no-store' });
        var data = await response.json();
        if (!response.ok || !data || data.ok !== true) {
            throw new Error((data && data.error) || ('HTTP ' + response.status));
        }
        window.__MYAGENT_FEATURES__ = window.__MYAGENT_FEATURES__ || {};
        window.__MYAGENT_FEATURES__.agentTeam = data.enabled === true;
        setAgentTeamFeatureUi(data.enabled === true);
    } catch (error) {
        setAgentTeamFeatureUi(null, {
            error: true,
            message: '读取失败：' + String(error && error.message ? error.message : error),
        });
    }
}

async function saveAgentTeamFeature(enabled) {
    if (agentTeamFeatureSaving) return;
    agentTeamFeatureSaving = true;
    setAgentTeamFeatureUi(enabled, { busy: true });
    try {
        var response = await fetch('/api/features/agent-team', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ enabled: enabled === true }),
        });
        var data = await response.json();
        if (!response.ok || !data || data.ok !== true) {
            throw new Error((data && data.error) || ('HTTP ' + response.status));
        }
        window.__MYAGENT_FEATURES__ = window.__MYAGENT_FEATURES__ || {};
        window.__MYAGENT_FEATURES__.agentTeam = data.enabled === true;
        setAgentTeamFeatureUi(data.enabled === true);
    } catch (error) {
        setAgentTeamFeatureUi(null, {
            error: true,
            message: '保存失败：' + String(error && error.message ? error.message : error),
        });
    } finally {
        agentTeamFeatureSaving = false;
        var off = document.getElementById('settings-agent-team-off');
        var on = document.getElementById('settings-agent-team-on');
        if (off) off.disabled = false;
        if (on) on.disabled = false;
    }
}

function setAskUserFeatureUi(enabled, options) {
    options = options || {};
    var off = document.getElementById('settings-ask-user-off');
    var on = document.getElementById('settings-ask-user-on');
    var status = document.getElementById('settings-ask-user-status');
    var known = typeof enabled === 'boolean';
    if (off) {
        off.classList.toggle('is-active', known && !enabled);
        off.disabled = !!options.busy;
    }
    if (on) {
        on.classList.toggle('is-active', known && enabled);
        on.disabled = !!options.busy;
    }
    if (status) {
        status.classList.toggle('is-error', !!options.error);
        if (options.message) status.textContent = options.message;
        else if (options.busy) status.textContent = '正在保存…';
        else if (enabled) status.textContent = '已启用；Agent 可在确实需要选择时暂停并向你提问。';
        else if (known) status.textContent = '已关闭；Agent 不会创建结构化提问卡片。';
        else status.textContent = '正在读取状态…';
    }
}

async function refreshAskUserFeature() {
    setAskUserFeatureUi(null, { busy: askUserFeatureSaving });
    try {
        var response = await fetch('/api/features/ask-user', { cache: 'no-store' });
        var data = await response.json();
        if (!response.ok || !data || data.ok !== true) throw new Error((data && data.error) || ('HTTP ' + response.status));
        window.__MYAGENT_FEATURES__ = window.__MYAGENT_FEATURES__ || {};
        window.__MYAGENT_FEATURES__.askUser = data.enabled === true;
        setAskUserFeatureUi(data.enabled === true);
    } catch (error) {
        setAskUserFeatureUi(null, { error: true, message: '读取失败：' + String(error && error.message ? error.message : error) });
    }
}

async function saveAskUserFeature(enabled) {
    if (askUserFeatureSaving) return;
    askUserFeatureSaving = true;
    setAskUserFeatureUi(enabled, { busy: true });
    try {
        var response = await fetch('/api/features/ask-user', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ enabled: enabled === true }),
        });
        var data = await response.json();
        if (!response.ok || !data || data.ok !== true) throw new Error((data && data.error) || ('HTTP ' + response.status));
        window.__MYAGENT_FEATURES__ = window.__MYAGENT_FEATURES__ || {};
        window.__MYAGENT_FEATURES__.askUser = data.enabled === true;
        setAskUserFeatureUi(data.enabled === true);
    } catch (error) {
        setAskUserFeatureUi(null, { error: true, message: '保存失败：' + String(error && error.message ? error.message : error) });
    } finally {
        askUserFeatureSaving = false;
    }
}

function getStoredFontLevel() {
    var n = parseInt(localStorage.getItem(LS_UI_FONT), 10);
    if (isNaN(n) || n < 0 || n > 2) return 1;
    return n;
}

function getStoredSessionListMode() {
    var m = localStorage.getItem(LS_SESSION_LIST_MODE);
    return m === 'compact' ? 'compact' : 'detailed';
}

function syncSettingsModalForm() {
    var lvl = getStoredFontLevel();
    for (var i = 0; i < 3; i++) {
        var b = document.getElementById('settings-font-' + i);
        if (b) b.classList.toggle('is-active', i === lvl);
    }
    var light = document.documentElement.classList.contains('theme-light');
    var bd = document.getElementById('settings-theme-dark');
    var bl = document.getElementById('settings-theme-light');
    if (bd) bd.classList.toggle('is-active', !light);
    if (bl) bl.classList.toggle('is-active', light);
    var compact = getStoredSessionListMode() === 'compact';
    var sc = document.getElementById('settings-session-compact');
    var sd = document.getElementById('settings-session-detailed');
    if (sc) sc.classList.toggle('is-active', compact);
    if (sd) sd.classList.toggle('is-active', !compact);
}

function applyFontLevel(level, persist) {
    level = Math.max(0, Math.min(2, level));
    document.documentElement.style.fontSize = UI_FONT_PX[level] + 'px';
    document.documentElement.setAttribute('data-font-level', String(level));
    if (persist) localStorage.setItem(LS_UI_FONT, String(level));
    syncSettingsModalForm();
}

function applyUiTheme(theme, persist) {
    var light = theme === 'light';
    document.documentElement.classList.toggle('theme-light', light);
    if (persist) localStorage.setItem(LS_UI_THEME, light ? 'light' : 'dark');
    syncSettingsModalForm();
}

function applySessionListMode(mode, persist) {
    var next = mode === 'compact' ? 'compact' : 'detailed';
    document.documentElement.setAttribute('data-session-list-mode', next);
    if (persist) localStorage.setItem(LS_SESSION_LIST_MODE, next);
    syncSettingsModalForm();
}

function restoreUiPreferences() {
    applyFontLevel(getStoredFontLevel(), false);
    var t = localStorage.getItem(LS_UI_THEME);
    applyUiTheme(t === 'dark' ? 'dark' : 'light', false);
    applySessionListMode(getStoredSessionListMode(), false);
}
restoreUiPreferences();

function openSettingsModal() {
    var root = document.getElementById('settings-modal-root');
    var panel = root && root.querySelector('.settings-modal');
    if (!root || !panel) return;
    syncSettingsModalForm();
    void refreshAgentTeamFeature();
    void refreshAskUserFeature();
    root.classList.add('is-open');
    root.setAttribute('aria-hidden', 'false');
    document.body.style.overflow = 'hidden';
    try { panel.focus(); } catch (e) {}
    settingsModalKeyHandler = function (ev) {
        if (ev.key === 'Escape') { ev.preventDefault(); closeSettingsModal(); }
    };
    document.addEventListener('keydown', settingsModalKeyHandler);
}

function closeSettingsModal() {
    var root = document.getElementById('settings-modal-root');
    if (!root) return;
    root.classList.remove('is-open');
    root.setAttribute('aria-hidden', 'true');
    document.body.style.overflow = '';
    if (settingsModalKeyHandler) {
        document.removeEventListener('keydown', settingsModalKeyHandler);
        settingsModalKeyHandler = null;
    }
}

function initUiSettingsControls() {
    var root = document.getElementById('settings-modal-root');
    var gear = document.getElementById('sidebar-settings-btn');
    var closeBtn = document.getElementById('settings-modal-close');
    if (!root) return;
    if (gear) {
        gear.addEventListener('click', function (e) {
            e.preventDefault();
            e.stopPropagation();
            openSettingsModal();
        });
    }
    if (closeBtn) closeBtn.addEventListener('click', function () { closeSettingsModal(); });
    root.addEventListener('click', function (e) {
        if (e.target === root) closeSettingsModal();
    });
    var pan = root.querySelector('.settings-modal');
    if (pan) pan.addEventListener('click', function (e) { e.stopPropagation(); });
    for (var i = 0; i < 3; i++) {
        (function (idx) {
            var b = document.getElementById('settings-font-' + idx);
            if (b) b.addEventListener('click', function () { applyFontLevel(idx, true); });
        })(i);
    }
    var bd = document.getElementById('settings-theme-dark');
    var bl = document.getElementById('settings-theme-light');
    if (bd) bd.addEventListener('click', function () { applyUiTheme('dark', true); });
    if (bl) bl.addEventListener('click', function () { applyUiTheme('light', true); });
    var sc = document.getElementById('settings-session-compact');
    var sd = document.getElementById('settings-session-detailed');
    if (sc) sc.addEventListener('click', function () { applySessionListMode('compact', true); });
    if (sd) sd.addEventListener('click', function () { applySessionListMode('detailed', true); });
    var agentTeamOff = document.getElementById('settings-agent-team-off');
    var agentTeamOn = document.getElementById('settings-agent-team-on');
    if (agentTeamOff) agentTeamOff.addEventListener('click', function () { void saveAgentTeamFeature(false); });
    if (agentTeamOn) agentTeamOn.addEventListener('click', function () { void saveAgentTeamFeature(true); });
    var askUserOff = document.getElementById('settings-ask-user-off');
    var askUserOn = document.getElementById('settings-ask-user-on');
    if (askUserOff) askUserOff.addEventListener('click', function () { void saveAskUserFeature(false); });
    if (askUserOn) askUserOn.addEventListener('click', function () { void saveAskUserFeature(true); });
    var agentTeamManage = document.getElementById('settings-agent-team-manage');
    if (agentTeamManage) agentTeamManage.addEventListener('click', function () {
        closeSettingsModal();
        if (typeof openAgentTeamModal === 'function') void openAgentTeamModal();
    });
    var languageBtn = document.getElementById('sidebar-language-btn');
    if (languageBtn) {
        languageBtn.addEventListener('click', function () {
            applyUiLanguage(uiLanguage === 'en' ? 'zh-CN' : 'en', true);
        });
    }
    var envAdv = document.getElementById('settings-env-advanced');
    if (envAdv) {
        envAdv.addEventListener('click', function () {
            closeSettingsModal();
            var query = new URLSearchParams();
            if (currentSessionId) query.set('session_id', String(currentSessionId));
            if (window.__WORK_DIR__) query.set('workspace', String(window.__WORK_DIR__));
            var settingsUrl = '/setup/env' + (query.toString() ? ('?' + query.toString()) : '');
            var w = window.open(settingsUrl, 'myagent-env');
            if (w) {
                try { w.focus(); } catch (e) {}
            } else {
                window.location.href = settingsUrl;
            }
        });
    }
    var dashboardBtn = document.getElementById('settings-execution-dashboard');
    if (dashboardBtn) dashboardBtn.addEventListener('click', function () {
        closeSettingsModal();
        var w = window.open('/execution-dashboard', 'myagent-execution-dashboard');
        if (w) { try { w.focus(); } catch (e) {} }
        else window.location.href = '/execution-dashboard';
    });
}
initUiSettingsControls();
`,bt=`let currentSessionId = null;
/** Blocks repeat sends while the async send pipeline is claiming a sessionStore run slot. */
const sendPipelineLocksBySession = Object.create(null);
/** Optimistic preflight before the first session id has been allocated. */
let optimisticNewSessionRun = null;
const followupQueueBySession = Object.create(null);
const followupQueueLoadedBySession = Object.create(null);
let followupQueueSeq = 1;
const followupWatchTimers = Object.create(null);
const followupServerSyncInFlight = Object.create(null);
/** 会话级自动续发定时器；同一会话只保留一个最近到期的任务。 */
const followupDrainTimers = Object.create(null);
/** 会话级追问发送互斥链：显式立即发送共用，保证同一会话同一时刻只处理一条追问。 */
const followupDispatchChain = Object.create(null);
/** 手动“立即发送”代次；用于淘汰已排队但尚未开始的旧自动队首发送。 */
const followupManualDispatchEpochBySession = Object.create(null);
let followupSnapshotRecoveryInitialized = false;
/** 会话在后台跑完后未点开过：侧栏绿点，点开即清除（localStorage 持久化，刷新不丢） */
const sessionUnreadComplete = new Set();
const LS_SESSION_UNREAD = 'myagent-session-unread';
const sessionUnreadClearInFlight = Object.create(null);
/** 每个会话独立的输入草稿（切换会话恢复） */
const draftBySession = Object.create(null);
const LS_INPUT_DRAFT_PREFIX = 'myagent-input-draft-';
const LS_FOLLOWUP_QUEUE_PREFIX = 'myagent-followup-queue-';
const inputPathTokenMap = Object.create(null);
let inputPathRewriteGuard = false;
/** 本会话最近一次成功点击「发送」的用户消息全文（供工具确认失败后「重新发送」） */
const lastUserMessageBySession = Object.create(null);
/** 离开会话时主列表 scrollTop，切回时恢复（本页内；首次进入该会话无记录则置底） */
const LS_SESSION_SECTION_PREFIX = 'myagent-session-section-';
let streamPollTimer = null;
const messageRawMarkdown = new WeakMap();
let liveAutoFollow = true;
/** 生成中：对话区 / 执行过程区是否在底部附近（二者同时满足才跟流，见 refreshLiveAutoFollowPins） */
let streamChatNearBottom = true;
let streamProcNearBottom = true;
let mermaidInitialized = false;
let mermaidIdSeq = 0;
/** 重放历史消息时创建的过程块不记真实起止时间（仅显示步数与工具次数） */
let replayingMessages = false;

/** 历史消息分页：按「对话轮」（每条用户提问为一轮起点），每页条数见 HISTORY_DIALOGUES_PER_PAGE */
let sessionHistoryPaging = null;
let historyOlderLoading = false;
/** 每次加载末尾或更早一页时包含的用户提问轮数（含其间全部工具/过程事件） */
const HISTORY_DIALOGUES_PER_PAGE = 5;
/** Event-heavy turns can contain hundreds of tool/process rows; cap initial replay at turn boundaries. */
const HISTORY_EVENT_BUDGET = 500;

/** 右侧「历史记录」重建序号：防止切换会话后旧 fetch 与当前 DOM 合并导致目录串台 */
let tocRebuildEpoch = 0;
let todoRefreshEpoch = 0;
let tocActiveUpdateRaf = 0;
let tocScrollBottomOnNextBuild = false;
let suppressTocDuringSessionLoad = false;
let switchSessionEpoch = 0;
let messageLoadEpoch = 0;

/** 右侧「历史记录」链接悬停浮层（替代浏览器原生 title） */
let uiHoverTooltipEl = null;
let hoverTooltipMoveScheduled = false;
const UI_HOVER_TIP_DELAY_MS = 500;
let uiHoverTipTimer = null;
let uiHoverTipActiveEl = null;
let uiHoverTipLastEv = null;

let mermaidIoObserver = null;

const defaultCtxThreshold = (typeof window.__CONTEXT_WINDOW__ === 'number' && window.__CONTEXT_WINDOW__ > 0)
    ? window.__CONTEXT_WINDOW__
    : 90000;
let streamScrollFollowRaf = 0;
let subagentScrollFollowRaf = 0;
var subagentCardNearBottom = Object.create(null);
const SUBAGENT_CARD_NEAR_BOTTOM_PX = 48;
const USER_MESSAGE_COLLAPSE_LINES = 10;
const USER_MESSAGE_VIRTUAL_LINE_CHARS = 100;

var uiModalKeyHandler = null;

function isMyAgentFeatureEnabled(name, defaultValue) {
    var features = (typeof window !== 'undefined' && window.__MYAGENT_FEATURES__ && typeof window.__MYAGENT_FEATURES__ === 'object')
        ? window.__MYAGENT_FEATURES__
        : {};
    if (Object.prototype.hasOwnProperty.call(features, name)) return !!features[name];
    return !!defaultValue;
}

function clearSessionUnreadState(sessionId, opts) {
    var sid = String(sessionId || '');
    if (!sid) return;
    opts = opts || {};
    sessionUnreadComplete.delete(sid);
    persistSessionUnread();
    if (typeof sessionStore !== 'undefined') {
        var sess = sessionStore.get(sid);
        if (sess) {
            sess.unread_result = false;
            delete sess.unread_result_at;
            delete sess.unread_result_status;
        }
    }
    if (typeof syncSessionListIndicatorClasses === 'function') syncSessionListIndicatorClasses();
    if (opts.server === false || sessionUnreadClearInFlight[sid]) return;
    sessionUnreadClearInFlight[sid] = true;
    fetch('/sessions/' + encodeURIComponent(sid) + '/unread-result/clear', { method: 'POST' })
        .catch(function () { /* ignore */ })
        .finally(function () { delete sessionUnreadClearInFlight[sid]; });
}

function splitUserMessageVisualLines(text) {
    var raw = text == null ? '' : String(text);
    var physical = raw.split('\\n');
    var out = [];
    for (var i = 0; i < physical.length; i += 1) {
        var line = physical[i];
        if (line.length === 0) {
            out.push('');
            continue;
        }
        for (var j = 0; j < line.length; j += USER_MESSAGE_VIRTUAL_LINE_CHARS) {
            out.push(line.slice(j, j + USER_MESSAGE_VIRTUAL_LINE_CHARS));
        }
    }
    return out;
}

function buildUserMessageSummary(text) {
    var lines = splitUserMessageVisualLines(text);
    return lines.slice(0, USER_MESSAGE_COLLAPSE_LINES).join('\\n') + '\\n...';
}

function userMessageShouldCollapse(text) {
    return false;
}

// The backend appends this short, system-owned decoration when Skills are
// selected. Keep the user's message verbatim, but render the decoration as a
// runtime-owned span so the English UI can translate it without changing the
// stored/user-authored content.
function splitSelectedSkillsUiMessage(text) {
    var source = String(text == null ? '' : text);
    var match = source.match(/\\n\\n(?:(?:已选择|激活) Skill：|Activated Skill:[ \\t]*)([^\\n]*)$/);
    if (!match || !String(match[1] || '').trim()) return null;
    return {
        message: source.slice(0, match.index),
        decoration: 'Activated Skill: ' + String(match[1] || '').trim().replace(/、/g, ', '),
    };
}

function renderSelectedSkillsUiMessage(container, text, linkifier) {
    if (!container) return;
    var source = String(text == null ? '' : text);
    var parts = splitSelectedSkillsUiMessage(source);
    container.textContent = '';
    if (!parts) {
        container.textContent = source;
    } else {
        container.appendChild(document.createTextNode(parts.message));
        container.appendChild(document.createTextNode('\\n\\n'));
        var decoration = document.createElement('span');
        decoration.className = 'user-msg-selected-skills';
        if (typeof setUiRuntimeText === 'function') setUiRuntimeText(decoration, parts.decoration);
        else decoration.textContent = parts.decoration;
        container.appendChild(decoration);
    }
    if (typeof linkifier === 'function') linkifier(container);
}

function renderUserMessageContent(wrap, div, rawStr, linkifier) {
    var applyLinks = typeof linkifier === 'function' ? linkifier : null;

    function setPlain() {
        renderSelectedSkillsUiMessage(div, rawStr, applyLinks);
    }

    function setCollapsed() {
        if (div.classList.contains('is-collapsible')) return;
        wrap.classList.add('has-turn-process');
        div.classList.add('is-collapsible');
        div.textContent = '';
        var sum = document.createElement('div');
        sum.className = 'user-msg-summary';
        renderSelectedSkillsUiMessage(sum, buildUserMessageSummary(rawStr), applyLinks);
        var ful = document.createElement('div');
        ful.className = 'user-msg-full';
        renderSelectedSkillsUiMessage(ful, rawStr, applyLinks);
        var ch = document.createElement('div');
        ch.className = 'user-msg-chevron';
        var arrow = document.createElement('span');
        arrow.className = 'chevron-arrow';
        ch.appendChild(arrow);
        ch.addEventListener('click', function(e) {
            e.stopPropagation();
            wrap.classList.toggle('user-msg-expanded');
        });
        div.appendChild(sum);
        div.appendChild(ful);
        div.appendChild(ch);
    }

    setPlain();
    requestAnimationFrame(function () {
        if (!div.isConnected || div.classList.contains('is-collapsible')) return;
        var cs = window.getComputedStyle ? window.getComputedStyle(div) : null;
        var lineHeight = cs ? parseFloat(cs.lineHeight) : NaN;
        if (!Number.isFinite(lineHeight) || lineHeight <= 0) {
            var fontSize = cs ? parseFloat(cs.fontSize) : NaN;
            lineHeight = Number.isFinite(fontSize) && fontSize > 0 ? fontSize * 1.65 : 18;
        }
        if (div.scrollHeight > lineHeight * USER_MESSAGE_COLLAPSE_LINES + 1) {
            setCollapsed();
        }
    });
}

function closeUiModal(result) {
    var root = document.getElementById('ui-modal-root');
    if (!root) return;
    root.classList.remove('is-open');
    root.setAttribute('aria-hidden', 'true');
    root.onclick = null;
    var okBtn = document.getElementById('ui-modal-ok');
    var cancelBtn = document.getElementById('ui-modal-cancel');
    if (okBtn) okBtn.onclick = null;
    if (cancelBtn) cancelBtn.onclick = null;
    if (uiModalKeyHandler) {
        document.removeEventListener('keydown', uiModalKeyHandler);
        uiModalKeyHandler = null;
    }
    document.body.style.overflow = '';
    var p = root._resolve;
    root._resolve = null;
    if (typeof p === 'function') p(result);
}

var UI_MODAL_SVG_TRASH = '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M3 6h18"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6"/><path d="M8 6V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/><line x1="10" y1="11" x2="10" y2="17"/><line x1="14" y1="11" x2="14" y2="17"/></svg>';
var UI_MODAL_SVG_INFO = '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><circle cx="12" cy="12" r="10"/><path d="M12 16v-4M12 8h.01"/></svg>';

function openUiModal(options) {
    return new Promise(function (resolve) {
        var root = document.getElementById('ui-modal-root');
        var titleEl = document.getElementById('ui-modal-title');
        var subEl = document.getElementById('ui-modal-subtitle');
        var bodyEl = document.getElementById('ui-modal-desc');
        var iconEl = document.getElementById('ui-modal-icon');
        var okBtn = document.getElementById('ui-modal-ok');
        var cancelBtn = document.getElementById('ui-modal-cancel');
        if (!root || !titleEl || !bodyEl || !okBtn || !cancelBtn || !iconEl) {
            resolve(false);
            return;
        }
        root._resolve = resolve;
        var o = options || {};
        titleEl.textContent = o.title || '提示';
        if (subEl) {
            subEl.textContent = o.subtitle || '';
            subEl.style.display = (o.subtitle) ? '' : 'none';
        }
        bodyEl.textContent = o.message || '';
        bodyEl.style.display = (o.message) ? '' : 'none';
        var showCancel = o.showCancel !== false;
        cancelBtn.style.display = showCancel ? '' : 'none';
        okBtn.textContent = o.confirmText || (showCancel ? '确定' : '知道了');
        cancelBtn.textContent = o.cancelText || '取消';

        var danger = !!o.danger;
        iconEl.className = 'ui-modal__icon ' + (danger ? 'ui-modal__icon--danger' : 'ui-modal__icon--info');
        iconEl.innerHTML = danger ? UI_MODAL_SVG_TRASH : UI_MODAL_SVG_INFO;

        okBtn.className = 'ui-modal-btn ' + (danger ? 'ui-modal-btn--danger' : 'ui-modal-btn--primary');

        function onOk() { closeUiModal(true); }
        function onCancel() { closeUiModal(false); }
        okBtn.onclick = onOk;
        cancelBtn.onclick = onCancel;
        root.onclick = function (e) { if (e.target === root) onCancel(); };

        uiModalKeyHandler = function (e) {
            if (e.key === 'Escape') { e.preventDefault(); onCancel(); }
            else if (e.key === 'Enter' && !e.shiftKey && !e.ctrlKey && !e.metaKey && document.activeElement !== cancelBtn) {
                e.preventDefault();
                onOk();
            }
        };
        document.addEventListener('keydown', uiModalKeyHandler);

        root.classList.add('is-open');
        root.setAttribute('aria-hidden', 'false');
        document.body.style.overflow = 'hidden';
        requestAnimationFrame(function () { okBtn.focus(); });
    });
}

function showUiAlert(opts) {
    var o = opts || {};
    var root = document.getElementById('ui-modal-root');
    var token = Date.now() + ':' + Math.random();
    if (root && o.autoCloseMs) root.dataset.alertToken = token;
    var p = openUiModal({
        title: o.title || '提示',
        subtitle: o.subtitle,
        message: o.message || '',
        variant: o.variant || 'info',
        danger: false,
        showCancel: false,
        confirmText: o.confirmText || '知道了',
    });
    if (root && o.autoCloseMs) {
        setTimeout(function () {
            if (!root.classList.contains('is-open')) return;
            if (root.dataset.alertToken !== token) return;
            closeUiModal(true);
        }, Math.max(800, Number(o.autoCloseMs) || 0));
    }
    return p;
}
`,yt=`var agentTeamModalKeyHandler = null;
var agentTeamBusy = false;

function agentTeamSessionId() {
    return typeof currentSessionId !== 'undefined' && currentSessionId
        ? String(currentSessionId)
        : '';
}

function setAgentTeamError(message) {
    var row = document.getElementById('agent-team-error');
    if (!row) return;
    row.textContent = String(message || '');
    row.classList.toggle('hidden', !message);
}

async function agentTeamApi(path, options) {
    var response = await fetch(path, options || { cache: 'no-store' });
    var data = await response.json();
    if (!response.ok || !data || data.ok !== true) {
        throw new Error((data && data.error) || ('HTTP ' + response.status));
    }
    return data.data;
}

function agentTeamRow(title, meta, badge) {
    var row = document.createElement('div');
    row.className = 'agent-team-row';
    var copy = document.createElement('div');
    copy.className = 'agent-team-row__copy';
    var strong = document.createElement('strong');
    strong.textContent = String(title || '—');
    var small = document.createElement('span');
    small.textContent = String(meta || '');
    copy.appendChild(strong);
    copy.appendChild(small);
    var state = document.createElement('span');
    state.className = 'agent-team-badge';
    state.textContent = String(badge || '—');
    row.appendChild(copy);
    row.appendChild(state);
    return row;
}

function renderAgentTeam(team) {
    var empty = document.getElementById('agent-team-empty');
    var content = document.getElementById('agent-team-content');
    var toolbar = document.querySelector('.agent-team-toolbar');
    if (empty) empty.classList.toggle('hidden', !!team);
    if (content) content.classList.toggle('hidden', !team);
    if (toolbar) toolbar.classList.toggle('hidden', !team);
    if (!team) return;

    var members = Object.values(team.members || {});
    var tasks = Object.values(team.tasks || {});
    var permissions = Object.values(team.permissions || {});
    var summary = document.getElementById('agent-team-summary');
    if (summary) {
        summary.textContent = (team.title || team.team_id || 'Agent Team')
            + ' · ' + (team.status || 'unknown')
            + ' · ' + members.length + ' 成员 · ' + tasks.length + ' 任务';
    }

    var memberRoot = document.getElementById('agent-team-members');
    if (memberRoot) {
        memberRoot.replaceChildren();
        members.forEach(function (member) {
            memberRoot.appendChild(agentTeamRow(
                member.name || member.member_id,
                (member.role || '') + (member.child_session_id ? ' · ' + member.child_session_id.slice(0, 8) : ''),
                member.state || 'unknown'
            ));
        });
        if (!members.length) memberRoot.appendChild(agentTeamRow('暂无成员', '请让 Agent 使用 team spawn_member', 'empty'));
    }

    var taskRoot = document.getElementById('agent-team-tasks');
    if (taskRoot) {
        taskRoot.replaceChildren();
        tasks.forEach(function (task) {
            taskRoot.appendChild(agentTeamRow(
                task.title || task.task_id,
                (task.priority || 'normal') + (task.assignee_id ? ' · ' + task.assignee_id.slice(0, 12) : ''),
                task.status || 'pending'
            ));
        });
        if (!tasks.length) taskRoot.appendChild(agentTeamRow('暂无任务', '', 'empty'));
    }

    var permissionRoot = document.getElementById('agent-team-permissions');
    if (permissionRoot) {
        permissionRoot.replaceChildren();
        permissions.slice().reverse().forEach(function (permission) {
            var row = agentTeamRow(
                permission.action || permission.permission_id,
                (permission.member_id || '') + (permission.resource ? ' · ' + permission.resource : ''),
                permission.status || 'pending'
            );
            if (permission.status === 'pending') {
                var actions = document.createElement('div');
                actions.className = 'agent-team-row__actions';
                ['allowed', 'denied'].forEach(function (decision) {
                    var button = document.createElement('button');
                    button.type = 'button';
                    button.className = 'agent-team-mini-btn';
                    button.textContent = decision === 'allowed' ? '允许一次' : '拒绝';
                    button.addEventListener('click', function () {
                        void resolveAgentTeamPermission(permission.permission_id, decision);
                    });
                    actions.appendChild(button);
                });
                row.appendChild(actions);
            }
            permissionRoot.appendChild(row);
        });
        if (!permissions.length) permissionRoot.appendChild(agentTeamRow('暂无权限请求', '', 'clear'));
    }
}

async function refreshAgentTeamPanel() {
    var sid = agentTeamSessionId();
    var subtitle = document.getElementById('agent-team-modal-subtitle');
    if (!sid) {
        setAgentTeamError('请先选择或新建一个会话。');
        renderAgentTeam(null);
        return;
    }
    if (subtitle) subtitle.textContent = '会话 ' + sid;
    setAgentTeamError('');
    try {
        renderAgentTeam(await agentTeamApi('/api/agent-team/' + encodeURIComponent(sid)));
    } catch (error) {
        setAgentTeamError(error && error.message ? error.message : error);
    }
}

async function mutateAgentTeam(path, payload, method) {
    if (agentTeamBusy) return;
    agentTeamBusy = true;
    setAgentTeamError('');
    try {
        await agentTeamApi(path, {
            method: method || 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: payload === undefined ? undefined : JSON.stringify(payload),
        });
        await refreshAgentTeamPanel();
    } catch (error) {
        setAgentTeamError(error && error.message ? error.message : error);
    } finally {
        agentTeamBusy = false;
    }
}

async function resolveAgentTeamPermission(permissionId, decision) {
    var sid = agentTeamSessionId();
    if (!sid) return;
    await mutateAgentTeam(
        '/api/agent-team/' + encodeURIComponent(sid) + '/permissions/' + encodeURIComponent(permissionId) + '/resolve',
        { decision: decision, resolved_by: 'lead' }
    );
}

async function openAgentTeamModal() {
    var root = document.getElementById('agent-team-modal-root');
    var panel = root && root.querySelector('.agent-team-modal');
    if (!root || !panel) return;
    root.classList.add('is-open');
    root.setAttribute('aria-hidden', 'false');
    document.body.style.overflow = 'hidden';
    try { panel.focus(); } catch (e) {}
    agentTeamModalKeyHandler = function (event) {
        if (event.key === 'Escape') closeAgentTeamModal();
    };
    document.addEventListener('keydown', agentTeamModalKeyHandler);
    await refreshAgentTeamPanel();
}

function closeAgentTeamModal() {
    var root = document.getElementById('agent-team-modal-root');
    if (!root) return;
    root.classList.remove('is-open');
    root.setAttribute('aria-hidden', 'true');
    document.body.style.overflow = '';
    if (agentTeamModalKeyHandler) {
        document.removeEventListener('keydown', agentTeamModalKeyHandler);
        agentTeamModalKeyHandler = null;
    }
}

function initAgentTeamControls() {
    var root = document.getElementById('agent-team-modal-root');
    var close = document.getElementById('agent-team-modal-close');
    if (close) close.addEventListener('click', closeAgentTeamModal);
    if (root) root.addEventListener('click', function (event) {
        if (event.target === root) closeAgentTeamModal();
    });
    var refresh = document.getElementById('agent-team-refresh');
    if (refresh) refresh.addEventListener('click', function () { void refreshAgentTeamPanel(); });
    var create = document.getElementById('agent-team-create');
    if (create) create.addEventListener('click', function () {
        var sid = agentTeamSessionId();
        var input = document.getElementById('agent-team-title-input');
        if (sid) void mutateAgentTeam('/api/agent-team/' + encodeURIComponent(sid), { title: input ? input.value : '' });
    });
    var createTask = document.getElementById('agent-team-task-create');
    if (createTask) createTask.addEventListener('click', function () {
        var sid = agentTeamSessionId();
        var input = document.getElementById('agent-team-task-title');
        var title = input ? input.value.trim() : '';
        if (sid && title) void mutateAgentTeam('/api/agent-team/' + encodeURIComponent(sid) + '/tasks', { title: title });
    });
    [['agent-team-shutdown', 'shutdown'], ['agent-team-complete-shutdown', 'shutdown/complete'], ['agent-team-archive', 'archive']].forEach(function (entry) {
        var button = document.getElementById(entry[0]);
        if (button) button.addEventListener('click', function () {
            var sid = agentTeamSessionId();
            if (sid) void mutateAgentTeam('/api/agent-team/' + encodeURIComponent(sid) + '/' + entry[1], {});
        });
    });
}

initAgentTeamControls();
`,wt=`const ARCHIVED_SESSIONS_PAGE_SIZE = 20;

const sessionStore = {
    seq: 0,\r
    sessionsById: new Map(),\r
    sessionOrder: [],\r
    currentSessionId: null,\r
    runsBySession: new Map(),\r
    terminalRunIdsBySession: new Map(),\r
    activeRunInfoBySession: new Map(),\r
    archivedCount: 0,
    archivedLoaded: false,
    archivedSessions: null,
    archivedVisibleCount: 0,
    unreadComplete: new Set(),\r
    sseSeqBySession: new Map(),\r
    deletedSessionTombstones: new Map(),\r
    ui: {\r
        loadingSessions: false,\r
        loadingMessages: false,\r
    },\r
    streamActiveById: Object.create(null),\r
\r
    applySnapshot(sessions, archivedCount) {\r
        this.pruneDeletedSessionTombstones();\r
        const nextById = new Map();\r
        const nextOrder = [];\r
        const nextStreamActive = Object.create(null);\r
        const list = Array.isArray(sessions) ? sessions : [];\r
        let unreadChanged = false;\r
        for (let i = 0; i < list.length; i += 1) {\r
            const s = list[i];\r
            if (!s || !s.id) continue;\r
            const sid = String(s.id);\r
            if (this.isDeletedSessionTombstoned(sid)) continue;\r
            const nextSession = Object.assign({}, s);\r
            if (typeof isSessionStreamStopSuppressed === 'function' && isSessionStreamStopSuppressed(sid)) {\r
                nextSession.stream_active = false;\r
                nextSession.run_active = false;\r
                nextSession.run_started_at = null;\r
            }\r
            if (typeof sessionUnreadComplete !== 'undefined') {\r
                if (nextSession.unread_result) {\r
                    if (!sessionUnreadComplete.has(sid)) {\r
                        sessionUnreadComplete.add(sid);\r
                        unreadChanged = true;\r
                    }\r
                } else if (sessionUnreadComplete.delete(sid)) {\r
                    unreadChanged = true;\r
                }\r
            }\r
            nextById.set(sid, nextSession);\r
            nextOrder.push(sid);\r
            nextStreamActive[sid] = !!nextSession.stream_active;\r
        }\r
        this.sessionsById = nextById;\r
        this.sessionOrder = nextOrder;\r
        this.streamActiveById = nextStreamActive;\r
        if (Number.isFinite(Number(archivedCount)) && Number(archivedCount) >= 0) {\r
            this.archivedCount = Number(archivedCount);\r
        }\r
        if (unreadChanged && typeof persistSessionUnread === 'function') persistSessionUnread();\r
    },\r
\r
    upsert(session) {\r
        if (!session || !session.id) return;\r
        const sid = String(session.id);\r
        if (this.isDeletedSessionTombstoned(sid)) return;\r
        const existed = this.sessionOrder.indexOf(sid) >= 0;\r
        this.sessionsById.set(sid, session);\r
        if (!existed) {\r
            this.sessionOrder.unshift(sid);\r
        }\r
        // 任何字段更新都可能改变 last_activity_at / pinned_at，需立即重排，\r
        // 否则老会话有了新对话后仍停留在原分组、原位置（仅靠 800ms 后的\r
        // applySnapshot 兜底，期间 UI 顺序与时间分组不一致）。\r
        this._reorderSessionOrder();\r
        if (Object.prototype.hasOwnProperty.call(session, 'stream_active')) {\r
            this.streamActiveById[sid] = !!session.stream_active;\r
        }\r
    },\r
\r
    // 与后端 list_sessions 的 sort_key 保持一致：\r
    //   pinned 在前；pinned 之间按 pinned_at 倒序；非 pinned 按 last_activity_at 倒序。\r
    // 缺失时间字段时回退到 updated_at / created_at，仍解析失败则视为 0（沉底）。\r
    _activityTimeMs(session) {\r
        if (!session) return 0;\r
        var raw = session.last_activity_at || session.updated_at || session.created_at || '';\r
        var t = Date.parse(String(raw || ''));\r
        return Number.isFinite(t) ? t : 0;\r
    },\r
\r
    _pinnedTimeMs(session) {\r
        if (!session) return 0;\r
        var raw = session.pinned_at || session.updated_at || session.created_at || '';\r
        var t = Date.parse(String(raw || ''));\r
        return Number.isFinite(t) ? t : 0;\r
    },\r
\r
    _reorderSessionOrder() {\r
        const self = this;\r
        this.sessionOrder.sort(function (aId, bId) {\r
            const a = self.sessionsById.get(aId);\r
            const b = self.sessionsById.get(bId);\r
            if (!a) return 1;\r
            if (!b) return -1;\r
            const aPinned = !!a.pinned;\r
            const bPinned = !!b.pinned;\r
            if (aPinned !== bPinned) return aPinned ? -1 : 1;\r
            if (aPinned) return self._pinnedTimeMs(b) - self._pinnedTimeMs(a);\r
            return self._activityTimeMs(b) - self._activityTimeMs(a);\r
        });\r
    },\r
\r
    remove(sessionId) {\r
        const sid = String(sessionId || '');\r
        if (!sid) return;\r
        this.sessionsById.delete(sid);\r
        delete this.streamActiveById[sid];\r
        this.runsBySession.delete(sid);\r
        this.terminalRunIdsBySession.delete(sid);\r
        this.activeRunInfoBySession.delete(sid);\r
        this.unreadComplete.delete(sid);\r
        this.sessionOrder = this.sessionOrder.filter(function (id) { return id !== sid; });\r
    },\r
\r
    markDeletedSession(sessionId) {\r
        const sid = String(sessionId || '');\r
        if (!sid) return;\r
        this.deletedSessionTombstones.set(sid, Date.now());\r
        this.remove(sid);\r
    },\r
\r
    clearDeletedSessionTombstone(sessionId) {\r
        const sid = String(sessionId || '');\r
        if (!sid) return;\r
        this.deletedSessionTombstones.delete(sid);\r
    },\r
\r
    pruneDeletedSessionTombstones() {\r
        const now = Date.now();\r
        const ttl = 120000;\r
        this.deletedSessionTombstones.forEach(function (createdAt, sid, map) {\r
            if (now - Number(createdAt || 0) > ttl) map.delete(sid);\r
        });\r
    },\r
\r
    isDeletedSessionTombstoned(sessionId) {\r
        this.pruneDeletedSessionTombstones();\r
        return this.deletedSessionTombstones.has(String(sessionId || ''));\r
    },\r
\r
    list() {\r
        const out = [];\r
        for (let i = 0; i < this.sessionOrder.length; i += 1) {\r
            const s = this.sessionsById.get(this.sessionOrder[i]);\r
            if (s) out.push(s);\r
        }\r
        return out;\r
    },\r
\r
    get(sessionId) {\r
        return this.sessionsById.get(String(sessionId || '')) || null;\r
    },\r
\r
    setCurrentSession(sessionId) {\r
        this.currentSessionId = sessionId ? String(sessionId) : null;\r
    },\r
\r
    setArchivedCount(count) {\r
        if (Number.isFinite(Number(count)) && Number(count) >= 0) {\r
            this.archivedCount = Number(count);\r
        }\r
    },\r
\r
    setArchivedLoaded(sessions, options) {
        options = options || {};
        const filtered = Array.isArray(sessions)
            ? sessions.filter(function (s) { return s && s.id && !!s.archived; })
            : [];
        const requestedTotal = options.totalCount != null ? Number(options.totalCount) : filtered.length;
        const totalCount = Number.isFinite(requestedTotal)
            ? Math.max(0, requestedTotal)
            : filtered.length;
        const list = filtered.slice(0, totalCount);
        const requestedVisible = options.visibleCount != null ? Number(options.visibleCount) : list.length;
        this.archivedLoaded = true;
        this.archivedSessions = list;
        this.archivedVisibleCount = Math.max(0, Math.min(
            list.length,
            Number.isFinite(requestedVisible) ? requestedVisible : list.length
        ));
        this.archivedCount = totalCount;
    },
\r
    clearArchivedLoaded() {
        this.archivedLoaded = false;
        this.archivedSessions = null;
        this.archivedVisibleCount = 0;
    },

    archivedList() {
        if (!this.archivedLoaded || !Array.isArray(this.archivedSessions)) return [];
        return this.archivedSessions.slice(0, this.archivedVisibleCount);
    },

    revealNextArchivedPage() {
        if (!this.archivedLoaded || !Array.isArray(this.archivedSessions)) return 0;
        const previous = this.archivedVisibleCount;
        this.archivedVisibleCount = Math.min(
            this.archivedSessions.length,
            previous + ARCHIVED_SESSIONS_PAGE_SIZE
        );
        return this.archivedVisibleCount - previous;
    },

    hasMoreArchivedSessions() {
        return this.archivedVisibleCount < this.archivedCount;
    },
\r
    isStreamActive(sessionId) {\r
        const sid = String(sessionId || '');\r
        if (!sid) return false;\r
        if (Object.prototype.hasOwnProperty.call(this.streamActiveById, sid)) {\r
            return !!this.streamActiveById[sid];\r
        }\r
        const sess = this.get(sid);\r
        return !!(sess && sess.stream_active);\r
    },\r
\r
    setStreamActive(sessionId, active) {\r
        const sid = String(sessionId || '');\r
        if (!sid) return;\r
        this.streamActiveById[sid] = !!active;\r
        const sess = this.sessionsById.get(sid);\r
        if (sess) sess.stream_active = !!active;\r
    },\r
\r
    applyStreamActiveMap(activeMap) {\r
        const next = Object.create(null);\r
        const src = activeMap || {};\r
        Object.keys(src).forEach(function (sid) {\r
            next[String(sid)] = !!src[sid];\r
        });\r
        this.streamActiveById = next;\r
        this.sessionsById.forEach(function (sess, sid) {\r
            sess.stream_active = !!next[sid];\r
            sess.run_active = !!next[sid];\r
            if (!next[sid]) sess.run_started_at = null;\r
        });\r
    },\r
\r
    setRun(sessionId, run) {\r
        const sid = String(sessionId || '');\r
        if (!sid) return;\r
        if (run) this.runsBySession.set(sid, run);\r
        else this.runsBySession.delete(sid);\r
    },\r
\r
    getRun(sessionId) {\r
        return this.runsBySession.get(String(sessionId || '')) || null;\r
    },\r
\r
    hasRun(sessionId) {\r
        return this.runsBySession.has(String(sessionId || ''));\r
    },\r
\r
    markTerminalRun(sessionId, runId) {\r
        const sid = String(sessionId || '');\r
        const rid = String(runId || '').trim();\r
        if (!sid || !rid) return;\r
        let bucket = this.terminalRunIdsBySession.get(sid);\r
        if (!bucket) {\r
            bucket = new Set();\r
            this.terminalRunIdsBySession.set(sid, bucket);\r
        }\r
        bucket.add(rid);\r
    },\r
\r
    isTerminalRun(sessionId, runId) {\r
        const sid = String(sessionId || '');\r
        const rid = String(runId || '').trim();\r
        if (!sid || !rid) return false;\r
        const bucket = this.terminalRunIdsBySession.get(sid);\r
        return !!(bucket && bucket.has(rid));\r
    },\r
\r
    applyActiveRuns(activeRuns) {\r
        const next = new Map();\r
        const list = Array.isArray(activeRuns) ? activeRuns : [];\r
        list.forEach(function (run) {\r
            const sid = typeof run === 'string' ? run : (run && run.session_id);\r
            if (!sid) return;\r
            const runId = typeof run === 'string' ? '' : String((run && (run.run_id || run.runId)) || '').trim();\r
            if (runId && this.isTerminalRun(sid, runId)) return;\r
            if (typeof isSessionStreamStopSuppressed === 'function' && isSessionStreamStopSuppressed(sid)) return;\r
            next.set(String(sid), typeof run === 'string' ? { session_id: String(sid) } : Object.assign({}, run));\r
        }, this);\r
        this.activeRunInfoBySession = next;\r
    },\r
\r
    activeRunIds() {\r
        return Array.from(this.activeRunInfoBySession.keys());\r
    },\r
\r
    getActiveRunInfo(sessionId) {\r
        return this.activeRunInfoBySession.get(String(sessionId || '')) || null;\r
    },\r
\r
    shouldAcceptSseEvent(sessionId, seq, scope) {
        const sid = String(sessionId || '');
        const n = Number(seq);
        if (!sid || !Number.isFinite(n) || n <= 0) return true;
        const seqScope = String(scope || 'default');
        const key = sid + '::' + seqScope;
        const prev = Number(this.sseSeqBySession.get(key) || 0);
        if (n <= prev) return false;
        this.sseSeqBySession.set(key, n);
        if (Number.isFinite(Number(this.seq)) && n > Number(this.seq)) this.seq = n;
        return true;
    },\r
\r
    resetSseSeq(sessionId) {\r
        const sid = String(sessionId || '');
        if (!sid) return;
        this.sseSeqBySession.delete(sid);
        Array.from(this.sseSeqBySession.keys()).forEach(function (key) {
            if (String(key).indexOf(sid + '::') === 0) this.sseSeqBySession.delete(key);
        }, this);
    },\r
};\r
\r
const SESSION_STREAM_STOP_SUPPRESS_MS = 60000;\r
const sessionStreamStopSuppressUntil = Object.create(null);\r
\r
function isSessionStreamStopSuppressed(sessionId) {\r
    const sid = String(sessionId || '');\r
    if (!sid) return false;\r
    const until = Number(sessionStreamStopSuppressUntil[sid] || 0);\r
    if (!until) return false;\r
    if (Date.now() <= until) return true;\r
    delete sessionStreamStopSuppressUntil[sid];\r
    return false;\r
}\r
\r
function clearSessionStreamStopSuppress(sessionId) {\r
    const sid = String(sessionId || '');\r
    if (!sid) return;\r
    delete sessionStreamStopSuppressUntil[sid];\r
}\r
\r
function suppressSessionServerStreamActive(sessionId, ms) {\r
    const sid = String(sessionId || '');\r
    if (!sid) return;\r
    sessionStreamStopSuppressUntil[sid] = Date.now() + (Number(ms) > 0 ? Number(ms) : SESSION_STREAM_STOP_SUPPRESS_MS);\r
    sessionStore.setStreamActive(sid, false);\r
    sessionStore.activeRunInfoBySession.delete(sid);\r
    const sess = sessionStore.get(sid);\r
    if (sess) {\r
        sess.stream_active = false;\r
        sess.run_active = false;\r
        sess.run_started_at = null;\r
    }\r
}\r
\r
function setSessionServerStreamActive(sessionId, active) {\r
    const sid = String(sessionId || '');\r
    if (!sid) return;\r
    if (active && isSessionStreamStopSuppressed(sid)) active = false;\r
    sessionStore.setStreamActive(sid, !!active);\r
}\r
\r
function isServerStreamActive(sessionId) {\r
    const sid = String(sessionId || '');\r
    if (!sid) return false;\r
    if (isSessionStreamStopSuppressed(sid)) return false;\r
    return sessionStore.isStreamActive(sid);\r
}\r
\r
function applyServerStreamActiveMap(activeMap) {\r
    const src = activeMap || Object.create(null);\r
    const m = Object.create(null);\r
    Object.keys(src).forEach(function (sid) {\r
        var active = !!src[sid];\r
        if (active && isSessionStreamStopSuppressed(sid)) active = false;\r
        m[sid] = active;\r
    });\r
    sessionStore.applyStreamActiveMap(m);\r
}\r
`,It=`function selectCurrentSession() {
    return sessionStore.get(sessionStore.currentSessionId);
}

function selectAllSessions() {
    return sessionStore.list();
}

function selectArchivedSessions() {
    return sessionStore.archivedList();
}

function sessionActivityTimeMs(session) {
    if (!session) return 0;
    var raw = session.last_activity_at || session.updated_at || session.created_at || '';
    var t = Date.parse(String(raw || ''));
    return Number.isFinite(t) ? t : 0;
}

function selectNormalSessionTimeGroups(normalList) {
    var groups = [
        { key: 'today', title: '今天', sessions: [] },
        { key: 'yesterday', title: '昨天', sessions: [] },
        { key: 'week', title: '近7天', sessions: [] },
        { key: 'fortnight', title: '近14天', sessions: [] },
    ];
    var now = new Date();
    var startToday = new Date(now.getFullYear(), now.getMonth(), now.getDate()).getTime();
    var startYesterday = startToday - 86400000;
    var sevenDaysAgo = Date.now() - (7 * 86400000);
    var fourteenDaysAgo = Date.now() - (14 * 86400000);
    for (var i = 0; i < normalList.length; i += 1) {
        var s = normalList[i];
        var t = sessionActivityTimeMs(s);
        if (t >= startToday) groups[0].sessions.push(s);
        else if (t >= startYesterday) groups[1].sessions.push(s);
        else if (t >= sevenDaysAgo) groups[2].sessions.push(s);
        else if (t >= fourteenDaysAgo) groups[3].sessions.push(s);
    }
    return groups.filter(function (g) { return g.sessions.length > 0; });
}

function selectSessionSections() {
    const pinnedList = [];
    const normalList = [];
    const allSessions = selectAllSessions();
    for (let i = 0; i < allSessions.length; i += 1) {
        const s = allSessions[i];
        if (!s || !s.id || !!s.archived) continue;
        if (s.pinned) pinnedList.push(s);
        else normalList.push(s);
    }
    return {
        pinned: pinnedList,
        normal: normalList,
        normalGroups: selectNormalSessionTimeGroups(normalList),
        archived: selectArchivedSessions(),
    };
}

function selectArchivedDisplayCount() {
    return sessionStore.archivedCount;
}

function selectIsSessionRunning(sessionId) {
    if (!sessionId) return false;
    if (typeof isSessionStreamStopSuppressed === 'function' && isSessionStreamStopSuppressed(sessionId)) return false;
    if (sessionStore.hasRun(sessionId)) return true;
    const info = sessionStore.getActiveRunInfo(sessionId);
    if (info && Object.prototype.hasOwnProperty.call(info, 'run_active')) {
        return !!info.run_active;
    }
    const sess = sessionStore.get(sessionId);
    if (sess && Object.prototype.hasOwnProperty.call(sess, 'run_active')) {
        return !!sess.run_active;
    }
    return false;
}

function selectRunForSession(sessionId) {
    return sessionStore.getRun(sessionId);
}
`,xt=`function applySessionSnapshot(snapshot) {\r
    snapshot = snapshot || {};\r
    const sessions = Array.isArray(snapshot.sessions) ? snapshot.sessions : [];\r
    const archivedCount = snapshot.archived_count != null ? snapshot.archived_count : snapshot.archivedCount;\r
    const previousActive = new Set();\r
    sessionStore.activeRunInfoBySession.forEach(function (_run, sid) {\r
        if (sid) previousActive.add(String(sid));\r
    });\r
    if (Number.isFinite(Number(snapshot.seq)) && Number(snapshot.seq) > sessionStore.seq) {\r
        sessionStore.seq = Number(snapshot.seq);\r
    }\r
    sessionStore.applySnapshot(sessions, archivedCount);\r
    if (sessionStore.archivedLoaded && (snapshot.include_archived || snapshot.includeArchived)) {\r
        const loadedCount = Array.isArray(sessionStore.archivedSessions)\r
            ? sessionStore.archivedSessions.length\r
            : 0;\r
        const visibleCount = sessionStore.archivedVisibleCount;\r
        const archived = sessions.filter(function (s) { return s && s.id && !!s.archived; });\r
        sessionStore.setArchivedLoaded(archived.slice(0, loadedCount), {\r
            visibleCount: visibleCount,\r
            totalCount: archivedCount,\r
        });\r
    }\r
    if (snapshot.current_session_id || snapshot.currentSessionId) {\r
        sessionStore.setCurrentSession(snapshot.current_session_id || snapshot.currentSessionId);\r
    }\r
    if (Array.isArray(snapshot.active_runs)) {\r
        sessionStore.applyActiveRuns(snapshot.active_runs);\r
        const active = Object.create(null);\r
        sessionStore.activeRunInfoBySession.forEach(function (_run, sid) {\r
            if (sid) active[String(sid)] = true;\r
        });\r
        applyServerStreamActiveMap(active);\r
        if (typeof recoverFollowupQueueDrainsFromSessionSnapshot === 'function') {\r
            recoverFollowupQueueDrainsFromSessionSnapshot(previousActive, new Set(Object.keys(active)));\r
        }\r
    }\r
}\r
\r
function applySessionPatch(patch) {\r
    patch = patch || {};\r
    if (Number.isFinite(Number(patch.seq)) && Number(patch.seq) <= sessionStore.seq) return;\r
    if (Number.isFinite(Number(patch.seq))) sessionStore.seq = Number(patch.seq);\r
    if (patch.session) sessionStore.upsert(patch.session);\r
    if (patch.remove_session_id || patch.removedSessionId) {\r
        sessionStore.remove(patch.remove_session_id || patch.removedSessionId);\r
    }\r
    if (patch.current_session_id || patch.currentSessionId) {\r
        sessionStore.setCurrentSession(patch.current_session_id || patch.currentSessionId);\r
    }\r
    if (patch.archived_count != null || patch.archivedCount != null) {\r
        sessionStore.setArchivedCount(patch.archived_count != null ? patch.archived_count : patch.archivedCount);\r
    }\r
    if (patch.stream_active != null && (patch.session_id || patch.sessionId)) {\r
        setSessionServerStreamActive(patch.session_id || patch.sessionId, !!patch.stream_active);\r
    }\r
}\r
\r
function setCurrentSessionState(sessionId) {\r
    currentSessionId = sessionId || null;\r
    sessionStore.setCurrentSession(currentSessionId);\r
    if (typeof refreshPermissionModeSelector === 'function') refreshPermissionModeSelector(currentSessionId);\r
}\r
\r
function setSessionRunState(sessionId, run) {\r
    const sid = String(sessionId || '');\r
    if (!sid) return;\r
    sessionStore.setRun(sid, run || null);\r
}\r
\r
function getSessionRunState(sessionId) {\r
    const sid = String(sessionId || '');\r
    if (!sid) return null;\r
    return sessionStore.getRun(sid) || null;\r
}\r
\r
function clearSessionRunState(sessionId) {\r
    setSessionRunState(sessionId, null);\r
}\r
\r
function clearSessionRunStateIfMatch(sessionId, runId) {\r
    const sid = String(sessionId || '');\r
    if (!sid) return;\r
    const expected = String(runId || '');\r
    if (!expected) {\r
        clearSessionRunState(sid);\r
        return;\r
    }\r
    const run = getSessionRunState(sid);\r
    if (!run || String(run.runId || '') === expected) {\r
        clearSessionRunState(sid);\r
    }\r
}\r
\r
function markSessionRunInactive(sessionId) {\r
    const sid = String(sessionId || '');\r
    if (!sid) return;\r
    setSessionServerStreamActive(sid, false);\r
    sessionStore.activeRunInfoBySession.delete(sid);\r
    const sess = sessionStore.get(sid);\r
    if (sess) {\r
        sess.run_active = false;\r
        sess.run_started_at = null;\r
        sess.stream_active = false;\r
    }\r
}\r
\r
function markRunAbortReason(run, reason) {\r
    if (!run) return;\r
    var r = reason || 'cleanup';\r
    run.abortReason = r;\r
    if (run.ctx) run.ctx.abortReason = r;\r
}\r
\r
function getRunAbortReason(sessionId, ctx) {\r
    const run = getSessionRunState(sessionId);\r
    return (run && run.abortReason) || (ctx && ctx.abortReason) || '';\r
}\r
\r
function abortSessionRun(sessionId, reason, opts) {\r
    opts = opts || {};\r
    const run = getSessionRunState(sessionId);\r
    if (!run) return null;\r
    markRunAbortReason(run, reason || 'cleanup');\r
    try { if (run.controller) run.controller.abort(); } catch (e) { /* ignore */ }\r
    if (opts.clear !== false) clearSessionRunState(sessionId);\r
    return run;\r
}\r
`,kt=`function renderSessionListFromStore() {
    if (!sessionsList) return Object.create(null);
    const nextStreamMap = Object.create(null);
    const sections = selectSessionSections();
    const allSessions = selectAllSessions();

    sessionsList.innerHTML = '';

    function appendSection(sectionKey, title, list) {
        var displayCount = sectionKey === 'archived' ? selectArchivedDisplayCount() : list.length;
        if (!displayCount) return;
        var expanded = sessionSectionExpanded(sectionKey);
        var sec = document.createElement('div');
        sec.className = 'session-section' + (expanded ? '' : ' is-collapsed');
        sec.dataset.section = sectionKey;

        var toggle = document.createElement('button');
        toggle.type = 'button';
        toggle.className = 'session-section-toggle';
        toggle.setAttribute('aria-expanded', expanded ? 'true' : 'false');
        toggle.innerHTML = '<span class="session-section-toggle-label">' + escapeHtml(title) + '</span>'
            + '<span class="session-section-meta">'
            + '<span class="session-section-count">' + String(displayCount) + '</span>'
            + '<span class="session-section-chev" aria-hidden="true">▾</span>'
            + '</span>';
        toggle.addEventListener('click', function (e) {
            e.preventDefault();
            sec.classList.toggle('is-collapsed');
            var isExpanded = !sec.classList.contains('is-collapsed');
            persistSessionSectionExpanded(sectionKey, isExpanded);
            toggle.setAttribute('aria-expanded', isExpanded ? 'true' : 'false');
        });

        var body = document.createElement('div');
        body.className = 'session-section-body';
        if (sectionKey === 'normal' && Array.isArray(sections.normalGroups) && sections.normalGroups.length) {
            for (let g = 0; g < sections.normalGroups.length; g += 1) {
                var group = sections.normalGroups[g];
                var groupTitle = document.createElement('div');
                groupTitle.className = 'session-time-group-title';
                groupTitle.textContent = group.title;
                body.appendChild(groupTitle);
                for (let k = 0; k < group.sessions.length; k += 1) {
                    body.appendChild(buildAndBindSessionRow(group.sessions[k], allSessions, nextStreamMap));
                }
            }
        } else {
            for (let j = 0; j < list.length; j += 1) {
                body.appendChild(buildAndBindSessionRow(list[j], allSessions, nextStreamMap));
            }
        }
        if (sectionKey === 'archived') appendArchiveLoadButton(body);
        sec.appendChild(toggle);
        sec.appendChild(body);
        sessionsList.appendChild(sec);
    }

    appendSection('pinned', '置顶目录', sections.pinned);
    appendSection('normal', '会话目录', sections.normal);
    appendSection('archived', '归档目录', sections.archived);
    return nextStreamMap;
}

function appendArchiveLoadButton(body) {
    var loadBtn = document.createElement('button');
    loadBtn.type = 'button';
    loadBtn.className = 'session-archive-load-btn';
    loadBtn.textContent = !sessionStore.archivedLoaded
        ? '加载归档目录'
        : (sessionStore.hasMoreArchivedSessions() ? '加载更多' : '刷新归档目录');
    loadBtn.addEventListener('click', async function (e) {
        e.preventDefault();
        e.stopPropagation();
        loadBtn.disabled = true;
        loadBtn.textContent = '加载中...';
        try {
            await loadArchivedSessions({ forceRender: true });
        } catch (err) {
            console.error('加载归档目录失败:', err);
            loadBtn.disabled = false;
            loadBtn.textContent = !sessionStore.archivedLoaded
                ? '加载归档目录'
                : (sessionStore.hasMoreArchivedSessions() ? '加载更多' : '刷新归档目录');
        }
    });
    body.appendChild(loadBtn);
}

function renderSessionTitleFromStore() {
    updateSessionTitle();
}
`,Ct=`const messageStore = {
    sessions: new Map(),

    ensureSession(sessionId) {
        const sid = String(sessionId || '');
        if (!sid) return null;
        let st = this.sessions.get(sid);
        if (!st) {
            st = {
                sessionId: sid,
                events: [],
                eventsByIndex: new Map(),
                processEvents: [],
                messageEvents: [],
                rangeStart: 0,
                rangeEnd: 0,
                total: 0,
                loadedAt: 0,
            };
            this.sessions.set(sid, st);
        }
        return st;
    },

    clearSession(sessionId) {
        const sid = String(sessionId || '');
        if (!sid) return;
        this.sessions.delete(sid);
    },

    beginReplay(sessionId, meta) {
        const st = this.ensureSession(sessionId);
        if (!st) return null;
        st.events = [];
        st.eventsByIndex = new Map();
        st.processEvents = [];
        st.messageEvents = [];
        st.rangeStart = Number(meta && meta.range_start) || 0;
        st.rangeEnd = Number(meta && meta.range_end) || 0;
        st.total = Number(meta && meta.total) || 0;
        st.loadedAt = Date.now();
        return st;
    },

    applyEvent(sessionId, event, eventIndex, source) {
        const st = this.ensureSession(sessionId);
        if (!st || !event || typeof event !== 'object') return null;
        const idx = Number.isFinite(Number(eventIndex)) ? Number(eventIndex) : st.events.length;
        const prevRecord = st.eventsByIndex.get(idx) || null;
        const record = {
            index: idx,
            type: String(event.type || ''),
            event: event,
            source: source || 'unknown',
            at: Date.now(),
        };
        st.eventsByIndex.set(idx, record);
        const lastRecord = st.events.length ? st.events[st.events.length - 1] : null;
        if (!prevRecord && (!lastRecord || idx > lastRecord.index)) {
            st.events.push(record);
            if (record.type === 'user' || record.type === 'final') st.messageEvents.push(record);
            else st.processEvents.push(record);
        } else {
            st.events = Array.from(st.eventsByIndex.keys()).sort(function (a, b) { return a - b; })
                .map(function (key) { return st.eventsByIndex.get(key); });
            st.messageEvents = [];
            st.processEvents = [];
            st.events.forEach(function (item) {
                if (item.type === 'user' || item.type === 'final') st.messageEvents.push(item);
                else st.processEvents.push(item);
            });
        }
        st.rangeEnd = Math.max(st.rangeEnd || 0, idx + 1);
        st.total = Math.max(st.total || 0, st.rangeEnd);
        return record;
    },

    getSession(sessionId) {
        return this.sessions.get(String(sessionId || '')) || null;
    },

    listEvents(sessionId) {
        const st = this.getSession(sessionId);
        return st ? st.events.slice() : [];
    },

    listEventsInRange(sessionId, startIndex, endIndex) {
        const start = Number.isFinite(Number(startIndex)) ? Number(startIndex) : -Infinity;
        const end = Number.isFinite(Number(endIndex)) ? Number(endIndex) : Infinity;
        return this.listEvents(sessionId).filter(function (record) {
            return record.index >= start && record.index < end;
        });
    },

    eventCount(sessionId) {
        const st = this.getSession(sessionId);
        return st ? st.events.length : 0;
    },

    truncateSession(sessionId, beforeIndex) {
        const st = this.getSession(sessionId);
        if (!st) return null;
        const before = Math.max(0, Number(beforeIndex) || 0);
        st.events = st.events.filter(function (record) { return Number(record.index) < before; });
        st.eventsByIndex = new Map();
        st.messageEvents = [];
        st.processEvents = [];
        st.events.forEach(function (record) {
            st.eventsByIndex.set(Number(record.index), record);
            if (record.type === 'user' || record.type === 'final') st.messageEvents.push(record);
            else st.processEvents.push(record);
        });
        st.rangeEnd = Math.min(Number(st.rangeEnd) || before, before);
        st.total = Math.min(Number(st.total) || before, before);
        st.loadedAt = Date.now();
        return st;
    },
};

function beginMessageReplay(sessionId, meta) {
    return messageStore.beginReplay(sessionId, meta);
}

function clearMessageStateForSession(sessionId) {
    messageStore.clearSession(sessionId);
}

function applyMessageEvent(sessionId, event, eventIndex, source) {
    return messageStore.applyEvent(sessionId, event, eventIndex, source);
}

function selectMessageEvents(sessionId) {
    return messageStore.listEvents(sessionId);
}

function selectMessageEventsInRange(sessionId, startIndex, endIndex) {
    return messageStore.listEventsInRange(sessionId, startIndex, endIndex);
}

function selectMessageEventCount(sessionId) {
    return messageStore.eventCount(sessionId);
}

function truncateMessageStateForSession(sessionId, beforeIndex) {
    return messageStore.truncateSession(sessionId, beforeIndex);
}
`,Tt=`function renderMessageRecord(ctx, record, sessionId) {
    if (!ctx || !record || !record.event) return null;
    const sid = sessionId || record.sessionId || currentSessionId;
    renderEvent(ctx, record.event, record.index, sid);
    return record;
}

function reduceAndRenderMessageEvent(ctx, event, opts) {
    opts = opts || {};
    if (!event || typeof event !== 'object') return { handled: false };
    const reduced = applySessionEvent(event, opts);
    if (!opts.skipRender && !(reduced && reduced.handled)) {
        const record = reduced && reduced.messageRecord
            ? reduced.messageRecord
            : {
                index: opts.eventIndex,
                event: event,
                source: opts.source || 'render',
            };
        renderMessageRecord(ctx, record, opts.sessionId || event.session_id || event.sessionId);
    }
    return reduced || { handled: false };
}

function renderMessageRecords(ctx, records, sessionId) {
    const list = Array.isArray(records) ? records : [];
    for (let i = 0; i < list.length; i += 1) {
        renderMessageRecord(ctx, list[i], sessionId);
    }
}
`,Et=`const subagentStore = {
    sessions: new Map(),

    ensureSession(sessionId) {
        const sid = String(sessionId || '');
        if (!sid) return null;
        let st = this.sessions.get(sid);
        if (!st) {
            st = {
                sessionId: sid,
                itemsById: new Map(),
                order: [],
                runningIds: new Set(),
                pendingResultIds: new Set(),
                eventCountsById: new Map(),
                snapshotLoaded: false,
                updatedAt: 0,
            };
            this.sessions.set(sid, st);
        }
        return st;
    },

    clearSession(sessionId) {
        const sid = String(sessionId || '');
        if (!sid) return;
        this.sessions.delete(sid);
    },

    applySnapshot(sessionId, flat) {
        const st = this.ensureSession(sessionId);
        if (!st) return null;
        const list = Array.isArray(flat) ? flat : [];
        const nextById = new Map();
        const nextOrder = [];
        const nextRunning = new Set();
        const nextPending = new Set();
        list.forEach(function (node) {
            if (!node || !node.id) return;
            const id = String(node.id);
            const prev = st.itemsById.get(id) || {};
            const merged = Object.assign({}, prev, node, { id: id });
            nextById.set(id, merged);
            nextOrder.push(id);
            const eventCount = Number(node.event_count != null ? node.event_count : node.eventCount);
            if (Number.isFinite(eventCount) && eventCount >= 0) st.eventCountsById.set(id, Math.floor(eventCount));
            if (merged.running) nextRunning.add(id);
            if (merged.pending_continue || merged.pending_result || merged.can_continue) nextPending.add(id);
        });
        st.itemsById = nextById;
        st.order = nextOrder;
        st.runningIds = nextRunning;
        st.pendingResultIds = nextPending;
        st.snapshotLoaded = true;
        st.updatedAt = Date.now();
        return st;
    },

    applyLifecycleEvent(sessionId, event) {
        const st = this.ensureSession(sessionId);
        if (!st || !event || typeof event !== 'object') return null;
        const id = String(event.agent_id || event.run_id || '');
        if (!id) return null;
        const prev = st.itemsById.get(id) || { id: id };
        const next = Object.assign({}, prev, {
            id: id,
            description: event.description || prev.description || id,
            subagent_type: event.subagent_type || prev.subagent_type || '',
            updated_at: Date.now(),
        });
        if (event.type === 'subagent_start' || event.type === 'subagent_started') {
            next.running = true;
            next.status = 'running';
            st.runningIds.add(id);
            st.pendingResultIds.delete(id);
        } else if (event.type === 'subagent_finish' || event.type === 'subagent_finished') {
            const preview = String(event.result_preview || prev.result_preview || '').trim();
            const hasFinal = Object.prototype.hasOwnProperty.call(event, 'has_final') ? !!event.has_final : !!preview;
            next.running = false;
            next.has_final = hasFinal;
            next.status = (event.ok === false || !hasFinal) ? 'failed' : 'finished';
            if (event.result_preview) next.result_preview = String(event.result_preview);
            if (event.error || !hasFinal) next.error = String(event.error || 'missing final');
            st.runningIds.delete(id);
            st.pendingResultIds.add(id);
        }
        st.itemsById.set(id, next);
        if (st.order.indexOf(id) < 0) st.order.unshift(id);
        st.updatedAt = Date.now();
        return next;
    },

    remove(sessionId, agentId) {
        const st = this.ensureSession(sessionId);
        const id = String(agentId || '');
        if (!st || !id) return;
        st.itemsById.delete(id);
        st.runningIds.delete(id);
        st.pendingResultIds.delete(id);
        st.eventCountsById.delete(id);
        st.order = st.order.filter(function (x) { return x !== id; });
        st.updatedAt = Date.now();
    },

    setEventCount(sessionId, agentId, count) {
        const st = this.ensureSession(sessionId);
        const id = String(agentId || '');
        const n = Number(count);
        if (!st || !id || !Number.isFinite(n)) return;
        st.eventCountsById.set(id, Math.max(0, n));
    },

    deleteEventCount(sessionId, agentId) {
        const st = this.sessions.get(String(sessionId || ''));
        const id = String(agentId || '');
        if (!st || !id) return;
        st.eventCountsById.delete(id);
    },

    clearEventCounts(sessionId) {
        const st = this.sessions.get(String(sessionId || ''));
        if (!st) return;
        st.eventCountsById.clear();
    },

    getEventCount(sessionId, agentId) {
        const st = this.sessions.get(String(sessionId || ''));
        if (!st) return 0;
        return Number(st.eventCountsById.get(String(agentId || '')) || 0);
    },

    getSession(sessionId) {
        return this.sessions.get(String(sessionId || '')) || null;
    },

    list(sessionId) {
        const st = this.getSession(sessionId);
        if (!st) return [];
        const out = [];
        st.order.forEach(function (id) {
            const item = st.itemsById.get(id);
            if (item) out.push(item);
        });
        return out;
    },

    runningCount(sessionId) {
        const st = this.getSession(sessionId);
        return st ? st.runningIds.size : 0;
    },
};

function applySubagentSnapshot(sessionId, flat) {
    return subagentStore.applySnapshot(sessionId, flat);
}

function applySubagentLifecycleToStore(sessionId, event) {
    return subagentStore.applyLifecycleEvent(sessionId, event);
}

function clearSubagentStateForSession(sessionId) {
    subagentStore.clearSession(sessionId);
}

function selectSubagentList(sessionId) {
    return subagentStore.list(sessionId);
}

function selectSubagentRunningCount(sessionId) {
    return subagentStore.runningCount(sessionId);
}
`,At=`var subagentContinueInFlight = false;
var subagentContinueSessionId = null;
var subagentContinueBannerTimer = null;
var subagentContinueDismissedForSession = Object.create(null);

function hideSubagentContinueBanner() {
    var banner = document.getElementById('subagent-continue-banner');
    if (!banner) return;
    var mode = banner && banner.dataset ? String(banner.dataset.continueMode || '') : '';
    banner.classList.remove('is-on');
}

function dismissSubagentContinueBanner(sessionId) {
    var sid = sessionId || currentSessionId;
    if (sid) subagentContinueDismissedForSession[sid] = true;
    hideSubagentContinueBanner();
    if (sid) {
        fetch('/sessions/' + encodeURIComponent(sid) + '/continue-subagents/dismiss', { method: 'POST' })
            .catch(function () { /* ignore */ });
    }
}

function showSubagentContinueBanner(pendingCount) {
    var banner = document.getElementById('subagent-continue-banner');
    if (!banner) return;
    var n = Math.max(1, parseInt(String(pendingCount), 10) || 1);
    var msg = banner.querySelector('.subagent-continue-banner-msg');
    if (msg) {
        msg.textContent = n + ' 个子任务已完成，点击继续让主 Agent 综合子任务结果（不会自动续跑）。';
    }
    if (msg) msg.textContent = n + ' 个子任务结果尚未纳入上方回答，点击补充综合。';
    banner.classList.add('is-on');
}

async function fetchSubagentContinueState(sessionId) {
    if (!sessionId) return { pending: 0, running: 0, can_continue: false };
    try {
        var r = await fetch('/sessions/' + encodeURIComponent(sessionId) + '?include_subagents=true');
        if (!r.ok) return { pending: 0, running: 0, can_continue: false };
        var j = await r.json();
        var continuation = j.subagent_continuation || {};
        return {
            pending: Number(continuation.pending_count != null ? continuation.pending_count : (j.subagent_pending_continue || 0)),
            running: Number(j.subagent_running || 0),
            can_continue: continuation.state ? continuation.state === 'ready' : !!j.subagent_can_continue,
            state: String(continuation.state || ''),
            reason: String(continuation.reason || ''),
        };
    } catch (e) {
        return { pending: 0, running: 0, can_continue: false };
    }
}

function updateSubagentContinueBanner(sessionId) {
    if (!sessionId || sessionId !== currentSessionId || replayingMessages) {
        hideSubagentContinueBanner();
        return;
    }
    if (subagentContinueDismissedForSession[sessionId]) {
        hideSubagentContinueBanner();
        return;
    }
    if (subagentContinueBannerTimer) clearTimeout(subagentContinueBannerTimer);
    subagentContinueBannerTimer = setTimeout(function () {
        subagentContinueBannerTimer = null;
        void (async function () {
            var st = await fetchSubagentContinueState(sessionId);
            if (sessionId !== currentSessionId) return;
            if (st.can_continue && st.pending > 0 && st.running === 0
                && !isSessionRunning(sessionId) && !subagentContinueInFlight) {
                showSubagentContinueBanner(st.pending);
            } else {
                hideSubagentContinueBanner();
            }
        })();
    }, 280);
}

async function tryMarkSessionUnreadComplete(sessionId) {
    if (!sessionId || sessionId === currentSessionId) return;
    try {
        var r = await fetch('/sessions/' + encodeURIComponent(sessionId) + '?include_subagents=true');
        if (!r.ok) return;
        var j = await r.json();
        if (j.stream_active || Number(j.subagent_running || 0) > 0) return;
        sessionUnreadComplete.add(sessionId);
        var sess = sessionStore.get(sessionId);
        if (sess && j.unread_result_status) sess.unread_result_status = j.unread_result_status;
        if (sess && Object.prototype.hasOwnProperty.call(j, 'unread_result')) sess.unread_result = !!j.unread_result;
        persistSessionUnread();
        syncSessionListIndicatorClasses();
    } catch (e) { /* ignore */ }
}
`,_t=`function setSubagentCardEventCount(agentId, count) {
    var aid = String(agentId || '');
    var n = Number(count);
    if (!aid || !Number.isFinite(n)) return;
    n = Math.max(0, n);
    if (currentSessionId) subagentStore.setEventCount(currentSessionId, aid, n);
}

function bumpSubagentCardEventCount(agentId, eventIndex, increment) {
    var aid = String(agentId || '');
    if (!aid) return;
    var prev = currentSessionId ? subagentStore.getEventCount(currentSessionId, aid) : 0;
    if (typeof eventIndex === 'number' && eventIndex >= 0) {
        setSubagentCardEventCount(aid, Math.max(prev, eventIndex + 1));
    } else if (increment) {
        setSubagentCardEventCount(aid, prev + 1);
    }
}

function trackSubagentStreamEventLightweight(card, agentId, event, eventIndex) {
    if (!card || !agentId || !event) return;
    var t = event.type;
    bumpSubagentCardEventCount(agentId, eventIndex, !event.ephemeral);
    if (t === 'context_tokens') {
        card.dataset.procCtxEstimated = String(event.estimated);
        card.dataset.procCtxThreshold = String(event.threshold);
    } else if (t === 'process_metrics') {
        applySubagentProcessMetricsToCard(card, event);
    } else if (t === 'cache_stats') {
        if (event.cache_hit != null) card.dataset.procCacheHit = String(Math.max(0, Math.floor(Number(event.cache_hit))));
        if (event.cache_miss != null) card.dataset.procCacheMiss = String(Math.max(0, Math.floor(Number(event.cache_miss))));
        if (event.hit_rate != null) card.dataset.procCacheRate = String(Math.max(0, Number(event.hit_rate)));
        if (event.model != null) card.dataset.procCacheModel = String(event.model);
    }
    if (event.react_iter != null) bumpAggregateMaxReactIter(card, event.react_iter);
    scheduleSubagentCardStats(card);
}
`,Rt=`function subagentMoreDotsHtml() {
    return '<span class="session-more-dots" aria-hidden="true"><span></span><span></span><span></span></span>';
}

function subagentSortKey(n) {
    var t = Date.parse(String((n && (n.updated_at || n.created_at)) || ''));
    return isNaN(t) ? 0 : t;
}

function sortSubagentsByUpdated(flat) {
    return (flat || []).slice().sort(function (a, b) {
        return subagentSortKey(b) - subagentSortKey(a);
    });
}

function subagentStatusFromNode(n) {
    var taskStatus = String((n && (n.task_status || n.status)) || '').toLowerCase();
    var hasFinalKnown = !!(n && Object.prototype.hasOwnProperty.call(n, 'has_final'));
    var hasPreview = !!String((n && n.result_preview) || '').trim();
    var hasFinal = !n || !hasFinalKnown ? hasPreview : !!n.has_final;
    var canTreatCompleted = hasFinal || (!hasFinalKnown && hasPreview) || (n && n.virtual_task && hasPreview && !hasFinalKnown);
    if (n && n.running) {
        return { label: n.background ? '后台运行' : '运行中', dotCls: 'is-running' };
    }
    if (taskStatus === 'running') return { label: '后台运行', dotCls: 'is-running' };
    if (taskStatus === 'completed' && canTreatCompleted) return { label: '完成', dotCls: 'is-done' };
    if (taskStatus === 'completed') return { label: '缺少 final 结果', dotCls: 'is-error' };
    if (taskStatus === 'failed') return { label: '失败', dotCls: 'is-error' };
    if (taskStatus === 'interrupted') return { label: '已中断', dotCls: 'is-error' };
    if (n && n.ok === false) {
        var err = String(n.error || n.result_preview || '').trim();
        if (/interrupt/i.test(err)) return { label: '已中断', dotCls: 'is-error' };
        return { label: '失败', dotCls: 'is-error' };
    }
    if (n && n.status === 'interrupted') return { label: '已中断', dotCls: 'is-error' };
    if (n && n.status === 'failed') return { label: '失败', dotCls: 'is-error' };
    var prev = String((n && n.result_preview) || '').trim();
    if (/^Error:|^错误|失败|异常|interrupt/i.test(prev)) {
        return { label: '失败', dotCls: 'is-error' };
    }
    return { label: '完成', dotCls: 'is-done' };
}

function subagentCardViewModel(n) {
    n = n || {};
    var id = String(n.id || '');
    var running = !!n.running && !n.virtual_task;
    var name = n.description || id.slice(0, 8);
    return {
        id: id,
        running: running,
        name: name,
        idShort: id.length > 5 ? id.slice(0, 5) + '...' : id,
        typeLabel: n.subagent_type || 'subagent',
        status: subagentStatusFromNode(n),
        resultPreview: String(n.result_preview || '').trim(),
        outputFile: !!n.output_file,
        virtualTask: !!n.virtual_task,
        taskStatus: n.task_status || n.status || '',
        hasFinalKnown: Object.prototype.hasOwnProperty.call(n, 'has_final'),
        hasFinal: !!n.has_final,
        executorModel: n.executor_model || '',
    };
}

function renderSubagentCardHtml(n) {
    var vm = subagentCardViewModel(n);
    if (!vm.id) return '';
    var stopBtn = vm.running ? '<button type="button" class="subagent-card-menu-item subagent-card-stop" role="menuitem" data-agent-id="' + escapeHtml(vm.id) + '">停止</button>' : '';
    var outputBtn = vm.outputFile ? '<button type="button" class="subagent-card-menu-item subagent-card-output" role="menuitem" data-agent-id="' + escapeHtml(vm.id) + '">查看输出</button>' : '';
    var html = '<div class="process-aggregate subagent-grid-card" data-agent-id="' + escapeHtml(vm.id) + '"';
    if (vm.executorModel) html += ' data-executor-model="' + escapeHtml(String(vm.executorModel)) + '"';
    if (vm.outputFile) html += ' data-output-file="1"';
    if (vm.virtualTask) html += ' data-virtual-task="1"';
    if (vm.taskStatus) html += ' data-task-status="' + escapeHtml(String(vm.taskStatus)) + '"';
    if (vm.hasFinalKnown) html += ' data-has-final="' + (vm.hasFinal ? '1' : '0') + '"';
    html += ' data-subagent-running="' + (vm.running ? '1' : '0') + '"';
    html += ' data-description="' + escapeHtml(String(vm.name || '')) + '"';
    html += '>';
    html += '<div class="subagent-card-head">';
    html += '<div class="subagent-card-head-line">';
    html += '<span class="process-aggregate-title-wrap">';
    html += '<div class="subagent-card-title-row">';
    html += '<span class="subagent-status"><span class="subagent-status-dot ' + vm.status.dotCls + '" data-ui-tip="' + escapeHtml(vm.status.label) + '"></span></span>';
    html += '<span class="subagent-card-name">' + escapeHtml(vm.name) + '</span>';
    html += '<span class="subagent-card-type">' + escapeHtml(vm.typeLabel) + '</span>';
    html += '<span class="subagent-card-id">' + escapeHtml(vm.idShort) + '</span>';
    html += '</div>';
    html += '<span class="process-aggregate-stats" aria-live="polite"></span>';
    html += '</span>';
    html += '<span class="subagent-card-head-actions">';
    html += '<button type="button" class="subagent-card-expand" data-agent-id="' + escapeHtml(vm.id) + '" aria-label="放大显示" aria-pressed="false" data-ui-tip="在浮窗内全屏显示"><svg class="subagent-card-expand-icon" viewBox="0 0 16 16" aria-hidden="true" focusable="false"><path d="M3 6V3h3M10 3h3v3M13 10v3h-3M6 13H3v-3" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round"/></svg></button>';
    html += '<span class="subagent-card-menu">'
        + '<button type="button" class="subagent-card-menu-btn" aria-label="更多操作" aria-expanded="false" data-ui-tip="更多操作">' + subagentMoreDotsHtml() + '</button>'
        + '<span class="subagent-card-menu-pop" role="menu">'
        + outputBtn
        + stopBtn
        + '<button type="button" class="subagent-card-menu-item subagent-card-delete" role="menuitem" data-agent-id="' + escapeHtml(vm.id) + '">删除</button>'
        + '</span></span>';
    html += '</span>';
    html += '</div></div>';
    html += '<div class="subagent-card-body subagent-dialogue-body" data-agent-id="' + escapeHtml(vm.id) + '"'
        + (vm.resultPreview ? ' data-result-preview="' + escapeHtml(vm.resultPreview.slice(0, 400)) + '"' : '')
        + '></div>';
    html += '</div>';
    return html;
}

function buildSubagentGridHtml(flat) {
    var sorted = sortSubagentsByUpdated(flat);
    if (!sorted.length) return '<div class="subagent-grid-empty">无 Subagent</div>';
    return sorted.map(renderSubagentCardHtml).join('');
}

function ensureSubagentActionMenu(actions, id) {
    if (!actions) return null;
    var menu = actions.querySelector('.subagent-card-menu');
    if (menu) return menu;
    menu = document.createElement('span');
    menu.className = 'subagent-card-menu';
    menu.innerHTML = '<button type="button" class="subagent-card-menu-btn" aria-label="更多操作" aria-expanded="false" data-ui-tip="更多操作">'
        + subagentMoreDotsHtml() + '</button>'
        + '<span class="subagent-card-menu-pop" role="menu"></span>';
    actions.appendChild(menu);
    return menu;
}

function ensureSubagentMenuButton(menu, cls, label, agentId) {
    if (!menu) return null;
    var pop = menu.querySelector('.subagent-card-menu-pop');
    if (!pop) return null;
    var btn = pop.querySelector('.' + cls);
    if (btn) {
        btn.setAttribute('data-agent-id', agentId);
        return btn;
    }
    btn = document.createElement('button');
    btn.type = 'button';
    btn.className = 'subagent-card-menu-item ' + cls;
    btn.setAttribute('data-agent-id', agentId);
    btn.setAttribute('role', 'menuitem');
    btn.textContent = label;
    pop.appendChild(btn);
    return btn;
}

function applySubagentNodeMetaToCard(card, n) {
    if (!card || !n) return;
    var id = String(n.id || '');
    var running = !!n.running && !n.virtual_task;
    card.dataset.subagentRunning = running ? '1' : '0';
    card.dataset.description = String(n.description || id.slice(0, 8) || '');
    if (n.result_preview) card.dataset.resultPreview = String(n.result_preview);
    if (n.virtual_task) card.dataset.virtualTask = '1';
    else delete card.dataset.virtualTask;
    if (Object.prototype.hasOwnProperty.call(n, 'has_final')) card.dataset.hasFinal = n.has_final ? '1' : '0';
    if (n.session_metrics) applySubagentSessionMetricsToCard(card, n.session_metrics);
    var st = subagentStatusFromNode(n);
    var dot = card.querySelector('.subagent-status-dot');
    if (dot) {
        dot.className = 'subagent-status-dot ' + st.dotCls;
        dot.setAttribute('data-ui-tip', st.label);
    }
    var actions = card.querySelector('.subagent-card-head-actions');
    if (actions) {
        var menu = ensureSubagentActionMenu(actions, id);
        var stopExisting = actions.querySelector('.subagent-card-stop');
        if (running && !stopExisting) {
            ensureSubagentMenuButton(menu, 'subagent-card-stop', '停止', id);
        } else if (!running && stopExisting) {
            stopExisting.remove();
        }
        var outputExisting = actions.querySelector('.subagent-card-output');
        var hasOutput = !!n.output_file;
        if (hasOutput) {
            card.dataset.outputFile = '1';
            if (!outputExisting) {
                ensureSubagentMenuButton(menu, 'subagent-card-output', '查看输出', id);
            }
        } else {
            delete card.dataset.outputFile;
            if (outputExisting) outputExisting.remove();
            var panel = card.querySelector('.subagent-output-panel');
            if (panel) panel.remove();
        }
        ensureSubagentMenuButton(menu, 'subagent-card-delete', '删除', id);
    }
    if (n.task_status || n.status) card.dataset.taskStatus = String(n.task_status || n.status);
    if (n.executor_model) {
        card.dataset.executorModel = String(n.executor_model);
        if (!card.dataset.procCacheModel) card.dataset.procCacheModel = String(n.executor_model);
    }
    if (running && !card.dataset.procStartedAt) card.dataset.procStartedAt = String(procNow());
    if (!running) {
        card.dataset.procEndedAt = String(procNow());
        if (id) void refreshSubagentContextForCard(card, id, true);
        if (!card.classList.contains('is-expanded')) {
            updateSubagentCardSummaryOnly(card, n.result_preview);
        }
    }
    refreshSubagentCardStats(card);
}

function appendSubagentGridCardFromNode(grid, n) {
    if (!grid || !n) return null;
    var html = buildSubagentGridHtml([n]);
    if (html.indexOf('subagent-grid-empty') >= 0) return null;
    var tmp = document.createElement('div');
    tmp.innerHTML = html;
    var card = tmp.firstElementChild;
    if (!card) return null;
    grid.appendChild(card);
    if (n.result_preview) card.dataset.resultPreview = String(n.result_preview);
    return card;
}

function syncSubagentGridFromFlat(flat, sessionId) {
    var grid = document.getElementById('subagent-grid');
    if (!grid) return;
    if (grid.dataset.sessionId && grid.dataset.sessionId !== sessionId) {
        grid.innerHTML = '';
        disconnectSubagentCardViewportObserver();
    }
    grid.dataset.sessionId = sessionId;
    var sorted = sortSubagentsByUpdated(flat);
    var existingIds = new Set();
    sorted.forEach(function (n) {
        var id = String(n.id || '');
        if (!id) return;
        existingIds.add(id);
        var card = grid.querySelector('.subagent-grid-card[data-agent-id="' + id + '"]');
        if (!card) {
            card = appendSubagentGridCardFromNode(grid, n);
            if (card && subagentPanelOpen) observeSubagentCardViewport(card);
        } else {
            applySubagentNodeMetaToCard(card, n);
        }
    });
    grid.querySelectorAll('.subagent-grid-card').forEach(function (card) {
        var id = card.getAttribute('data-agent-id');
        if (id && !existingIds.has(id)) {
            subagentStore.deleteEventCount(sessionId, id);
            delete subagentCardLoadQueued[id];
            card.remove();
        }
    });
    bindSubagentGridActions(grid, sessionId);
    if (shouldLoadSubagentCardBodies()) {
        loadVisibleSubagentCardBodies(grid, sessionId);
    }
}

function refreshSubagentToggleFromGrid(flat) {
    var toggleBtn = document.getElementById('subagent-toggle-btn');
    var toggleBadge = document.getElementById('subagent-toggle-badge');
    if (!toggleBtn) return;
    var list = flat || [];
    var runningN = list.filter(function (n) { return n.running; }).length;
    if (!list.length) {
        toggleBtn.classList.add('hidden');
        return;
    }
    toggleBtn.classList.remove('hidden');
    if (toggleBadge) toggleBadge.textContent = String(list.length) + (runningN ? (' · ' + runningN) : '');
    toggleBtn.classList.toggle('is-running', runningN > 0);
}

function createSubagentMiniMessage(role, content, eventIndex, createdAt) {
    var wrap = document.createElement('div');
    wrap.className = 'msg-wrap msg-wrap--' + (role === 'user' ? 'user' : 'assistant');
    if (role === 'assistant') wrap.classList.add('msg-wrap--answer-frame');
    if (eventIndex != null) wrap.setAttribute('data-event-index', String(eventIndex));
    var div = document.createElement('div');
    div.className = 'message ' + (role === 'user' ? 'user' : 'assistant');
    var rawStr = content == null ? '' : String(content);
    if (role === 'user') {
        renderUserMessageContent(wrap, div, rawStr);
    }
    else {
        var displayStr = rawStr;
        if (typeof splitThinkTagsForUi === 'function') displayStr = splitThinkTagsForUi(rawStr).content;
        if (typeof stripOrphanThinkCloseForFinalCard === 'function') displayStr = stripOrphanThinkCloseForFinalCard(displayStr);
        div.innerHTML = renderMarkdown(displayStr);
        enhanceAssistantMessageContent(div);
    }
    wrap.appendChild(div);
    if (role === 'user') {
        var ts = createdAt || new Date().toISOString();
        wrap.setAttribute('data-created-at', String(ts));
    }
    return wrap;
}

function openSubagentTurn(ctx, userContent, eventIndex, createdAt) {
    if (!ctx || !ctx._subagentBody) return null;
    var userRaw = userContent == null ? '' : String(userContent);
    if (userRaw.trim() && ctx.currentTurn && !ctx.currentTurn.querySelector('.msg-wrap--user')) {
        var userWrap0 = createSubagentMiniMessage('user', userRaw, eventIndex, createdAt);
        ctx.currentTurn.insertBefore(userWrap0, ctx.currentTurn.firstChild);
        bindSubagentTurnUserToggle(ctx.currentTurn, userWrap0);
        markSubagentTurnHasProcess(ctx.currentTurn);
        if (typeof eventIndex === 'number') ctx.lastUserEventIndex = eventIndex;
        return ctx.currentTurn;
    }
    sealSubagentTurn(ctx);
    var turn = document.createElement('div');
    turn.className = 'subagent-turn';
    var userWrap = userRaw.trim() ? createSubagentMiniMessage('user', userRaw, eventIndex, createdAt) : null;
    var processEl = document.createElement('div');
    processEl.className = 'subagent-turn-process';
    var finalSlot = document.createElement('div');
    finalSlot.className = 'subagent-turn-final-slot';
    if (userWrap) turn.appendChild(userWrap);
    turn.appendChild(processEl);
    turn.appendChild(finalSlot);
    ctx._subagentBody.appendChild(turn);
    ctx.currentTurn = turn;
    ctx._subagentTurnProcess = processEl;
    ctx._subagentTurnFinalSlot = finalSlot;
    if (userWrap) bindSubagentTurnUserToggle(turn, userWrap);
    return turn;
}

function ensureSubagentTurnForProcess(ctx, eventIndex) {
    if (ctx && ctx._subagentTurnProcess && ctx.currentTurn) return ctx.currentTurn;
    return openSubagentTurn(ctx, '', eventIndex);
}

function appendSubagentFinalToTurn(ctx, content, eventIndex) {
    if (!ctx) return;
    if (!ctx.currentTurn) openSubagentTurn(ctx, '', eventIndex);
    var slot = ctx._subagentTurnFinalSlot;
    if (!slot && ctx.currentTurn) slot = ctx.currentTurn.querySelector('.subagent-turn-final-slot');
    if (!slot) return;
    var existing = slot.querySelector('.msg-wrap--assistant');
    var txt = content == null ? '' : String(content);
    if (typeof splitThinkTagsForUi === 'function') {
        var thinkSplit = splitThinkTagsForUi(txt);
        if (thinkSplit.reasoning && thinkSplit.reasoning.trim()) {
            upsertLlmFeedRow(ctx, thinkSplit.reasoning, 'llm-reasoning', null, null);
        }
    }
    if (existing) {
        var msgEl = existing.querySelector('.message.assistant');
        if (msgEl) {
            var displayTxt = (typeof splitThinkTagsForUi === 'function') ? splitThinkTagsForUi(txt).content : txt;
            if (typeof stripOrphanThinkCloseForFinalCard === 'function') displayTxt = stripOrphanThinkCloseForFinalCard(displayTxt);
            msgEl.innerHTML = renderMarkdown(displayTxt);
            enhanceAssistantMessageContent(msgEl);
        }
        return;
    }
    slot.appendChild(createSubagentMiniMessage('assistant', txt, eventIndex));
    markSubagentTurnHasProcess(ctx.currentTurn);
}

function renderSubagentProcessEvents(bodyEl, hostEl, events, agentId, eventIndexBase) {
    if (!bodyEl) return Promise.resolve();
    var card = hostEl || (bodyEl.closest ? bodyEl.closest('.subagent-grid-card, .subagent-block') : null);
    if (card) {
        delete card.dataset.procDurationMs;
        delete card.dataset.procReactLoops;
        delete card.dataset.procToolCalls;
        delete card.dataset.procToolFails;
        delete card.dataset.procLiveToolCalls;
        delete card.dataset.procLiveToolFails;
    }
    bodyEl.innerHTML = '';
    delete bodyEl.dataset.cacheClean;
    delete bodyEl.dataset.finalOnly;
    bodyEl.classList.remove('is-final-only');
    bodyEl.classList.add('subagent-dialogue-body');
    if (!events || !events.length) {
        bodyEl.innerHTML = '<div class="subagent-detail-empty">(暂无事件)</div>';
        return Promise.resolve();
    }
    var ctx = getSubagentCardStreamCtx(bodyEl, hostEl, agentId);
    resetSubagentTurnStreamState(ctx);
    var idx = 0;
    var renderToken = String(Date.now()) + ':' + Math.random();
    bodyEl.dataset.renderToken = renderToken;
    bodyEl.dataset.rendering = '1';
    return new Promise(function (resolve) {
    function finish() {
        if (bodyEl.dataset.renderToken !== renderToken) {
            resolve();
            return;
        }
        finalizeLlmStreamChunks(ctx);
        finalizeProgressStreamChunks(ctx);
        rebindSubagentCardBody(bodyEl, hostEl, agentId);
        setSubagentCardEventCount(agentId, (events || []).length);
        delete bodyEl.dataset.streamReady;
        delete bodyEl.dataset.rendering;
        refreshSubagentProcessChunksLightly(bodyEl);
        if (card && (events || []).some(function (ev) { return ev && ev.type === 'final'; })) {
            markSubagentCardCompleted(card, true);
        }
        if (currentSessionId) {
            rememberSubagentBodyCache(currentSessionId, agentId, bodyEl.innerHTML);
            bodyEl.dataset.cacheClean = '1';
        }
        resolve();
    }
    function step() {
        if (!bodyEl.isConnected || bodyEl.dataset.renderToken !== renderToken) {
            resolve();
            return;
        }
        var end = Math.min(idx + SUBAGENT_DETAIL_RENDER_BATCH, events.length);
        for (; idx < end; idx += 1) {
            var ev = events[idx];
            if (ev && typeof ev === 'object') dispatchSubagentCardEvent(ctx, hostEl, ev, (eventIndexBase || 0) + idx, agentId);
        }
        if (idx < events.length) {
            scheduleSubagentDetailWork(step);
        } else {
            finish();
        }
    }
    step();
    });
}

function renderSubagentLatestFinalOnly(bodyEl, hostEl, events, agentId) {
    if (!bodyEl) return Promise.resolve();
    bodyEl.innerHTML = '';
    delete bodyEl.dataset.cacheClean;
    delete bodyEl.dataset.renderToken;
    delete bodyEl.dataset.rendering;
    delete bodyEl.dataset.streamReady;
    bodyEl.classList.add('subagent-dialogue-body', 'is-final-only');
    var finalIdx = -1;
    for (var i = (events || []).length - 1; i >= 0; i -= 1) {
        if (events[i] && events[i].type === 'final') {
            finalIdx = i;
            break;
        }
    }
    var ctx = getSubagentCardStreamCtx(bodyEl, hostEl, agentId);
    resetSubagentTurnStreamState(ctx);
    var lastUser = -1;
    if (finalIdx >= 0) {
        openSubagentTurn(ctx, '', finalIdx);
        appendSubagentFinalToTurn(ctx, events[finalIdx].content || '', finalIdx);
    } else {
        for (var u = (events || []).length - 1; u >= 0; u -= 1) {
            if (events[u] && events[u].type === 'user') { lastUser = u; break; }
        }
        if (lastUser >= 0) openSubagentTurn(ctx, events[lastUser].content || '', lastUser);
        else bodyEl.innerHTML = '<div class="subagent-detail-empty">(暂无 final 结果)</div>';
    }
    bodyEl.dataset.loaded = '1';
    bodyEl.dataset.finalOnly = '1';
    bodyEl.dataset.subagentSliceStart = String(finalIdx >= 0 ? finalIdx : Math.max(0, lastUser));
    delete bodyEl.dataset.historyComplete;
    bodyEl._subagentEvents = events || [];
    rebindSubagentCardBody(bodyEl, hostEl, agentId);
    if (hostEl && finalIdx >= 0) markSubagentCardCompleted(hostEl, true);
    requestAnimationFrame(function () {
        if (bodyEl.isConnected) bodyEl.scrollTop = 0;
    });
    return Promise.resolve();
}

function createSubagentBlockElement(event) {
    event = event || {};
    var aid = String(event.agent_id || event.run_id || '');
    if (!aid) return null;
    var blk = document.createElement('div');
    blk.className = 'subagent-block';
    blk.dataset.agentId = aid;
    var status = event.background ? '后台运行' : '运行中';
    blk.innerHTML = '<div class="subagent-block-head" role="button" tabindex="0">'
        + '<span class="subagent-block-badge is-running">' + escapeHtml(status) + '</span>'
        + '<strong>' + escapeHtml(event.description || 'subagent') + '</strong>'
        + '<span class="subagent-block-meta">' + escapeHtml(event.subagent_type || '') + '</span>'
        + '<span class="subagent-block-id">' + escapeHtml(aid.slice(0, 8)) + '…</span>'
        + '</div>'
        + '<div class="subagent-block-preview"></div>'
        + '<div class="subagent-block-body process-aggregate-body"></div>';
    return blk;
}

function applySubagentBlockFinish(blk, event) {
    if (!blk || !event) return;
    var badge = blk.querySelector('.subagent-block-badge');
    var preview = blk.querySelector('.subagent-block-preview');
    var ok = event.ok !== false;
    if (badge) {
        badge.textContent = ok ? '完成' : '失败';
        badge.classList.remove('is-running');
        badge.classList.toggle('is-done', ok);
        badge.classList.toggle('is-error', !ok);
    }
    if (preview) {
        var txt = event.result_preview || event.error || '';
        preview.textContent = txt ? String(txt).slice(0, 500) : '';
    }
}
`,Pt=`var subagentBodyHtmlCache = Object.create(null);

function subagentBodyCacheKey(sessionId, agentId) {
    return String(sessionId || '') + ':' + String(agentId || '');
}

function isSubagentDetailPendingHtml(html) {
    return !html || html.indexOf('加载中') >= 0;
}

function forgetSubagentBodyCache(sessionId, agentId) {
    if (sessionId && agentId) {
        delete subagentBodyHtmlCache[subagentBodyCacheKey(sessionId, agentId)];
        return;
    }
    if (sessionId) {
        var prefix = String(sessionId) + ':';
        Object.keys(subagentBodyHtmlCache).forEach(function (k) {
            if (k.indexOf(prefix) === 0) delete subagentBodyHtmlCache[k];
        });
    }
}

function isSubagentBodyCacheComplete(html) {
    if (!html || isSubagentDetailPendingHtml(html)) return false;
    if (html.indexOf('subagent-detail-empty') >= 0) return false;
    if (html.indexOf('subagent-turn-process') < 0) {
        return html.indexOf('subagent-turn') >= 0 || html.indexOf('msg-wrap--assistant') >= 0;
    }
    return html.indexOf('msg-wrap--user') >= 0;
}

function rememberSubagentBodyCache(sessionId, agentId, html) {
    if (!sessionId || !agentId || !html || !isSubagentBodyCacheComplete(html)) return;
    subagentBodyHtmlCache[subagentBodyCacheKey(sessionId, agentId)] = html;
}

function readSubagentBodyCache(sessionId, agentId) {
    return subagentBodyHtmlCache[subagentBodyCacheKey(sessionId, agentId)] || '';
}
`,Lt=`var subagentCardViewportObserver = null;
var subagentCardLoadQueue = [];
var subagentCardLoadInflight = 0;
var subagentCardLoadQueued = Object.create(null);
var SUBAGENT_BODY_LOAD_CONCURRENCY = 2;
var SUBAGENT_DETAIL_RENDER_BATCH = 8;
var SUBAGENT_HISTORY_TURNS_PER_PAGE = 3;

function scheduleSubagentDetailWork(fn) {
    setTimeout(fn, 0);
}

function shouldLoadSubagentCardBodies() {
    return !!subagentPanelOpen;
}

function ensureSubagentCardViewportObserver(grid) {
    if (!grid || subagentCardViewportObserver) return;
    subagentCardViewportObserver = new IntersectionObserver(function (entries) {
        entries.forEach(function (entry) {
            var card = entry.target;
            if (!card || !card.isConnected) return;
            if (entry.isIntersecting) {
                card.dataset.viewportVisible = '1';
                card.classList.add('is-viewport-visible');
                queueSubagentCardBodyLoad(card, currentSessionId);
            } else if (!card.classList.contains('is-expanded')) {
                card.dataset.viewportVisible = '0';
                card.classList.remove('is-viewport-visible');
                stashSubagentCardBodyForCollapse(card);
            }
        });
    }, { root: grid, rootMargin: '160px 0px', threshold: 0.01 });
}

function observeSubagentCardViewport(card) {
    if (!card) return;
    ensureSubagentCardViewportObserver(document.getElementById('subagent-grid'));
    if (subagentCardViewportObserver) subagentCardViewportObserver.observe(card);
}

function disconnectSubagentCardViewportObserver() {
    if (subagentCardViewportObserver) {
        subagentCardViewportObserver.disconnect();
        subagentCardViewportObserver = null;
    }
    subagentCardLoadQueue = [];
    subagentCardLoadInflight = 0;
    subagentCardLoadQueued = Object.create(null);
}

function drainSubagentCardLoadQueue() {
    if (!shouldLoadSubagentCardBodies()) return;
    while (subagentCardLoadInflight < SUBAGENT_BODY_LOAD_CONCURRENCY && subagentCardLoadQueue.length) {
        var job = subagentCardLoadQueue.shift();
        if (!job || !job.card || !job.card.isConnected) {
            if (job && job.agentId) delete subagentCardLoadQueued[job.agentId];
            continue;
        }
        var body = job.card.querySelector('.subagent-card-body');
        if (!job.card.classList.contains('is-expanded') && job.card.dataset.viewportVisible !== '1') {
            delete subagentCardLoadQueued[job.agentId];
            stashSubagentCardBodyForCollapse(job.card);
            continue;
        }
        var finalOnlyNeedsFull = job.card.classList.contains('is-expanded') && body && body.dataset.finalOnly === '1';
        if (!body || body.dataset.loading === '1' || (subagentBodyIsLoaded(body) && !finalOnlyNeedsFull)) {
            delete subagentCardLoadQueued[job.agentId];
            continue;
        }
        subagentCardLoadInflight += 1;
        (function (card, agentId, sessionId) {
            var cached = readSubagentBodyCache(sessionId, agentId);
            if (card.classList.contains('is-expanded') && cached && isSubagentBodyCacheComplete(cached)) {
                body.innerHTML = cached;
                body.dataset.loaded = '1';
                body.dataset.cacheClean = '1';
                delete body.dataset.finalOnly;
                body.classList.remove('is-final-only');
                delete body.dataset.loading;
                rebindSubagentCardBody(body, card, agentId);
                body._subagentStreamCtx = getSubagentCardStreamCtx(body, card, agentId);
                subagentCardLoadInflight -= 1;
                delete subagentCardLoadQueued[agentId];
                drainSubagentCardLoadQueue();
                return;
            }
            loadSubagentDetailInto(body, agentId, card, sessionId).finally(function () {
                subagentCardLoadInflight -= 1;
                delete subagentCardLoadQueued[agentId];
                drainSubagentCardLoadQueue();
            });
        })(job.card, job.agentId, job.sessionId);
    }
}

function queueSubagentCardBodyLoad(card, sessionIdOpt) {
    if (!card || !shouldLoadSubagentCardBodies()) return;
    if (!card.classList.contains('is-expanded') && card.dataset.viewportVisible !== '1') return;
    var sessionId = sessionIdOpt || currentSessionId;
    var agentId = card.getAttribute('data-agent-id');
    if (!agentId || subagentCardLoadQueued[agentId]) return;
    var body = card.querySelector('.subagent-card-body');
    if (!body || body.dataset.loading === '1') return;
    if (subagentBodyIsLoaded(body) && !(card.classList.contains('is-expanded') && body.dataset.finalOnly === '1')) return;
    subagentCardLoadQueued[agentId] = true;
    subagentCardLoadQueue.push({ card: card, agentId: agentId, sessionId: sessionId });
    drainSubagentCardLoadQueue();
}

function cardIntersectsGridViewport(card, grid) {
    if (!card || !grid || !card.isConnected) return false;
    var cr = card.getBoundingClientRect();
    var gr = grid.getBoundingClientRect();
    return cr.bottom > gr.top + 4 && cr.top < gr.bottom - 4;
}

function loadVisibleSubagentCardBodies(grid, sessionIdOpt) {
    if (!grid || !shouldLoadSubagentCardBodies()) return;
    ensureSubagentCardViewportObserver(grid);
    var sessionId = sessionIdOpt || currentSessionId;
    grid.querySelectorAll('.subagent-grid-card').forEach(function (card) {
        observeSubagentCardViewport(card);
        if (card.classList.contains('is-expanded')) {
            card.dataset.viewportVisible = '1';
            card.classList.add('is-viewport-visible');
            queueSubagentCardBodyLoad(card, sessionId);
        } else if (cardIntersectsGridViewport(card, grid)) {
            card.dataset.viewportVisible = '1';
            card.classList.add('is-viewport-visible');
            queueSubagentCardBodyLoad(card, sessionId);
        }
    });
}

function normalizeSubagentMessagesPayload(data) {
    if (Array.isArray(data)) return data;
    if (data && Array.isArray(data.events)) return data.events;
    return [];
}

function findSubagentSliceStartByTurns(events, beforeIndex, turnCount) {
    var arr = events || [];
    var limit = Math.max(0, Math.min(arr.length - 1, Number(beforeIndex) || 0));
    var found = 0;
    for (var i = limit - 1; i >= 0; i -= 1) {
        if (arr[i] && arr[i].type === 'user') {
            found += 1;
            if (found >= turnCount) return i;
        }
    }
    return 0;
}

function bindSubagentFinalOnlyHistoryLoader(bodyEl, hostEl, agentId, hasOlder, rangeStart) {
    if (!bodyEl || bodyEl.dataset.finalOnlyLoaderBound === '1') return;
    bodyEl.dataset.finalOnlyLoaderBound = '1';

    bodyEl._hasOlderEvents = hasOlder !== false;
    bodyEl._rangeStart = typeof rangeStart === 'number' ? rangeStart : 0;
    bodyEl._historyLoadedEvents = [];

    function loadMoreHistory() {
        if (!bodyEl.isConnected || bodyEl.dataset.historyLoading === '1' || bodyEl.dataset.historyComplete === '1') return;

        if (!bodyEl._hasOlderEvents) {
            bodyEl.dataset.historyComplete = '1';
            delete bodyEl.dataset.finalOnly;
            bodyEl.classList.remove('is-final-only');
            return;
        }

        var oldScrollHeight = bodyEl.scrollHeight || 0;
        var oldScrollTop = bodyEl.scrollTop || 0;
        bodyEl.dataset.historyLoading = '1';

        var beforeIndex = bodyEl._rangeStart;
        var turnsParam = '&turns=' + SUBAGENT_HISTORY_TURNS_PER_PAGE;
        var url = '/sessions/' + encodeURIComponent(agentId) + '/messages?before_index=' + beforeIndex + turnsParam;

        fetch(url)
            .then(function(resp) {
                if (!resp.ok) throw new Error('HTTP ' + resp.status);
                return resp.json();
            })
            .then(function(data) {
                if (!bodyEl.isConnected) return;

                var events, hasOlderNew, rangeStartNew;
                if (data && Array.isArray(data)) {
                    events = data;
                    hasOlderNew = false;
                    rangeStartNew = 0;
                } else if (data && Array.isArray(data.events)) {
                    events = data.events;
                    hasOlderNew = !!data.has_older;
                    rangeStartNew = typeof data.range_start === 'number' ? data.range_start : 0;
                } else {
                    events = [];
                    hasOlderNew = false;
                    rangeStartNew = 0;
                }

                bodyEl._hasOlderEvents = hasOlderNew;
                bodyEl._rangeStart = rangeStartNew;
                bodyEl._historyLoadedEvents = events.concat(bodyEl._historyLoadedEvents);

                var allEvents = bodyEl._historyLoadedEvents;
                void renderSubagentProcessEvents(bodyEl, hostEl, allEvents, agentId, 0).then(function () {
                    if (!bodyEl._hasOlderEvents || events.length === 0) {
                        bodyEl.dataset.historyComplete = '1';
                        delete bodyEl.dataset.finalOnly;
                        bodyEl.classList.remove('is-final-only');
                    }
                    requestAnimationFrame(function () {
                        if (!bodyEl.isConnected) return;
                        var keepTop = Math.max(0, (bodyEl.scrollHeight || 0) - oldScrollHeight + oldScrollTop);
                        bodyEl.scrollTop = keepTop;
                    });
                });
            })
            .catch(function(err) {
                console.error('加载subagent历史失败:', err);
            })
            .finally(function() {
                delete bodyEl.dataset.historyLoading;
            });
    }

    bodyEl.addEventListener('wheel', function (ev) {
        if (ev.deltaY < 0) loadMoreHistory();
    }, { passive: true });
    bodyEl.addEventListener('scroll', function () {
        if (bodyEl.scrollTop <= 8) loadMoreHistory();
    }, { passive: true });
}

async function loadSubagentOutputAsFinalEvent(parentSessionId, agentId) {
    if (!parentSessionId || !agentId) throw new Error('missing subagent output context');
    var url = '/sessions/' + encodeURIComponent(parentSessionId)
        + '/subagents/' + encodeURIComponent(agentId) + '/output';
    var resp = await fetch(url);
    var data = null;
    try { data = await resp.json(); } catch (ignore) { /* handled below */ }
    if (!resp.ok || !data || !data.ok) {
        throw new Error((data && data.error) || ('HTTP ' + resp.status));
    }
    return [{ type: 'final', content: String(data.content || '') }];
}

async function loadSubagentDetailInto(el, agentId, hostEl, sessionIdOpt) {
    if (!el || !agentId) return;
    if (el.dataset.loading === '1') return;
    var card = hostEl || (el.closest ? el.closest('.subagent-grid-card, .subagent-block') : null);
    el.dataset.loading = '1';
    delete el.dataset.loaded;
    el.innerHTML = '<div class="subagent-detail-empty">加载详情中…</div>';
    try {
        var isCollapsed = card && card.classList && !card.classList.contains('is-expanded') && card.classList.contains('subagent-grid-card');
        var parentSessionId = sessionIdOpt || currentSessionId || '';
        var virtualTask = !!(card && card.dataset && card.dataset.virtualTask === '1');
        var data;
        if (virtualTask) {
            data = { events: await loadSubagentOutputAsFinalEvent(parentSessionId, agentId) };
        } else {
            var turnsParam = isCollapsed ? '&turns=3' : '&turns=10';
            var resp = await fetch('/sessions/' + encodeURIComponent(agentId) + '/messages?' + turnsParam);
            if (!resp.ok) {
                var canUseOutput = !!(card && card.dataset && card.dataset.outputFile === '1' && parentSessionId);
                if (!canUseOutput) throw new Error('HTTP ' + resp.status);
                try {
                    data = { events: await loadSubagentOutputAsFinalEvent(parentSessionId, agentId) };
                } catch (outputError) {
                    throw new Error('HTTP ' + resp.status + '; output fallback failed: ' + String(outputError));
                }
            } else {
                data = await resp.json();
            }
        }

        var events, hasOlder, rangeStart;
        if (data && Array.isArray(data)) {
            events = data;
            hasOlder = false;
            rangeStart = 0;
        } else if (data && Array.isArray(data.events)) {
            events = data.events;
            hasOlder = !!data.has_older;
            rangeStart = typeof data.range_start === 'number' ? data.range_start : 0;
        } else {
            events = [];
            hasOlder = false;
            rangeStart = 0;
        }

        if (!el.isConnected) return;
        await new Promise(function (resolve) { setTimeout(resolve, 0); });

        if (isCollapsed) {
            await renderSubagentLatestFinalOnly(el, card, events, agentId);
            bindSubagentFinalOnlyHistoryLoader(el, card, agentId, hasOlder, rangeStart);
        } else {
            await renderSubagentProcessEvents(el, card, events, agentId);
        }
        el.dataset.loaded = '1';
        delete el.dataset.streamReady;
        setSubagentCardEventCount(agentId, events.length);
    } catch (e) {
        if (!el.isConnected) return;
        el.innerHTML = '<div class="subagent-detail-empty">加载失败: ' + escapeHtml(String(e)) + '</div>';
        el.dataset.loaded = '1';
    } finally {
        delete el.dataset.loading;
    }
}
`,Mt=`var subagentCardSyncTimer = null;
var subagentContextFetchInFlight = Object.create(null);
var subagentTreeRefreshTimer = null;
var subagentTreeRefreshTarget = null;
var subagentTreeRefreshInflightBySession = Object.create(null);
var subagentTreeRefreshQueuedBySession = Object.create(null);
var subagentStatsRefreshRaf = 0;
var subagentStatsPending = new Set();

function scheduleSubagentCardStats(card) {
    if (!card) return;
    if (subagentPanelOpen
        && !card.classList.contains('is-expanded')
        && card.dataset.viewportVisible !== '1') return;
    subagentStatsPending.add(card);
    if (subagentStatsRefreshRaf) return;
    subagentStatsRefreshRaf = setTimeout(function () {
        subagentStatsRefreshRaf = 0;
        var cards = Array.from(subagentStatsPending);
        subagentStatsPending.clear();
        cards.forEach(refreshSubagentCardStats);
    }, 250);
}

function getSubagentIncrementalSyncDelay(runningCount) {
    if (isSessionRunning(currentSessionId)) return 8000;
    if (runningCount > 20) return 6000;
    if (runningCount > 10) return 4000;
    if (runningCount > 5) return 3000;
    return 2200;
}

function runTasksWithConcurrency(items, limit, worker) {
    if (!items || !items.length) return Promise.resolve();
    var idx = 0;
    var n = Math.max(1, Math.min(limit || 1, items.length));
    function next() {
        if (idx >= items.length) return Promise.resolve();
        var cur = idx++;
        return Promise.resolve(worker(items[cur], cur)).then(next);
    }
    var starters = [];
    for (var i = 0; i < n; i += 1) starters.push(next());
    return Promise.all(starters);
}

function scheduleRefreshSubagentTreePanel(sessionId, delayMs) {
    if (!sessionId || replayingMessages) return;
    subagentTreeRefreshTarget = sessionId;
    if (subagentTreeRefreshTimer) clearTimeout(subagentTreeRefreshTimer);
    subagentTreeRefreshTimer = setTimeout(function () {
        subagentTreeRefreshTimer = null;
        var sid = subagentTreeRefreshTarget;
        subagentTreeRefreshTarget = null;
        if (sid && sid === currentSessionId) void refreshSubagentTreePanel(sid);
    }, delayMs == null ? 150 : delayMs);
}

function cancelScheduledSubagentTreeRefresh() {
    if (subagentTreeRefreshTimer) {
        clearTimeout(subagentTreeRefreshTimer);
        subagentTreeRefreshTimer = null;
    }
    subagentTreeRefreshTarget = null;
    subagentTreeRefreshQueuedBySession = Object.create(null);
}

function stopSubagentIncrementalSync() {
    if (subagentCardSyncTimer) {
        clearTimeout(subagentCardSyncTimer);
        subagentCardSyncTimer = null;
    }
}

function scheduleSubagentIncrementalSync() {
    if (subagentCardSyncTimer) return;
    var delay = isSessionRunning(currentSessionId) ? 4000 : 1200;
    subagentCardSyncTimer = setTimeout(function () {
        subagentCardSyncTimer = null;
        runSubagentIncrementalSync();
    }, delay);
}

function countRunningSubagentCards() {
    var n = 0;
    document.querySelectorAll('.subagent-grid-card .subagent-status-dot.is-running').forEach(function () { n += 1; });
    return n;
}

async function runSubagentIncrementalSync() {
    var grid = document.getElementById('subagent-grid');
    if (!grid || !currentSessionId || !subagentPanelOpen) {
        stopSubagentIncrementalSync();
        return;
    }
    if (document.visibilityState !== 'visible') {
        subagentCardSyncTimer = setTimeout(function () {
            subagentCardSyncTimer = null;
            runSubagentIncrementalSync();
        }, 5000);
        return;
    }
    var tasks = [];
    grid.querySelectorAll('.subagent-grid-card').forEach(function (card) {
        var dot = card.querySelector('.subagent-status-dot.is-running');
        if (!dot) return;
        var aid = card.getAttribute('data-agent-id');
        if (!aid) return;
        tasks.push({ aid: aid, card: card });
    });
    if (tasks.length) {
        await runTasksWithConcurrency(tasks, 1, function (t) {
            return incrementalSyncSubagentCard(t.aid, t.card);
        });
    }
    var runningN = countRunningSubagentCards();
    if (runningN === 0 && currentSessionId && !replayingMessages) {
        updateSubagentContinueBanner(currentSessionId);
        void tryMarkSessionUnreadComplete(currentSessionId);
    }
    if (runningN > 0 && subagentPanelOpen) {
        subagentCardSyncTimer = setTimeout(function () {
            subagentCardSyncTimer = null;
            runSubagentIncrementalSync();
        }, getSubagentIncrementalSyncDelay(runningN));
    }
}

async function incrementalSyncSubagentCard(agentId, card) {
    if (!agentId || !card) return;
    var body = card.querySelector('.subagent-card-body');
    if (!body || body.dataset.loading === '1') return;
    if (!shouldLoadSubagentCardBodies() && body.dataset.loaded !== '1') return;
    var parentRunning = isSessionRunning(currentSessionId);
    var prevCount = currentSessionId ? subagentStore.getEventCount(currentSessionId, agentId) : 0;
    var summaryOnly = !shouldStreamSubagentProcessDom(card);
    try {
        var afterIndex = Math.max(-1, Math.floor(Number(prevCount) || 0) - 1);
        var msgResp = await fetch('/sessions/' + encodeURIComponent(agentId)
            + '/messages?after_index=' + encodeURIComponent(String(afterIndex))
            + '&limit=500');
        if (!msgResp.ok) return;
        var msgData = await msgResp.json();
        var events = normalizeSubagentMessagesPayload(msgData);
        var rangeStart = msgData && Number.isFinite(Number(msgData.range_start))
            ? Math.floor(Number(msgData.range_start))
            : Math.max(0, afterIndex + 1);
        var total = msgData && Number.isFinite(Number(msgData.total))
            ? Math.floor(Number(msgData.total))
            : Math.max(prevCount, rangeStart + events.length);
        if (!events.length || total <= prevCount) {
            if (total > prevCount) setSubagentCardEventCount(agentId, total);
            return;
        }
        if (parentRunning && body.dataset.loaded === '1') {
            setSubagentCardEventCount(agentId, total);
            return;
        }
        if (!body.isConnected) return;
        var gotFinal = false;
        for (var fi = 0; fi < events.length; fi += 1) {
            if (events[fi] && events[fi].type === 'final') { gotFinal = true; break; }
        }
        if (body.dataset.loaded !== '1') {
            if (!shouldLoadSubagentCardBodies()) return;
            if (summaryOnly) {
                ensureSubagentCardStreamReady(card, agentId);
                var ctxNew = getSubagentCardStreamCtx(body, card, agentId);
                for (var si = 0; si < events.length; si += 1) {
                    var sev = events[si];
                    if (!sev || typeof sev !== 'object') continue;
                    if (sev.type !== 'user' && sev.type !== 'final') continue;
                    dispatchSubagentCardEvent(ctxNew, card, sev, rangeStart + si, agentId);
                }
                rebindSubagentCardBody(body, card, agentId);
            } else {
                renderSubagentProcessEvents(body, card, events, agentId, rangeStart);
            }
            setSubagentCardEventCount(agentId, total);
            if (gotFinal) markSubagentCardCompleted(card, true);
            return;
        }
        var ctx = getSubagentCardStreamCtx(body, card, agentId);
        for (var i = 0; i < events.length; i += 1) {
            if (events[i] && typeof events[i] === 'object') {
                if (summaryOnly && events[i].type !== 'user' && events[i].type !== 'final' && !events[i].ephemeral) continue;
                dispatchSubagentCardEvent(ctx, card, events[i], rangeStart + i, agentId);
            }
        }
        rebindSubagentCardBody(body, card, agentId);
        setSubagentCardEventCount(agentId, total);
        if (gotFinal) markSubagentCardCompleted(card, true);
    } catch (e) { /* ignore */ }
}

async function refreshSubagentContextForCard(card, agentId, force) {
    if (!card || !agentId) return;
    if (!force && !subagentPanelOpen) return;
    if (!force && card.dataset.procCtxEstimated != null && card.dataset.procCtxEstimated !== '') return;
    if (subagentContextFetchInFlight[agentId]) return subagentContextFetchInFlight[agentId];
    subagentContextFetchInFlight[agentId] = (async function () {
        try {
            var r = await fetch('/sessions/' + encodeURIComponent(agentId) + '/context_tokens');
            var j = await r.json();
            if (r.ok && j && j.ok && j.estimated != null && j.estimated >= 0) {
                card.dataset.procCtxEstimated = String(j.estimated);
                card.dataset.procCtxThreshold = String(j.threshold);
                refreshSubagentCardStats(card);
            }
        } catch (e) { /* ignore */ }
        finally {
            delete subagentContextFetchInFlight[agentId];
        }
    })();
    return subagentContextFetchInFlight[agentId];
}

async function refreshSubagentTreePanel(sessionId) {
    if (!sessionId || sessionId !== currentSessionId) return;
    var inflight = subagentTreeRefreshInflightBySession[sessionId];
    if (inflight) {
        subagentTreeRefreshQueuedBySession[sessionId] = true;
        return inflight;
    }
    var refreshPromise = refreshSubagentTreePanelInner(sessionId);
    subagentTreeRefreshInflightBySession[sessionId] = refreshPromise;
    try {
        return await refreshPromise;
    } finally {
        if (subagentTreeRefreshInflightBySession[sessionId] === refreshPromise) {
            delete subagentTreeRefreshInflightBySession[sessionId];
        }
        if (subagentTreeRefreshQueuedBySession[sessionId] && sessionId === currentSessionId) {
            delete subagentTreeRefreshQueuedBySession[sessionId];
            void refreshSubagentTreePanel(currentSessionId);
        } else {
            delete subagentTreeRefreshQueuedBySession[sessionId];
        }
    }
}

async function refreshSubagentTreePanelInner(sessionId) {
    bindSubagentPanelOnce();
    var seq = ++subagentPanelRefreshSeq;
    var grid = document.getElementById('subagent-grid');
    var toggleBtn = document.getElementById('subagent-toggle-btn');
    if (sessionId !== currentSessionId) return;
    if (!grid || !sessionId) {
        if (toggleBtn) toggleBtn.classList.add('hidden');
        closeSubagentPanel();
        stopSubagentIncrementalSync();
        return;
    }
    if (grid.dataset.sessionId && grid.dataset.sessionId !== sessionId) {
        grid.innerHTML = '';
        subagentStore.clearEventCounts(sessionId);
    }
    grid.dataset.sessionId = sessionId;
    try {
        var resp = await fetch('/sessions/' + encodeURIComponent(sessionId) + '/subagents?lite=1');
        if (seq !== subagentPanelRefreshSeq || sessionId !== currentSessionId) return;
        var data = await resp.json();
        var flat = (data && data.subagents) ? data.subagents : [];
        applySubagentSnapshot(sessionId, flat);
        flat = selectSubagentList(sessionId);
        if (!flat.length) {
            if (toggleBtn) toggleBtn.classList.add('hidden');
            closeSubagentPanel();
            grid.innerHTML = '';
            grid.dataset.sessionId = sessionId;
            subagentStore.clearEventCounts(sessionId);
            stopSubagentIncrementalSync();
            return;
        }
        refreshSubagentToggleFromGrid(flat);
        syncSubagentGridFromFlat(flat, sessionId);
        if (seq !== subagentPanelRefreshSeq || sessionId !== currentSessionId) return;
        if (subagentPanelOpen) {
            document.getElementById('subagent-dock').classList.remove('hidden');
            ensureSubagentCardViewportObserver(grid);
            grid.querySelectorAll('.subagent-grid-card').forEach(function (card) {
                observeSubagentCardViewport(card);
                if (card.classList.contains('is-expanded')) {
                    scheduleSubagentCardStats(card);
                }
            });
            loadVisibleSubagentCardBodies(grid, sessionId);
            flat.forEach(function (n) {
                if (!n || !n.id) return;
                var card = grid.querySelector('.subagent-grid-card[data-agent-id="' + String(n.id || '') + '"]');
                if (card && card.classList.contains('is-expanded')) {
                    refreshSubagentContextForCard(card, String(n.id || ''), true);
                }
            });
        }
        var runningN = selectSubagentRunningCount(sessionId);
        if (runningN > 0 && subagentPanelOpen) scheduleSubagentIncrementalSync();
        else {
            stopSubagentIncrementalSync();
            if (sessionId === currentSessionId) updateSubagentContinueBanner(sessionId);
        }
    } catch (e) {
        if (seq !== subagentPanelRefreshSeq || sessionId !== currentSessionId) return;
        if (toggleBtn) toggleBtn.classList.add('hidden');
        closeSubagentPanel();
        stopSubagentIncrementalSync();
    }
}
`,Ft=`async function toggleSubagentOutputPanel(card, sessionId) {
    if (!card || !sessionId) return;
    var agentId = card.getAttribute('data-agent-id') || '';
    if (!agentId) return;
    var panel = card.querySelector('.subagent-output-panel');
    if (!panel) {
        panel = document.createElement('div');
        panel.className = 'subagent-output-panel';
        var body = card.querySelector('.subagent-card-body');
        if (body) card.insertBefore(panel, body);
        else card.appendChild(panel);
    }
    var wasOpen = panel.classList.contains('is-open');
    panel.classList.toggle('is-open', !wasOpen);
    var btn = card.querySelector('.subagent-card-output');
    if (btn) btn.classList.toggle('is-active', !wasOpen);
    if (wasOpen || panel.dataset.loaded === '1' || panel.dataset.loading === '1') return;
    panel.dataset.loading = '1';
    panel.innerHTML = '<div class="subagent-output-empty">加载中...</div>';
    try {
        var resp = await fetch('/sessions/' + encodeURIComponent(sessionId) + '/subagents/' + encodeURIComponent(agentId) + '/output');
        var data = await resp.json();
        if (!resp.ok || !data || !data.ok) throw new Error((data && data.error) || ('HTTP ' + resp.status));
        var content = String(data.content || '').trim();
        panel.innerHTML = content
            ? '<div class="subagent-output-content markdown-body">' + renderMarkdown(content) + '</div>'
            : '<div class="subagent-output-empty">(无输出)</div>';
        enhanceAssistantMessageContent(panel);
        panel.dataset.loaded = '1';
    } catch (e) {
        panel.innerHTML = '<div class="subagent-output-empty">加载失败: ' + escapeHtml(String(e)) + '</div>';
    } finally {
        delete panel.dataset.loading;
    }
}

function bindSubagentGridActions(grid, sessionId) {
    if (!grid) return;
    grid.querySelectorAll('.subagent-grid-card').forEach(function (card) {
        bindProcessAggregate(card);
    });
    grid.querySelectorAll('.subagent-card-stop').forEach(function (btn) {
        if (btn.dataset.subagentStopBound) return;
        btn.dataset.subagentStopBound = '1';
        btn.addEventListener('click', async function (e) {
            e.stopPropagation();
            var aid = btn.getAttribute('data-agent-id');
            if (!aid || !sessionId) return;
            try {
                await fetch('/sessions/' + encodeURIComponent(sessionId) + '/subagents/' + encodeURIComponent(aid) + '/interrupt', { method: 'POST' });
            } catch (err) { /* ignore */ }
            var menu = btn.closest('.subagent-card-menu');
            if (menu) menu.classList.remove('is-open');
            scheduleRefreshSubagentTreePanel(sessionId);
        });
    });
    grid.querySelectorAll('.subagent-card-delete').forEach(function (btn) {
        if (btn.dataset.subagentDeleteBound) return;
        btn.dataset.subagentDeleteBound = '1';
        btn.addEventListener('click', async function (e) {
            e.stopPropagation();
            var aid = btn.getAttribute('data-agent-id');
            if (!aid || !sessionId) return;
            var ok = await openUiModal({
                title: '删除 Subagent',
                subtitle: aid.slice(0, 8) + '…',
                message: '将删除该 subagent 的会话记录、过程卡片及其嵌套子任务。该操作不可撤销。',
                danger: true,
                confirmText: '删除',
                cancelText: '取消',
            });
            if (!ok) return;
            var menu = btn.closest('.subagent-card-menu');
            if (menu) menu.classList.remove('is-open');
            btn.disabled = true;
            try {
                var resp = await fetch('/sessions/' + encodeURIComponent(sessionId) + '/subagents/' + encodeURIComponent(aid), { method: 'DELETE' });
                if (!resp.ok) {
                    showUiAlert({ title: '删除失败', message: '无法删除该 Subagent，请稍后重试。', variant: 'error' });
                    btn.disabled = false;
                    return;
                }
                forgetSubagentBodyCache(sessionId, aid);
                subagentStore.remove(sessionId, aid);
                delete subagentCardLoadQueued[aid];
                var card = btn.closest('.subagent-grid-card');
                if (card) card.remove();
                scheduleRefreshSubagentTreePanel(sessionId, 0);
            } catch (err) {
                btn.disabled = false;
                showUiAlert({ title: '删除失败', message: String((err && err.message) || err || 'unknown error'), variant: 'error' });
            }
        });
    });
    grid.querySelectorAll('.subagent-card-menu-btn').forEach(function (btn) {
        if (btn.dataset.subagentMenuBound) return;
        btn.dataset.subagentMenuBound = '1';
        btn.addEventListener('click', function (e) {
            e.stopPropagation();
            var menu = btn.closest('.subagent-card-menu');
            if (!menu) return;
            var open = !menu.classList.contains('is-open');
            grid.querySelectorAll('.subagent-card-menu.is-open').forEach(function (m) {
                if (m !== menu) {
                    m.classList.remove('is-open');
                    var b = m.querySelector('.subagent-card-menu-btn');
                    if (b) b.setAttribute('aria-expanded', 'false');
                }
            });
            menu.classList.toggle('is-open', open);
            btn.setAttribute('aria-expanded', open ? 'true' : 'false');
        });
    });
    grid.querySelectorAll('.subagent-card-expand').forEach(function (btn) {
        if (btn.dataset.subagentExpandBound) return;
        btn.dataset.subagentExpandBound = '1';
        btn.addEventListener('click', function (e) {
            e.stopPropagation();
            var card = btn.closest('.subagent-grid-card');
            if (card) toggleSubagentCardExpanded(card);
        });
    });
    grid.querySelectorAll('.subagent-card-body').forEach(function (body) {
        if (body.dataset.subagentBodyExpandBound) return;
        body.dataset.subagentBodyExpandBound = '1';
        body.addEventListener('click', function (e) {
            var card = body.closest('.subagent-grid-card');
            if (!card || card.classList.contains('is-expanded')) return;
            var target = e.target;
            if (target && target.closest && target.closest('button,a,input,textarea,select,.feed-chunk-scroller,.copy-btn,.subagent-card-menu,.msg-wrap--user')) return;
            var sel = window.getSelection && window.getSelection();
            if (sel && String(sel).trim()) return;
            setSubagentCardExpanded(card, true);
        });
    });
    grid.querySelectorAll('.subagent-card-output').forEach(function (btn) {
        if (btn.dataset.subagentOutputBound) return;
        btn.dataset.subagentOutputBound = '1';
        btn.addEventListener('click', function (e) {
            e.stopPropagation();
            var card = btn.closest('.subagent-grid-card');
            if (card) toggleSubagentOutputPanel(card, sessionId);
            var menu = btn.closest('.subagent-card-menu');
            if (menu) menu.classList.remove('is-open');
        });
    });
    syncSubagentExpandButtons(grid);
    initUiHoverTips(grid);
}
`,Bt=`function onSubagentDockWheel(e) {
    var dock = document.getElementById('subagent-dock');
    if (!dock || dock.classList.contains('hidden') || !dock.contains(e.target)) return;
    var dy = e.deltaY;
    var eps = 2;
    var node = e.target;
    while (node && node !== dock) {
        if (node.nodeType === 1) {
            var style = window.getComputedStyle(node);
            var scrollable = node.classList && (
                node.classList.contains('subagent-grid') ||
                node.classList.contains('process-aggregate-body') ||
                node.classList.contains('process-aggregate-brief') ||
                node.classList.contains('feed-chunk-scroller')
            );
            if (scrollable || /(auto|scroll|overlay)/.test(style.overflowY)) {
                if (node.scrollHeight > node.clientHeight + eps) {
                    var st = node.scrollTop;
                    var max = node.scrollHeight - node.clientHeight;
                    if (dy < 0 && st > eps) {
                        e.stopPropagation();
                        return;
                    }
                    if (dy > 0 && st < max - eps) {
                        e.stopPropagation();
                        return;
                    }
                }
            }
        }
        node = node.parentElement;
    }
    var grid = dock.querySelector('.subagent-grid');
    if (grid && grid.scrollHeight > grid.clientHeight + eps) {
        var gst = grid.scrollTop;
        var gmax = grid.scrollHeight - grid.clientHeight;
        var next = Math.max(0, Math.min(gmax, gst + dy));
        if (next !== gst) grid.scrollTop = next;
    }
    e.preventDefault();
    e.stopPropagation();
}

function syncSubagentDockResizeUi() {
    var dock = document.getElementById('subagent-dock');
    var resizeBtn = document.getElementById('subagent-dock-resize');
    if (!dock || !resizeBtn) return;
    dock.classList.toggle('is-expanded', subagentDockExpanded);
    resizeBtn.setAttribute('aria-label', subagentDockExpanded ? '收起 Subagent 面板' : '展开 Subagent 面板');
}

function toggleSubagentDockExpand() {
    var grid = document.getElementById('subagent-grid');
    if (grid) {
        grid.classList.add('is-resizing');
        stashSubagentInactiveBodies(grid, grid.querySelector('.subagent-grid-card.is-expanded'));
    }
    subagentDockExpanded = !subagentDockExpanded;
    syncSubagentDockResizeUi();
    if (grid) {
        requestAnimationFrame(function () {
            grid.classList.remove('is-resizing');
            loadVisibleSubagentCardBodies(grid, currentSessionId);
        });
    }
}

function bindSubagentPanelOnce() {
    if (subagentPanelBound) return;
    subagentPanelBound = true;
    var dock = document.getElementById('subagent-dock');
    var panel = dock && dock.querySelector('.subagent-panel');
    if (dock) dock.addEventListener('wheel', onSubagentDockWheel, { passive: false, capture: true });
    if (panel) panel.addEventListener('wheel', onSubagentDockWheel, { passive: false, capture: true });
    var btn = document.getElementById('subagent-toggle-btn');
    if (btn) {
        btn.addEventListener('click', function (e) {
            e.stopPropagation();
            if (subagentPanelOpen) closeSubagentPanel();
            else openSubagentPanel();
        });
    }
    var resizeBtn = document.getElementById('subagent-dock-resize');
    if (resizeBtn && !resizeBtn.dataset.subagentBound) {
        resizeBtn.dataset.subagentBound = '1';
        resizeBtn.addEventListener('click', function (e) {
            e.stopPropagation();
            toggleSubagentDockExpand();
        });
    }
    document.addEventListener('mousedown', function (e) {
        if (!subagentPanelOpen) return;
        if (!(e.target && e.target.closest && e.target.closest('.subagent-card-menu'))) {
            document.querySelectorAll('.subagent-card-menu.is-open').forEach(function (menu) {
                menu.classList.remove('is-open');
                var mb = menu.querySelector('.subagent-card-menu-btn');
                if (mb) mb.setAttribute('aria-expanded', 'false');
            });
        }
        var dock = document.getElementById('subagent-dock');
        var btnEl = document.getElementById('subagent-toggle-btn');
        if (dock && dock.contains(e.target)) return;
        if (btnEl && btnEl.contains(e.target)) return;
        closeSubagentPanel();
    });
}
`,Nt=`const contextStore = {
    tokensBySession: new Map(),
    todoBySession: new Map(),
    progressBySession: new Map(),

    setTokens(sessionId, estimated, threshold) {
        const sid = String(sessionId || '');
        if (!sid) return;
        if (estimated != null && Number(estimated) >= 0) {
            this.tokensBySession.set(sid, {
                estimated: Number(estimated),
                threshold: threshold,
                updatedAt: Date.now(),
            });
        } else {
            this.tokensBySession.delete(sid);
        }
    },

    getTokens(sessionId) {
        return this.tokensBySession.get(String(sessionId || '')) || null;
    },

    clearTokens(sessionId) {
        this.tokensBySession.delete(String(sessionId || ''));
    },

    setTodo(sessionId, payload) {
        const sid = String(sessionId || '');
        if (!sid) return null;
        const data = payload && typeof payload === 'object' ? payload : {};
        const items = Array.isArray(data.items) ? data.items.slice() : [];
        const done = typeof data.done === 'number'
            ? data.done
            : items.filter(function (x) { return x && x.status === 'completed'; }).length;
        const total = typeof data.total === 'number' ? data.total : items.length;
        const snapshot = {
            has_plan: !!(data.has_plan && items.length > 0),
            items: items,
            done: done,
            total: total,
            updatedAt: Date.now(),
        };
        this.todoBySession.set(sid, snapshot);
        return snapshot;
    },

    getTodo(sessionId) {
        return this.todoBySession.get(String(sessionId || '')) || null;
    },

    clearTodo(sessionId) {
        this.todoBySession.delete(String(sessionId || ''));
    },

    appendProgress(sessionId, kind, delta) {
        const sid = String(sessionId || '');
        const k = String(kind || '');
        if (!sid || !k) return null;
        let st = this.progressBySession.get(sid);
        if (!st) {
            st = {
                sessionId: sid,
                contextSummary: '',
                keyContext: '',
                updatedAt: 0,
            };
            this.progressBySession.set(sid, st);
        }
        const text = delta == null ? '' : String(delta);
        if (k === 'context-summary') st.contextSummary += text;
        else if (k === 'key-context') st.keyContext += text;
        st.updatedAt = Date.now();
        return st;
    },

    clearProgress(sessionId) {
        this.progressBySession.delete(String(sessionId || ''));
    },

    clearSession(sessionId) {
        const sid = String(sessionId || '');
        if (!sid) return;
        this.clearTokens(sid);
        this.clearTodo(sid);
        this.clearProgress(sid);
    },
};

function setContextTokensForSession(sessionId, estimated, threshold) {
    contextStore.setTokens(sessionId, estimated, threshold);
}

function selectContextTokens(sessionId) {
    return contextStore.getTokens(sessionId);
}

function clearContextStateForSession(sessionId) {
    contextStore.clearSession(sessionId);
}

function applyTodoPlanToStore(sessionId, payload) {
    return contextStore.setTodo(sessionId, payload);
}

function selectTodoPlan(sessionId) {
    return contextStore.getTodo(sessionId);
}

function clearTodoPlanState(sessionId) {
    contextStore.clearTodo(sessionId);
}

function appendContextProgressForSession(sessionId, kind, delta) {
    return contextStore.appendProgress(sessionId, kind, delta);
}

function selectContextProgress(sessionId) {
    return contextStore.progressBySession.get(String(sessionId || '')) || null;
}
`,Ot=`function markUiEventStoreApplied(event) {
    if (!event || typeof event !== 'object') return;
    try {
        Object.defineProperty(event, '__storeApplied', {
            value: true,
            configurable: true,
            enumerable: false,
        });
    } catch (e) {
        event.__storeApplied = true;
    }
}

function applySessionEvent(event, opts) {
    if (!event || typeof event !== 'object') return { handled: false };
    opts = opts || {};
    const sessionId = String(
        opts.sessionId
        || event.session_id
        || event.sessionId
        || currentSessionId
        || ''
    );
    const eventIndex = opts.eventIndex;
    const source = opts.source || 'event';
    const type = String(event.type || '');
    const runId = String(event.run_id || event.runId || '').trim();
    let messageRecord = null;
    const ephemeral = !!event.ephemeral;
    const isLiveOnlyDelta = ephemeral && (
        type === 'llm_reasoning_delta'
        || type === 'llm_response_delta'
        || type === 'tool_call_delta'
        || type === 'tool_command_delta'
        || type === 'context_summary_delta'
        || type === 'key_context_delta'
    );
    if (sessionId && !isLiveOnlyDelta) {
        messageRecord = applyMessageEvent(sessionId, event, eventIndex, source);
        markUiEventStoreApplied(event);
    }
    if (type === 'run_started' || type === 'run_attached') {
        if (runId && sessionStore.isTerminalRun(sessionId, runId)) {
            markSessionRunInactive(sessionId);
            return { handled: true, runStateChanged: true, messageRecord: messageRecord };
        }
        const suppressed = typeof isSessionStreamStopSuppressed === 'function'
            && isSessionStreamStopSuppressed(sessionId);
        setSessionServerStreamActive(sessionId, !suppressed);
        const sess = sessionStore.get(sessionId);
        if (sess) {
            sess.run_active = !suppressed;
            sess.run_started_at = suppressed
                ? null
                : (event.started_at || event.startedAt || sess.run_started_at || new Date().toISOString());
        }
        return { handled: true, runStateChanged: true, messageRecord: messageRecord };
    }
    if (type === 'run_finished' || type === 'run_interrupted' || type === 'run_failed') {
        if (runId) sessionStore.markTerminalRun(sessionId, runId);
        const localRun = getSessionRunState(sessionId);
        const localRunId = String((localRun && localRun.runId) || '').trim();
        const activeInfo = sessionStore.activeRunInfoBySession.get(sessionId);
        const activeRunId = String((activeInfo && (activeInfo.run_id || activeInfo.runId)) || '').trim();
        const knownCurrentRunId = localRunId || activeRunId;
        if (runId && knownCurrentRunId && runId !== knownCurrentRunId) {
            return { handled: true, staleTerminalIgnored: true, messageRecord: messageRecord };
        }
        if (type === 'run_finished' && typeof clearSessionStreamStopSuppress === 'function') clearSessionStreamStopSuppress(sessionId);
        markSessionRunInactive(sessionId);
        const sess = sessionStore.get(sessionId);
        if (sess) {
            sess.unread_result = true;
            sess.unread_result_status = (type === 'run_interrupted' || type === 'run_failed') ? 'failed' : 'success';
            sess.unread_result_at = new Date().toISOString();
        }
        return { handled: true, runStateChanged: true, messageRecord: messageRecord };
    }
    if (type === 'final' && source === 'sse') {
        markSessionRunInactive(sessionId);
        return { handled: false, finalStateChanged: true, messageRecord: messageRecord };
    }
    if (type === 'context_tokens') {
        setContextTokensForSession(sessionId, event.estimated, event.threshold);
        return { handled: false, contextStateChanged: true, messageRecord: messageRecord };
    }
    if (type === 'context_summary_delta') {
        appendContextProgressForSession(sessionId, 'context-summary', event.delta);
        return { handled: false, contextStateChanged: true, messageRecord: messageRecord };
    }
    if (type === 'key_context_delta') {
        appendContextProgressForSession(sessionId, 'key-context', event.delta);
        return { handled: false, contextStateChanged: true, messageRecord: messageRecord };
    }
    if (type === 'todo_plan') {
        applyTodoPlanToStore(sessionId, event);
        return { handled: false, contextStateChanged: true, messageRecord: messageRecord };
    }
    if (type === 'subagent_start' || type === 'subagent_finish'
        || type === 'subagent_started' || type === 'subagent_finished') {
        applySubagentLifecycleToStore(sessionId, event);
        return { handled: false, subagentStateChanged: true, messageRecord: messageRecord };
    }
    return { handled: false, messageRecord: messageRecord };
}
`,qt=`let modelProfilesCache = null;
const modelProfilesRefreshPromises = Object.create(null);
const modelProfileBusyBySession = Object.create(null);
const modelProfileIdBySession = Object.create(null);
const modelProfileToggleBusy = Object.create(null);
let modelProfileSelectionEpoch = 0;
let activeModelProfileId = '';

function h(str) {
    return String(str == null ? '' : str)
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#39;');
}

function modelToggleIcon(action) {
    if (action === 'enable') {
        return '<svg viewBox="0 0 24 24" width="13" height="13" fill="none" stroke="currentColor" stroke-width="2.1" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M12 2v10"/><path d="M18.4 6.6a9 9 0 1 1-12.8 0"/></svg>';
    }
    return '<svg viewBox="0 0 24 24" width="13" height="13" fill="none" stroke="currentColor" stroke-width="2.1" stroke-linecap="round" aria-hidden="true"><circle cx="12" cy="12" r="8.5"/><path d="m5.5 5.5 13 13"/></svg>';
}

function modelToggleHtml(enabled) {
    return '<span class="composer-model-toggle-ico" aria-hidden="true">' + modelToggleIcon(enabled ? 'disable' : 'enable') + '</span>';
}

function profileLabel(profile) {
    if (!profile) return '默认方案';
    return String(profile.name || profile.model || '未命名方案');
}

function formatContextWindow(value) {
    var n = Number(value);
    if (!Number.isFinite(n) || n <= 0) return String(value == null ? '' : value);
    if (n >= 1000000) {
        var m = n / 1000000;
        return String(Math.round(m * 10) / 10).replace(/\\.0$/, '') + 'M';
    }
    if (n >= 1000) return String(Math.round(n / 1000)) + 'k';
    return String(Math.round(n));
}

function profileEffortValue(profile) {
    var p = profile || {};
    var thinkingDisabled = String(p.thinking_mode || '').toLowerCase() === 'disabled';
    return String(p.reasoning_effort || (thinkingDisabled ? 'none' : 'high')).toLowerCase();
}

function profileMeta(profile) {
    if (!profile) return '';
    var model = profile.model || '';
    var effort = profileEffortValue(profile);
    var ctx = profile.context_window ? formatContextWindow(profile.context_window) + ' ctx' : '';
    var out = profile.max_output_tokens ? formatContextWindow(profile.max_output_tokens) + ' out' : '';
    return [model, effort, ctx, out].filter(Boolean).join(' · ');
}

function modelProfileCapabilityDescription(profile) {
    var p = profile || {};
    var language = (document.documentElement && document.documentElement.getAttribute('data-language'))
        || localStorage.getItem('myagent-language')
        || 'zh-CN';
    if (language === 'en' && p.capability_description_en) return String(p.capability_description_en);
    return String(p.capability_description || '');
}

function modelProfileUiLanguage() {
    return (document.documentElement && document.documentElement.getAttribute('data-language'))
        || localStorage.getItem('myagent-language')
        || 'zh-CN';
}

function modelProfileHoverDetail(profile) {
    var p = profile || {};
    var english = modelProfileUiLanguage() === 'en';
    var lines = [
        (english ? 'Model profile: ' : '模型配置：') + profileLabel(p),
        (english ? 'Model ID: ' : '模型 ID：') + String(p.model || (english ? 'Not set' : '未设置')),
        (english ? 'API type: ' : '接口类型：') + String(p.llm_type || 'openai'),
        (english ? 'Context window: ' : '上下文窗口：') + (p.context_window ? formatContextWindow(p.context_window) : (english ? 'Not set' : '未设置')),
        (english ? 'Max output: ' : '最大输出：') + String(p.max_output_tokens || (english ? 'Not set' : '未设置')),
        (english ? 'Thinking effort: ' : '思考强度：') + profileEffortValue(p),
    ];
    var capability = modelProfileCapabilityDescription(p);
    if (capability) lines.push((english ? 'Capability: ' : '能力：') + capability);
    lines.push((english ? 'Status: ' : '状态：') + (
        p.enabled === false
            ? (english ? 'Disabled' : '已禁用')
            : (p.usable === false ? (english ? 'Not ready' : '未就绪') : (english ? 'Available' : '可用'))
    ));
    return lines.join('\\n');
}

function els() {
    return {
        control: document.getElementById('model-profile-control'),
        trigger: document.getElementById('model-profile-trigger'),
        current: document.getElementById('model-profile-current'),
        menu: document.getElementById('model-profile-menu'),
    };
}

async function loadModelProfilesForSwitcher() {
    const response = await fetch('/api/model_profiles', { credentials: 'same-origin' });
    const data = await response.json();
    if (!data || !data.ok) throw new Error((data && data.error) || '模型配置加载失败');
    modelProfilesCache = data;
    return data;
}

function storedProfiles() {
    if (!modelProfilesCache) return [];
    return (modelProfilesCache.profiles || []).filter((profile) => profile);
}

function allProfiles() {
    return storedProfiles().filter((profile) => profile.enabled !== false && profile.usable !== false);
}

function activeProfile() {
    var list = allProfiles();
    for (var i = 0; i < list.length; i += 1) {
        if (String(list[i].id || '') === String(activeModelProfileId || '')) return list[i];
    }
    return list[0] || null;
}

function activeProfileContextWindow() {
    var profile = activeProfile();
    var n = profile && profile.context_window != null ? Number(profile.context_window) : 0;
    return Number.isFinite(n) && n > 0 ? Math.floor(n) : null;
}

function closeModelMenu() {
    var e = els();
    if (e.menu) e.menu.classList.remove('is-open');
    if (e.trigger) {
        e.trigger.classList.remove('is-open');
        e.trigger.setAttribute('aria-expanded', 'false');
    }
}

function openModelMenu() {
    var e = els();
    if (!e.menu || !e.trigger) return;
    constrainModelMenuToTitlebar();
    e.menu.classList.add('is-open');
    e.trigger.classList.add('is-open');
    e.trigger.setAttribute('aria-expanded', 'true');
}

function constrainModelMenuToTitlebar() {
    var e = els();
    if (!e.menu || !e.trigger) return;
    var titlebar = document.querySelector('.titlebar');
    var titlebarBottom = titlebar ? titlebar.getBoundingClientRect().bottom : 44;
    var triggerTop = e.trigger.getBoundingClientRect().top;
    var available = Math.max(1, Math.floor(triggerTop - titlebarBottom - 8));
    var rootSize = parseFloat(getComputedStyle(document.documentElement).fontSize || '16') || 16;
    var cap = Math.floor(44 * rootSize);
    e.menu.style.setProperty('--composer-popover-max-height', Math.min(cap, available) + 'px');
}

function renderModelProfileControl() {
    var e = els();
    if (!e.trigger || !e.current || !e.menu) return;
    var active = activeProfile();
    e.current.textContent = active ? profileLabel(active) : '没有启用的模型配置';
    e.trigger.removeAttribute('title');
    e.trigger.removeAttribute('data-ui-tip');
    var profiles = storedProfiles();
    if (!profiles.length) {
        e.menu.innerHTML = '<button type="button" class="composer-model-option" disabled><span class="composer-model-option-name">没有可用模型配置</span></button>';
        return;
    }
    var html = '';
    for (var i = 0; i < profiles.length; i += 1) {
        var p = profiles[i] || {};
        var id = String(p.id || '');
        var enabled = p.enabled !== false;
        var activeCls = id === String(activeModelProfileId || '') ? ' is-active' : '';
        html += '<div class="composer-model-option-row' + (enabled ? '' : ' is-disabled') + '" data-ui-tip="' + h(modelProfileHoverDetail(p)) + '">'
            + '<button type="button" class="composer-model-option' + activeCls + '" role="option" data-profile-id="' + h(id) + '"' + (enabled ? '' : ' disabled') + '>'
            + '<span class="composer-model-option-name">' + h(profileLabel(p)) + '</span>'
            + '<span class="composer-model-option-meta">' + h(profileMeta(p)) + '</span>'
            + '</button>'
            + '<button type="button" class="composer-model-toggle" data-toggle-profile-id="' + h(id) + '" data-enabled="' + (enabled ? 'true' : 'false') + '" data-ui-tip="' + (enabled ? '禁用' : '启用') + '" aria-label="' + (enabled ? '禁用' : '启用') + '">' + modelToggleHtml(enabled) + '</button>'
            + '</div>';
    }
    e.menu.innerHTML = html;
    if (typeof initUiHoverTips === 'function') initUiHoverTips(e.menu);
    e.menu.querySelectorAll('[data-profile-id]').forEach((btn) => {
        btn.addEventListener('click', () => {
            setCurrentSessionModelProfile(btn.getAttribute('data-profile-id') || '');
            closeModelMenu();
        });
    });
    e.menu.querySelectorAll('[data-toggle-profile-id]').forEach((btn) => {
        btn.addEventListener('click', () => {
            var enabled = btn.getAttribute('data-enabled') !== 'true';
            setModelProfileEnabled(btn.getAttribute('data-toggle-profile-id') || '', enabled);
        });
    });
}

async function setModelProfileEnabled(profileId, enabled) {
    const id = String(profileId || '');
    const sid = String(currentSessionId || '');
    if (!id || modelProfileToggleBusy[id]) return;
    modelProfileToggleBusy[id] = true;
    try {
        var response = await fetch('/api/model_profiles/' + encodeURIComponent(id) + '/enabled', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            credentials: 'same-origin',
            body: JSON.stringify({ enabled: enabled === true }),
        });
        var data = await response.json();
        if (!data || !data.ok) throw new Error((data && data.error) || '模型配置启停失败');
        await refreshModelProfileSelector(sid, { silent: true });
        openModelMenu();
    } catch (err) {
        if (typeof appendLogVisible === 'function') appendLogVisible('模型配置启停失败: ' + String(err.message || err), 'error-log');
    } finally {
        delete modelProfileToggleBusy[id];
    }
}

function renderModelProfileLoadingMenu() {
    var e = els();
    if (!e.menu) return;
    e.menu.innerHTML = '<button type="button" class="composer-model-option" disabled>'
        + '<span class="composer-model-option-name">正在加载模型配置</span>'
        + '<span class="composer-model-option-meta">请稍候</span>'
        + '</button>';
}

async function refreshModelProfileSelector(sessionId, opts) {
    const sid = String(sessionId || currentSessionId || '');
    const requestEpoch = ++modelProfileSelectionEpoch;
    var e = els();
    opts = opts || {};
    if (!e.control) return;
    if (!opts.silent && e.current) e.current.textContent = '正在加载模型配置';
    try {
        await loadModelProfilesForSwitcher();
        var selectedProfileId = modelProfileIdBySession[sid]
            || modelProfilesCache.new_session_default_profile_id
            || '';
        if (sid) {
            var r = await fetch('/sessions/' + encodeURIComponent(sid) + '/model_profile', { credentials: 'same-origin' });
            var j = await r.json();
            if (j && j.ok && j.profile_id) {
                selectedProfileId = String(j.profile_id);
                modelProfileIdBySession[sid] = selectedProfileId;
            }
        }
        if (sid !== String(currentSessionId || '') || requestEpoch !== modelProfileSelectionEpoch) return;
        activeModelProfileId = selectedProfileId;
        renderModelProfileControl();
    } catch (err) {
        if (sid !== String(currentSessionId || '') || requestEpoch !== modelProfileSelectionEpoch) return;
        if (e.current) e.current.textContent = '模型配置加载失败';
        if (e.menu) e.menu.innerHTML = '<button type="button" class="composer-model-option" disabled><span class="composer-model-option-name">模型配置加载失败</span><span class="composer-model-option-meta">' + h(err.message || err) + '</span></button>';
    }
}

function refreshModelProfileSelectorInBackground(sessionId, opts) {
    const sid = String(sessionId || currentSessionId || '');
    const existing = modelProfilesRefreshPromises[sid];
    if (existing && existing.epoch === modelProfileSelectionEpoch) return existing.promise;
    const promise = refreshModelProfileSelector(sid, opts)
        .catch(function (err) {
            console.error('refresh model profiles failed:', err);
        })
        .finally(function () {
            if (modelProfilesRefreshPromises[sid] === entry) {
                delete modelProfilesRefreshPromises[sid];
            }
        });
    const entry = { promise: promise, epoch: modelProfileSelectionEpoch };
    modelProfilesRefreshPromises[sid] = entry;
    return promise;
}

async function setCurrentSessionModelProfile(profileId) {
    const sid = String(currentSessionId || '');
    const selectedProfileId = String(profileId || '');
    if (!sid || modelProfileBusyBySession[sid]) return;
    modelProfileBusyBySession[sid] = true;
    try {
        var response = await fetch('/sessions/' + encodeURIComponent(sid) + '/model_profile', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            credentials: 'same-origin',
            body: JSON.stringify({ profile_id: selectedProfileId }),
        });
        var data = await response.json();
        if (!data || !data.ok) throw new Error((data && data.error) || '切换失败');
        modelProfileIdBySession[sid] = selectedProfileId;
        if (sid !== String(currentSessionId || '')) return;
        modelProfileSelectionEpoch += 1;
        activeModelProfileId = selectedProfileId;
        renderModelProfileControl();
        var cachedTokens = selectContextTokens(sid);
        var nextThreshold = activeProfileContextWindow();
        if (cachedTokens && cachedTokens.estimated != null) {
            recordContextTokens(
                sid,
                cachedTokens.estimated,
                nextThreshold != null ? nextThreshold : cachedTokens.threshold
            );
        } else {
            scheduleContextTokensAfterPaint(sid);
        }
    } catch (err) {
        if (sid === String(currentSessionId || '')) {
            appendLogVisible('模型配置切换失败: ' + String(err.message || err), 'error-log');
            await refreshModelProfileSelector(sid);
        }
    } finally {
        delete modelProfileBusyBySession[sid];
    }
}

function initModelProfileSwitcher() {
    var e = els();
    if (!e.control || !e.trigger || !e.menu) return;
    e.trigger.addEventListener('click', async () => {
        var willOpen = !e.menu.classList.contains('is-open');
        if (!willOpen) {
            closeModelMenu();
            return;
        }
        if (modelProfilesCache) renderModelProfileControl();
        else renderModelProfileLoadingMenu();
        openModelMenu();
        refreshModelProfileSelectorInBackground(currentSessionId, { silent: true });
    });
    document.addEventListener('click', (ev) => {
        if (!e.control.contains(ev.target)) closeModelMenu();
    });
    document.addEventListener('keydown', (ev) => {
        if (ev.key === 'Escape') closeModelMenu();
    });
    window.addEventListener('resize', () => {
        var fresh = els();
        if (fresh.menu && fresh.menu.classList.contains('is-open')) constrainModelMenuToTitlebar();
    });
    refreshModelProfileSelectorInBackground(currentSessionId);
}

initModelProfileSwitcher();
document.addEventListener('myagent:language-change', function () {
    if (modelProfilesCache) renderModelProfileControl();
});
window.refreshModelProfileSelector = refreshModelProfileSelector;
window.loadModelProfilesForSwitcher = loadModelProfilesForSwitcher;
`,Dt=`let skillPickerCache = null;
let skillPickerRefreshPromise = null;
let selectedSkillNames = [];
let skillPickerActiveTab = 'skills';
let mcpToolsCache = null;
let mcpToolsRefreshPromise = null;
let mcpToolsLoading = false;
let mcpToolsError = null;
let extensionsCache = null;
let extensionsRefreshPromise = null;
let extensionsLoading = false;
let extensionsError = null;
const skillPickerToggleBusy = Object.create(null);
const LS_SKILL_DRAFT_PREFIX = 'myagent-skill-draft:';

function skillPickerEls() {
    return {
        row: document.querySelector('.composer-row'),
        button: document.getElementById('skill-picker-btn'),
        popover: document.getElementById('skill-picker-popover'),
    };
}

function skillPickerEscape(str) {
    return String(str == null ? '' : str)
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#39;');
}

function skillPickerHoverDetail(skill) {
    var name = String(skill && skill.name || '未命名 Skill');
    var description = String(skill && skill.description || '').trim() || '暂无描述';
    var status = skill && skill.enabled !== false ? '已启用' : '已禁用';
    return ['Skill：' + name, '描述：' + description, '状态：' + status].join('\\n');
}

function selectedSkillSet() {
    var out = {};
    selectedSkillNames.forEach(function (name) { out[String(name)] = true; });
    return out;
}

function reconcileSelectedSkillsWithEnabledCatalog() {
    if (!skillPickerCache) return;
    var enabled = {};
    (skillPickerCache.skills || []).forEach(function (skill) {
        if (skill && skill.enabled !== false) enabled[String(skill.name || '')] = true;
    });
    selectedSkillNames = selectedSkillNames.filter(function (name) { return enabled[String(name)]; });
    persistSkillPickerDraft(currentSessionId);
    syncSkillPickerButton();
}

function skillDraftStorageKey(sessionId) {
    return LS_SKILL_DRAFT_PREFIX + String(sessionId || '');
}

function persistSkillPickerDraft(sessionId) {
    if (!sessionId) return;
    try {
        var key = skillDraftStorageKey(sessionId);
        if (selectedSkillNames.length) localStorage.setItem(key, JSON.stringify(selectedSkillNames));
        else localStorage.removeItem(key);
    } catch (e) { /* ignore */ }
}

function readStoredSkillPickerDraft(sessionId) {
    if (!sessionId) return [];
    try {
        var raw = localStorage.getItem(skillDraftStorageKey(sessionId));
        var parsed = raw ? JSON.parse(raw) : [];
        if (!Array.isArray(parsed)) return [];
        return parsed.map(function (item) { return String(item || '').trim(); }).filter(Boolean);
    } catch (e) {
        return [];
    }
}

function removeStoredSkillPickerDraft(sessionId) {
    if (!sessionId) return;
    try { localStorage.removeItem(skillDraftStorageKey(sessionId)); } catch (e) { /* ignore */ }
}

function skillPickerPlusIcon() {
    return '<svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" aria-hidden="true"><path d="M12 5v14M5 12h14"/></svg>';
}

function syncSkillPickerButton() {
    var e = skillPickerEls();
    if (!e.button) return;
    var count = selectedSkillNames.length;
    e.button.classList.toggle('is-active', count > 0);
    e.button.innerHTML = skillPickerPlusIcon()
        + (count > 0 ? '<span class="skill-picker-count">' + count + '</span>' : '');
    e.button.setAttribute('data-ui-tip', count > 0 ? ('已选择 ' + count + ' 个 Skill') : '选择 Skill');
}

function closeSkillPicker() {
    var e = skillPickerEls();
    if (e.popover) e.popover.classList.remove('is-open');
    if (e.button) e.button.setAttribute('aria-expanded', 'false');
}

function openSkillPicker() {
    var e = skillPickerEls();
    if (!e.popover || !e.button) return;
    constrainSkillPickerToTitlebar();
    e.popover.classList.add('is-open');
    e.button.setAttribute('aria-expanded', 'true');
}

function constrainSkillPickerToTitlebar() {
    var e = skillPickerEls();
    if (!e.popover || !e.row) return;
    var titlebar = document.querySelector('.titlebar');
    var titlebarBottom = titlebar ? titlebar.getBoundingClientRect().bottom : 44;
    var rowTop = e.row.getBoundingClientRect().top;
    var available = Math.max(1, Math.floor(rowTop - titlebarBottom - 10));
    var rootSize = parseFloat(getComputedStyle(document.documentElement).fontSize || '16') || 16;
    var cap = Math.floor(44 * rootSize);
    e.popover.style.setProperty('--composer-popover-max-height', Math.min(cap, available) + 'px');
}

function renderSkillPickerLoading() {
    var e = skillPickerEls();
    if (!e.popover) return;
    e.popover.innerHTML = '<div class="skill-picker-empty">正在加载 Skill</div>';
}

function renderSkillPickerError(err) {
    var e = skillPickerEls();
    if (!e.popover) return;
    e.popover.innerHTML = '<div class="skill-picker-empty">Skill 加载失败：' + skillPickerEscape(err && err.message ? err.message : err) + '</div>';
}

function skillPickerToggleIcon(action) {
    if (action === 'enable') {
        return '<svg viewBox="0 0 24 24" width="13" height="13" fill="none" stroke="currentColor" stroke-width="2.1" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M12 2v10"/><path d="M18.4 6.6a9 9 0 1 1-12.8 0"/></svg>';
    }
    return '<svg viewBox="0 0 24 24" width="13" height="13" fill="none" stroke="currentColor" stroke-width="2.1" stroke-linecap="round" aria-hidden="true"><circle cx="12" cy="12" r="8.5"/><path d="m5.5 5.5 13 13"/></svg>';
}

function skillPickerToggleHtml(enabled) {
    return '<span class="skill-picker-toggle-ico" aria-hidden="true">' + skillPickerToggleIcon(enabled ? 'disable' : 'enable') + '</span>';
}

function skillPickerMcpToolHoverDetail(tool) {
    var toolName = String(tool && tool.tool_name || '');
    var server = String(tool && tool.server || '');
    var description = String(tool && tool.description || '').trim() || '暂无描述';
    return ['MCP 工具：' + toolName, '服务器：' + server, '描述：' + description].join('\\n');
}

function renderSkillPickerSkillsHtml() {
    var skills = (skillPickerCache && skillPickerCache.skills) || [];
    if (!skills.length) {
        return '<div class="skill-picker-empty">当前没有已注册 Skill</div>';
    }
    var active = selectedSkillSet();
    var html = '';
    skills.forEach(function (skill) {
        var name = String(skill && skill.name || '');
        var enabled = skill && skill.enabled !== false;
        var checked = active[name] ? ' checked' : '';
        var disabled = enabled ? '' : ' disabled';
        html += '<div class="skill-picker-option' + (enabled ? '' : ' is-disabled') + '" data-ui-tip="' + skillPickerEscape(skillPickerHoverDetail(skill)) + '">'
            + '<label class="skill-picker-select">'
            + '<input type="checkbox" value="' + skillPickerEscape(name) + '"' + checked + disabled + '>'
            + '<span class="skill-picker-option-body">'
            + '<span class="skill-picker-option-name">' + skillPickerEscape(name) + '</span>'
            + '<span class="skill-picker-option-desc">' + skillPickerEscape(skill && skill.description || '') + '</span>'
            + '</span>'
            + '</label>'
            + '<button type="button" class="skill-picker-toggle" data-skill-name="' + skillPickerEscape(name) + '" data-enabled="' + (enabled ? 'true' : 'false') + '" data-ui-tip="' + (enabled ? '禁用' : '启用') + '" aria-label="' + (enabled ? '禁用' : '启用') + '">' + skillPickerToggleHtml(enabled) + '</button>'
            + '</div>';
    });
    return html;
}

function renderSkillPickerMcpToolsHtml() {
    if (mcpToolsLoading && !mcpToolsCache) {
        return '<div class="skill-picker-empty">正在加载 MCP 工具</div>';
    }
    if (mcpToolsError && !mcpToolsCache) {
        return '<div class="skill-picker-empty">MCP 工具加载失败：' + skillPickerEscape(mcpToolsError && mcpToolsError.message ? mcpToolsError.message : String(mcpToolsError)) + '</div>';
    }
    var tools = mcpToolsCache || [];
    if (!tools.length) {
        return '<div class="skill-picker-empty">当前没有已注册的 MCP 工具</div>';
    }
    return tools.map(function (tool) {
        var fn = String(tool && tool.function_name || '');
        var server = String(tool && tool.server || '');
        var name = String(tool && tool.tool_name || fn);
        var desc = String(tool && tool.description || '').trim();
        var prefix = '[MCP server \`' + server + '\`] ';
        if (desc.indexOf(prefix) === 0) desc = desc.slice(prefix.length).trim();
        return '<div class="skill-picker-option mcp-tool-option" data-ui-tip="' + skillPickerEscape(skillPickerMcpToolHoverDetail(tool)) + '">'
            + '<span class="mcp-tool-badge">' + skillPickerEscape(server) + '</span>'
            + '<span class="skill-picker-option-body">'
            + '<span class="skill-picker-option-name">' + skillPickerEscape(name) + '</span>'
            + (desc ? '<span class="skill-picker-option-desc">' + skillPickerEscape(desc) + '</span>' : '')
            + (fn ? '<span class="mcp-tool-fname">' + skillPickerEscape(fn) + '</span>' : '')
            + '</span>'
            + '</div>';
    }).join('');
}

function skillPickerComponentPills(plugin) {
    var components = (plugin && plugin.components) || {};
    var keys = ['skills', 'hooks', 'commands', 'mcp_servers', 'agents', 'prompts', 'runtime'];
    var rows = [];
    keys.forEach(function (key) {
        var value = components[key];
        var count = Array.isArray(value)
            ? value.length
            : (value && typeof value === 'object'
                ? (key === 'runtime' ? 1 : Object.keys(value).length)
                : Number(value || 0));
        if (count) rows.push('<span class="ext-pill">' + skillPickerEscape(key) + ' ' + count + '</span>');
    });
    return rows.join('') || '<span class="ext-pill">' + skillPickerEscape('无') + '</span>';
}

function renderSkillPickerHooksHtml() {
    if (extensionsLoading && !extensionsCache) {
        return '<div class="skill-picker-empty">正在加载扩展</div>';
    }
    if (extensionsError && !extensionsCache) {
        return '<div class="skill-picker-empty">扩展加载失败：' + skillPickerEscape(extensionsError && extensionsError.message ? extensionsError.message : String(extensionsError)) + '</div>';
    }
    var hooks = (extensionsCache && extensionsCache.hooks) || [];
    if (!hooks.length) {
        return '<div class="skill-picker-empty">当前没有已注册 Hook</div>';
    }
    return hooks.map(function (hook) {
        var id = String(hook && hook.id || '');
        var event = String(hook && hook.event || '');
        var matcher = String(hook && hook.matcher || '(全部)');
        var source = String(hook && (hook.source_id || hook.source) || 'project');
        var policy = String(hook && hook.failure_policy || 'warn');
        var timeout = hook && (hook.timeout_seconds != null ? hook.timeout_seconds : hook.timeout);
        var detail = ['事件：' + event, '匹配器：' + matcher, '来源：' + source, '策略 / 超时：' + policy + ' / ' + (timeout != null ? timeout + 's' : '—')].join('\\n');
        return '<div class="skill-picker-option ext-option" data-ui-tip="' + skillPickerEscape(detail) + '">'
            + '<span class="hook-event-badge">' + skillPickerEscape(event || 'hook') + '</span>'
            + '<span class="skill-picker-option-body">'
            + '<span class="skill-picker-option-name">' + skillPickerEscape(id) + '</span>'
            + '<span class="skill-picker-option-desc">' + skillPickerEscape([matcher, source, policy + ' / ' + (timeout != null ? timeout + 's' : '—')].join(' · ')) + '</span>'
            + '</span>'
            + '</div>';
    }).join('');
}

function renderSkillPickerPluginsHtml() {
    if (extensionsLoading && !extensionsCache) {
        return '<div class="skill-picker-empty">正在加载扩展</div>';
    }
    if (extensionsError && !extensionsCache) {
        return '<div class="skill-picker-empty">扩展加载失败：' + skillPickerEscape(extensionsError && extensionsError.message ? extensionsError.message : String(extensionsError)) + '</div>';
    }
    var plugins = (extensionsCache && extensionsCache.plugins) || [];
    if (!plugins.length) {
        return '<div class="skill-picker-empty">当前没有已发现插件</div>';
    }
    return plugins.map(function (plugin) {
        var name = String(plugin && (plugin.name || plugin.id) || '');
        var id = String(plugin && plugin.id || '');
        var version = String(plugin && plugin.version || '');
        var enabled = plugin && (plugin.configured_enabled === undefined ? !!plugin.enabled : !!plugin.configured_enabled);
        var type = String(plugin && (plugin.source_format || plugin.format) || 'native');
        var compatibility = plugin && plugin.compatibility && plugin.compatibility.status || 'unknown';
        var detail = ['插件：' + name, 'ID：' + id, '版本：' + version, '格式：' + type, '兼容性：' + compatibility, '状态：' + (enabled ? '已启用' : '已禁用')].join('\\n');
        return '<div class="skill-picker-option ext-option" data-ui-tip="' + skillPickerEscape(detail) + '">'
            + '<span class="plugin-type-badge">' + skillPickerEscape(type) + '</span>'
            + '<span class="skill-picker-option-body">'
            + '<span class="skill-picker-option-name">' + skillPickerEscape(name) + ' <span class="plugin-state' + (enabled ? '' : ' is-off') + '">' + (enabled ? '已启用' : '已禁用') + '</span></span>'
            + '<span class="skill-picker-option-desc">' + skillPickerEscape(id + (version ? ' · v' + version : '')) + '</span>'
            + '<span class="ext-pills">' + skillPickerComponentPills(plugin) + '</span>'
            + '</span>'
            + '</div>';
    }).join('');
}

function renderSkillPicker(opts) {
    opts = opts || {};
    var e = skillPickerEls();
    if (!e.popover) return;
    var prevList = e.popover.querySelector('.skill-picker-list');
    var prevScrollTop = opts.preserveScroll === false ? 0 : (prevList ? prevList.scrollTop : 0);
    var focusedToggleName = '';
    if (document.activeElement && e.popover.contains(document.activeElement)) {
        var active = document.activeElement;
        if (active.classList && active.classList.contains('skill-picker-toggle')) {
            focusedToggleName = String(active.getAttribute('data-skill-name') || '');
        }
    }
    var skills = (skillPickerCache && skillPickerCache.skills) || [];
    var activeTab = ['skills', 'mcp', 'hooks', 'plugins'].indexOf(skillPickerActiveTab) >= 0
        ? skillPickerActiveTab
        : 'skills';
    var selectedCount = selectedSkillNames.length;
    var enabledCount = skills.filter(function (skill) { return skill && skill.enabled !== false; }).length;
    var hooks = (extensionsCache && extensionsCache.hooks) || [];
    var plugins = (extensionsCache && extensionsCache.plugins) || [];
    var title = activeTab === 'mcp' ? 'MCP 工具'
        : activeTab === 'hooks' ? 'Hooks'
            : activeTab === 'plugins' ? 'Plugins'
                : '选择 Skill';
    var total = activeTab === 'mcp'
        ? (mcpToolsCache ? '共 ' + mcpToolsCache.length : '')
        : activeTab === 'hooks'
            ? (extensionsCache ? '共 ' + hooks.length : '')
            : activeTab === 'plugins'
                ? (extensionsCache ? '共 ' + plugins.length : '')
                : '已选 ' + selectedCount + ' / 已启用 ' + enabledCount + ' / 共 ' + skills.length;
    var html = '<div class="skill-picker-head">'
        + '<div class="skill-picker-title">' + skillPickerEscape(title)
        + (total ? ' <span class="skill-picker-total">' + skillPickerEscape(total) + '</span>' : '')
        + '</div>'
        + '<button type="button" class="skill-picker-clear' + (activeTab === 'skills' ? '' : ' is-hidden') + '"' + (activeTab === 'skills' ? '' : ' tabindex="-1" aria-hidden="true"') + '>清空</button>'
        + '</div>'
        + '<div class="skill-picker-tabs" role="tablist" aria-label="Skill">'
        + '<button type="button" class="skill-picker-tab' + (activeTab === 'skills' ? ' is-active' : '') + '" role="tab" aria-selected="' + (activeTab === 'skills' ? 'true' : 'false') + '" data-skill-picker-tab="skills">Skill</button>'
        + '<button type="button" class="skill-picker-tab' + (activeTab === 'mcp' ? ' is-active' : '') + '" role="tab" aria-selected="' + (activeTab === 'mcp' ? 'true' : 'false') + '" data-skill-picker-tab="mcp">MCP 工具</button>'
        + '<button type="button" class="skill-picker-tab' + (activeTab === 'hooks' ? ' is-active' : '') + '" role="tab" aria-selected="' + (activeTab === 'hooks' ? 'true' : 'false') + '" data-skill-picker-tab="hooks">Hooks</button>'
        + '<button type="button" class="skill-picker-tab' + (activeTab === 'plugins' ? ' is-active' : '') + '" role="tab" aria-selected="' + (activeTab === 'plugins' ? 'true' : 'false') + '" data-skill-picker-tab="plugins">Plugins</button>'
        + '</div>'
        + '<div class="skill-picker-list">'
        + (activeTab === 'mcp' ? renderSkillPickerMcpToolsHtml()
            : activeTab === 'hooks' ? renderSkillPickerHooksHtml()
                : activeTab === 'plugins' ? renderSkillPickerPluginsHtml()
                    : renderSkillPickerSkillsHtml())
        + '</div>';
    e.popover.innerHTML = html;
    if (typeof initUiHoverTips === 'function') initUiHoverTips(e.popover);
    var nextList = e.popover.querySelector('.skill-picker-list');
    if (nextList && prevScrollTop > 0) nextList.scrollTop = prevScrollTop;
    if (focusedToggleName) {
        var focusTarget = null;
        e.popover.querySelectorAll('.skill-picker-toggle').forEach(function (btn) {
            if (String(btn.getAttribute('data-skill-name') || '') === focusedToggleName) focusTarget = btn;
        });
        if (focusTarget) focusTarget.focus();
    }
    e.popover.querySelectorAll('input[type="checkbox"]').forEach(function (checkbox) {
        checkbox.addEventListener('change', function () {
            var name = String(checkbox.value || '');
            var set = selectedSkillSet();
            if (checkbox.checked) set[name] = true;
            else delete set[name];
            selectedSkillNames = Object.keys(set).filter(Boolean);
            persistSkillPickerDraft(currentSessionId);
            syncSkillPickerButton();
            renderSkillPicker();
        });
    });
    e.popover.querySelectorAll('[data-skill-picker-tab]').forEach(function (tab) {
        tab.addEventListener('click', function (ev) {
            ev.preventDefault();
            ev.stopPropagation();
            skillPickerActiveTab = tab.getAttribute('data-skill-picker-tab') || 'skills';
            renderSkillPicker({ preserveScroll: false });
        });
    });
    var clear = e.popover.querySelector('.skill-picker-clear');
    if (clear) {
        clear.addEventListener('click', function (ev) {
            ev.preventDefault();
            ev.stopPropagation();
            selectedSkillNames = [];
            persistSkillPickerDraft(currentSessionId);
            syncSkillPickerButton();
            renderSkillPicker();
        });
    }
    e.popover.querySelectorAll('.skill-picker-toggle').forEach(function (button) {
        button.addEventListener('click', function (ev) {
            ev.preventDefault();
            ev.stopPropagation();
            var name = String(button.getAttribute('data-skill-name') || '');
            var enabled = button.getAttribute('data-enabled') !== 'true';
            setSkillPickerEnabled(name, enabled);
        });
    });
}

async function setSkillPickerEnabled(name, enabled) {
    name = String(name || '').trim();
    if (!name || skillPickerToggleBusy[name]) return;
    skillPickerToggleBusy[name] = true;
    try {
        var response = await fetch('/api/skills/' + encodeURIComponent(name) + '/enabled', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            credentials: 'same-origin',
            body: JSON.stringify({ enabled: enabled === true }),
        });
        var data = await response.json();
        if (!data || !data.ok) throw new Error((data && data.error) || 'Skill 启停失败');
        (skillPickerCache.skills || []).forEach(function (skill) {
            if (String(skill && skill.name || '') === name) skill.enabled = enabled === true;
        });
        reconcileSelectedSkillsWithEnabledCatalog();
        renderSkillPicker();
    } catch (err) {
        if (typeof appendLogVisible === 'function') appendLogVisible('Skill 启停失败：' + String(err.message || err), 'error-log');
    } finally {
        delete skillPickerToggleBusy[name];
    }
}

async function loadSkillPickerSkills() {
    const response = await fetch('/api/skills', { credentials: 'same-origin' });
    const data = await response.json();
    if (!data || !data.ok) throw new Error((data && data.error) || 'Skill 加载失败');
    skillPickerCache = data;
    reconcileSelectedSkillsWithEnabledCatalog();
    return data;
}

async function loadSkillPickerMcpTools() {
    const response = await fetch('/api/mcp/tools', { credentials: 'same-origin' });
    const data = await response.json();
    if (!data || !data.ok) throw new Error((data && data.error) || 'MCP 工具加载失败');
    mcpToolsCache = Array.isArray(data.tools) ? data.tools : [];
    mcpToolsError = null;
    return mcpToolsCache;
}

function refreshSkillPickerSkills() {
    if (skillPickerRefreshPromise) return skillPickerRefreshPromise;
    skillPickerRefreshPromise = loadSkillPickerSkills()
        .then(function () { renderSkillPicker(); })
        .catch(function (err) { renderSkillPickerError(err); })
        .finally(function () { skillPickerRefreshPromise = null; });
    return skillPickerRefreshPromise;
}

function refreshSkillPickerMcpTools() {
    if (mcpToolsRefreshPromise) return mcpToolsRefreshPromise;
    mcpToolsLoading = true;
    renderSkillPicker();
    mcpToolsRefreshPromise = loadSkillPickerMcpTools()
        .catch(function (err) { mcpToolsError = err; })
        .finally(function () {
            mcpToolsLoading = false;
            mcpToolsRefreshPromise = null;
            renderSkillPicker();
        });
    return mcpToolsRefreshPromise;
}

async function loadSkillPickerExtensions() {
    const response = await fetch('/api/extensions', { credentials: 'same-origin' });
    const data = await response.json();
    if (!data || !data.ok) throw new Error((data && data.error) || '扩展加载失败');
    extensionsCache = data;
    extensionsError = null;
    return data;
}

function refreshSkillPickerExtensions() {
    if (extensionsRefreshPromise) return extensionsRefreshPromise;
    extensionsLoading = true;
    renderSkillPicker();
    extensionsRefreshPromise = loadSkillPickerExtensions()
        .catch(function (err) { extensionsError = err; })
        .finally(function () {
            extensionsLoading = false;
            extensionsRefreshPromise = null;
            renderSkillPicker();
        });
    return extensionsRefreshPromise;
}

function consumeSelectedSkillsForSend() {
    var out = selectedSkillNames.slice();
    selectedSkillNames = [];
    removeStoredSkillPickerDraft(currentSessionId);
    syncSkillPickerButton();
    closeSkillPicker();
    if (skillPickerCache) renderSkillPicker();
    return out;
}

function setSelectedSkillsForCurrentSession(skills) {
    selectedSkillNames = Array.isArray(skills)
        ? skills.map(function (item) { return String(item || '').trim(); }).filter(Boolean)
        : [];
    persistSkillPickerDraft(currentSessionId);
    syncSkillPickerButton();
    if (skillPickerCache) renderSkillPicker();
}

function setSelectedSkillsForSession(sessionId, skills) {
    if (!sessionId) return;
    if (sessionId === currentSessionId) {
        setSelectedSkillsForCurrentSession(skills);
        return;
    }
    var normalized = Array.isArray(skills)
        ? skills.map(function (item) { return String(item || '').trim(); }).filter(Boolean)
        : [];
    try {
        var key = skillDraftStorageKey(sessionId);
        if (normalized.length) localStorage.setItem(key, JSON.stringify(normalized));
        else localStorage.removeItem(key);
    } catch (e) { /* ignore */ }
}

function stashSkillPickerDraft(sessionId) {
    persistSkillPickerDraft(sessionId);
}

function restoreSkillPickerDraft(sessionId) {
    selectedSkillNames = readStoredSkillPickerDraft(sessionId);
    syncSkillPickerButton();
    closeSkillPicker();
    if (skillPickerCache) renderSkillPicker();
}

function initSkillPicker() {
    var e = skillPickerEls();
    if (!e.button || !e.popover) return;
    syncSkillPickerButton();
    e.button.addEventListener('click', function (ev) {
        ev.preventDefault();
        ev.stopPropagation();
        var willOpen = !e.popover.classList.contains('is-open');
        if (!willOpen) {
            closeSkillPicker();
            return;
        }
        if (skillPickerCache) renderSkillPicker();
        else renderSkillPickerLoading();
        openSkillPicker();
        refreshSkillPickerSkills();
        refreshSkillPickerMcpTools();
        refreshSkillPickerExtensions();
    });
    document.addEventListener('click', function (ev) {
        var fresh = skillPickerEls();
        if (!fresh.row || !fresh.row.contains(ev.target)) closeSkillPicker();
    });
    document.addEventListener('keydown', function (ev) {
        if (ev.key === 'Escape') closeSkillPicker();
    });
    window.addEventListener('resize', function () {
        var fresh = skillPickerEls();
        if (fresh.popover && fresh.popover.classList.contains('is-open')) constrainSkillPickerToTitlebar();
    });
}

initSkillPicker();
window.consumeSelectedSkillsForSend = consumeSelectedSkillsForSend;
window.setSelectedSkillsForCurrentSession = setSelectedSkillsForCurrentSession;
window.setSelectedSkillsForSession = setSelectedSkillsForSession;
window.refreshSkillPickerSkills = refreshSkillPickerSkills;
window.stashSkillPickerDraft = stashSkillPickerDraft;
window.restoreSkillPickerDraft = restoreSkillPickerDraft;
`,Ut=`function formatTokenCompact(n) {\r
    if (n == null || !Number.isFinite(Number(n))) return '—';\r
    const x = Math.max(0, Math.round(Number(n)));\r
    if (x >= 1000000) return (x / 1000000).toFixed(1).replace(/\\.0$/, '') + 'M';\r
    if (x >= 10000) return (x / 1000).toFixed(x % 1000 === 0 ? 0 : 1).replace(/\\.0$/, '') + 'k';\r
    if (x >= 1000) return (x / 1000).toFixed(1).replace(/\\.0$/, '') + 'k';\r
    return String(x);\r
}\r
\r
function setContextTokenLabel(estimated, threshold) {\r
    const el = document.getElementById('ctx-tokens');\r
    if (!el) return;\r
    const label = el.querySelector('.ctx-label');\r
    const fill = el.querySelector('.ctx-fill');\r
    const pctEl = el.querySelector('.ctx-pct');\r
    const t = (threshold != null && Number(threshold) > 0) ? Number(threshold) : defaultCtxThreshold;\r
    const n = (estimated != null && Number(estimated) >= 0) ? Math.round(Number(estimated)) : null;\r
    if (n == null) {\r
        if (label) label.textContent = '— / —';\r
        if (pctEl) pctEl.textContent = '';\r
        if (fill) fill.style.width = '0%';\r
        el.classList.remove('is-warn', 'is-bad');\r
        el.setAttribute('data-ui-tip', '预估上下文 token：选择会话并加载或发送消息后显示。分母为压缩摘要阈值。');\r
        bindUiHoverTip(el);\r
        return;\r
    }\r
    const pct = (n / t) * 100;\r
    const pctDisp = (Math.round(pct * 10) / 10);\r
    if (label) label.textContent = formatTokenCompact(n) + ' / ' + formatTokenCompact(t);\r
    if (pctEl) pctEl.textContent = pctDisp + '%';\r
    if (fill) fill.style.width = Math.min(100, pct) + '%';\r
    el.classList.remove('is-warn', 'is-bad');\r
    if (pct >= 100) el.classList.add('is-bad');\r
    else if (pct >= 80) el.classList.add('is-warn');\r
    var tipPct = pct >= 100\r
        ? ('约 ' + pctDisp + '%，超出门限 ' + (Math.round((pct - 100) * 10) / 10) + '%')\r
        : ('约 ' + pctDisp + '%');\r
    el.setAttribute(\r
        'data-ui-tip',\r
        formatTokenCompact(n) + ' / ' + formatTokenCompact(t) + ' tokens（' + tipPct\r
            + '）。预估进入模型的上下文规模，含历史与系统提示；分母为当前 model profile 中触发压缩摘要的上下文门限。'
    );\r
    bindUiHoverTip(el);\r
}\r
\r
let contextTokenRequestSeq = 0;\r
const contextTokenInFlightBySession = Object.create(null);\r
const CONTEXT_TOKEN_CACHE_TTL_MS = 3000;\r
\r
async function refreshContextTokensFromServer(sid, seq) {\r
    if (!sid) return;\r
    const cached = selectContextTokens(sid);\r
    if (cached && cached.updatedAt && (Date.now() - cached.updatedAt) < CONTEXT_TOKEN_CACHE_TTL_MS) {\r
        if (sid === currentSessionId) setContextTokenLabel(cached.estimated, cached.threshold);\r
        return;\r
    }\r
    if (contextTokenInFlightBySession[sid]) return;\r
    contextTokenInFlightBySession[sid] = true;\r
    try {\r
        const r = await fetch('/sessions/' + encodeURIComponent(sid) + '/context_tokens');
        const j = await r.json();\r
        if (seq != null && seq !== contextTokenRequestSeq) return;\r
        if (sid !== currentSessionId) return;\r
        if (r.ok && j && j.ok && j.estimated != null && j.estimated >= 0) {\r
            recordContextTokens(sid, j.estimated, j.threshold);\r
            return;\r
        }\r
    } catch (e) { /* ignore */ }\r
    finally {\r
        delete contextTokenInFlightBySession[sid];\r
    }\r
    applyContextTokenLabelForCurrentSession();\r
}\r
\r
/** 在浏览器完成首帧绘制后再请求 context_tokens，避免与切换会话/新建会话的 DOM 抢主线程。 */\r
function scheduleContextTokensAfterPaint(sid) {
    if (!sid) return;
    if (sid === currentSessionId) applyContextTokenLabelForCurrentSession();
    const seq = ++contextTokenRequestSeq;
    requestAnimationFrame(function () {
        requestAnimationFrame(function () {
            refreshContextTokensFromServer(sid, seq);\r
        });\r
    });\r
}\r
\r
function recordContextTokens(sessionId, estimated, threshold) {\r
    if (!sessionId) return;\r
    setContextTokensForSession(sessionId, estimated, threshold);\r
    if (sessionId === currentSessionId) setContextTokenLabel(estimated, threshold);\r
}\r
\r
function applyContextTokenLabelForCurrentSession() {\r
    if (!currentSessionId) { setContextTokenLabel(null, null); return; }\r
    const x = selectContextTokens(currentSessionId);\r
    if (x) setContextTokenLabel(x.estimated, x.threshold);\r
    else setContextTokenLabel(null, null);\r
}\r
\r
/** 主对话区跟到底 */\r
function scrollChatToBottomIfFollow(runSessionId, opts) {
    opts = opts || {};
    if (shouldGateScrollByRunSession(null, runSessionId)) return;
    if (!opts.force && !liveAutoFollow) return;
    if (chatContainer) setScrollTopImmediate(chatContainer, chatContainer.scrollHeight);
}
\r
function setScrollTopImmediate(el, y) {\r
    if (!el) return;\r
    var prev = el.style.scrollBehavior;\r
    el.style.scrollBehavior = 'auto';\r
    el.scrollTop = y;\r
    requestAnimationFrame(function () {\r
        if (el) el.style.scrollBehavior = prev;\r
    });\r
}\r
\r
/** 当前运行会话对应的执行过程框滚动容器（.process-aggregate-body） */\r
function getProcessBodyElForCurrentRun() {\r
    var sid = currentSessionId;\r
    var run = sid && getSessionRunState(sid);\r
    if (!run || !run.ctx) return null;\r
    var c = run.ctx;\r
    if (c.currentProcessGroup && c.currentProcessGroup.isConnected) {\r
        return c.currentProcessGroup.querySelector('.process-aggregate-body');\r
    }\r
    if (!c.stream) return null;\r
    var agg = c.stream.querySelector('.process-aggregate:last-of-type');\r
    return agg ? agg.querySelector('.process-aggregate-body') : null;\r
}\r
\r
var STREAM_PROC_NEAR_BOTTOM_PX = 96;\r
var STREAM_CHAT_NEAR_BOTTOM_PX = 72;\r
\r
/** 生成中时：对话区与当前执行过程区均在底部附近时才允许自动跟随流式滚动 */\r
function refreshLiveAutoFollowPins() {\r
    if (!chatContainer) return;\r
    if (isSessionRunning(currentSessionId)) {\r
        streamChatNearBottom = isNearBottom(chatContainer, STREAM_CHAT_NEAR_BOTTOM_PX);\r
        var pb = getProcessBodyElForCurrentRun();\r
        streamProcNearBottom = !pb || isNearBottom(pb, STREAM_PROC_NEAR_BOTTOM_PX);\r
        liveAutoFollow = streamChatNearBottom && streamProcNearBottom;\r
    } else {\r
        liveAutoFollow = isNearBottom(chatContainer, STREAM_CHAT_NEAR_BOTTOM_PX);\r
    }\r
}\r
\r
function isSubagentStreamCtx(ctx) {\r
    if (!ctx) return false;\r
    if (ctx._subagentBody && ctx._subagentBody.isConnected) return true;\r
    if (ctx.currentProcessGroup && ctx.currentProcessGroup.isConnected\r
        && ctx.currentProcessGroup.classList.contains('subagent-grid-card')) return true;\r
    return false;\r
}\r
\r
/** 子 agent 卡片流式更新用 agentId 作 runSessionId，不能按主会话 currentSessionId 拦截滚动 */\r
function shouldGateScrollByRunSession(ctx, runSessionId) {\r
    if (!runSessionId) return false;\r
    if (isSubagentStreamCtx(ctx)) return false;\r
    return runSessionId !== currentSessionId;\r
}\r
\r
function collectFeedChunkRootsFromCtx(ctx) {\r
    var roots = [];\r
    var seen = new Set();\r
    function addRoot(root) {\r
        if (!root || !root.isConnected || seen.has(root)) return;\r
        seen.add(root);\r
        roots.push(root);\r
    }\r
    if (ctx && ctx.stream && ctx.stream.isConnected) addRoot(ctx.stream);\r
    if (ctx && ctx._subagentTurnProcess) addRoot(ctx._subagentTurnProcess);\r
    if (ctx && ctx._subagentBody) addRoot(ctx._subagentBody);\r
    return roots;\r
}\r
\r
function queryFeedChunksInCtx(ctx, selector) {\r
    var sel = selector || '.feed-chunk';\r
    var out = [];\r
    var seen = new Set();\r
    collectFeedChunkRootsFromCtx(ctx).forEach(function (root) {\r
        root.querySelectorAll(sel).forEach(function (ch) {\r
            if (!seen.has(ch)) {\r
                seen.add(ch);\r
                out.push(ch);\r
            }\r
        });\r
    });\r
    return out;\r
}\r
\r
function refreshFeedChunksInCtx(ctx, selector) {\r
    queryFeedChunksInCtx(ctx, selector).forEach(function (ch) {\r
        scheduleFeedChunkOverflowRefresh(ch);\r
    });\r
}\r
\r
function ensureSubagentTurnProcessOpen(ctx) {\r
    /* 默认折叠执行过程，不在自动滚动时强制展开 */\r
}\r
\r
function shouldDeferSubagentProcessDom(ctx) {\r
    if (!ctx || !ctx.currentTurn || !ctx.currentTurn.isConnected) return true;\r
    return !ctx.currentTurn.classList.contains('is-process-open');\r
}\r
\r
function deferSubagentProcessEvent(turn, event, eventIndex) {\r
    if (!turn || !event) return;\r
    if (!turn._deferredProcessEvents) turn._deferredProcessEvents = [];\r
    turn._deferredProcessEvents.push({ event: event, eventIndex: eventIndex });\r
    turn.dataset.processDeferred = '1';\r
}\r
\r
function pinSubagentCardScrollForManualExpand(body) {\r
    if (!body) return { savedScroll: 0, release: function () {} };\r
    var ctx = body._subagentStreamCtx;\r
    var savedScroll = body.scrollTop;\r
    if (ctx) ctx._suppressSubagentScrollFollow = true;\r
    return {\r
        savedScroll: savedScroll,\r
        release: function () {\r
            if (ctx) ctx._suppressSubagentScrollFollow = false;\r
        },\r
        restoreScroll: function () {\r
            if (body.isConnected) body.scrollTop = savedScroll;\r
        }\r
    };\r
}\r
\r
function restoreSubagentCardScrollAfterLayout(body, savedScroll) {\r
    if (!body) return;\r
    requestAnimationFrame(function () {\r
        requestAnimationFrame(function () {\r
            if (body.isConnected) body.scrollTop = savedScroll;\r
        });\r
    });\r
}\r
\r
var SUBAGENT_PROCESS_HYDRATE_BATCH = 24;\r
var SUBAGENT_PROCESS_REFRESH_CHUNK_LIMIT = 80;\r
\r
function runSubagentProcessBatch(fn) {\r
    if (typeof requestIdleCallback === 'function') {\r
        requestIdleCallback(fn, { timeout: 120 });\r
    } else {\r
        requestAnimationFrame(fn);\r
    }\r
}\r
\r
function refreshSubagentProcessChunksLightly(turn) {\r
    if (!turn || !turn.querySelectorAll) return;\r
    var chunks = turn.querySelectorAll('.feed-chunk');\r
    var limit = Math.min(chunks.length, SUBAGENT_PROCESS_REFRESH_CHUNK_LIMIT);\r
    for (var i = 0; i < limit; i += 1) {\r
        scheduleFeedChunkOverflowRefresh(chunks[i]);\r
    }\r
}\r
\r
function hydrateSubagentTurnProcess(turn, ctx, agentId) {\r
    if (!turn || !ctx) return;\r
    var processEl = turn.querySelector('.subagent-turn-process');\r
    if (turn.dataset.processHydrated === '1' && processEl && processEl.children.length) return;\r
    var items = turn._deferredProcessEvents;\r
    if (!items || !items.length) {\r
        turn.dataset.processHydrated = '1';\r
        return;\r
    }\r
    var body = ctx._subagentBody;\r
    var pin = pinSubagentCardScrollForManualExpand(body);\r
    ctx.currentTurn = turn;\r
    ctx._subagentTurnProcess = processEl;\r
    ctx._subagentTurnFinalSlot = turn.querySelector('.subagent-turn-final-slot');\r
    resetLlmState(ctx);\r
    finalizeProgressStreamChunks(ctx);\r
    function replayDeferredProcessEvent(item) {\r
        var ev = item && item.event;\r
        if (!ev || typeof ev !== 'object') return;\r
        if (shouldSkipSubagentProcessEvent(ev)) return;\r
        if (ev.ephemeral) {
            return;
        }
        reduceAndRenderMessageEvent(ctx, ev, {\r
            sessionId: agentId,\r
            eventIndex: item.eventIndex,\r
            source: 'subagent-history',\r
        });\r
    }\r
    var index = 0;\r
    turn.dataset.processLoading = '1';\r
    function finishHydrate() {\r
        finalizeLlmStreamChunks(ctx);\r
        finalizeProgressStreamChunks(ctx);\r
        delete turn._deferredProcessEvents;\r
        delete turn.dataset.processDeferred;\r
        delete turn.dataset.processLoading;\r
        turn.dataset.processHydrated = '1';\r
        markSubagentTurnHasProcess(turn);\r
        refreshSubagentProcessChunksLightly(turn);\r
        pin.release();\r
        restoreSubagentCardScrollAfterLayout(body, pin.savedScroll);\r
    }\r
    function step() {\r
        if (!turn.isConnected || !body || !body.isConnected) {\r
            delete turn.dataset.processLoading;\r
            pin.release();\r
            return;\r
        }\r
        var end = Math.min(index + SUBAGENT_PROCESS_HYDRATE_BATCH, items.length);\r
        for (; index < end; index += 1) {\r
            replayDeferredProcessEvent(items[index]);\r
        }\r
        if (index < items.length) {\r
            runSubagentProcessBatch(step);\r
        } else {\r
            finishHydrate();\r
        }\r
    }\r
    step();\r
}\r
\r
function repairMisplacedSubagentFeedItems(body, turn) {\r
    if (!body || !turn) return;\r
    var proc = turn.querySelector('.subagent-turn-process');\r
    if (!proc) return;\r
    Array.prototype.slice.call(body.children).forEach(function (node) {\r
        if (!node || !node.classList || !node.classList.contains('feed-item')) return;\r
        proc.appendChild(node);\r
    });\r
}\r
\r
function collectSubagentTurnProcessSlice(events, userEventIndex) {\r
    var slice = [];\r
    if (!events || !events.length || !Number.isFinite(userEventIndex) || userEventIndex < 0) return slice;\r
    for (var i = userEventIndex + 1; i < events.length; i += 1) {\r
        var ev = events[i];\r
        if (!ev || typeof ev !== 'object') continue;\r
        var t = ev.type;\r
        if (t === 'user') break;\r
        if (t === 'final') break;\r
        if (t === 'subagent_start' || t === 'subagent_finish') continue;\r
        if (shouldSkipSubagentProcessEvent(ev)) continue;\r
        slice.push({ event: ev, eventIndex: i });\r
    }\r
    return slice;\r
}\r
\r
async function fetchAndHydrateSubagentTurnProcess(turn, body) {\r
    if (!turn || !body || turn.dataset.processLoading === '1' || turn.dataset.processFetching === '1') return;\r
    var card = body.closest('.subagent-grid-card');\r
    var agentId = (card && card.getAttribute('data-agent-id')) || body.getAttribute('data-agent-id') || '';\r
    if (!agentId) return;\r
    var userWrap = turn.querySelector('.msg-wrap--user');\r
    var userIdx = userWrap ? parseInt(userWrap.getAttribute('data-event-index') || '-1', 10) : -1;\r
    if (!Number.isFinite(userIdx) || userIdx < 0) return;\r
    var pin = pinSubagentCardScrollForManualExpand(body);\r
    turn.dataset.processFetching = '1';\r
    try {\r
        var resp = await fetch('/sessions/' + encodeURIComponent(agentId) + '/messages');\r
        if (!resp.ok) return;\r
        var events = normalizeSubagentMessagesPayload(await resp.json());\r
        if (!turn.isConnected) return;\r
        turn._deferredProcessEvents = collectSubagentTurnProcessSlice(events, userIdx);\r
        delete turn.dataset.processHydrated;\r
        hydrateSubagentTurnProcessFromEl(turn, body);\r
    } catch (e) { /* ignore */ }\r
    finally {\r
        delete turn.dataset.processFetching;\r
        pin.release();\r
        restoreSubagentCardScrollAfterLayout(body, pin.savedScroll);\r
    }\r
}\r
\r
function ensureSubagentTurnProcessContent(turn, body) {\r
    if (!turn || !body) return;\r
    repairMisplacedSubagentFeedItems(body, turn);\r
    var processEl = turn.querySelector('.subagent-turn-process');\r
    if (processEl && processEl.children.length) return;\r
    if (turn._deferredProcessEvents && turn._deferredProcessEvents.length) {\r
        hydrateSubagentTurnProcessFromEl(turn, body);\r
        return;\r
    }\r
    if (turn.dataset.processDeferred === '1' || turn.querySelector('.msg-wrap--user.has-turn-process')) {\r
        void fetchAndHydrateSubagentTurnProcess(turn, body);\r
    }\r
}\r
\r
function toggleSubagentTurnProcess(turn, body, userWrap) {\r
    if (!turn || !body || !userWrap) return;\r
    var open = !turn.classList.contains('is-process-open');\r
    turn.classList.toggle('is-process-open', open);\r
    userWrap.classList.toggle('is-process-open', open);\r
    delete body.dataset.cacheClean;\r
    if (open) {\r
        ensureSubagentTurnProcessContent(turn, body);\r
        refreshSubagentProcessChunksLightly(turn);\r
        return;\r
    }\r
}\r
\r
function hydrateSubagentTurnProcessFromEl(turn, body) {\r
    if (!turn || !body) return;\r
    var card = body.closest('.subagent-grid-card');\r
    var agentId = (card && card.getAttribute('data-agent-id')) || body.getAttribute('data-agent-id') || '';\r
    var ctx = body._subagentStreamCtx || (agentId && card ? getSubagentCardStreamCtx(body, card, agentId) : null);\r
    if (ctx && agentId) hydrateSubagentTurnProcess(turn, ctx, agentId);\r
}\r
\r
function feedChunkCollapsedMax(chunk) {\r
    var styles = getComputedStyle(chunk);\r
    var line = parseFloat(styles.getPropertyValue('--line')) || 21.6;\r
    var pad = parseFloat(styles.getPropertyValue('--scroller-pad-y')) || 4;\r
    return line * 2.5 + pad * 2;\r
}\r
\r
function feedChunkInHiddenSubagentProcess(chunk) {\r
    var process = chunk.closest('.subagent-turn-process');\r
    if (!process || !process.children.length) return false;\r
    var turn = process.closest('.subagent-turn');\r
    return !!(turn && !turn.classList.contains('is-process-open'));\r
}\r
\r
function measureFeedChunkScrollerHeight(sc, chunk) {\r
    if (!sc) return 0;\r
    var h = sc.scrollHeight;\r
    if (h > 1) return h;\r
    var process = chunk && chunk.closest('.subagent-turn-process');\r
    var turn = process && process.closest('.subagent-turn');\r
    if (!process || !turn || turn.classList.contains('is-process-open')) return h;\r
    var prevDisplay = process.style.display;\r
    var prevVis = process.style.visibility;\r
    var prevPos = process.style.position;\r
    var prevLeft = process.style.left;\r
    var prevRight = process.style.right;\r
    var prevPointer = process.style.pointerEvents;\r
    process.style.display = 'block';\r
    process.style.visibility = 'hidden';\r
    process.style.position = 'absolute';\r
    process.style.left = '0';\r
    process.style.right = '0';\r
    process.style.pointerEvents = 'none';\r
    h = sc.scrollHeight;\r
    process.style.display = prevDisplay;\r
    process.style.visibility = prevVis;\r
    process.style.position = prevPos;\r
    process.style.left = prevLeft;\r
    process.style.right = prevRight;\r
    process.style.pointerEvents = prevPointer;\r
    return h;\r
}\r
\r
function refreshAllFeedChunksUnder(root) {\r
    if (!root || !root.querySelectorAll) return;\r
    root.querySelectorAll('.feed-chunk').forEach(scheduleFeedChunkOverflowRefresh);\r
}\r
\r
function shouldFollowSubagentCard(ctx) {\r
    if (!ctx || ctx._suppressSubagentScrollFollow) return false;\r
    if (!ctx._subagentBody || !ctx._subagentBody.isConnected) return false;\r
    var aid = ctx._subagentBody.getAttribute('data-agent-id') || '';\r
    if (aid && subagentCardNearBottom[aid] === false) return false;\r
    return liveAutoFollow || subagentCardNearBottom[aid] !== false;\r
}\r
\r
function bindSubagentCardBodyScrollFollow(body) {\r
    if (!body || body.dataset.subagentScrollFollowBound) return;\r
    body.dataset.subagentScrollFollowBound = '1';\r
    var aid = body.getAttribute('data-agent-id') || ('body-' + Math.random());\r
    if (subagentCardNearBottom[aid] == null) subagentCardNearBottom[aid] = true;\r
    body.addEventListener('scroll', function () {\r
        subagentCardNearBottom[aid] = isNearBottom(body, SUBAGENT_CARD_NEAR_BOTTOM_PX);\r
    }, { passive: true });\r
}\r
\r
function scrollSubagentCardBodyToBottom(ctx) {\r
    if (!ctx || !ctx._subagentBody || !ctx._subagentBody.isConnected) return;\r
    var body = ctx._subagentBody;\r
    var aid = body.getAttribute('data-agent-id') || '';\r
    if (aid) subagentCardNearBottom[aid] = true;\r
    requestAnimationFrame(function () {\r
        body.scrollTop = body.scrollHeight;\r
        requestAnimationFrame(function () {\r
            body.scrollTop = body.scrollHeight;\r
        });\r
    });\r
}\r
\r
function scrollContentAreaIfFollow(ctx, runSessionId) {\r
    if (shouldGateScrollByRunSession(ctx, runSessionId)) return;\r
    if (isSubagentStreamCtx(ctx)) {\r
        if (!shouldFollowSubagentCard(ctx)) return;\r
        scrollSubagentCardBodyToBottom(ctx);\r
        return;\r
    }\r
    if (!liveAutoFollow) return;\r
    scrollProcessBodyToBottom(ctx, runSessionId);\r
    scrollChatToBottomIfFollow(runSessionId, {});\r
}\r
\r
/** 将当前轮次的执行框滚到底（流式增量主要长在这里，必须滚 procBody 而不是只滚对话区） */\r
function scrollProcessBodyToBottom(ctx, runSessionId) {\r
    if (shouldGateScrollByRunSession(ctx, runSessionId)) return;\r
    if (isSubagentStreamCtx(ctx)) {\r
        scrollSubagentCardBodyToBottom(ctx);\r
        return;\r
    }\r
    if (!ctx || !ctx.stream) return;\r
    var agg = (ctx.currentProcessGroup && ctx.currentProcessGroup.isConnected)\r
        ? ctx.currentProcessGroup\r
        : ctx.stream.querySelector('.process-aggregate:last-of-type');\r
    if (agg) {\r
        var procBody = agg.querySelector('.process-aggregate-body');\r
        if (procBody) procBody.scrollTop = procBody.scrollHeight;\r
    }\r
}\r
\r
function followStreamProcessScroll(ctx, runSessionId) {\r
    if (shouldGateScrollByRunSession(ctx, runSessionId)) return;\r
    if (isSubagentStreamCtx(ctx)) {\r
        if (!shouldFollowSubagentCard(ctx)) return;\r
        if (subagentScrollFollowRaf) return;\r
        subagentScrollFollowRaf = requestAnimationFrame(function () {\r
            subagentScrollFollowRaf = 0;\r
            scrollSubagentCardBodyToBottom(ctx);\r
            refreshFeedChunksInCtx(ctx, '.feed-chunk.is-streaming');\r
        });\r
        return;\r
    }\r
    if (!liveAutoFollow) return;\r
    if (streamScrollFollowRaf) return;\r
    streamScrollFollowRaf = requestAnimationFrame(function () {\r
        streamScrollFollowRaf = 0;\r
        if (!liveAutoFollow) return;\r
        if (ctx && ctx.currentProcessGroup && ctx.currentProcessGroup.isConnected) {\r
            if (ctx.currentProcessGroup.classList.contains('is-collapsed')) {\r
                ctx.currentProcessGroup.classList.remove('is-collapsed');\r
                const topN = ctx.currentProcessGroup.querySelector('.process-aggregate-top');\r
                if (topN) topN.setAttribute('aria-expanded', 'true');\r
            }\r
        }\r
        scrollProcessBodyToBottom(ctx, runSessionId);\r
        scrollChatToBottomIfFollow(runSessionId, {});\r
        refreshLiveAutoFollowPins();\r
    });\r
}\r
\r
function getVisibleChatStream() { return document.getElementById('chat-stream'); }\r
\r
function ensureVisibleChatStreamSlot() {\r
    if (getVisibleChatStream() || !chatContainer) return;\r
    const ns = document.createElement('div');\r
    ns.className = 'chat-stream';\r
    ns.id = 'chat-stream';\r
    ns.setAttribute('aria-label', '消息');\r
    chatContainer.appendChild(ns);\r
}\r
\r
function emptyChatStreamKeepingStrip(streamEl) {\r
    if (!streamEl) return;\r
    const strip = streamEl.querySelector('#history-load-sentinel');\r
    Array.from(streamEl.children).forEach(function (ch) {\r
        if (strip && ch === strip) return;\r
        ch.remove();\r
    });\r
}\r
\r
function persistHistoryPagingToStream(streamEl, paging) {
    if (!streamEl) return;\r
    if (!paging || paging.sessionId !== currentSessionId) {\r
        delete streamEl.dataset.historyPaging;\r
        return;\r
    }\r
    streamEl.dataset.historyPaging = JSON.stringify({\r
        sessionId: paging.sessionId,\r
        total: Number(paging.total) || 0,\r
        range_start: Number(paging.range_start) || 0,
        range_end: Number(paging.range_end) || 0,
        has_older: !!paging.has_older,
        has_newer: !!paging.has_newer,
    });\r
}\r
\r
function restoreHistoryPagingFromStream(streamEl) {\r
    if (!streamEl || !streamEl.dataset.historyPaging) return null;\r
    try {\r
        var raw = JSON.parse(streamEl.dataset.historyPaging);\r
        if (!raw || raw.sessionId !== currentSessionId) return null;\r
        return {\r
            sessionId: raw.sessionId,\r
            total: Number(raw.total) || 0,\r
            range_start: Number(raw.range_start) || 0,
            range_end: Number(raw.range_end) || 0,
            has_older: !!raw.has_older,
            has_newer: !!raw.has_newer,
        };\r
    } catch (_e) {\r
        delete streamEl.dataset.historyPaging;\r
        return null;\r
    }\r
}\r
\r
function setSessionHistoryPaging(paging) {
    sessionHistoryPaging = paging || null;\r
    persistHistoryPagingToStream(getVisibleChatStream(), sessionHistoryPaging);\r
    updateHistorySentinelVisibility();\r
}\r
\r
function ensureHistorySentinel(streamEl) {
    if (!streamEl) return null;\r
    var el = streamEl.querySelector('#history-load-sentinel');\r
    if (el) return el;\r
    el = document.createElement('div');\r
    el.id = 'history-load-sentinel';\r
    el.className = 'history-load-sentinel';\r
    el.hidden = true;\r
    var btn = document.createElement('button');\r
    btn.type = 'button';\r
    btn.className = 'history-load-older-btn';\r
    btn.textContent = '加载更早记录';
    btn.addEventListener('click', function () { loadOlderHistoryChunk(); });\r
    el.appendChild(btn);\r
    streamEl.insertBefore(el, streamEl.firstChild);\r
    return el;
}

var latestHistoryTailRestoreBySession = Object.create(null);

function getSessionHistoryPaging(sessionId) {
    var sid = String(sessionId || '');
    if (!sid) return null;
    var paging = sessionHistoryPaging;
    var stream = getVisibleChatStream();
    if ((!paging || paging.sessionId !== sid) && stream) {
        paging = restoreHistoryPagingFromStream(stream);
        if (paging) sessionHistoryPaging = paging;
    }
    return paging && paging.sessionId === sid ? paging : null;
}

function sessionHasLiveHistoryOwner(sessionId) {
    var sid = String(sessionId || '');
    return !!sid && (
        isSessionRunning(sid)
        || (typeof isServerStreamActive === 'function' && isServerStreamActive(sid))
    );
}

async function refreshSessionLiveHistoryOwner(sessionId) {
    var sid = String(sessionId || '');
    if (!sid || sessionHasLiveHistoryOwner(sid)) return !!sid;
    if (typeof fetchSessionStreamActiveMap !== 'function') return sessionHasLiveHistoryOwner(sid);
    var activeMap = await fetchSessionStreamActiveMap();
    if (activeMap && Object.prototype.hasOwnProperty.call(activeMap, sid)) {
        if (typeof applyServerStreamActiveMap === 'function') applyServerStreamActiveMap(activeMap);
        if (activeMap[sid]) return true;
    }
    return sessionHasLiveHistoryOwner(sid);
}

async function ensureLatestHistoryTailForLiveAppend(sessionId) {
    var sid = String(sessionId || '');
    if (!sid || sid !== currentSessionId) return true;
    var paging = getSessionHistoryPaging(sid);
    if (!paging || !paging.has_newer) return true;
    if (latestHistoryTailRestoreBySession[sid]) return latestHistoryTailRestoreBySession[sid];
    var restore = (async function () {
        var loaded = await loadSessionMessages(sid, 'bottom', {
            useSnapshot: false,
            preloadOlderIfShort: false,
        });
        if (sid !== currentSessionId) return true;
        var current = getSessionHistoryPaging(sid);
        return loaded === true && !(current && current.has_newer);
    })();
    latestHistoryTailRestoreBySession[sid] = restore;
    try {
        return await restore;
    } finally {
        if (latestHistoryTailRestoreBySession[sid] === restore) {
            delete latestHistoryTailRestoreBySession[sid];
        }
    }
}

var HISTORY_AUTO_LOAD_TOP_PX = 32;

/** 滚到历史顶部附近时自动向前分页；按钮仍保留为加载状态提示和手动兜底。 */
function maybeAutoLoadOlderHistory() {
    if (typeof isHistorySmoothScrollActive === 'function' && isHistorySmoothScrollActive()) return;
    if (!chatContainer || chatContainer.scrollTop > HISTORY_AUTO_LOAD_TOP_PX) return;
    void loadOlderHistoryChunk({ trigger: 'scroll-top' });
}
\r
function updateHistorySentinelVisibility() {\r
    var strip = document.getElementById('history-load-sentinel');\r
    var btn = strip && strip.querySelector('.history-load-older-btn');\r
    var ph = sessionHistoryPaging;\r
    if (!strip || !btn) return;\r
    if (!ph || !ph.has_older || ph.sessionId !== currentSessionId) {\r
        strip.hidden = true;\r
        btn.disabled = false;\r
        btn.textContent = '加载更早记录';
        return;\r
    }\r
    strip.hidden = false;\r
    btn.disabled = historyOlderLoading;\r
    btn.textContent = historyOlderLoading ? '加载中…' : '加载更早记录';
}\r
\r
function resetSessionHistoryPaging() {\r
    setSessionHistoryPaging(null);\r
    historyOlderLoading = false;\r
    updateHistorySentinelVisibility();\r
}\r
\r
async function loadOlderHistoryChunk(opts) {\r
    opts = opts || {};\r
    var sid = currentSessionId;\r
    var stream = getVisibleChatStream();\r
    var ph = sessionHistoryPaging;\r
    if ((!ph || ph.sessionId !== sid) && stream) {\r
        ph = restoreHistoryPagingFromStream(stream);\r
        if (ph) sessionHistoryPaging = ph;\r
    }\r
    if (!sid || !ph || ph.sessionId !== sid || !ph.has_older || historyOlderLoading) return;\r
    historyOlderLoading = true;\r
    var prevReplaying = replayingMessages;\r
    replayingMessages = true;
    updateHistorySentinelVisibility();
    var cc = chatContainer;
    var prependScrollTop = null;
    var prependScrollHeight = null;
    var loadedOlder = false;
    try {\r
        var pageTurns = Math.max(1, Math.min(Number(opts.turns) || HISTORY_DIALOGUES_PER_PAGE, 50));\r
        var url = '/sessions/' + encodeURIComponent(sid)
            + '/messages?turns=' + encodeURIComponent(String(pageTurns))
            + '&before_index=' + ph.range_start
            + '&event_budget=' + encodeURIComponent(String(HISTORY_EVENT_BUDGET));
        var response = await fetch(url);
        var data = await response.json();
        if (!response.ok || !data || typeof data !== 'object') return;
        // 自动加载请求返回前可能已切换会话，旧页不能插入新的可见消息流。
        if (sid !== currentSessionId || stream !== getVisibleChatStream()) return;
        var events = data.events;
        if (!Array.isArray(events) || events.length === 0) {\r
            setSessionHistoryPaging(Object.assign({}, ph, { has_older: !!data.has_older }));\r
            return;\r
        }\r
        ensureHistorySentinel(stream);\r
        var frag = document.createDocumentFragment();\r
        var tmpCtx = newDomContext(frag);\r
        tmpCtx.lastUserEventIndex = -1;\r
        var rs = typeof data.range_start === 'number' ? data.range_start : 0;\r
        for (var i = 0; i < events.length; i += 1) {\r
            var ev = events[i];\r
            if (ev && typeof ev === 'object' && ev.type) {\r
                reduceAndRenderMessageEvent(tmpCtx, ev, {\r
                    sessionId: sid,\r
                    eventIndex: rs + i,\r
                    source: 'history-older',\r
                });\r
            }\r
        }
        var sen = stream && stream.querySelector('#history-load-sentinel');
        if (stream && frag.childNodes.length) {
            // fetch 期间用户仍可能滚动，所以必须在真正插入前才记录视口。
            // 插入后补上新增的高度，原来可见的内容就会停在相同屏幕位置。
            if (cc && stream.parentNode === cc) {
                prependScrollTop = cc.scrollTop;
                prependScrollHeight = cc.scrollHeight;
            }
            stream.insertBefore(frag, sen ? sen.nextSibling : stream.firstChild);
        }
        loadedOlder = true;\r
        setSessionHistoryPaging({
            sessionId: sid,
            total: typeof data.total === 'number' ? data.total : ph.total,
            range_start: typeof data.range_start === 'number' ? data.range_start : ph.range_start,
            range_end: ph.range_end,
            has_older: !!data.has_older,
            has_newer: !!ph.has_newer,
        });
    } catch (e) {\r
        console.error('加载更早消息失败:', e);\r
    } finally {
        historyOlderLoading = false;
        updateHistorySentinelVisibility();
        if (loadedOlder) {
            bindExistingLogs(stream);
            if (!opts.keepTocStable) rebuildToc();
            scheduleTocActiveUpdate();
        }
        if (
            cc && stream && stream.parentNode === cc
            && prependScrollTop != null && prependScrollHeight != null
            && !(typeof isHistorySmoothScrollActive === 'function' && isHistorySmoothScrollActive())
        ) {
            setScrollTopImmediate(
                cc,
                prependScrollTop + Math.max(0, cc.scrollHeight - prependScrollHeight)
            );
        }
        replayingMessages = prevReplaying;
    }
}
\r
function insertNewEmptyChatStream() { ensureVisibleChatStreamSlot(); }

async function loadHistoryWindowAroundEventIndex(sessionId, eventIndex, opts) {
    opts = opts || {};
    var sid = String(sessionId || '');
    var ei = Number(eventIndex);
    if (!sid || !Number.isFinite(ei)) return false;
    // A running session's ctx.stream is the append target for live SSE. Never
    // replace that DOM with an isolated history window or subsequent output
    // will be inserted in the middle of history. Older pages are prepended by
    // scrollToUserTurnOrLoadOlder instead.
    if (sessionHasLiveHistoryOwner(sid)) return false;
    var prevReplaying = replayingMessages;
    try {
        var turns = Math.max(1, Math.min(Number(opts.turns) || 50, 50));
        var url = '/sessions/' + encodeURIComponent(sid)
            + '/messages?turns=' + encodeURIComponent(String(turns))
            + '&target_index=' + encodeURIComponent(String(Math.floor(ei)));
        var response = await fetch(url);
        var data = await response.json().catch(function () { return null; });
        if (!response.ok || !data || typeof data !== 'object' || !Array.isArray(data.events)) return false;
        if (sid !== currentSessionId) return false;
        // The run may have started while the target window request was in
        // flight, or the local stream-active snapshot may have been stale.
        // Revalidate against the server before mutating the live append owner.
        if (await refreshSessionLiveHistoryOwner(sid)) return false;
        if (sid !== currentSessionId) return false;
        if (!getVisibleChatStream()) ensureVisibleChatStreamSlot();
        var stream = getVisibleChatStream();
        if (!stream) return false;
        emptyChatStreamKeepingStrip(stream);
        var total = Number(data.total) || 0;
        var rangeEnd = Number(data.range_end) || 0;
        var pageMeta = {
            total: total,
            range_start: Number(data.range_start) || 0,
            range_end: rangeEnd,
            has_older: !!data.has_older,
            has_newer: data.has_newer == null ? rangeEnd < total : !!data.has_newer,
        };
        beginMessageReplay(sid, pageMeta);
        setSessionHistoryPaging({
            sessionId: sid,
            total: pageMeta.total,
            range_start: pageMeta.range_start,
            range_end: pageMeta.range_end,
            has_older: !!pageMeta.has_older,
            has_newer: !!pageMeta.has_newer,
        });
        ensureHistorySentinel(stream);
        var ctx = newDomContext(stream);
        ctx.lastUserEventIndex = -1;
        replayingMessages = true;
        for (var i = 0; i < data.events.length; i += 1) {
            var ev = data.events[i];
            if (ev && typeof ev === 'object' && ev.type) {
                reduceAndRenderMessageEvent(ctx, ev, {
                    sessionId: sid,
                    eventIndex: pageMeta.range_start + i,
                    source: 'history-target',
                });
            }
        }
        replayingMessages = prevReplaying;
        bindExistingLogs(stream);
        rebuildToc();
        updateHistorySentinelVisibility();
        return true;
    } catch (e) {
        replayingMessages = prevReplaying;
        console.error('load target history window failed:', e);
        return false;
    }
}

const SESSION_STREAM_CACHE_LIMIT = 6;
const cachedSessionStreamOrder = [];
\r
function cssEscapeIdent(value) {\r
    if (window.CSS && typeof window.CSS.escape === 'function') return window.CSS.escape(value);\r
    return String(value || '').replace(/["\\\\]/g, '\\\\$&');\r
}\r
\r
function cacheOrderTouch(sessionId) {\r
    var sid = String(sessionId || '');\r
    if (!sid) return;\r
    var idx = cachedSessionStreamOrder.indexOf(sid);\r
    if (idx >= 0) cachedSessionStreamOrder.splice(idx, 1);\r
    cachedSessionStreamOrder.push(sid);\r
}\r
\r
function discardCachedSessionStream(sessionId) {\r
    var sid = String(sessionId || '');\r
    if (!sid || !offscreenRoot) return;\r
    var cached = offscreenRoot.querySelector('.chat-stream[data-cache-session-id="' + cssEscapeIdent(sid) + '"]');\r
    if (cached && cached.parentNode) cached.remove();\r
    var idx = cachedSessionStreamOrder.indexOf(sid);\r
    if (idx >= 0) cachedSessionStreamOrder.splice(idx, 1);\r
}\r
\r
function trimCachedSessionStreams() {
    if (!offscreenRoot) return;\r
    while (cachedSessionStreamOrder.length > SESSION_STREAM_CACHE_LIMIT) {\r
        var sid = cachedSessionStreamOrder.shift();\r
        var cached = offscreenRoot.querySelector('.chat-stream[data-cache-session-id="' + cssEscapeIdent(sid) + '"]');\r
        if (cached && cached.parentNode) cached.remove();\r
    }
}

function isCompleteLocalRunStream(sessionId, stream) {
    var run = getSessionRunState(sessionId);
    return !!(run && run.ctx && run.ctx.stream === stream
        && stream && stream.dataset
        && stream.dataset.partialBackgroundRun !== '1'
        && stream.dataset.sessionLoadFailed !== '1');
}

function stashVisibleStreamForSession(sessionId, opts) {
    opts = opts || {};\r
    var sid = String(sessionId || '');\r
    if (!sid || !offscreenRoot) return false;\r
    const el = getVisibleChatStream();
    if (!el || !el.parentNode) return false;
    /* A stream owned by this tab's active run is already the authoritative,
       gap-free UI projection even when no history request was needed (notably
       a newly-created session).  Certify it before moving it offscreen so a
       same-page switch can restore the live DOM instead of fetching snapshot. */
    if (opts.certifyLocalRun && isCompleteLocalRunStream(sid, el)) {
        el.dataset.sessionLoadOk = '1';
        delete el.dataset.sessionLoading;
    }
    if (!opts.force && el.dataset.sessionLoadOk !== '1') return false;
    if (el.dataset.sessionLoadFailed === '1') return false;\r
    discardCachedSessionStream(sid);\r
    el.remove();\r
    el.removeAttribute('id');\r
    el.removeAttribute('aria-label');\r
    el.classList.add('is-offscreen');\r
    el.setAttribute('data-cache-session-id', sid);\r
    offscreenRoot.appendChild(el);\r
    cacheOrderTouch(sid);\r
    trimCachedSessionStreams();\r
    return true;\r
}\r
\r
function prepareStashLeaving(leavingId) {
    if (!leavingId) return;
    if (isSessionRunning(leavingId)) {
        stashVisibleStreamForSession(leavingId, { force: true, certifyLocalRun: true });
        insertNewEmptyChatStream();
    } else {\r
        if (!stashVisibleStreamForSession(leavingId)) ensureVisibleChatStreamSlot();\r
        insertNewEmptyChatStream();\r
    }\r
}\r
\r
function restoreStreamForRunningSession(enteringId) {
    const run = getSessionRunState(enteringId);
    if (!run || !run.ctx || !run.ctx.stream) return false;
    const st = run.ctx.stream;
    if (!st.parentNode) return false;
    if (st.parentNode === chatContainer) return st.id === 'chat-stream';
    if (offscreenRoot && st.parentNode !== offscreenRoot) return false;
    const completeLocalRun = isCompleteLocalRunStream(enteringId, st);
    if (st.dataset && (st.dataset.partialBackgroundRun === '1'
        || (st.dataset.sessionLoadOk !== '1' && !completeLocalRun))) {
        abortSessionRun(enteringId, 'reattach-incomplete-background');
        if (st.parentNode) st.remove();
        return false;
    }
    if (completeLocalRun && st.dataset.sessionLoadOk !== '1') {
        st.dataset.sessionLoadOk = '1';
        delete st.dataset.sessionLoading;
    }
    const cur = getVisibleChatStream();
    if (cur && cur.parentNode === chatContainer) cur.remove();\r
    st.classList.remove('is-offscreen');\r
    st.removeAttribute('data-cache-session-id');\r
    st.id = 'chat-stream';\r
    st.setAttribute('aria-label', '消息');\r
    chatContainer.appendChild(st);\r
    cacheOrderTouch(enteringId);\r
    var restoredPaging = restoreHistoryPagingFromStream(st);\r
    if (restoredPaging) sessionHistoryPaging = restoredPaging;\r
    updateHistorySentinelVisibility();\r
    bindExistingLogs(st);\r
    return true;\r
}\r
\r
function restoreCachedSessionStream(enteringId) {
    var sid = String(enteringId || '');\r
    if (!sid || !offscreenRoot) return false;\r
    var st = offscreenRoot.querySelector('.chat-stream[data-cache-session-id="' + cssEscapeIdent(sid) + '"]');\r
    if (!st || !st.parentNode) return false;\r
    if (st.dataset.sessionLoadOk !== '1' || st.dataset.sessionLoadFailed === '1') {\r
        discardCachedSessionStream(sid);\r
        return false;\r
    }\r
    const cur = getVisibleChatStream();\r
    if (cur && cur.parentNode === chatContainer) cur.remove();\r
    st.classList.remove('is-offscreen');\r
    st.removeAttribute('data-cache-session-id');\r
    st.id = 'chat-stream';\r
    st.setAttribute('aria-label', '消息');\r
    chatContainer.appendChild(st);\r
    cacheOrderTouch(sid);\r
    var restoredPaging = restoreHistoryPagingFromStream(st);\r
    if (restoredPaging) sessionHistoryPaging = restoredPaging;\r
    updateHistorySentinelVisibility();\r
    bindExistingLogs(st);\r
    return true;
}

function scrollCurrentRunningProcessToBottom(sessionId) {
    if (!sessionId || sessionId !== currentSessionId) return;
    var run = getSessionRunState(sessionId);
    var ctx = run && run.ctx;
    var stream = ctx && ctx.stream && ctx.stream.isConnected ? ctx.stream : getVisibleChatStream();
    if (!stream) return;
    var agg = ctx && ctx.currentProcessGroup && ctx.currentProcessGroup.isConnected
        ? ctx.currentProcessGroup
        : null;
    if (!agg) {
        var runningAggs = stream.querySelectorAll('.process-aggregate.is-running');
        agg = runningAggs.length ? runningAggs[runningAggs.length - 1] : null;
    }
    // A restored server-side run may not yet have rebuilt the local run
    // context or the is-running class. Its last process block still owns the
    // newest generated entries, so use it as the authoritative fallback.
    if (!agg) {
        var allAggs = stream.querySelectorAll('.process-aggregate');
        agg = allAggs.length ? allAggs[allAggs.length - 1] : null;
    }
    if (!agg) return;
    if (agg.classList.contains('is-collapsed')) {
        agg.classList.remove('is-collapsed');
        var top = agg.querySelector('.process-aggregate-top');
        if (top) top.setAttribute('aria-expanded', 'true');
    }
    var viewports = [
        agg.querySelector('.process-aggregate-body'),
        agg.querySelector('.process-aggregate-brief'),
    ].filter(function (el) { return !!el; });
    function pinBottom() {
        viewports.forEach(function (el) {
            setScrollTopImmediate(el, el.scrollHeight);
        });
    }
    requestAnimationFrame(function () {
        pinBottom();
        requestAnimationFrame(pinBottom);
    });
}

function restoreCachedSessionScrollPosition(sessionId) {
    if (!chatContainer || !sessionId) return;
    if (sessionId !== currentSessionId) return;
    var running = isSessionRunning(sessionId)
        || (typeof isServerStreamActive === 'function' && isServerStreamActive(sessionId));
    var saved = (typeof getSavedScrollPosition === 'function') ? getSavedScrollPosition(sessionId) : null;
    if (running) {
        setScrollTopImmediate(chatContainer, chatContainer.scrollHeight);
        scrollCurrentRunningProcessToBottom(sessionId);
        streamChatNearBottom = true;
        streamProcNearBottom = true;
        liveAutoFollow = true;
    } else if (saved !== null && Number.isFinite(Number(saved))) {
        setScrollTopImmediate(chatContainer, Number(saved));
    } else {
        setScrollTopImmediate(chatContainer, chatContainer.scrollHeight);
    }
    refreshLiveAutoFollowPins();
    scheduleTocActiveUpdate();
    requestAnimationFrame(function () {
        if (sessionId !== currentSessionId) return;
        if (running) {
            setScrollTopImmediate(chatContainer, chatContainer.scrollHeight);
            scrollCurrentRunningProcessToBottom(sessionId);
        }
        else if (saved !== null && Number.isFinite(Number(saved))) setScrollTopImmediate(chatContainer, Number(saved));
        refreshLiveAutoFollowPins();
        scheduleTocActiveUpdate();
    });
}\r
\r
function markVisibleSessionStreamLoadState(sessionId, state) {\r
    var stream = getVisibleChatStream();\r
    if (!stream) return;\r
    stream.dataset.sessionId = String(sessionId || '');\r
    if (state === 'ok') {\r
        stream.dataset.sessionLoadOk = '1';\r
        delete stream.dataset.sessionLoadFailed;\r
        delete stream.dataset.sessionLoading;\r
    } else if (state === 'failed') {\r
        stream.dataset.sessionLoadFailed = '1';\r
        delete stream.dataset.sessionLoadOk;\r
        delete stream.dataset.sessionLoading;\r
        discardCachedSessionStream(sessionId);\r
    } else if (state === 'loading') {\r
        stream.dataset.sessionLoading = '1';\r
        delete stream.dataset.sessionLoadOk;\r
        delete stream.dataset.sessionLoadFailed;\r
    }\r
}\r
\r
function appendLogVisible(msg, type) {\r
    if (!getVisibleChatStream()) ensureVisibleChatStreamSlot();\r
    const c = newDomContext(getVisibleChatStream());\r
    appendLog(c, msg, type, currentSessionId);\r
}\r
\r
function newLlmState() {\r
    return {\r
        llmStreamReasoningIter: null,\r
        llmStreamResponseIter: null,\r
        llmStreamReasoningScroller: null,\r
        llmStreamResponseScroller: null,\r
        llmDeltaLastSeq: null,
        llmPendingReasoningDelta: '',
        llmPendingResponseDelta: '',
        llmDeltaFlushRaf: 0,
        llmThinkTagMode: 'response',
        llmThinkTagCarry: '',
        llmThinkTagAllowLeading: true,
    };
}
\r
function newDomContext(streamEl) {\r
    return {\r
        stream: streamEl,\r
        currentProcessGroup: null,\r
        lastUserEventIndex: -1,\r
        progressScrollers: {},\r
        progressStream: {},\r
        keyContextStreamFilter: { phase: 'seek', carry: '' },\r
        runStartedAt: null,
        reactGeneration: 0,
        _seenStreamDeltaKeys: new Set(),
        llm: newLlmState(),
    };\r
}\r
\r
function resetKeyContextStreamFilter(ctx) {\r
    if (ctx) ctx.keyContextStreamFilter = { phase: 'seek', carry: '' };\r
}\r
\r
/** 要点流式输出：隐藏 <analysis>…</analysis>，仅展示 <summary> 内正文 */\r
function extractKeyContextVisibleDelta(filter, delta) {\r
    if (!filter) return String(delta || '');\r
    filter.carry += String(delta || '');\r
    var out = '';\r
    var tagTail = 24;\r
    while (filter.carry.length > 0) {\r
        var lower = filter.carry.toLowerCase();\r
        if (filter.phase === 'seek') {\r
            var ai = lower.indexOf('<analysis');\r
            var si = lower.indexOf('<summary');\r
            if (ai >= 0 && (si < 0 || ai < si)) {\r
                if (ai > 0) out += filter.carry.slice(0, ai);\r
                filter.carry = filter.carry.slice(ai);\r
                filter.phase = 'in_analysis';\r
                continue;\r
            }\r
            if (si >= 0) {\r
                if (si > 0) out += filter.carry.slice(0, si);\r
                filter.carry = filter.carry.slice(si);\r
                filter.phase = 'in_summary';\r
                continue;\r
            }\r
            if (filter.carry.length > tagTail) {\r
                var safe = filter.carry.length - tagTail;\r
                out += filter.carry.slice(0, safe);\r
                filter.carry = filter.carry.slice(safe);\r
            }\r
            break;\r
        }\r
        if (filter.phase === 'in_analysis') {\r
            var ae = lower.indexOf('</analysis>');\r
            if (ae >= 0) {\r
                var aClose = filter.carry.slice(ae).match(/^<\\/analysis\\s*>/i);\r
                var aLen = aClose ? aClose[0].length : 11;\r
                filter.carry = filter.carry.slice(ae + aLen);\r
                filter.phase = 'seek';\r
                continue;\r
            }\r
            filter.carry = '';\r
            break;\r
        }\r
        if (filter.phase === 'in_summary') {\r
            var se = lower.indexOf('</summary>');\r
            var chunk = se >= 0 ? filter.carry.slice(0, se) : filter.carry;\r
            chunk = chunk.replace(/^<summary[^>]*>\\s*/i, '');\r
            out += chunk;\r
            if (se >= 0) {\r
                var sClose = filter.carry.slice(se).match(/^<\\/summary\\s*>/i);\r
                var sLen = sClose ? sClose[0].length : 10;\r
                filter.carry = filter.carry.slice(se + sLen);\r
                filter.phase = 'done';\r
            } else {\r
                filter.carry = '';\r
            }\r
            break;\r
        }\r
        if (filter.phase === 'done') {\r
            filter.carry = '';\r
            break;\r
        }\r
        break;\r
    }\r
    return out;\r
}\r
\r
function appendKeyContextStreamDelta(ctx, delta, runSessionId) {\r
    if (!ctx || !delta) return;\r
    if (!ctx.keyContextStreamFilter) resetKeyContextStreamFilter(ctx);\r
    var vis = extractKeyContextVisibleDelta(ctx.keyContextStreamFilter, delta);\r
    if (vis) appendProgressStreamDelta(ctx, vis, 'key-context', runSessionId);\r
}\r
\r
function isSessionRunning(sessionId) {\r
    return selectIsSessionRunning(sessionId);\r
}\r
\r
function syncDisconnectedProcessGroups() {\r
    sessionStore.runsBySession.forEach(function (run, sid) {\r
        const c = run && run.ctx;\r
        if (c && c.currentProcessGroup && !c.currentProcessGroup.isConnected) c.currentProcessGroup = null;\r
    });\r
}\r
\r
function finalizeLlmStreamChunks(ctx) {\r
    if (!ctx) return;\r
    flushLlmDeltaText(ctx);\r
    queryFeedChunksInCtx(ctx, '.feed-chunk.is-streaming').forEach(function (ch) {\r
        ch.classList.remove('is-streaming');\r
        scheduleFeedChunkOverflowRefresh(ch);\r
    });\r
    if (ctx.llm) {\r
        const l = ctx.llm;\r
        l.llmStreamReasoningIter = null;\r
        l.llmStreamResponseIter = null;\r
        l.llmStreamReasoningScroller = null;\r
        l.llmStreamResponseScroller = null;
        l.llmDeltaLastSeq = null;
        l.llmThinkTagMode = 'response';
        l.llmThinkTagCarry = '';
        l.llmThinkTagAllowLeading = true;
    }
    var bodies = [];\r
    if (ctx.currentProcessGroup && !isSubagentStreamCtx(ctx)) {\r
        var mainBody = ctx.currentProcessGroup.querySelector('.process-aggregate-body');\r
        if (mainBody) bodies.push(mainBody);\r
    }\r
    if (ctx._subagentTurnProcess && ctx._subagentTurnProcess.isConnected) {\r
        bodies.push(ctx._subagentTurnProcess);\r
    }\r
    bodies.forEach(function (body) {\r
        body.querySelectorAll('.feed-item.feed--llm, .feed-item.feed--llm2').forEach(function (el) {\r
            var sc = el.querySelector('.feed-chunk-scroller');\r
            var ch = el.querySelector('.feed-chunk');\r
            if (sc) {\r
                var norm = trimSurroundingBlankLines(sc.textContent || '');\r
                sc.textContent = truncateLogTextForUi(norm);\r
                if (ch) {\r
                    refreshFeedChunkOverflow(ch);\r
                    requestAnimationFrame(function () { refreshFeedChunkOverflow(ch); });\r
                }\r
            }\r
            if (!getFeedItemText(el).trim()) el.remove();\r
        });\r
    });\r
}\r
\r
function discardLlmStreamChunks(ctx, ev) {
    if (!ctx) return;
    ev = ev || {};
    if (ev.cleanup_scope === 'none') {
        finalizeLlmStreamChunks(ctx);
        return;
    }
    if (ctx.llm) {
        const l = ctx.llm;\r
        if (l.llmDeltaFlushRaf) {\r
            cancelAnimationFrame(l.llmDeltaFlushRaf);\r
            l.llmDeltaFlushRaf = 0;\r
        }\r
        l.llmPendingReasoningDelta = '';\r
        l.llmPendingResponseDelta = '';\r
        l.llmStreamReasoningIter = null;\r
        l.llmStreamResponseIter = null;\r
        l.llmStreamReasoningScroller = null;\r
        l.llmStreamResponseScroller = null;
        l.llmDeltaLastSeq = null;
        l.llmThinkTagMode = 'response';
        l.llmThinkTagCarry = '';
        l.llmThinkTagAllowLeading = true;
    }
    var bodies = [];\r
    if (ctx.currentProcessGroup && !isSubagentStreamCtx(ctx)) {\r
        var mainBody = ctx.currentProcessGroup.querySelector('.process-aggregate-body');\r
        if (mainBody) bodies.push(mainBody);\r
    }\r
    if (ctx._subagentTurnProcess && ctx._subagentTurnProcess.isConnected) {\r
        bodies.push(ctx._subagentTurnProcess);\r
    }\r
    var reactIter = ev && ev.react_iter != null && Number.isFinite(Number(ev.react_iter))
        ? String(Math.max(1, Math.floor(Number(ev.react_iter))))
        : '';
    var runId = String((ev && (ev.run_id || ev.runId)) || '');
    var hasScopedAbort = !!(reactIter || runId || (ev && ev.react_generation != null));
    var reactGeneration = ev && ev.react_generation != null && Number.isFinite(Number(ev.react_generation))
        ? String(Math.max(0, Math.floor(Number(ev.react_generation))))
        : (hasScopedAbort ? String(reactGenerationForContext(ctx)) : null);
    function matchesAbortScope(el) {
        if (!el) return false;
        if (reactIter && String(el.getAttribute('data-react-iter') || '') !== reactIter) return false;
        if (reactGeneration !== null && String(el.getAttribute('data-react-generation') || '0') !== reactGeneration) return false;
        var rowRunId = String(el.getAttribute('data-run-id') || '');
        if (runId && rowRunId && rowRunId !== runId) return false;
        return true;
    }
    bodies.forEach(function (body) {
        body.querySelectorAll('.feed-item[data-llm-live-row="1"]').forEach(function (el) {
            if (matchesAbortScope(el)) el.remove();
        });
        body.querySelectorAll(
            '.feed-item.feed--tool[data-tool-draft-key], '
            + '.feed-item.feed--tool[data-tool-pending="1"]'
        ).forEach(function (el) {
            if (matchesAbortScope(el)) el.remove();
        });
    });
}
\r
function flushLlmDeltaText(ctx) {
    if (!ctx || !ctx.llm) return;
    const l = ctx.llm;
    if (typeof flushThinkTagCarry === 'function') flushThinkTagCarry(ctx);
    if (l.llmDeltaFlushRaf) {
        cancelAnimationFrame(l.llmDeltaFlushRaf);
        l.llmDeltaFlushRaf = 0;
    }\r
    if (l.llmPendingReasoningDelta && l.llmStreamReasoningScroller) {\r
        var rs = trimSurroundingBlankLines((l.llmStreamReasoningScroller.textContent || '') + l.llmPendingReasoningDelta);\r
        l.llmStreamReasoningScroller.textContent = truncateLogTextForUi(rs);\r
    }\r
    l.llmPendingReasoningDelta = '';
    if (l.llmPendingResponseDelta && l.llmStreamResponseScroller) {
        var responseRow = l.llmStreamResponseScroller.closest
            ? l.llmStreamResponseScroller.closest('.feed-item')
            : null;
        var responseHead = responseRow && typeof responseRow._processBriefRawText === 'string'
            ? responseRow._processBriefRawText
            : (l.llmStreamResponseScroller.textContent || '');
        var rsp = trimSurroundingBlankLines(responseHead + l.llmPendingResponseDelta);
        if (responseRow) responseRow._processBriefRawText = rsp;
        l.llmStreamResponseScroller.textContent = truncateLogTextForUi(rsp);
    }
    l.llmPendingResponseDelta = '';\r
}\r
\r
function scheduleLlmDeltaFlush(ctx, runSessionId) {\r
    const l = ctx.llm;\r
    if (!l || l.llmDeltaFlushRaf) return;\r
    l.llmDeltaFlushRaf = requestAnimationFrame(function () {\r
        l.llmDeltaFlushRaf = 0;\r
        flushLlmDeltaText(ctx);\r
        followStreamProcessScroll(ctx, runSessionId);\r
    });\r
}\r
\r
function resetLlmState(ctx) {\r
    if (!ctx || !ctx.llm) return;\r
    flushLlmDeltaText(ctx);\r
    const l = ctx.llm;\r
    l.llmStreamReasoningIter = null;\r
    l.llmStreamResponseIter = null;\r
    l.llmStreamReasoningScroller = null;
    l.llmStreamResponseScroller = null;
    l.llmDeltaLastSeq = null;
    l.llmThinkTagMode = 'response';
    l.llmThinkTagCarry = '';
    l.llmThinkTagAllowLeading = true;
}
\r
function showCopyFeedback() {\r
    const t = document.getElementById('copy-toast');\r
    if (!t) return;\r
    t.classList.add('is-on');\r
    if (t._copyTm) clearTimeout(t._copyTm);\r
    t._copyTm = setTimeout(function () { t.classList.remove('is-on'); }, 1500);\r
}\r
\r
function showOpenFileFeedback(msg) {\r
    var t = document.getElementById('copy-toast');\r
    if (!t) return;\r
    var prev = t.getAttribute('data-default-msg') || t.textContent || '已复制';\r
    if (!t.getAttribute('data-default-msg')) t.setAttribute('data-default-msg', prev);\r
    t.textContent = msg || '已请求打开';\r
    t.classList.add('is-on');\r
    if (t._openFileTm) clearTimeout(t._openFileTm);\r
    t._openFileTm = setTimeout(function () {\r
        t.classList.remove('is-on');\r
        t.textContent = t.getAttribute('data-default-msg') || '已复制';\r
    }, 2200);\r
}\r
\r
(function initWorkspaceFileOpenDelegation() {\r
    if (document.body.dataset.workspaceFileOpenBound) return;\r
    document.body.dataset.workspaceFileOpenBound = '1';\r
    document.body.addEventListener('click', function (ev) {\r
        var el = ev.target;\r
        if (!el || !el.closest) return;\r
        var a = el.closest('a.msg-link-workspace-open');\r
        if (!a) return;\r
        ev.preventDefault();\r
        var rel = a.getAttribute('data-workspace-open') || '';\r
        var controller = (typeof AbortController !== 'undefined') ? new AbortController() : null;\r
        var timer = controller ? setTimeout(function () { controller.abort(); }, 8000) : null;\r
        fetch('/api/open-workspace-file?rel=' + encodeURIComponent(rel), controller ? { signal: controller.signal } : undefined)\r
            .then(function (r) {\r
                if (timer) clearTimeout(timer);\r
                return r.json().catch(function () { return { ok: false, error: '响应异常' }; });\r
            })\r
            .then(function (j) {\r
                if (j && j.ok) showOpenFileFeedback('已调用系统打开文件');\r
                else showOpenFileFeedback((j && j.error) ? ('无法打开：' + j.error) : '无法打开文件');\r
            })\r
            .catch(function () { showOpenFileFeedback('无法连接服务'); });\r
    });\r
})();\r
\r
let rewriteUndoState = null;\r
/** 改写待发送：仅在点击发送时调用截断；取消则丢弃 */\r
let pendingRewriteTruncate = null;\r
function hideRewriteUndoToast() {\r
    const t = document.getElementById('rewrite-undo-toast');\r
    if (t) {\r
        t.classList.remove('is-on');\r
        const btn = t.querySelector('.rewrite-undo-btn');\r
        if (btn) btn.textContent = '撤销';\r
    }\r
    rewriteUndoState = null;\r
}\r
function showRewriteUndoToast(type, data) {\r
    const t = document.getElementById('rewrite-undo-toast');\r
    const msgEl = t && t.querySelector('.rewrite-undo-msg');\r
    const btn = t && t.querySelector('.rewrite-undo-btn');\r
    if (!t || !msgEl) return;\r
    rewriteUndoState = { type: type, data: data };\r
    if (type === 'rewrite_pending') {\r
        msgEl.textContent = '改写待生效：发送消息后才会截断历史并发送；点此取消改写。';\r
        if (btn) btn.textContent = '取消改写';\r
    } else if (type === 'tail') {\r
        msgEl.textContent = '已截断历史，可撤销恢复';\r
        if (btn) btn.textContent = '撤销';\r
    } else {\r
        msgEl.textContent = '已填入输入框，可撤销';\r
        if (btn) btn.textContent = '撤销';\r
    }\r
    t.classList.add('is-on');\r
}\r
\r
function smoothScrollBy(el, dy) {\r
    if (!el || !dy) return;\r
    const bMax = Math.max(0, el.scrollHeight - el.clientHeight);\r
    const start = el.scrollTop;\r
    const target = Math.max(0, Math.min(bMax, start + dy));\r
    const dist = target - start;\r
    if (Math.abs(dist) < 0.5) return;\r
    const frames = 3;\r
    let f = 0;\r
    function step() {\r
        f += 1;\r
        const t = f / frames;\r
        const ease = 1 - Math.pow(1 - t, 2);\r
        el.scrollTop = start + dist * ease;\r
        if (f < frames) requestAnimationFrame(step);\r
    }\r
    requestAnimationFrame(step);\r
}\r
\r
function isNearBottom(el, thresholdPx) {\r
    if (!el) return true;\r
    const th = (thresholdPx == null) ? 56 : thresholdPx;\r
    return (el.scrollHeight - el.clientHeight - el.scrollTop) <= th;\r
}\r
\r
async function getUiEventCount(sessionId, opts) {
    opts = opts || {};
    const sid = sessionId != null ? sessionId : currentSessionId;
    if (!sid) return 0;
    if (
        opts.preferCache
        && typeof uiEventCountCache !== 'undefined'
        && typeof uiEventCountCache.has === 'function'
        && uiEventCountCache.has(sid)
        && (typeof uiEventCountCache.isFresh !== 'function' || uiEventCountCache.isFresh(sid, opts.maxAgeMs))
    ) {
        return uiEventCountCache.get(sid);
    }
    try {
        const controller = new AbortController();
        const externalSignal = opts.signal;
        const abortFromExternal = function () { controller.abort(); };
        if (externalSignal) {
            if (externalSignal.aborted) controller.abort();
            else externalSignal.addEventListener('abort', abortFromExternal, { once: true });
        }
        const timer = setTimeout(function () { controller.abort(); }, Math.max(250, Number(opts.timeoutMs) || 5000));
        let r;
        try {
            r = await fetch('/sessions/' + encodeURIComponent(sid) + '/messages/count', {
                signal: controller.signal
            });
        } finally {
            clearTimeout(timer);
            if (externalSignal) externalSignal.removeEventListener('abort', abortFromExternal);
        }
        if (!r.ok) return 0;
        const j = await r.json();
        const count = (j && typeof j.count === 'number') ? j.count : 0;
        if (typeof uiEventCountCache !== 'undefined') uiEventCountCache.updateFromServer(sid, count);
        return count;
    } catch (e) { return 0; }
}
\r
function loadUnreadFromStorage() {\r
    try {\r
        const raw = localStorage.getItem(LS_SESSION_UNREAD);\r
        if (!raw) return;\r
        const arr = JSON.parse(raw);\r
        if (!Array.isArray(arr)) return;\r
        arr.forEach(function (id) { sessionUnreadComplete.add(String(id)); });\r
    } catch (e) { /* ignore */ }\r
}\r
\r
function persistSessionUnread() {\r
    try {\r
        localStorage.setItem(LS_SESSION_UNREAD, JSON.stringify([...sessionUnreadComplete]));\r
    } catch (e) { /* ignore */ }\r
}\r
\r
function stashInputDraft(sessionId) {\r
    if (!messageInput || !sessionId) return;\r
    draftBySession[sessionId] = messageInput.value;\r
    persistInputDraft(sessionId, messageInput.value);\r
}\r
\r
function restoreInputDraft(sessionId) {\r
    if (!messageInput) return;\r
    const v = (sessionId && Object.prototype.hasOwnProperty.call(draftBySession, sessionId))\r
        ? draftBySession[sessionId]\r
        : readStoredInputDraft(sessionId);\r
    messageInput.value = v != null ? String(v) : '';\r
    rewriteInputWorkspacePaths();\r
    autoResizeTextarea();\r
}\r
\r
function inputDraftStorageKey(sessionId) {\r
    return LS_INPUT_DRAFT_PREFIX + String(sessionId || '');\r
}\r
\r
function persistInputDraft(sessionId, value) {\r
    if (!sessionId) return;\r
    const text = String(value || '');\r
    draftBySession[sessionId] = text;\r
    try {\r
        const key = inputDraftStorageKey(sessionId);\r
        if (text) localStorage.setItem(key, text);\r
        else localStorage.removeItem(key);\r
    } catch (e) { /* ignore */ }\r
}\r
\r
function readStoredInputDraft(sessionId) {\r
    if (!sessionId) return '';\r
    try {\r
        return localStorage.getItem(inputDraftStorageKey(sessionId)) || '';\r
    } catch (e) {\r
        return '';\r
    }\r
}\r
\r
function removeStoredInputDraft(sessionId) {\r
    if (!sessionId) return;\r
    delete draftBySession[sessionId];\r
    try { localStorage.removeItem(inputDraftStorageKey(sessionId)); } catch (e) { /* ignore */ }\r
}\r
\r
function clearStreamPoll() {\r
    if (streamPollTimer) {\r
        clearInterval(streamPollTimer);\r
        streamPollTimer = null;\r
    }\r
}\r
\r
async function fetchSessionStreamActiveMap() {\r
    try {\r
        const response = await fetch('/sessions');\r
        const sessions = await response.json();\r
        if (!Array.isArray(sessions)) return Object.create(null);\r
        const m = Object.create(null);\r
        for (let i = 0; i < sessions.length; i += 1) {\r
            const s = sessions[i];\r
            if (s && s.id) m[s.id] = !!s.stream_active;\r
        }\r
        return m;\r
    } catch (e) {\r
        return Object.create(null);\r
    }\r
}\r
\r
function maybeStartStreamPollForSession(sid, opts) {\r
    opts = opts || {};\r
    clearStreamPoll();\r
    if (!sid) return;\r
    if (!isSessionRunning(sid)) return;\r
    if (!getSessionRunState(sid) && typeof attachSessionEventStream === 'function') {\r
        void attachSessionEventStream(sid, { skipInitialLoad: !!opts.skipInitialLoad });\r
    }\r
    let pollCount = 0;\r
    let MAX_POLL_COUNT = 20;\r
    streamPollTimer = setInterval(function () {\r
        (async function () {\r
            if (currentSessionId !== sid) {\r
                clearStreamPoll();\r
                return;\r
            }\r
            pollCount += 1;\r
            const m = await fetchSessionStreamActiveMap();\r
            applyServerStreamActiveMap(m);\r
            const still = !!m[sid];\r
            if (!still || pollCount >= MAX_POLL_COUNT) {\r
                clearStreamPoll();\r
                await loadSessions();\r
                syncSessionListIndicatorClasses();\r
                setSendButtonState();\r
                return;\r
            }\r
            if (currentSessionId === sid && document.visibilityState === 'visible') {\r
                syncSessionListIndicatorClasses();\r
                setSendButtonState();\r
            }\r
        })();\r
    }, 15000);\r
}\r
\r
async function scrollToUserTurnOrLoadOlder(eventIndex, opts) {
    opts = opts || {};\r
    var ei = Number(eventIndex);\r
    if (!Number.isFinite(ei)) return false;\r
    var silent = !!opts.silent;
    var scrollBehavior = opts.instant ? 'auto' : 'smooth';
    var viewportOffset = Number(opts.viewportOffset);
    var hasViewportOffset = Number.isFinite(viewportOffset);
    var liveHistoryOwner = isSessionRunning(currentSessionId)
        || (typeof isServerStreamActive === 'function' && isServerStreamActive(currentSessionId));
    var allowFullReload = opts.allowFullReload !== false && !silent && !liveHistoryOwner;
    var maxOlderLoads = Number.isFinite(Number(opts.maxOlderLoads))\r
        ? Math.max(0, Number(opts.maxOlderLoads))\r
        : 120;\r
    function setTocJumpLoading(active) {\r
        var list = document.getElementById('chat-toc-list');\r
        var link = list && list.querySelector('a[data-event-index="' + ei + '"]');\r
        if (!link) return;\r
        link.classList.toggle('is-loading', !!active);\r
        if (active) link.setAttribute('aria-busy', 'true');\r
        else link.removeAttribute('aria-busy');\r
    }\r
    function findWrap() {
        var stream = getVisibleChatStream();\r
        if (!stream) return null;\r
        return stream.querySelector('.msg-wrap--user[data-event-index="' + ei + '"]')\r
            || stream.querySelector('#user-msg-' + ei);
    }
    function scrollToWrap(wrap) {
        if (!wrap) return;
        if (!hasViewportOffset || !chatContainer) {
            wrap.scrollIntoView({ behavior: scrollBehavior, block: 'start' });
            return;
        }
        var viewportRect = chatContainer.getBoundingClientRect();
        var wrapRect = wrap.getBoundingClientRect();
        var maxTop = Math.max(0, chatContainer.scrollHeight - chatContainer.clientHeight);
        var targetTop = chatContainer.scrollTop + wrapRect.top - viewportRect.top - viewportOffset;
        targetTop = Math.max(0, Math.min(maxTop, targetTop));
        if (scrollBehavior === 'smooth' && typeof chatContainer.scrollTo === 'function') {
            chatContainer.scrollTo({ top: targetTop, behavior: 'smooth' });
        } else {
            setScrollTopImmediate(chatContainer, targetTop);
        }
    }
    async function loadFullHistoryForTarget(sid) {\r
        if (!allowFullReload) return;\r
        if (sid !== currentSessionId || typeof loadSessionMessages !== 'function') return;\r
        try {\r
            await loadSessionMessages(sid, 'saved-or-bottom', { full: true });
        } catch (e) {\r
            console.error('reload full history for toc target failed:', e);\r
        }\r
    }\r
    setTocJumpLoading(true);\r
    try {\r
        var wrap = findWrap();
        if (wrap) {
            scrollToWrap(wrap);
            return true;
        }
        var sid = currentSessionId;
        if (allowFullReload) {
            var loadedTargetWindow = await loadHistoryWindowAroundEventIndex(sid, ei, { turns: 50 });
            if (loadedTargetWindow && sid === currentSessionId) {
                wrap = findWrap();
                if (wrap) {
                    scrollToWrap(wrap);
                    return true;
                }
            }
        }
        var safety = 0;
        var olderLoads = 0;\r
        var pagingCoveredTarget = false;\r
        while (sid === currentSessionId && safety < 120) {\r
            safety += 1;\r
            wrap = findWrap();
            if (wrap) {
                scrollToWrap(wrap);
                return true;
            }\r
            var ph = sessionHistoryPaging;\r
            if ((!ph || ph.sessionId !== sid) && getVisibleChatStream()) {\r
                ph = restoreHistoryPagingFromStream(getVisibleChatStream());\r
                if (ph) sessionHistoryPaging = ph;\r
            }\r
            if (!ph || ph.sessionId !== sid) {\r
                await loadFullHistoryForTarget(sid);\r
                break;\r
            }\r
            if (ei >= ph.range_start) {\r
                pagingCoveredTarget = true;\r
                break;\r
            }\r
            if (!ph.has_older) break;\r
            if (olderLoads >= maxOlderLoads) break;\r
            while (historyOlderLoading && currentSessionId === sid) {\r
                await new Promise(function (r) { setTimeout(r, 40); });\r
            }\r
            olderLoads += 1;\r
            await loadOlderHistoryChunk({ keepTocStable: true, turns: 50 });\r
        }\r
        wrap = findWrap();
        if (wrap) {
            scrollToWrap(wrap);
            return true;
        }\r
        if (allowFullReload && sid === currentSessionId && pagingCoveredTarget) {\r
            await loadFullHistoryForTarget(sid);\r
            if (sid !== currentSessionId) return false;\r
            wrap = findWrap();\r
            if (wrap) {\r
                wrap.scrollIntoView({ behavior: scrollBehavior, block: 'start' });
                return true;\r
            }\r
            rebuildToc();\r
        }\r
        if (wrap) wrap.scrollIntoView({ behavior: scrollBehavior, block: 'start' });
        else if (!silent) {\r
            showUiAlert({\r
                title: '无法定位该条',\r
                message: '未能加载到对应的用户提问（可能索引不一致）。可刷新页面或使用「更早 ' + HISTORY_DIALOGUES_PER_PAGE + ' 轮对话」手动分页。',\r
                showCancel: false,\r
                confirmText: '知道了',\r
            });\r
        }\r
        return !!wrap;\r
    } finally {\r
        setTocJumpLoading(false);\r
    }\r
}\r
`,Ht=`function ensureUiHoverTooltipEl() {
    if (uiHoverTooltipEl) return uiHoverTooltipEl;
    uiHoverTooltipEl = document.getElementById('ui-hover-tooltip');
    if (!uiHoverTooltipEl) {
        uiHoverTooltipEl = document.createElement('div');
        uiHoverTooltipEl.id = 'ui-hover-tooltip';
        uiHoverTooltipEl.setAttribute('role', 'tooltip');
        document.body.appendChild(uiHoverTooltipEl);
    }
    return uiHoverTooltipEl;
}

function showUiHoverTooltip(ev, text) {
    var t = (text != null) ? String(text) : '';
    if (!t.trim()) return;
    var el = ensureUiHoverTooltipEl();
    el.textContent = t;
    el.classList.add('is-visible');
    requestAnimationFrame(function () {
        positionUiHoverTooltip(ev);
    });
}

function moveUiHoverTooltip(ev) {
    if (!uiHoverTooltipEl || !uiHoverTooltipEl.classList.contains('is-visible')) return;
    if (hoverTooltipMoveScheduled) return;
    hoverTooltipMoveScheduled = true;
    requestAnimationFrame(function () {
        hoverTooltipMoveScheduled = false;
        positionUiHoverTooltip(ev);
    });
}

function clearUiHoverTipTimer() {
    if (uiHoverTipTimer) {
        clearTimeout(uiHoverTipTimer);
        uiHoverTipTimer = null;
    }
}

function hideUiHoverTooltip() {
    clearUiHoverTipTimer();
    uiHoverTipActiveEl = null;
    uiHoverTipLastEv = null;
    if (uiHoverTooltipEl) uiHoverTooltipEl.classList.remove('is-visible');
}

function positionUiHoverTooltip(ev) {
    var el = uiHoverTooltipEl;
    if (!el) return;
    el.style.left = '-9999px';
    el.style.top = '0';
    var pad = 14;
    var bw = el.offsetWidth;
    var bh = el.offsetHeight;
    var vw = window.innerWidth;
    var vh = window.innerHeight;
    var x = ev.clientX + pad;
    var y = ev.clientY + pad;
    if (x + bw > vw - 10) x = Math.max(10, vw - bw - 10);
    if (y + bh > vh - 10) y = Math.max(10, ev.clientY - bh - pad);
    if (x < 10) x = 10;
    if (y < 10) y = 10;
    el.style.left = x + 'px';
    el.style.top = y + 'px';
}

/** 统一悬停说明（替代原生 title），文案来自 data-ui-tip；停留超过 UI_HOVER_TIP_DELAY_MS 才显示 */
function bindUiHoverTip(el) {
    if (!el || el._uiHoverTipBound) return;
    var tip = el.getAttribute('data-ui-tip');
    if (!tip || !String(tip).trim()) {
        var legacyTitle = el.getAttribute('title');
        if (legacyTitle && String(legacyTitle).trim()) {
            el.setAttribute('data-ui-tip', legacyTitle);
            tip = legacyTitle;
        }
    }
    if (!tip || !String(tip).trim()) return;
    el._uiHoverTipBound = true;
    el.removeAttribute('title');
    el.addEventListener('mouseenter', function (ev) {
        var t = el.getAttribute('data-ui-tip');
        if (t == null || !String(t).trim()) return;
        if (typeof translateUiString === 'function') t = translateUiString(t);
        clearUiHoverTipTimer();
        hideUiHoverTooltip();
        uiHoverTipActiveEl = el;
        uiHoverTipLastEv = ev;
        uiHoverTipTimer = setTimeout(function () {
            uiHoverTipTimer = null;
            if (uiHoverTipActiveEl !== el) return;
            showUiHoverTooltip(uiHoverTipLastEv || ev, t);
        }, UI_HOVER_TIP_DELAY_MS);
    });
    el.addEventListener('mousemove', function (ev) {
        uiHoverTipLastEv = ev;
        moveUiHoverTooltip(ev);
    });
    el.addEventListener('mouseleave', function () {
        if (uiHoverTipActiveEl === el) uiHoverTipActiveEl = null;
        clearUiHoverTipTimer();
        hideUiHoverTooltip();
    });
    el.addEventListener('focus', function () {
        var t = el.getAttribute('data-ui-tip');
        if (t == null || !String(t).trim()) return;
        if (typeof translateUiString === 'function') t = translateUiString(t);
        var rect = el.getBoundingClientRect();
        showUiHoverTooltip({ clientX: rect.right, clientY: rect.top }, t);
    });
    el.addEventListener('blur', hideUiHoverTooltip);
}

function initUiHoverTips(root) {
    root = root || document;
    root.querySelectorAll('[data-ui-tip]').forEach(function (el) {
        bindUiHoverTip(el);
    });
    root.querySelectorAll('[title]').forEach(function (el) {
        bindUiHoverTip(el);
    });
}

function scheduleTocActiveUpdate() {
    var list = document.getElementById('chat-toc-list');
    if (!list || !list.querySelector('a[data-event-index]')) return;
    if (tocActiveUpdateRaf) return;
    tocActiveUpdateRaf = requestAnimationFrame(function () {
        tocActiveUpdateRaf = 0;
        updateTocActiveFromViewport();
    });
}

function updateTocActiveFromViewport() {
    var list = document.getElementById('chat-toc-list');
    if (!list || !chatContainer) return;
    var stream = getVisibleChatStream();
    if (!stream) return;
    var users = stream.querySelectorAll('.msg-wrap--user[data-event-index]');
    if (!users.length) return;
    var cr = chatContainer.getBoundingClientRect();
    var pivot = cr.top + cr.height * 0.5;
    var chosen = null;
    for (var i = 0; i < users.length; i += 1) {
        var u = users[i];
        var r = u.getBoundingClientRect();
        if (r.top <= pivot) {
            chosen = u;
            continue;
        }
        break;
    }
    if (!chosen) chosen = users[0];
    if (!chosen) return;
    var idx = chosen.getAttribute('data-event-index');
    if (idx == null) return;
    var active = list.querySelector('a[data-event-index="' + idx + '"]');
    list.querySelectorAll('a.is-current').forEach(function (a) {
        if (a !== active) a.classList.remove('is-current');
    });
    if (!active) return;
    active.classList.add('is-current');
    var pad = 6;
    var top = active.offsetTop;
    var bottom = top + active.offsetHeight;
    if (top < list.scrollTop + pad) {
        list.scrollTop = Math.max(0, top - pad);
    } else if (bottom > list.scrollTop + list.clientHeight - pad) {
        list.scrollTop = bottom - list.clientHeight + pad;
    }
}

function clearTocForSessionLoad() {
    const toc = document.getElementById('chat-toc');
    const list = document.getElementById('chat-toc-list');
    tocRebuildEpoch += 1;
    if (list) list.textContent = '';
    if (toc) toc.classList.remove('is-open');
    notifyPanelContentChanged();
}

function clearTodoForSessionLoad() {
    const root = document.getElementById('chat-todo-plan');
    const statsEl = document.getElementById('chat-todo-plan-stats');
    const listEl = document.getElementById('chat-todo-plan-list');
    todoRefreshEpoch += 1;
    if (currentSessionId) clearTodoPlanState(currentSessionId);
    if (statsEl) statsEl.textContent = '';
    if (listEl) listEl.textContent = '';
    if (root) root.classList.remove('is-open');
    notifyPanelContentChanged();
}

const tocTurnsCacheBySession = new Map();

function setTocTurnsForSession(sessionId, turns) {
    if (!sessionId || !Array.isArray(turns)) return;
    tocTurnsCacheBySession.set(sessionId, turns);
}

function truncateTocTurnsForSession(sessionId, beforeIndex) {
    if (!sessionId) return;
    const before = Math.max(0, Number(beforeIndex) || 0);
    const turns = tocTurnsCacheBySession.get(sessionId) || [];
    tocTurnsCacheBySession.set(sessionId, turns.filter(function (row) {
        return Number(row && row.event_index) < before;
    }));
}

function startTocForSessionLoad(sessionId) {
    if (!sessionId || sessionId !== currentSessionId) return;
    var prevSuppress = suppressTocDuringSessionLoad;
    suppressTocDuringSessionLoad = false;
    try {
        rebuildToc();
    } finally {
        suppressTocDuringSessionLoad = prevSuppress;
    }
}

function rebuildToc(options) {
    options = options || {};
    const toc = document.getElementById('chat-toc');
    const list = document.getElementById('chat-toc-list');
    if (!toc || !list) return;
    if (suppressTocDuringSessionLoad) {
        return;
    }
    if (!list._tocTipScrollHide) {
        list._tocTipScrollHide = true;
        list.addEventListener('scroll', hideUiHoverTooltip, { passive: true });
    }
    list.textContent = '';
    const sid = currentSessionId;
    const epoch = ++tocRebuildEpoch;
    (async function () {
        let turns = [];
        if (sid) {
            if (Array.isArray(options.turns)) {
                turns = options.turns;
                tocTurnsCacheBySession.set(sid, turns);
            } else if (options.localOnly) {
                turns = tocTurnsCacheBySession.get(sid) || [];
            } else {
                try {
                    const r = await fetch('/sessions/' + encodeURIComponent(sid) + '/user_turns');
                    if (epoch !== tocRebuildEpoch || sid !== currentSessionId) return;
                    if (r.ok) {
                        const j = await r.json();
                        if (Array.isArray(j)) {
                            turns = j;
                            tocTurnsCacheBySession.set(sid, j);
                        }
                    }
                } catch (e) {
                    turns = tocTurnsCacheBySession.get(sid) || [];
                }
            }
        }
        if (epoch !== tocRebuildEpoch || sid !== currentSessionId) return;
        /** event_index → 预览（服务端与当前 DOM 合并：刚发出的提问尚未写入 ui_events，由气泡补上） */
        const merged = new Map();
        turns.forEach(function (row) {
            const ei = Number(row.event_index);
            if (!Number.isFinite(ei)) return;
            merged.set(ei, String(row.preview || '').trim());
        });
        const vs = getVisibleChatStream();
        const rootForUsers = vs || chatContainer;
        if (rootForUsers) {
            rootForUsers.querySelectorAll('.msg-wrap--user[data-event-index]').forEach(function (wrap) {
                const ei = parseInt(wrap.getAttribute('data-event-index'), 10);
                if (!Number.isFinite(ei)) return;
                const text = (wrap.querySelector('.message') && wrap.querySelector('.message').innerText || '').trim();
                merged.set(ei, text);
            });
        }
        if (epoch !== tocRebuildEpoch || sid !== currentSessionId) return;
        list.replaceChildren();
        let indices = [...merged.keys()].filter(function (x) { return Number.isFinite(x); }).sort(function (a, b) { return a - b; });
        function normalizedPreviewKey(p) {
            return String(p || '').trim().replace(/\\s+/g, ' ');
        }
        const dupCountByKey = new Map();
        indices.forEach(function (ei) {
            const k = normalizedPreviewKey(merged.get(ei));
            dupCountByKey.set(k, (dupCountByKey.get(k) || 0) + 1);
        });
        function appendTocLink(label, titleFull, scrollToWrap, eventIndex) {
            const a = document.createElement('a');
            a.href = '#';
            if (eventIndex != null) a.setAttribute('data-event-index', String(eventIndex));
            var tipText = (titleFull != null && String(titleFull).trim() !== '')
                ? String(titleFull)
                : String(label || '');
            a.setAttribute('data-ui-tip', tipText);
            bindUiHoverTip(a);
            const tocSpan = document.createElement('span');
            tocSpan.className = 'chat-toc-text';
            tocSpan.textContent = label;
            a.appendChild(tocSpan);
            a.addEventListener('click', function (e) {
                e.preventDefault();
                hideUiHoverTooltip();
                if (typeof scrollToWrap === 'function') scrollToWrap();
            });
            list.appendChild(a);
        }
        if (indices.length === 0) {
            const users = rootForUsers ? rootForUsers.querySelectorAll('.msg-wrap--user') : [];
            if (users.length === 0) {
                toc.classList.remove('is-open');
                notifyPanelContentChanged();
                return;
            }
            toc.classList.add('is-open');
            users.forEach(function (wrap, idx) {
                if (!wrap.id) wrap.id = 'user-msg-' + idx;
                const text = (wrap.querySelector('.message') && wrap.querySelector('.message').innerText || '').trim();
                const label = text.length > 44 ? text.slice(0, 42) + '…' : (text || ('问题 ' + (idx + 1)));
                appendTocLink(label, text, function () {
                    wrap.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
                }, wrap.getAttribute('data-event-index'));
            });
        } else {
            toc.classList.add('is-open');
            indices.forEach(function (ei) {
                const preview = merged.get(ei) || '';
                var label = preview.length > 44 ? preview.slice(0, 42) + '…' : (preview || ('问题 #' + (ei + 1)));
                var titleFull = preview || label;
                const nk = normalizedPreviewKey(preview);
                if ((dupCountByKey.get(nk) || 0) > 1) {
                    label = label + ' #' + (ei + 1);
                    titleFull = (preview || '') + '（事件索引 ' + ei + '）';
                }
                appendTocLink(label, titleFull, function () {
                    void scrollToUserTurnOrLoadOlder(ei);
                }, ei);
            });
        }
        notifyPanelContentChanged();
        if (tocScrollBottomOnNextBuild) {
            tocScrollBottomOnNextBuild = false;
            list.scrollTop = list.scrollHeight;
        } else if (!replayingMessages) {
            requestAnimationFrame(function () {
                requestAnimationFrame(function () {
                    list.scrollTop = list.scrollHeight;
                });
            });
        } else {
            scheduleTocActiveUpdate();
        }
    })();
}

function todoPlanStatusLabel(st) {
    if (st === 'completed') return '已完成';
    if (st === 'in_progress') return '进行中';
    return '待处理';
}

function syncGoalTodoPanelVisibility() {
    const root = document.getElementById('chat-todo-plan');
    const goalCard = document.getElementById('chat-goal-card');
    const todoCard = document.getElementById('chat-todo-card');
    if (!root) return;
    const hasVisibleCard = !!((goalCard && !goalCard.hidden) || (todoCard && !todoCard.hidden));
    root.classList.toggle('is-open', hasVisibleCard);
    notifyPanelContentChanged();
}

async function clearTodoPlan() {
    const sid = currentSessionId;
    if (!sid) return;
    try {
        await fetch('/sessions/' + encodeURIComponent(sid) + '/todo_plan', { method: 'DELETE' });
    } catch (e) { /* ignore */ }
    clearTodoPlanState(sid);
    const todoCard = document.getElementById('chat-todo-card');
    if (todoCard) todoCard.hidden = true;
    const statsEl = document.getElementById('chat-todo-plan-stats');
    const listEl = document.getElementById('chat-todo-plan-list');
    if (statsEl) statsEl.textContent = '';
    if (listEl) listEl.textContent = '';
    syncGoalTodoPanelVisibility();
}

function renderTodoPlanSnapshot(snapshot) {
    const root = document.getElementById('chat-todo-plan');
    const listEl = document.getElementById('chat-todo-plan-list');
    const statsEl = document.getElementById('chat-todo-plan-stats');
    const todoCard = document.getElementById('chat-todo-card');
    if (!root || !listEl || !statsEl || !todoCard) return;
    const data = snapshot || { items: [], done: 0, total: 0, has_plan: false };
    const items = Array.isArray(data.items) ? data.items : [];
    const has = !!(data.has_plan && items.length > 0);
    todoCard.hidden = !has;
    if (!has) {
        listEl.textContent = '';
        statsEl.textContent = '';
        syncGoalTodoPanelVisibility();
        return;
    }
    const done = data.done;
    const total = data.total;
    const statsText = String(done) + ' / ' + String(total) + ' 已完成';
    statsEl.textContent = typeof translateUiString === 'function' ? translateUiString(statsText) : statsText;
    listEl.textContent = '';
    items.forEach(function (it) {
        const li = document.createElement('li');
        const st = (it && it.status) || 'pending';
        li.className = 'todo-plan-item todo-plan--' + String(st);
        const tag = document.createElement('span');
        tag.className = 'todo-plan-status-tag';
        const statusLabel = todoPlanStatusLabel(st);
        tag.textContent = typeof translateUiString === 'function' ? translateUiString(statusLabel) : statusLabel;
        li.appendChild(tag);
        const text = document.createElement('span');
        text.textContent = (it && it.text != null) ? String(it.text) : '';
        li.appendChild(text);
        listEl.appendChild(li);
    });
    syncGoalTodoPanelVisibility();
}

function applyTodoPlanFromPayload(data) {
    renderTodoPlanSnapshot(applyTodoPlanToStore(currentSessionId, data));
}

function renderTodoPlanForCurrentSession() {
    renderTodoPlanSnapshot(selectTodoPlan(currentSessionId));
    renderGoalForCurrentSession();
    void refreshGoalCard();
}

let renderedGoalState = null;
const goalStateBySession = new Map();
const goalElapsedAnchorBySession = new Map();
const goalRefreshInFlightBySession = new Map();
const goalStreamRecoveryInFlightBySession = new Set();

function summarizeGoalObjective(value, maxLength) {
    const full = String(value == null ? '' : value).replace(/\\s+/g, ' ').trim();
    const limit = Math.max(24, Number(maxLength) || 96);
    if (full.length <= limit) return full;
    return full.slice(0, limit - 1).trimEnd() + '…';
}

function renderGoalForCurrentSession() {
    const sid = String(currentSessionId || '');
    const goal = sid && goalStateBySession.has(sid) ? goalStateBySession.get(sid) : null;
    renderGoalCard(goal, sid);
}

function setGoalStateForSession(sessionId, goal) {
    const sid = String(sessionId || '').trim();
    if (!sid) return;
    const now = Date.now();
    const previous = goalStateBySession.get(sid);
    const previousAnchor = goalElapsedAnchorBySession.get(sid);
    const normalized = goal && goal.id
        ? Object.assign({}, goal)
        : null;
    goalStateBySession.set(sid, normalized);
    if (normalized) {
        let elapsedSeconds = Math.max(0, Number(normalized.elapsed_seconds || 0));
        const sameGoal = previous && previousAnchor
            && String(previous.id || '') === String(normalized.id || '')
            && String(previousAnchor.goalId || '') === String(normalized.id || '');
        if (sameGoal) {
            const previousLiveSeconds = String(previousAnchor.status || '') === 'active'
                ? Math.max(0, (now - Number(previousAnchor.receivedAt || now)) / 1000)
                : 0;
            elapsedSeconds = Math.max(
                elapsedSeconds,
                Number(previousAnchor.elapsedSeconds || 0) + previousLiveSeconds,
            );
        }
        normalized.elapsed_seconds = elapsedSeconds;
        goalElapsedAnchorBySession.set(sid, {
            goalId: String(normalized.id || ''),
            status: String(normalized.status || ''),
            elapsedSeconds: elapsedSeconds,
            receivedAt: now,
        });
    } else {
        goalElapsedAnchorBySession.delete(sid);
    }
    if (sid === String(currentSessionId || '')) {
        renderGoalCard(normalized, sid);
        if (normalized && String(normalized.status || '') === 'active') {
            void recoverActiveGoalStream(sid);
        }
    }
}

async function recoverActiveGoalStream(sessionId) {
    const sid = String(sessionId || '').trim();
    if (!sid || sid !== String(currentSessionId || '') || document.visibilityState === 'hidden') return false;
    const goal = goalStateBySession.get(sid);
    if (!goal || String(goal.status || '') !== 'active') return false;
    if (typeof getSessionRunState === 'function' && getSessionRunState(sid)) return false;
    if (goalStreamRecoveryInFlightBySession.has(sid)) return false;
    goalStreamRecoveryInFlightBySession.add(sid);
    try {
        if (typeof reconcileRunStateFromServer === 'function') {
            await reconcileRunStateFromServer({ silent: true });
        }
        if (sid !== String(currentSessionId || '')) return false;
        const latestGoal = goalStateBySession.get(sid);
        if (!latestGoal || String(latestGoal.status || '') !== 'active') return false;
        if (typeof getSessionRunState === 'function' && getSessionRunState(sid)) return false;
        const serverActive = (typeof isServerStreamActive === 'function' && isServerStreamActive(sid))
            || (typeof isSessionRunning === 'function' && isSessionRunning(sid));
        if (!serverActive || typeof maybeStartStreamPollForSession !== 'function') return false;
        maybeStartStreamPollForSession(sid, { skipInitialLoad: true });
        return true;
    } catch (error) {
        return false;
    } finally {
        goalStreamRecoveryInFlightBySession.delete(sid);
    }
}

function formatGoalElapsed(seconds) {
    const total = Math.max(0, Math.floor(Number(seconds) || 0));
    const hours = Math.floor(total / 3600);
    const minutes = Math.floor((total % 3600) / 60);
    const secs = total % 60;
    const translate = function (value) {
        return typeof translateUiString === 'function' ? translateUiString(value) : value;
    };
    if (hours > 0) return String(hours) + translate('小时') + ' ' + String(minutes) + translate('分') + ' ' + String(secs).padStart(2, '0') + translate('秒');
    if (minutes > 0) return String(minutes) + translate('分') + ' ' + String(secs).padStart(2, '0') + translate('秒');
    return String(secs) + translate('秒');
}

function renderGoalMeta(goal, sessionId) {
    const sid = String(sessionId || currentSessionId || '');
    if (!goal || sid !== String(currentSessionId || '')) return;
    const metaEl = document.getElementById('chat-goal-meta');
    if (!metaEl) return;
    const translate = function (value) {
        return typeof translateUiString === 'function' ? translateUiString(value) : value;
    };
    const status = String(goal.status || 'active');
    const anchor = goalElapsedAnchorBySession.get(sid);
    const anchorMatches = anchor && String(anchor.goalId || '') === String(goal.id || '');
    const receivedAt = Number(anchorMatches ? anchor.receivedAt : Date.now());
    const liveSeconds = status === 'active' ? Math.max(0, (Date.now() - receivedAt) / 1000) : 0;
    const elapsed = Number(anchorMatches ? anchor.elapsedSeconds : goal.elapsed_seconds || 0) + liveSeconds;
    const statusEl = document.getElementById('chat-goal-status');
    if (statusEl && status === 'active') {
        statusEl.textContent = translate('进行中') + ' · ' + formatGoalElapsed(elapsed);
    }
    const usedTokens = Math.max(0, Number(goal.used_tokens || 0));
    const tokenText = goal.token_budget == null
        ? 'Token ' + translate('已消耗') + ' ' + String(usedTokens)
        : 'Token ' + String(usedTokens) + ' / ' + String(goal.token_budget);
    const continuationText = translate('续跑') + ' ' + String(goal.continuation_count || 0);
    const failureText = translate('连续失败') + ' ' + String(goal.consecutive_failures || 0);
    const judgeText = 'Judge ' + String(goal.judge_count || 0);
    const reasonLabels = {
        token_budget_exhausted: 'Token 预算已耗尽',
        consecutive_run_failures: '连续运行失败',
        judge_parse_failures: 'Judge 解析连续失败',
        judge_transport_failures: 'Judge 调用连续失败',
        react_iteration_limit: 'ReAct 已达到轮次上限',
        manual: '手动暂停'
    };
    const rawReason = String(goal.pause_reason || '');
    const reasonText = reasonLabels[rawReason] || rawReason;
    const pauseReason = reasonText ? ' · ' + translate(reasonText) : '';
    const metaText = tokenText + ' · ' + translate('用时') + ' ' + formatGoalElapsed(elapsed)
        + ' · ' + judgeText + ' · ' + continuationText + ' · ' + failureText + pauseReason;
    let help = translate('连续失败表示 Goal 执行中连续以失败或错误结束的运行次数（包括初始执行和自动续跑）；任一轮成功完成后会归零。');
    if (goal.last_error) help += '\\n' + translate('最近错误') + ': ' + String(goal.last_error);
    if (goal.last_judge_verdict) {
        help += '\\n' + translate('最近 Judge') + ': ' + String(goal.last_judge_verdict);
        if (goal.last_judge_reason) help += ' · ' + String(goal.last_judge_reason);
    }
    metaEl.setAttribute('data-ui-tip', metaText + '\\n' + help);
    metaEl.setAttribute('aria-label', translate('统计信息') + ': ' + metaText + '. ' + help);
    bindUiHoverTip(metaEl);
}

function renderGoalCard(goal, sessionId) {
    const sid = String(sessionId || currentSessionId || '');
    if (sid !== String(currentSessionId || '')) return;
    const card = document.getElementById('chat-goal-card');
    if (!card) return;
    const has = !!(goal && goal.id);
    renderedGoalState = has ? Object.assign({}, goal) : null;
    const statusEl = document.getElementById('chat-goal-status');
    const objectiveEl = document.getElementById('chat-goal-objective');
    const metaEl = document.getElementById('chat-goal-meta');
    const toggle = document.getElementById('chat-goal-toggle');
    const edit = document.getElementById('chat-goal-edit');
    const remove = document.getElementById('chat-goal-delete');
    const review = document.getElementById('chat-goal-review');
    card.hidden = !has;
    if (!has) {
        if (statusEl) statusEl.textContent = '';
        if (objectiveEl) {
            objectiveEl.textContent = '';
            objectiveEl.removeAttribute('data-ui-tip');
            objectiveEl.removeAttribute('aria-label');
        }
        if (metaEl) {
            metaEl.removeAttribute('data-ui-tip');
            metaEl.removeAttribute('aria-label');
            metaEl.hidden = true;
        }
        if (toggle) toggle.hidden = true;
        if (edit) edit.hidden = true;
        if (remove) remove.hidden = true;
        if (review) review.hidden = true;
        syncGoalTodoPanelVisibility();
        return;
    }
    if (metaEl) metaEl.hidden = false;
    const status = String(goal.status || 'active');
    const statusLabels = {
        active: '进行中', paused: '已暂停', completed: '已完成', blocked: '已阻塞', cancelled: '已取消'
    };
    if (statusEl) {
        const label = statusLabels[status] || status;
        statusEl.textContent = typeof translateUiString === 'function' ? translateUiString(label) : label;
    }
    if (objectiveEl) {
        const fullObjective = String(goal.objective || '').trim();
        const summary = summarizeGoalObjective(fullObjective, 200);
        objectiveEl.textContent = summary;
        objectiveEl.setAttribute('aria-label', fullObjective);
        if (summary !== fullObjective) {
            objectiveEl.setAttribute('data-ui-tip', fullObjective);
            bindUiHoverTip(objectiveEl);
        } else {
            objectiveEl.removeAttribute('data-ui-tip');
        }
    }
    renderGoalMeta(goal, sid);
    if (toggle) {
        const canToggle = status === 'active' || status === 'paused';
        const isPaused = status === 'paused';
        const toggleLabel = isPaused ? '开始 Goal' : '暂停 Goal';
        const translatedToggleLabel = typeof translateUiString === 'function' ? translateUiString(toggleLabel) : toggleLabel;
        toggle.hidden = !canToggle;
        toggle.setAttribute('aria-label', translatedToggleLabel);
        toggle.setAttribute('data-ui-tip', translatedToggleLabel);
        const playIcon = toggle.querySelector('.chat-goal-icon-play');
        const pauseIcon = toggle.querySelector('.chat-goal-icon-pause');
        if (playIcon) playIcon.toggleAttribute('hidden', !isPaused);
        if (pauseIcon) pauseIcon.toggleAttribute('hidden', isPaused);
    }
    const isCompleted = status === 'completed';
    if (edit) edit.hidden = isCompleted;
    if (remove) remove.hidden = isCompleted;
    if (review) review.hidden = !isCompleted;
    syncGoalTodoPanelVisibility();
}

async function refreshGoalCard() {
    const sid = currentSessionId;
    if (!sid) { renderGoalCard(null, ''); return; }
    if (goalRefreshInFlightBySession.has(sid)) return goalRefreshInFlightBySession.get(sid);
    const task = (async function () {
        try {
            const r = await fetch('/sessions/' + encodeURIComponent(sid) + '/goal');
            if (!r.ok) return;
            const data = await r.json();
            setGoalStateForSession(sid, data.goal || null);
        } catch (e) { /* the session-scoped cache or hidden state remains authoritative */ }
        finally { goalRefreshInFlightBySession.delete(sid); }
    })();
    goalRefreshInFlightBySession.set(sid, task);
    return task;
}

setInterval(function () {
    if (document.visibilityState === 'hidden' || isGoalEditModalOpen() || isGoalReviewModalOpen()) return;
    const sid = String(currentSessionId || '');
    const goal = sid ? goalStateBySession.get(sid) : null;
    if (goal) renderGoalMeta(goal, sid);
}, 1000);

setInterval(function () {
    if (document.visibilityState === 'hidden' || !currentSessionId || isGoalEditModalOpen() || isGoalReviewModalOpen()) return;
    void refreshGoalCard();
}, 5000);

setInterval(function () {
    if (document.visibilityState === 'hidden' || isGoalEditModalOpen() || isGoalReviewModalOpen()) return;
    const sid = String(currentSessionId || '');
    const goal = sid ? goalStateBySession.get(sid) : null;
    if (!goal || String(goal.status || '') !== 'active') return;
    if (typeof getSessionRunState === 'function' && getSessionRunState(sid)) return;
    void recoverActiveGoalStream(sid);
}, 2000);

async function controlCurrentGoal(action, payloadOverrides) {
    const sid = currentSessionId;
    if (!sid) return false;
    try {
        const payload = Object.assign({}, payloadOverrides || {});
        if (action === 'resume' && renderedGoalState
            && renderedGoalState.token_budget != null
            && Number(renderedGoalState.remaining_tokens || 0) <= 0) {
            const promptText = typeof translateUiString === 'function'
                ? translateUiString('请输入要增加的 Token 预算')
                : '请输入要增加的 Token 预算';
            const raw = window.prompt(promptText, '10000');
            if (raw == null) return false;
            const additional = Number(raw);
            if (!Number.isInteger(additional) || additional <= 0) {
                const message = typeof translateUiString === 'function'
                    ? translateUiString('预算必须是大于 0 的整数。')
                    : '预算必须是大于 0 的整数。';
                if (typeof showUiAlert === 'function') showUiAlert({ title: 'Goal', message: message, variant: 'error' });
                return false;
            }
            payload.additional_budget = additional;
        }
        const r = await fetch('/sessions/' + encodeURIComponent(sid) + '/goal/' + encodeURIComponent(action), {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload),
        });
        const data = await r.json();
        if (r.ok) setGoalStateForSession(sid, data.goal || null);
        if (!r.ok && typeof showUiAlert === 'function') {
            const title = typeof translateUiString === 'function' ? translateUiString('Goal 操作失败') : 'Goal 操作失败';
            showUiAlert({ title: title, message: String(data.error || 'Unknown error'), variant: 'error' });
        }
        if (action === 'resume' || (action === 'review' && String(payload.decision || '') === 'continue')) {
            void refreshSingleSessionRow(sid);
        }
        return r.ok;
    } catch (e) {
        if (typeof showUiAlert === 'function') {
            const title = typeof translateUiString === 'function' ? translateUiString('Goal 操作失败') : 'Goal 操作失败';
            showUiAlert({ title: title, message: String((e && e.message) || e), variant: 'error' });
        }
        return false;
    }
}

function toggleCurrentGoalState() {
    if (!renderedGoalState) return;
    const status = String(renderedGoalState.status || '');
    if (status === 'active') void controlCurrentGoal('pause');
    else if (status === 'paused') void controlCurrentGoal('resume');
}

function goalEditModalElements() {
    return {
        root: document.getElementById('goal-edit-modal-root'),
        input: document.getElementById('goal-edit-textarea'),
        count: document.getElementById('goal-edit-char-count'),
        save: document.getElementById('goal-edit-save'),
        cancel: document.getElementById('goal-edit-cancel'),
        close: document.getElementById('goal-edit-modal-close'),
    };
}

function isGoalEditModalOpen() {
    const root = document.getElementById('goal-edit-modal-root');
    return !!(root && root.classList.contains('is-open'));
}

function updateGoalEditModalState() {
    const elements = goalEditModalElements();
    if (!elements.root || !elements.input) return;
    const value = String(elements.input.value || '');
    const normalized = value.trim();
    const original = String(elements.root._goalOriginalObjective || '').trim();
    if (elements.count) elements.count.textContent = String(value.length) + ' / 12000';
    if (elements.save) {
        elements.save.disabled = !!elements.root._goalSaving
            || !normalized
            || normalized === original
            || value.length > 12000;
    }
}

function closeGoalEditModal(restoreFocus) {
    const elements = goalEditModalElements();
    if (!elements.root || !elements.root.classList.contains('is-open')) return;
    elements.root.classList.remove('is-open');
    elements.root.setAttribute('aria-hidden', 'true');
    elements.root._goalSaving = false;
    document.body.classList.remove('goal-editing');
    document.body.style.overflow = '';
    const returnFocus = elements.root._goalReturnFocus;
    elements.root._goalReturnFocus = null;
    if (restoreFocus !== false && returnFocus && typeof returnFocus.focus === 'function') {
        requestAnimationFrame(function () { returnFocus.focus(); });
    }
}

async function saveGoalEditModal() {
    const elements = goalEditModalElements();
    if (!elements.root || !elements.input || elements.root._goalSaving) return false;
    const objective = String(elements.input.value || '').trim();
    if (!objective || objective.length > 12000) return false;
    const sid = String(elements.root.dataset.sessionId || '');
    const goalId = String(elements.root.dataset.goalId || '');
    if (sid !== String(currentSessionId || '') || !renderedGoalState || String(renderedGoalState.id || '') !== goalId) {
        closeGoalEditModal(false);
        return false;
    }
    elements.root._goalSaving = true;
    updateGoalEditModalState();
    const saved = await controlCurrentGoal('edit', { objective: objective });
    elements.root._goalSaving = false;
    if (saved) closeGoalEditModal();
    else updateGoalEditModalState();
    return saved;
}

function ensureGoalEditModalBindings() {
    const elements = goalEditModalElements();
    if (!elements.root || elements.root._goalEditBound) return elements;
    elements.root._goalEditBound = true;
    if (elements.input) {
        elements.input.addEventListener('input', updateGoalEditModalState);
        elements.input.addEventListener('keydown', function (event) {
            if (event.key === 'Escape') {
                event.preventDefault();
                closeGoalEditModal();
            } else if (event.key === 'Enter' && (event.ctrlKey || event.metaKey)) {
                event.preventDefault();
                void saveGoalEditModal();
            }
        });
    }
    if (elements.save) elements.save.addEventListener('click', function () { void saveGoalEditModal(); });
    if (elements.cancel) elements.cancel.addEventListener('click', function () { closeGoalEditModal(); });
    if (elements.close) elements.close.addEventListener('click', function () { closeGoalEditModal(); });
    elements.root.addEventListener('mousedown', function (event) {
        if (event.target === elements.root) closeGoalEditModal();
    });
    return elements;
}

function editCurrentGoal() {
    if (!renderedGoalState) return;
    const elements = ensureGoalEditModalBindings();
    if (!elements.root || !elements.input) return;
    const currentObjective = String(renderedGoalState.objective || '');
    elements.root.dataset.sessionId = String(currentSessionId || '');
    elements.root.dataset.goalId = String(renderedGoalState.id || '');
    elements.root._goalOriginalObjective = currentObjective;
    elements.root._goalReturnFocus = document.activeElement;
    elements.root._goalSaving = false;
    elements.input.value = currentObjective;
    elements.root.classList.add('is-open');
    elements.root.setAttribute('aria-hidden', 'false');
    document.body.classList.add('goal-editing');
    document.body.style.overflow = 'hidden';
    updateGoalEditModalState();
    requestAnimationFrame(function () {
        elements.input.focus();
        elements.input.setSelectionRange(0, 0);
        elements.input.scrollTop = 0;
    });
}

async function deleteCurrentGoal() {
    if (!renderedGoalState) return;
    const translate = function (value) {
        return typeof translateUiString === 'function' ? translateUiString(value) : value;
    };
    const confirmed = typeof openUiModal === 'function'
        ? await openUiModal({
            title: translate('确认删除 Goal'),
            message: translate('删除后当前 Goal 将从此会话中移除。此操作不会删除历史审计事件。'),
            confirmText: translate('确认删除'),
            cancelText: translate('取消'),
            danger: true,
        })
        : window.confirm(translate('确认删除 Goal'));
    if (!confirmed) return;
    await controlCurrentGoal('delete');
}

function goalReviewModalElements() {
    return {
        root: document.getElementById('goal-review-modal-root'),
        objective: document.getElementById('goal-review-objective'),
        judge: document.getElementById('goal-review-judge-result'),
        status: document.getElementById('goal-review-modal-status'),
        approve: document.getElementById('goal-review-approve'),
        save: document.getElementById('goal-review-save'),
        continueGoal: document.getElementById('goal-review-continue'),
        close: document.getElementById('goal-review-modal-close'),
    };
}

function isGoalReviewModalOpen() {
    const root = document.getElementById('goal-review-modal-root');
    return !!(root && root.classList.contains('is-open'));
}

function setGoalReviewModalStatus(message, kind) {
    const elements = goalReviewModalElements();
    if (!elements.status) return;
    elements.status.textContent = String(message || '');
    elements.status.classList.toggle('is-error', kind === 'error');
    elements.status.classList.toggle('is-success', kind === 'success');
}

function setGoalReviewModalBusy(busy) {
    const elements = goalReviewModalElements();
    if (!elements.root) return;
    elements.root._goalReviewSaving = !!busy;
    [elements.approve, elements.save, elements.continueGoal].forEach(function (button) {
        if (button) button.disabled = !!busy;
    });
    if (elements.objective) elements.objective.disabled = !!busy;
    if (elements.judge) elements.judge.disabled = !!busy;
}

function closeGoalReviewModal(restoreFocus) {
    const elements = goalReviewModalElements();
    if (!elements.root || !elements.root.classList.contains('is-open')) return;
    elements.root.classList.remove('is-open');
    elements.root.setAttribute('aria-hidden', 'true');
    setGoalReviewModalBusy(false);
    document.body.classList.remove('goal-reviewing');
    document.body.style.overflow = '';
    const returnFocus = elements.root._goalReturnFocus;
    elements.root._goalReturnFocus = null;
    if (restoreFocus !== false && returnFocus && typeof returnFocus.focus === 'function') {
        requestAnimationFrame(function () { returnFocus.focus(); });
    }
}

async function submitGoalReview(decision) {
    const elements = goalReviewModalElements();
    if (!elements.root || elements.root._goalReviewSaving) return false;
    const objective = String((elements.objective && elements.objective.value) || '').trim();
    const judgeResult = String((elements.judge && elements.judge.value) || '').trim();
    if (!objective) {
        setGoalReviewModalStatus(
            typeof translateUiString === 'function' ? translateUiString('Goal 描述不能为空。') : 'Goal 描述不能为空。',
            'error'
        );
        return false;
    }
    const sid = String(elements.root.dataset.sessionId || '');
    const goalId = String(elements.root.dataset.goalId || '');
    if (
        sid !== String(currentSessionId || '')
        || !renderedGoalState
        || String(renderedGoalState.id || '') !== goalId
        || String(renderedGoalState.status || '') !== 'completed'
    ) {
        closeGoalReviewModal(false);
        return false;
    }
    const payload = {
        decision: String(decision || ''),
        objective: objective,
        judge_result: judgeResult
    };
    if (
        decision === 'continue'
        && renderedGoalState.token_budget != null
        && Number(renderedGoalState.remaining_tokens || 0) <= 0
    ) {
        const promptText = typeof translateUiString === 'function'
            ? translateUiString('请输入要增加的 Token 预算')
            : '请输入要增加的 Token 预算';
        const raw = window.prompt(promptText, '10000');
        if (raw == null) return false;
        const additional = Number(raw);
        if (!Number.isInteger(additional) || additional <= 0) {
            setGoalReviewModalStatus(
                typeof translateUiString === 'function'
                    ? translateUiString('预算必须是大于 0 的整数。')
                    : '预算必须是大于 0 的整数。',
                'error'
            );
            return false;
        }
        payload.additional_budget = additional;
    }

    setGoalReviewModalBusy(true);
    setGoalReviewModalStatus(
        typeof translateUiString === 'function' ? translateUiString('正在保存审核结果…') : '正在保存审核结果…',
        ''
    );
    const saved = await controlCurrentGoal('review', payload);
    setGoalReviewModalBusy(false);
    if (!saved) {
        setGoalReviewModalStatus(
            typeof translateUiString === 'function' ? translateUiString('审核结果保存失败。') : '审核结果保存失败。',
            'error'
        );
        return false;
    }
    if (decision === 'save') {
        elements.root._goalOriginalObjective = objective;
        elements.root._goalOriginalJudgeResult = judgeResult;
        setGoalReviewModalStatus(
            typeof translateUiString === 'function'
                ? translateUiString('修改已保存，可继续编辑或选择审核结果。')
                : '修改已保存，可继续编辑或选择审核结果。',
            'success'
        );
        return true;
    }
    closeGoalReviewModal();
    if (decision === 'continue') {
        const activeSid = String(currentSessionId || '');
        window.setTimeout(function () {
            if (activeSid === String(currentSessionId || '')) void recoverActiveGoalStream(activeSid);
        }, 150);
    }
    return true;
}

function ensureGoalReviewModalBindings() {
    const elements = goalReviewModalElements();
    if (!elements.root || elements.root._goalReviewBound) return elements;
    elements.root._goalReviewBound = true;
    if (elements.close) elements.close.addEventListener('click', function () { closeGoalReviewModal(); });
    if (elements.approve) elements.approve.addEventListener('click', function () { void submitGoalReview('approve'); });
    if (elements.save) elements.save.addEventListener('click', function () { void submitGoalReview('save'); });
    if (elements.continueGoal) elements.continueGoal.addEventListener('click', function () { void submitGoalReview('continue'); });
    elements.root.addEventListener('mousedown', function (event) {
        if (event.target === elements.root) closeGoalReviewModal();
    });
    elements.root.addEventListener('keydown', function (event) {
        if (event.key === 'Escape') {
            event.preventDefault();
            closeGoalReviewModal();
        }
    });
    return elements;
}

function openGoalReviewModal() {
    if (!renderedGoalState || String(renderedGoalState.status || '') !== 'completed') return;
    const elements = ensureGoalReviewModalBindings();
    if (!elements.root || !elements.objective || !elements.judge) return;
    const objective = String(renderedGoalState.objective || '');
    const judgeResult = String(
        renderedGoalState.review_judge_result != null
            ? renderedGoalState.review_judge_result
            : (renderedGoalState.last_judge_reason || '')
    );
    elements.root.dataset.sessionId = String(currentSessionId || '');
    elements.root.dataset.goalId = String(renderedGoalState.id || '');
    elements.root._goalOriginalObjective = objective;
    elements.root._goalOriginalJudgeResult = judgeResult;
    elements.root._goalReturnFocus = document.activeElement;
    elements.objective.value = objective;
    elements.judge.value = judgeResult;
    elements.root.classList.add('is-open');
    elements.root.setAttribute('aria-hidden', 'false');
    document.body.classList.add('goal-reviewing');
    document.body.style.overflow = 'hidden';
    setGoalReviewModalBusy(false);
    const reviewStatus = String(renderedGoalState.review_status || '');
    setGoalReviewModalStatus(
        reviewStatus === 'approved'
            ? (typeof translateUiString === 'function' ? translateUiString('该结果已审核通过。') : '该结果已审核通过。')
            : '',
        reviewStatus === 'approved' ? 'success' : ''
    );
    requestAnimationFrame(function () {
        elements.objective.focus();
        elements.objective.setSelectionRange(0, 0);
        elements.objective.scrollTop = 0;
    });
}

document.addEventListener('myagent:language-change', function () {
    renderGoalForCurrentSession();
});

if (typeof globalThis !== 'undefined') {
    globalThis.toggleCurrentGoalState = toggleCurrentGoalState;
    globalThis.editCurrentGoal = editCurrentGoal;
    globalThis.deleteCurrentGoal = deleteCurrentGoal;
    globalThis.openGoalReviewModal = openGoalReviewModal;
}

function setTodoPlanForSession(sessionId, snapshot) {
    if (!sessionId || !snapshot || typeof snapshot !== 'object') return;
    applyTodoPlanToStore(sessionId, snapshot);
}

function startTodoForSessionLoad(sessionId) {
    if (!sessionId || sessionId !== currentSessionId) return;
    void refreshTodoPlanPanel();
}

function renderLoadedTodoPlanForSession(sessionId, snapshot, alreadyStarted) {
    if (!sessionId || sessionId !== currentSessionId) return;
    if (snapshot && typeof snapshot === 'object') {
        setTodoPlanForSession(sessionId, snapshot);
        renderTodoPlanForCurrentSession();
        return;
    }
    if (alreadyStarted) {
        renderTodoPlanForCurrentSession();
        return;
    }
    void refreshTodoPlanPanel();
}

const TODO_PLAN_CACHE_TTL_MS = 2000;

async function refreshTodoPlanPanel() {
    const sid = currentSessionId;
    const epoch = ++todoRefreshEpoch;
    if (!sid) {
        clearTodoPlanState(sid);
        hideTodoPlanPanel();
        const statsEl = document.getElementById('chat-todo-plan-stats');
        const listEl = document.getElementById('chat-todo-plan-list');
        if (statsEl) statsEl.textContent = '';
        if (listEl) listEl.textContent = '';
        notifyPanelContentChanged();
        return;
    }
    const cached = selectTodoPlan(sid);
    if (cached && cached.updatedAt && (Date.now() - cached.updatedAt) < TODO_PLAN_CACHE_TTL_MS) {
        renderTodoPlanSnapshot(cached);
        return;
    }
    try {
        const r = await fetch('/sessions/' + encodeURIComponent(sid) + '/todo_plan');
        if (epoch !== todoRefreshEpoch || sid !== currentSessionId) return;
        if (!r.ok) {
            hideTodoPlanPanel();
            return;
        }
        const j = await r.json();
        if (epoch !== todoRefreshEpoch || sid !== currentSessionId) return;
        applyTodoPlanFromPayload(j);
    } catch (e) {
        if (epoch !== todoRefreshEpoch || sid !== currentSessionId) return;
        hideTodoPlanPanel();
    }
}
`,jt=`function removeMessagesFromNode(startWrap) {
    const stream = getVisibleChatStream() || chatContainer;
    if (!stream) return;
    const kids = Array.from(stream.children);
    const i = kids.indexOf(startWrap);
    if (i < 0) return;
    for (let j = kids.length - 1; j >= i; j--) kids[j].remove();
    syncDisconnectedProcessGroups();
}

function applyClientHistoryTruncate(sessionId, beforeIndex, anchor) {
    const sid = String(sessionId || '');
    const before = Math.max(0, Number(beforeIndex) || 0);
    if (!sid) return;
    if (typeof truncateMessageStateForSession === 'function') {
        truncateMessageStateForSession(sid, before);
    }
    if (typeof uiEventCountCache !== 'undefined') {
        uiEventCountCache.updateFromServer(sid, before);
    }
    if (typeof truncateTocTurnsForSession === 'function') {
        truncateTocTurnsForSession(sid, before);
    }
    if (typeof contextStore !== 'undefined') {
        contextStore.clearTokens(sid);
        contextStore.clearTodo(sid);
    }
    if (sid !== currentSessionId) return;
    if (anchor) removeMessagesFromNode(anchor);
    syncDisconnectedProcessGroups();
    rebuildToc({ localOnly: true });
    scheduleContextTokensAfterPaint(sid);
    if (typeof refreshTodoPlanPanel === 'function') void refreshTodoPlanPanel();
}

async function historyOperationJson(url, options, timeoutMs) {
    options = options || {};
    var ms = Number(timeoutMs) > 0 ? Number(timeoutMs) : 45000;
    var controller = (typeof AbortController !== 'undefined') ? new AbortController() : null;
    var timer = null;
    var requestOptions = Object.assign({}, options);
    if (controller && !requestOptions.signal) {
        requestOptions.signal = controller.signal;
        timer = setTimeout(function () { controller.abort(); }, ms);
    }
    try {
        var r = await fetch(url, requestOptions);
        var j = await r.json().catch(function () { return {}; });
        if (!j || typeof j !== 'object') j = {};
        j.ok = !!r.ok && j.ok !== false;
        if (!j.error && !r.ok) j.error = 'http_' + r.status;
        return j;
    } catch (e) {
        var isAbort = e && (e.name === 'AbortError' || String(e.message || e).indexOf('aborted') >= 0);
        return { ok: false, error: isAbort ? 'request_timeout' : ((e && e.message) || String(e)) };
    } finally {
        if (timer) clearTimeout(timer);
    }
}

async function truncateSessionOnServer(beforeIndex, options) {
    options = options || {};
    const sid = options.sessionId || currentSessionId;
    if (!sid) return { ok: false, error: 'no_session' };
    if (!Number.isFinite(Number(beforeIndex)) || Number(beforeIndex) < 0) {
        return { ok: false, error: 'invalid_before_index' };
    }
    var url = '/sessions/' + encodeURIComponent(sid) + '/truncate'
        + '?before_index=' + encodeURIComponent(String(beforeIndex))
        + '&backup=' + (options.backup ? '1' : '0');
    if (Number.isFinite(Number(options.beforeSeq)) && Number(options.beforeSeq) > 0) {
        url += '&before_seq=' + encodeURIComponent(String(Math.floor(Number(options.beforeSeq))));
    }
    return historyOperationJson(url, { method: 'POST' }, options.timeoutMs || 45000);
}

function describeServerSyncFailure(res, fallback) {
    var base = fallback || '无法同步服务器。';
    var err = res && res.error ? String(res.error).trim() : '';
    if (!err) return base;
    var friendly = err;
    if (err === 'no_session') friendly = '当前没有选中的会话。';
    else if (err === 'invalid_before_index' || err === 'invalid before_index') friendly = '消息定位索引无效，可能需要刷新当前会话。';
    else if (err === 'refuse empty truncation') friendly = '服务端拒绝清空整个会话。';
    else if (err === 'truncation failed') friendly = '服务端裁剪历史失败，可能是历史索引已变化或会话文件暂时不一致。';
    return base + '\\n原因：' + friendly;
}

function hasPreviousUserMessageBefore(wrap) {
    var node = wrap ? wrap.previousElementSibling : null;
    while (node) {
        if (node.classList && node.classList.contains('msg-wrap--user')) return true;
        node = node.previousElementSibling;
    }
    return false;
}

let activeInlineRewriteWrap = null;

function restoreUserMessageBubble(wrap, rawText) {
    if (!wrap) return;
    const div = wrap.querySelector('.message.user');
    if (!div) return;
    wrap.classList.remove('is-inline-rewriting', 'user-msg-expanded', 'has-turn-process');
    div.className = 'message user';
    div.textContent = '';
    messageRawMarkdown.set(wrap, String(rawText || ''));
    renderUserMessageContent(wrap, div, String(rawText || ''), linkifyAssistantTextNodes);
}

function closeInlineRewriteEditor(wrap, rawText) {
    restoreUserMessageBubble(wrap, rawText);
    if (activeInlineRewriteWrap === wrap) activeInlineRewriteWrap = null;
}

function autoResizeInlineRewriteTextarea(textarea) {
    if (!textarea) return;
    textarea.style.height = 'auto';
    textarea.style.height = Math.min(Math.max(textarea.scrollHeight, 84), 260) + 'px';
}

function openInlineRewriteEditor(wrap, rawText, beforeIndex) {
    if (!wrap) return;
    if (activeInlineRewriteWrap && activeInlineRewriteWrap !== wrap) {
        const prevRaw = messageRawMarkdown.get(activeInlineRewriteWrap) || '';
        closeInlineRewriteEditor(activeInlineRewriteWrap, prevRaw);
    }
    const div = wrap.querySelector('.message.user');
    if (!div) return;
    activeInlineRewriteWrap = wrap;
    wrap.classList.add('is-inline-rewriting');
    wrap.classList.remove('user-msg-expanded', 'has-turn-process');
    div.className = 'message user user-inline-rewrite';
    div.textContent = '';

    const editor = document.createElement('div');
    editor.className = 'user-inline-rewrite-box';
    const textarea = document.createElement('textarea');
    textarea.className = 'user-inline-rewrite-input';
    textarea.value = String(rawText || '');
    textarea.rows = 3;
    const actions = document.createElement('div');
    actions.className = 'user-inline-rewrite-actions';
    const cancelBtn = document.createElement('button');
    cancelBtn.type = 'button';
    cancelBtn.className = 'user-inline-rewrite-btn user-inline-rewrite-btn--ghost';
    cancelBtn.textContent = '取消';
    const confirmBtn = document.createElement('button');
    confirmBtn.type = 'button';
    confirmBtn.className = 'user-inline-rewrite-btn user-inline-rewrite-btn--primary';
    confirmBtn.textContent = '确认';
    actions.appendChild(cancelBtn);
    actions.appendChild(confirmBtn);
    editor.appendChild(textarea);
    editor.appendChild(actions);
    div.appendChild(editor);

    function cancel() {
        closeInlineRewriteEditor(wrap, rawText);
    }

    async function confirm() {
        const nextText = String(textarea.value || '');
        if (!nextText.trim()) {
            showUiAlert({
                title: '无法改写',
                message: '改写内容不能为空。',
                variant: 'warning',
            });
            return;
        }
        if (!currentSessionId || !Number.isFinite(Number(beforeIndex))) return;
        confirmBtn.disabled = true;
        cancelBtn.disabled = true;
        pendingRewriteTruncate = {
            sessionId: currentSessionId,
            before: Number(beforeIndex),
            beforeSeq: Number.isFinite(Number(wrap.dataset.runtimeSeq)) ? Math.floor(Number(wrap.dataset.runtimeSeq)) : null,
            prevInput: ''
        };
        try {
            await sendMessage({
                message: nextText,
                sessionId: currentSessionId,
                preserveInput: true,
                fromInlineRewrite: true,
            });
        } finally {
            if (wrap.isConnected) {
                confirmBtn.disabled = false;
                cancelBtn.disabled = false;
            }
        }
    }

    textarea.addEventListener('input', function () {
        autoResizeInlineRewriteTextarea(textarea);
    });
    textarea.addEventListener('keydown', function (e) {
        if (e.key === 'Escape') {
            e.preventDefault();
            cancel();
            return;
        }
        if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) {
            e.preventDefault();
            void confirm();
        }
    });
    cancelBtn.addEventListener('click', function (e) {
        e.preventDefault();
        cancel();
    });
    confirmBtn.addEventListener('click', function (e) {
        e.preventDefault();
        void confirm();
    });
    autoResizeInlineRewriteTextarea(textarea);
    textarea.focus();
    try {
        textarea.setSelectionRange(textarea.value.length, textarea.value.length);
    } catch (e) { /* ignore */ }
}

async function branchSessionOnServer(beforeIndex, sessionId, afterSeq) {
    const sid = sessionId || currentSessionId;
    if (!sid) return { ok: false, error: 'no_session' };
    var url = '/sessions/' + encodeURIComponent(sid) + '/branch'
        + '?before_index=' + encodeURIComponent(String(beforeIndex));
    if (Number.isFinite(Number(afterSeq)) && Number(afterSeq) > 0) {
        url += '&after_seq=' + encodeURIComponent(String(Math.floor(Number(afterSeq))));
    }
    return historyOperationJson(url, { method: 'POST' }, 60000);
}

function normalizeBranchFinalText(text) {
    return String(text || '').replace(/\\s+/g, ' ').trim();
}

function branchFinalTextMatches(eventContent, expectedText) {
    var a = normalizeBranchFinalText(eventContent);
    var b = normalizeBranchFinalText(expectedText);
    if (!a || !b) return false;
    if (a === b) return true;
    if (a.length > 80 && b.length > 80) {
        return a.indexOf(b.slice(0, 80)) >= 0 || b.indexOf(a.slice(0, 80)) >= 0;
    }
    return false;
}

async function waitForBranchFinalPersisted(sessionId, beforeIndex, expectedText) {
    if (!sessionId || !Number.isFinite(beforeIndex) || beforeIndex <= 0) {
        return { ready: true, beforeIndex: beforeIndex };
    }
    var deadline = Date.now() + 2600;
    while (Date.now() < deadline) {
        try {
            var url = '/sessions/' + encodeURIComponent(sessionId)
                + '/messages?limit=1&before_index=' + encodeURIComponent(String(beforeIndex));
            var r = await fetch(url);
            var j = await r.json().catch(function () { return null; });
            var events = Array.isArray(j) ? j : (j && Array.isArray(j.events) ? j.events : []);
            if (events.length && events[events.length - 1] && events[events.length - 1].type === 'final') {
                return { ready: true, beforeIndex: beforeIndex };
            }
            var recentUrl = '/sessions/' + encodeURIComponent(sessionId) + '/messages?limit=80';
            var rr = await fetch(recentUrl);
            var jj = await rr.json().catch(function () { return null; });
            var recent = Array.isArray(jj) ? jj : (jj && Array.isArray(jj.events) ? jj.events : []);
            var base = jj && typeof jj.range_start === 'number' ? jj.range_start : 0;
            for (var i = recent.length - 1; i >= 0; i -= 1) {
                var ev = recent[i];
                if (!ev || ev.type !== 'final') continue;
                if (branchFinalTextMatches(ev.content, expectedText)) {
                    return { ready: true, beforeIndex: base + i + 1 };
                }
            }
        } catch (e) { /* retry */ }
        await new Promise(function (resolve) { setTimeout(resolve, 180); });
    }
    return { ready: false, beforeIndex: beforeIndex };
}

function copyMessageText(wrap) {
    const msg = wrap && wrap.querySelector('.message');
    const plain = msg ? (msg.innerText || '') : '';
    const raw = messageRawMarkdown.get(wrap);
    const toCopy = raw !== undefined ? String(raw) : plain;
    const done = function () {
        showCopyFeedback();
        return true;
    };
    if (navigator.clipboard && navigator.clipboard.writeText) {
        return navigator.clipboard.writeText(toCopy).then(done).catch(function () {
            try {
                const ta = document.createElement('textarea');
                ta.value = toCopy;
                ta.setAttribute('readonly', 'readonly');
                ta.style.position = 'fixed';
                ta.style.opacity = '0';
                document.body.appendChild(ta);
                ta.select();
                document.execCommand('copy');
                document.body.removeChild(ta);
                return done();
            } catch (e) {
                throw e;
            }
        });
    }
    return Promise.reject(new Error('当前浏览器不支持复制文本'));
}

function buildFinalExportFilename(extension) {
    var sess = typeof selectCurrentSession === 'function' ? selectCurrentSession() : null;
    var nameEl = currentSessionId
        ? document.querySelector('.session-name[data-id="' + currentSessionId + '"]')
        : null;
    var rawName = sess && sess.name != null
        ? String(sess.name)
        : (nameEl ? String(nameEl.getAttribute('data-original') || nameEl.textContent || '') : '');
    var safeName = (rawName.trim() || 'Session')
        .replace(/[<>:"/\\\\|?*\\u0000-\\u001F]/g, '_')
        .replace(/[.\\s]+$/g, '')
        .slice(0, 100) || 'Session';
    var timestamp = new Date().toISOString().replace(/[:.]/g, '-');
    return safeName + '-' + timestamp + '.' + String(extension || '').replace(/^\\./, '');
}

function saveMessageAsMarkdown(wrap) {
    var msg = wrap && wrap.querySelector('.message');
    if (!msg) throw new Error('找不到可导出的 Final 内容');
    var raw = messageRawMarkdown.get(wrap);
    var markdown = raw !== undefined ? String(raw) : String(msg.innerText || '');
    var filename = buildFinalExportFilename('md');
    triggerDownloadBlob(new Blob([markdown], { type: 'text/markdown;charset=utf-8' }), filename);
    return true;
}

function waitForImageExportImages(target) {
    var images = target ? Array.prototype.slice.call(target.querySelectorAll('img')) : [];
    return Promise.all(images.map(function (img) {
        if (!img.complete) {
            return new Promise(function (resolve) {
                img.addEventListener('load', resolve, { once: true });
                img.addEventListener('error', resolve, { once: true });
            });
        }
        return img.decode ? img.decode().catch(function () {}) : Promise.resolve();
    }));
}

function imageExportCanvasToBlob(canvas) {
    return new Promise(function (resolve, reject) {
        try {
            canvas.toBlob(function (blob) {
                if (blob) resolve(blob);
                else reject(new Error('Final 卡片图片保存失败'));
            }, 'image/png');
        } catch (error) {
            reject(error);
        }
    });
}

function sanitizeImageExportDocument(clonedDocument, exportId) {
    var clone = clonedDocument.querySelector('[data-image-export-id="' + exportId + '"]');
    if (!clone) return;
    clone.querySelectorAll('img, svg, video, iframe, object, embed, canvas').forEach(function (node) {
        node.remove();
    });
    [clone].concat(Array.prototype.slice.call(clone.querySelectorAll('*'))).forEach(function (node) {
        node.style.setProperty('background-image', 'none', 'important');
        node.style.setProperty('border-image', 'none', 'important');
        node.style.setProperty('list-style-image', 'none', 'important');
        node.style.setProperty('mask-image', 'none', 'important');
        node.style.setProperty('-webkit-mask-image', 'none', 'important');
    });
    var safeStyle = clonedDocument.createElement('style');
    safeStyle.textContent = '[data-image-export-id="' + exportId + '"],'
        + '[data-image-export-id="' + exportId + '"] *,'
        + '[data-image-export-id="' + exportId + '"]::before,'
        + '[data-image-export-id="' + exportId + '"]::after,'
        + '[data-image-export-id="' + exportId + '"] *::before,'
        + '[data-image-export-id="' + exportId + '"] *::after'
        + '{background-image:none!important;border-image:none!important;'
        + 'list-style-image:none!important;mask-image:none!important;'
        + '-webkit-mask-image:none!important;}';
    clonedDocument.head.appendChild(safeStyle);
}

async function saveMessageAsImage(wrap) {
    var target = wrap && wrap.querySelector('.message');
    if (!target) throw new Error('找不到可保存的 Final 卡片');
    await waitForImageExportImages(target);
    await new Promise(function (resolve) { requestAnimationFrame(resolve); });

    var rect = target.getBoundingClientRect();
    var width = Math.max(1, Math.ceil(target.scrollWidth || rect.width));
    var height = Math.max(1, Math.ceil(target.scrollHeight || rect.height));
    var targetStyle = getComputedStyle(target);
    var background = targetStyle.backgroundColor;
    if (!background || background === 'rgba(0, 0, 0, 0)') {
        background = document.documentElement.classList.contains('theme-light') ? '#ffffff' : '#1e1e2e';
    }
    if (typeof globalThis.loadMyAgentHtml2Canvas !== 'function') {
        throw new Error('当前版本未加载图片导出组件');
    }
    var html2canvas = await globalThis.loadMyAgentHtml2Canvas();
    var scale = Math.min(2, 16384 / width, 16384 / height, Math.sqrt(100000000 / (width * height)));
    var exportId = 'final-' + Date.now() + '-' + Math.random().toString(36).slice(2);
    target.setAttribute('data-image-export-id', exportId);
    var baseOptions = {
        backgroundColor: background,
        scale: scale,
        width: width,
        height: height,
        useCORS: true,
        allowTaint: false,
        imageTimeout: 12000,
        logging: false,
        removeContainer: true,
        ignoreElements: function (node) {
            return !!(node.matches && node.matches('button, .mermaid-download-btn, .mermaid-zoom-btn'));
        }
    };
    var png;
    try {
        try {
            var canvas = await html2canvas(target, baseOptions);
            png = await imageExportCanvasToBlob(canvas);
        } catch (firstError) {
            var fallbackOptions = Object.assign({}, baseOptions, {
                useCORS: false,
                imageTimeout: 0,
                onclone: function (clonedDocument) {
                    sanitizeImageExportDocument(clonedDocument, exportId);
                }
            });
            canvas = await html2canvas(target, fallbackOptions);
            png = await imageExportCanvasToBlob(canvas);
        }
    } finally {
        target.removeAttribute('data-image-export-id');
    }
    var downloadUrl = URL.createObjectURL(png);
    var link = document.createElement('a');
    link.href = downloadUrl;
    link.download = buildFinalExportFilename('png');
    link.click();
    setTimeout(function () { URL.revokeObjectURL(downloadUrl); }, 1000);
}

function closeAllMessageCopyPopovers() {
    document.querySelectorAll('.msg-copy-popover.is-open').forEach(function (popover) {
        popover.classList.remove('is-open');
        var wrap = popover.closest('.msg-wrap');
        var button = wrap && wrap.querySelector('.msg-tb[data-act="copy"]');
        if (button) button.setAttribute('aria-expanded', 'false');
    });
}

(function bindMessageCopyPopoverCloserOnce() {
    if (window.__myAgentMessageCopyPopoverCloser) return;
    window.__myAgentMessageCopyPopoverCloser = true;
    document.addEventListener('click', closeAllMessageCopyPopovers);
})();

function toggleMessageCopyPopover(wrap) {
    var popover = wrap && wrap.querySelector('.msg-copy-popover');
    var button = wrap && wrap.querySelector('.msg-tb[data-act="copy"]');
    if (!popover) return;
    var open = !popover.classList.contains('is-open');
    closeAllMessageCopyPopovers();
    popover.classList.toggle('is-open', open);
    if (button) button.setAttribute('aria-expanded', open ? 'true' : 'false');
}

function applyMessageCopyOption(wrap, role, option) {
    closeAllMessageCopyPopovers();
    var button = wrap.querySelector('.msg-tb[data-act="copy"]');
    if (button) button.setAttribute('aria-expanded', 'false');
    var tasks = [];
    if (role === 'assistant' && option === 'text') tasks.push(Promise.resolve().then(function () {
        saveMessageAsMarkdown(wrap);
        showOpenFileFeedback('Markdown 已导出');
        return true;
    }));
    if (role === 'assistant' && option === 'image') tasks.push(saveMessageAsImage(wrap).then(function () {
        showOpenFileFeedback('图片已保存');
        return true;
    }));
    if (!tasks.length) return;
    Promise.all(tasks).catch(function (err) {
        showUiAlert({ title: '操作失败', message: String((err && err.message) || err || '无法完成导出'), variant: 'error' });
    });
}

function onMessageToolbarClick(wrap, role, act) {
    const msg = wrap.querySelector('.message');
    const plain = msg ? (msg.innerText || '') : '';
    const tf = wrap.dataset.truncateFrom;
    const eiRaw = wrap.dataset.eventIndex;
    const runtimeSeqRaw = wrap.dataset.runtimeSeq;
    const truncateBeforeSeqRaw = wrap.dataset.truncateBeforeSeq;
    const eventIndex = eiRaw !== undefined && eiRaw !== '' ? parseInt(eiRaw, 10) : NaN;
    const runtimeSeq = runtimeSeqRaw !== undefined && runtimeSeqRaw !== '' ? parseInt(runtimeSeqRaw, 10) : NaN;
    const truncateBeforeSeq = truncateBeforeSeqRaw !== undefined && truncateBeforeSeqRaw !== '' ? parseInt(truncateBeforeSeqRaw, 10) : NaN;
    const truncateFrom = tf !== undefined && tf !== '' ? parseInt(tf, 10) : NaN;
    const before = role === 'user' ? eventIndex : truncateFrom;
    const beforeSeq = role === 'user' ? runtimeSeq : truncateBeforeSeq;
    if ((act === 'delete' || act === 'rewrite') && isSessionRunning(currentSessionId)) {
        showUiAlert({
            title: '生成中不可操作',
            message: '当前会话仍在生成。请等待完成或停止后再修改历史。',
            variant: 'warning',
        });
        return;
    }
    if (act === 'copy') {
        if (role === 'assistant') {
            toggleMessageCopyPopover(wrap);
        } else {
            copyMessageText(wrap).catch(function () { /* preserve the original silent copy behavior */ });
        }
        return;
    }
    if (act === 'delete') {
        if (!Number.isFinite(before) || before < 0 || (before === 0 && hasPreviousUserMessageBefore(wrap))) {
            if (Number.isFinite(before) && (before < 0 || (before === 0 && hasPreviousUserMessageBefore(wrap)))) {
                showUiAlert({
                    title: '无法删除该条',
                    message: '消息索引异常，已阻止清空整个会话。请刷新后再试。',
                    variant: 'error'
                });
                return;
            }
            removeMessagesFromNode(wrap);
            syncDisconnectedProcessGroups();
            rebuildToc();
            return;
        }
        openUiModal({
            title: '删除消息',
            subtitle: '将同步到服务器',
            message: '确定删除本条及之后的所有对话内容吗？',
            danger: true,
            confirmText: '删除',
            cancelText: '取消',
        }).then(function (ok) {
            if (!ok) return;
            truncateSessionOnServer(before, { beforeSeq: beforeSeq }).then(function (res) {
                if (!res || !res.ok) {
                    showUiAlert({
                        title: '同步失败',
                        message: describeServerSyncFailure(res, '删除未生效。'),
                        variant: 'error'
                    });
                    return;
                }
                applyClientHistoryTruncate(currentSessionId, before, wrap);
            });
        });
        return;
    }
    if (act === 'rewrite' && role === 'user') {
        const raw = messageRawMarkdown.get(wrap);
        const toFill = raw !== undefined ? String(raw) : plain;
        if (Number.isFinite(before) && before === 0 && hasPreviousUserMessageBefore(wrap)) {
            showUiAlert({
                title: '无法改写该条',
                message: '消息索引异常，已阻止从错误位置清空会话。请刷新后再试。',
                variant: 'error'
            });
            return;
        }
        if (!Number.isFinite(before)) {
            showUiAlert({
                title: '无法改写该条',
                message: '该消息尚未与服务器索引对齐，请刷新当前会话后再试。',
                variant: 'warning',
            });
            return;
        }
        openInlineRewriteEditor(wrap, toFill, before);
        return;
    }
    if (act === 'branch' && role === 'assistant') {
        if (wrap.dataset.branching === '1') return;
        const sourceSessionId = currentSessionId;
        const sourceSwitchEpoch = (typeof switchSessionEpoch === 'number') ? switchSessionEpoch : null;
        const eiRaw = wrap.dataset.eventIndex;
        const eventIdx = eiRaw !== undefined && eiRaw !== '' ? parseInt(eiRaw, 10) : NaN;
        if (!Number.isFinite(eventIdx) || eventIdx < 0) {
            showUiAlert({
                title: '无法分支',
                message: '该回答尚未与服务器同步，请刷新页面后重试。',
                variant: 'error',
            });
            return;
        }
        const branchBefore = eventIdx + 1;
        openUiModal({
            title: '创建分支会话',
            subtitle: '原会话不会被修改',
            message: '将在当前回答之后创建独立分支会话。分支点之前的内容与原会话相同，可在分支中继续提问且不影响原会话。',
            confirmText: '创建分支',
            cancelText: '取消',
        }).then(function (ok) {
            if (!ok) return;
            wrap.dataset.branching = '1';
            (async function () {
                var runtimeEventType = String(wrap.dataset.runtimeEventType || '');
                var branchAfterSeq = runtimeEventType && runtimeEventType !== 'message_assistant_final'
                    ? null
                    : runtimeSeq;
                var res = await branchSessionOnServer(branchBefore, sourceSessionId, branchAfterSeq);
                if (!res || !res.ok || !res.session_id) {
                    showUiAlert({
                        title: '创建失败',
                        message: describeServerSyncFailure(res, '创建分支未生效。'),
                        variant: 'error',
                    });
                    return;
                }
                if (res.session && typeof sessionStore !== 'undefined') {
                    sessionStore.upsert(res.session);
                    renderSessionListIfChanged(true);
                }
                if (typeof discardCachedSessionStream === 'function') discardCachedSessionStream(res.session_id);
                const sourceStillActive = currentSessionId === sourceSessionId
                    && (sourceSwitchEpoch == null || sourceSwitchEpoch === switchSessionEpoch);
                if (!sourceStillActive) {
                    setTimeout(function () { void loadSessions({ forceRender: true }); }, 0);
                    return;
                }
                await switchSession(res.session_id, { forceReload: true });
                setTimeout(function () { void loadSessions({ forceRender: true }); }, 0);
                delete wrap.dataset.branching;
            })().catch(function (err) {
                console.error('branch session failed:', err);
                showUiAlert({
                    title: '创建失败',
                    message: String((err && err.message) || err || 'unknown error'),
                    variant: 'error',
                });
            }).finally(function () {
                delete wrap.dataset.branching;
            });
        });
        return;
    }
}

function attachMessageToolbar(wrap, role) {
    const bar = document.createElement('div');
    bar.className = 'msg-toolbar';
    if (role === 'user') {
        var createdAt = wrap && wrap.dataset ? (wrap.dataset.createdAt || '') : '';
        if (createdAt) {
            var timeEl = document.createElement('span');
            timeEl.className = 'user-message-time';
            timeEl.setAttribute('data-created-at', createdAt);
            timeEl.title = createdAt;
            timeEl.textContent = formatUserMessageTimestamp(createdAt);
            bar.appendChild(timeEl);
        }
    }
    var copyButtonLabel = role === 'assistant' ? '导出' : '复制';
    var copyButtonTip = role === 'assistant' ? '导出选项' : '复制';
    var html = '<button type="button" class="msg-tb" data-act="copy" data-ui-tip="' + copyButtonTip + '" aria-haspopup="true" aria-expanded="false">' + copyButtonLabel + '</button>'
        + '<button type="button" class="msg-tb" data-act="delete" data-ui-tip="删除">删除</button>';
    if (role === 'assistant') {
        html += '<button type="button" class="msg-tb" data-act="branch" data-ui-tip="分支">分支</button>';
    }
    if (role === 'user') html += '<button type="button" class="msg-tb" data-act="rewrite" data-ui-tip="改写">改写</button>';
    bar.insertAdjacentHTML('beforeend', html);
    if (role === 'assistant') {
        var copyPopover = document.createElement('div');
        copyPopover.className = 'msg-copy-popover';
        copyPopover.setAttribute('role', 'menu');
        copyPopover.innerHTML = '<button type="button" class="msg-copy-menu-item" data-copy-option="image" role="menuitem">导出图片</button>'
            + '<button type="button" class="msg-copy-menu-item" data-copy-option="text" role="menuitem">导出文本</button>';
        bar.appendChild(copyPopover);
        bar.querySelectorAll('[data-copy-option]').forEach(function (item) {
            item.addEventListener('click', function (e) {
                e.preventDefault();
                e.stopPropagation();
                applyMessageCopyOption(wrap, role, item.getAttribute('data-copy-option'));
            });
        });
        copyPopover.addEventListener('click', function (e) {
            e.stopPropagation();
        });
    }
    bar.querySelectorAll('.msg-tb').forEach(bindUiHoverTip);
    bar.addEventListener('click', function (e) {
        var t = e.target;
        if (!t || t.tagName !== 'BUTTON' || !t.getAttribute) return;
        e.preventDefault();
        e.stopPropagation();
        var a = t.getAttribute('data-act');
        if (a) onMessageToolbarClick(wrap, role, a);
    });
    wrap.appendChild(bar);
}

function getFeedItemText(row) {
    const sc = row.querySelector('.feed-chunk-scroller');
    if (sc) return sc.textContent.trim();
    const ch = row.querySelector('.feed-chunk');
    return ch ? ch.textContent.trim() : '';
}

function getProcessBriefComparableText(row) {
    if (row && typeof row._processBriefRawText === 'string') {
        return normalizeProcessBriefComparableText(row._processBriefRawText);
    }
    return normalizeProcessBriefComparableText(getFeedItemText(row));
}

function extractToolNameFromLog(text) {
    if (!text) return '工具';
    const line = (text.split(/\\n/)[0] || text).trim();
    var m = line.match(/^([A-Za-z_][\\w-]*)\\s*\\(/);
    if (m) return m[1];
    m = line.match(/^([^\\s(]+)\\s*\\(/);
    if (m) return m[1];
    m = line.match(/^(\\S+?)(?:\\(|：)/);
    if (m) return m[1];
    return '工具';
}

function pushBriefLine(lines, line, type) {
    if (!line || !String(line).trim()) return;
    var t = String(line);
    var previous = lines.length ? lines[lines.length - 1] : null;
    var previousText = previous && typeof previous === 'object' ? previous.text : previous;
    if (previousText === t) return;
    lines.push(type ? { text: t, type: type } : t);
}

function refreshFeedChunkOverflow(chunk) {
    if (!chunk || !chunk.isConnected) return;
    const sc = chunk.querySelector('.feed-chunk-scroller');
    if (!sc) return;
    if (feedChunkInHiddenSubagentProcess(chunk)) return;
    if (chunk.classList.contains('expanded')) {
        chunk.classList.remove('is-overflowing');
        return;
    }
    function measure() {
        if (!chunk.isConnected || chunk.classList.contains('expanded')) return;
        var collapsedMax = feedChunkCollapsedMax(chunk);
        var contentH = sc.scrollHeight;
        if (contentH < 2) contentH = measureFeedChunkScrollerHeight(sc, chunk);
        if (chunk.classList.contains('is-streaming') || sc.clientHeight < 2) {
            chunk.classList.toggle('is-overflowing', contentH > collapsedMax + 1);
            return;
        }
        chunk.classList.toggle('is-overflowing', sc.scrollHeight > sc.clientHeight + 1);
    }
    requestAnimationFrame(function () { requestAnimationFrame(measure); });
}

function scheduleFeedChunkOverflowRefresh(chunk) {
    if (!chunk) return;
    var card = chunk.closest && chunk.closest('.subagent-grid-card');
    if (card && subagentPanelOpen && !card.classList.contains('is-expanded') && card.dataset.viewportVisible !== '1') return;
    /* streaming 中的块每个 delta 都会触发本函数；measure 是 layout 重操作，
       3 次 RAF × 每个 delta = 主线程灾难。streaming 时只 set class、不 measure。 */
    if (chunk.classList && chunk.classList.contains('is-streaming')) {
        refreshFeedChunkOverflow(chunk);
        return;
    }
    refreshFeedChunkOverflow(chunk);
    requestAnimationFrame(function () { refreshFeedChunkOverflow(chunk); });
}

function bindFeedChunkScrollChain(sc) {
    if (!sc || sc._wheelScrollChainBound) return;
    sc._wheelScrollChainBound = true;
    sc.addEventListener('wheel', onFeedChunkScrollerWheel, { passive: false });
}

function onFeedChunkScrollerWheel(e) {
    const sc = e.currentTarget;
    const chunk = sc.closest && sc.closest('.feed-chunk');
    if (!chunk || !chunk.classList.contains('expanded')) return;
    const dy = e.deltaY;
    const eps = 2;
    const st = sc.scrollTop;
    const ch = sc.clientHeight;
    const sh = sc.scrollHeight;
    const canScrollY = sh > ch + eps;
    if (canScrollY) {
        if (dy < 0 && st > eps) return;
        if (dy > 0 && st < sh - ch - eps) return;
    }
    e.preventDefault();
    e.stopPropagation();
    const body = sc.closest('.process-aggregate-body');
    const chat = document.getElementById('chat-container');
    if (body) {
        const bPrev = body.scrollTop;
        const bMax = Math.max(0, body.scrollHeight - body.clientHeight);
        var bt = bPrev + dy;
        if (bt < 0) bt = 0;
        if (bt > bMax) bt = bMax;
        if (bt !== bPrev) { smoothScrollBy(body, dy); return; }
    }
    if (chat) smoothScrollBy(chat, dy);
}

function bindProcessBriefScrollChain(brief) {
    if (!brief || brief._briefWheelBound) return;
    brief._briefWheelBound = true;
    brief.addEventListener('wheel', onProcessBriefWheel, { passive: false });
}

function onProcessBriefWheel(e) {
    const brief = e.currentTarget;
    const agg = brief.closest && brief.closest('.process-aggregate');
    if (!agg || !agg.classList.contains('is-collapsed')) return;
    const dy = e.deltaY;
    const eps = 2;
    const st = brief.scrollTop;
    const ch = brief.clientHeight;
    const sh = brief.scrollHeight;
    const canScrollY = sh > ch + eps;
    if (canScrollY) {
        if (dy < 0 && st > eps) return;
        if (dy > 0 && st < sh - ch - eps) return;
    }
    e.preventDefault();
    e.stopPropagation();
    const chat = document.getElementById('chat-container');
    if (chat) smoothScrollBy(chat, dy);
}

function setBriefRows(brief, texts) {
    brief.textContent = '';
    texts.forEach(function (t) {
        var rowType = t && typeof t === 'object' ? String(t.type || '') : '';
        var sourceText = t && typeof t === 'object' ? String(t.text || '') : String(t || '');
        if (!sourceText.trim()) return;
        const row = document.createElement('div');
        row.className = 'process-brief-item';
        if (rowType === 'response') row.classList.add('process-brief-item--response');
        else if (sourceText.indexOf('Tool calls: ') === 0) row.classList.add('process-brief-item--tool');
        // The collapsed response line is model output and must stay verbatim;
        // only generated tool/status summary lines are runtime-owned UI copy.
        if (rowType !== 'response' && typeof setUiRuntimeText === 'function') setUiRuntimeText(row, sourceText);
        else row.textContent = sourceText;
        brief.appendChild(row);
    });
}

function normalizeProcessBriefComparableText(value) {
    return String(value == null ? '' : value).replace(/\\s+/g, ' ').trim();
}

function updateProcessBrief(agg) {
    if (!agg || !agg.isConnected) return;
    const body = agg.querySelector('.process-aggregate-body');
    const brief = agg.querySelector('.process-aggregate-brief');
    if (!body || !brief) return;
    const items = Array.from(body.querySelectorAll('.feed-item'));
    const lines = [];
    const finalComparable = String(agg._processFinalResponseComparable || '');
    var toolCountMap = {};
    var toolOrder = [];
    function flushBriefTools() {
        if (!toolOrder.length) return;
        var toolParts = [];
        for (var oi = 0; oi < toolOrder.length; oi += 1) {
            var toolName = toolOrder[oi];
            var toolCount = toolCountMap[toolName] || 0;
            if (toolCount > 0) toolParts.push(toolName + ' ×' + toolCount);
        }
        if (toolParts.length) pushBriefLine(lines, 'Tool calls: ' + toolParts.join(', '));
        toolCountMap = {};
        toolOrder = [];
    }
    items.forEach(function (el) {
        var raw = getFeedItemText(el);
        /* 摘要只保留模型 response；reasoning 仍完整保留在展开内容中。 */
        if (el.classList.contains('feed--llm2')) {
            flushBriefTools();
            var responseComparable = getProcessBriefComparableText(el);
            if (raw && (!finalComparable || responseComparable !== finalComparable)) {
                pushBriefLine(lines, raw, 'response');
            }
        } else if (el.classList.contains('feed--tool')) {
            var tname = extractToolNameFromLog(raw);
            if (toolCountMap[tname] === undefined) toolOrder.push(tname);
            toolCountMap[tname] = (toolCountMap[tname] || 0) + 1;
        }
        /* status/reasoning 不进入摘要；工具会在下一个 response 前统一落成一行。 */
    });
    flushBriefTools();
    if (lines.length) setBriefRows(brief, lines);
    else {
        var st = body.querySelector('.feed-item.feed--st .feed-chunk-scroller, .feed-item.feed--st .feed-chunk');
        var tSt = st ? (typeof getUiRuntimeText === 'function' ? getUiRuntimeText(st) : st.textContent).trim() : '';
        if (tSt) setBriefRows(brief, [tSt]);
        else {
            var any = body.querySelector('.feed-item:not(.feed--llm):not(.feed--llm2) .feed-chunk-scroller, .feed-item:not(.feed--llm):not(.feed--llm2) .feed-chunk');
            var tAny = any ? (typeof getUiRuntimeText === 'function' ? getUiRuntimeText(any) : any.textContent).trim() : '';
            setBriefRows(brief, [tAny || '本段过程已折叠']);
        }
    }
    scheduleProcessAggregateHeightUi(agg);
}

function syncProcessAggregateHeightUi(agg) {
    if (!agg) return;
    var btn = agg.querySelector('.process-aggregate-resize');
    if (!btn) return;
    if (!agg.isConnected) {
        btn.hidden = true;
        return;
    }
    if (!agg.classList.contains('is-collapsed')) {
        agg.classList.remove('is-height-expanded');
        agg.classList.remove('has-height-overflow');
        btn.hidden = true;
        btn.setAttribute('aria-expanded', 'false');
        return;
    }
    var expanded = agg.classList.contains('is-height-expanded');
    agg.classList.remove('is-height-expanded');
    agg.classList.remove('has-height-overflow');
    var target = agg.querySelector('.process-aggregate-brief');
    var hasOverflow = !!(target && target.scrollHeight > target.clientHeight + 1);
    agg.classList.toggle('has-height-overflow', hasOverflow);
    if (expanded && hasOverflow) agg.classList.add('is-height-expanded');
    else expanded = false;
    btn.hidden = !hasOverflow;
    var label = expanded ? '收起执行过程高度' : '展开执行过程高度';
    btn.setAttribute('aria-expanded', expanded ? 'true' : 'false');
    btn.setAttribute('aria-label', label);
    btn.setAttribute('data-ui-tip', label);
    var tip = btn._uiHoverTipBound;
    if (!tip && typeof bindUiHoverTip === 'function') bindUiHoverTip(btn);
}

function scheduleProcessAggregateHeightUi(agg) {
    if (!agg || agg.classList.contains('subagent-grid-card')) return;
    if (agg._processHeightUiRaf) cancelAnimationFrame(agg._processHeightUiRaf);
    agg._processHeightUiRaf = requestAnimationFrame(function () {
        agg._processHeightUiRaf = 0;
        syncProcessAggregateHeightUi(agg);
    });
}

function bindProcessAggregateHeightButton(agg) {
    if (!agg || agg.classList.contains('subagent-grid-card')) return;
    var btn = agg.querySelector('.process-aggregate-resize');
    if (!btn) {
        btn = document.createElement('button');
        btn.type = 'button';
        btn.className = 'process-aggregate-resize';
        btn.hidden = true;
        btn.innerHTML = '<span class="process-aggregate-chevron" aria-hidden="true"></span>';
        agg.appendChild(btn);
    }
    if (!btn.dataset.bound) {
        btn.dataset.bound = '1';
        btn.addEventListener('click', function (e) {
            e.preventDefault();
            e.stopPropagation();
            agg.classList.toggle('is-height-expanded');
            if (agg.classList.contains('is-collapsed')) updateProcessBrief(agg);
            requestAnimationFrame(function () {
                syncProcessAggregateHeightUi(agg);
                agg.querySelectorAll('.process-aggregate-body .feed-chunk').forEach(refreshFeedChunkOverflow);
                registerMermaidLazy(agg);
            });
        });
    }
    var body = agg.querySelector('.process-aggregate-body');
    if (body && !agg._processHeightMutationObserver && typeof MutationObserver !== 'undefined') {
        agg._processHeightMutationObserver = new MutationObserver(function () {
            scheduleProcessAggregateHeightUi(agg);
        });
        agg._processHeightMutationObserver.observe(body, {
            childList: true,
            characterData: true,
            subtree: true,
        });
    }
    if (!agg._processHeightResizeObserver && typeof ResizeObserver !== 'undefined') {
        agg._processHeightResizeObserver = new ResizeObserver(function () {
            scheduleProcessAggregateHeightUi(agg);
        });
        if (body) agg._processHeightResizeObserver.observe(body);
        var brief = agg.querySelector('.process-aggregate-brief');
        if (brief) agg._processHeightResizeObserver.observe(brief);
    }
    scheduleProcessAggregateHeightUi(agg);
}

function alignProcessAggregateToViewportTop(agg) {
    if (!agg || !agg.isConnected) return;
    var viewport = document.getElementById('chat-container');
    if (!viewport) return;
    var viewportRect = viewport.getBoundingClientRect();
    var aggregateRect = agg.getBoundingClientRect();
    var targetTop = viewport.scrollTop + aggregateRect.top - viewportRect.top;
    var maxTop = Math.max(0, viewport.scrollHeight - viewport.clientHeight);
    targetTop = Math.max(0, Math.min(maxTop, targetTop));
    if (typeof setScrollTopImmediate === 'function') setScrollTopImmediate(viewport, targetTop);
    else viewport.scrollTop = targetTop;
}

function bindProcessAggregateInteractions(agg) {
    const procBody = agg.querySelector('.process-aggregate-body, .subagent-card-body');
    if (procBody && !procBody._streamFollowScrollBound) {
        procBody._streamFollowScrollBound = true;
        procBody.addEventListener('scroll', function () {
            if (!isSessionRunning(currentSessionId)) return;
            var active = getProcessBodyElForCurrentRun();
            if (active !== procBody) return;
            refreshLiveAutoFollowPins();
        }, { passive: true });
    }
    if (agg.classList.contains('subagent-grid-card')) return;
    const top = agg.querySelector('.process-aggregate-top');
    if (top && !top.dataset.bound) {
        top.dataset.bound = '1';
        top.addEventListener('click', function () {
            var openingDetail = agg.classList.contains('is-collapsed');
            agg.classList.toggle('is-collapsed');
            const expanded = !agg.classList.contains('is-collapsed');
            top.setAttribute('aria-expanded', expanded ? 'true' : 'false');
            if (agg.classList.contains('is-collapsed')) {
                updateProcessBrief(agg);
            } else {
                requestAnimationFrame(function () {
                    requestAnimationFrame(function () {
                        syncProcessAggregateHeightUi(agg);
                        agg.querySelectorAll('.process-aggregate-body .feed-chunk').forEach(refreshFeedChunkOverflow);
                        registerMermaidLazy(agg);
                        if (openingDetail) alignProcessAggregateToViewportTop(agg);
                    });
                });
            }
        });
        top.addEventListener('keydown', function (e) {
            if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); top.click(); }
        });
    }
    const briefEl = agg.querySelector('.process-aggregate-brief');
    if (briefEl) bindProcessBriefScrollChain(briefEl);
}

function bindProcessAggregate(agg) {
    bindProcessAggregateInteractions(agg);
    if (!agg || agg.classList.contains('subagent-grid-card')) return;
    bindProcessAggregateHeightButton(agg);
}

function procNow() {
    return (typeof performance !== 'undefined' && typeof performance.now === 'function') ? performance.now() : Date.now();
}

var processAggregateStatsTimer = null;

function processAggregateNeedsLiveStats(agg) {
    if (!agg || !agg.isConnected || !agg.dataset) return false;
    if (!agg.dataset.procStartedAt || agg.dataset.procEndedAt) return false;
    return !(agg.dataset.procDurationMs != null && agg.dataset.procDurationMs !== '');
}

function refreshLiveProcessAggregateStats() {
    if (typeof document === 'undefined') return false;
    var live = Array.from(document.querySelectorAll('.process-aggregate[data-proc-started-at]'))
        .filter(processAggregateNeedsLiveStats);
    live.forEach(refreshAggregateStatsSmart);
    return live.length > 0;
}

function stopLiveProcessAggregateStats() {
    if (!processAggregateStatsTimer) return;
    clearInterval(processAggregateStatsTimer);
    processAggregateStatsTimer = null;
}

function scheduleLiveProcessAggregateStats() {
    if (processAggregateStatsTimer) return;
    if (!refreshLiveProcessAggregateStats()) return;
    processAggregateStatsTimer = setInterval(function () {
        if (!refreshLiveProcessAggregateStats()) stopLiveProcessAggregateStats();
    }, 250);
}

function formatProcDurationMs(ms) {
    if (ms == null || !Number.isFinite(ms) || ms < 0) return null;
    if (ms < 800) return Math.max(0, Math.round(ms)) + 'ms';
    if (ms < 60000) {
        var s = ms / 1000;
        return (s < 10 ? s.toFixed(1) : Math.round(s)) + 's';
    }
    var mi = Math.floor(ms / 60000);
    var sec = Math.round((ms % 60000) / 1000);
    return mi + '分' + sec + '秒';
}

function processStartedAtToProcNow(startedAt) {
    if (!startedAt) return null;
    var startedMs = Date.parse(String(startedAt));
    if (!Number.isFinite(startedMs)) return null;
    return procNow() - Math.max(0, Date.now() - startedMs);
}

function applyRunStartedAtToProcessGroup(agg, startedAt) {
    if (!agg || !startedAt) return;
    var t0 = processStartedAtToProcNow(startedAt);
    if (!Number.isFinite(Number(t0))) return;
    agg.dataset.procStartedAt = String(t0);
    delete agg.dataset.procEndedAt;
    if (!agg.dataset.procDurationMs) refreshProcessAggregateStats(agg);
    scheduleLiveProcessAggregateStats();
}

function bumpAggregateMaxReactIter(agg, reactIter) {
    if (!agg) return;
    var n = Number(reactIter);
    if (!Number.isFinite(n) || n < 1) return;
    var flo = Math.floor(n);
    var cur = parseInt(agg.dataset.maxReactIter || '0', 10);
    if (flo > cur) agg.dataset.maxReactIter = String(flo);
}

function resolveSubagentAggFromCtx(ctx) {
    if (!ctx) return null;
    if (ctx.currentProcessGroup && ctx.currentProcessGroup.isConnected
        && ctx.currentProcessGroup.classList.contains('subagent-grid-card')) {
        return ctx.currentProcessGroup;
    }
    if (ctx._subagentBody && ctx._subagentBody.isConnected) {
        var card = ctx._subagentBody.closest('.subagent-grid-card');
        if (card) return card;
    }
    return null;
}

function applySubagentSessionMetricsToCard(card, metrics) {
    if (!card || !metrics || typeof metrics !== 'object') return;
    if (metrics.duration_ms != null && Number.isFinite(Number(metrics.duration_ms))) {
        card.dataset.procDurationMs = String(Math.max(0, Math.floor(Number(metrics.duration_ms))));
    }
    if (metrics.react_loops != null && Number.isFinite(Number(metrics.react_loops))) {
        card.dataset.procReactLoops = String(Math.max(0, Math.floor(Number(metrics.react_loops))));
    }
    if (metrics.tool_calls != null && Number.isFinite(Number(metrics.tool_calls))) {
        card.dataset.procToolCalls = String(Math.max(0, Math.floor(Number(metrics.tool_calls))));
    }
    if (metrics.tool_failures != null && Number.isFinite(Number(metrics.tool_failures))) {
        card.dataset.procToolFails = String(Math.max(0, Math.floor(Number(metrics.tool_failures))));
    }
}

function applySubagentProcessMetricsToCard(card, event) {
    if (!card || !event) return;
    var isRunEnd = event.duration_ms != null && Number.isFinite(Number(event.duration_ms));
    if (isRunEnd) {
        var runDur = Math.max(0, Math.round(Number(event.duration_ms)));
        var runLoops = event.react_loops != null && Number.isFinite(Number(event.react_loops))
            ? Math.max(0, Math.floor(Number(event.react_loops))) : 0;
        var runTools = event.tool_calls != null && Number.isFinite(Number(event.tool_calls))
            ? Math.max(0, Math.floor(Number(event.tool_calls))) : 0;
        var runFails = event.tool_failures != null && Number.isFinite(Number(event.tool_failures))
            ? Math.max(0, Math.floor(Number(event.tool_failures))) : 0;
        card.dataset.procDurationMs = String((parseInt(card.dataset.procDurationMs || '0', 10) || 0) + runDur);
        card.dataset.procReactLoops = String((parseInt(card.dataset.procReactLoops || '0', 10) || 0) + runLoops);
        card.dataset.procToolCalls = String((parseInt(card.dataset.procToolCalls || '0', 10) || 0) + runTools);
        card.dataset.procToolFails = String((parseInt(card.dataset.procToolFails || '0', 10) || 0) + runFails);
        delete card.dataset.procLiveToolCalls;
        delete card.dataset.procLiveToolFails;
    } else {
        if (event.tool_calls != null && Number.isFinite(Number(event.tool_calls))) {
            var liveTools = Math.max(0, Math.floor(Number(event.tool_calls)));
            var prevTools = parseInt(card.dataset.procLiveToolCalls || '0', 10) || 0;
            card.dataset.procLiveToolCalls = String(Math.max(prevTools, liveTools));
        }
        if (event.tool_failures != null && Number.isFinite(Number(event.tool_failures))) {
            var liveFails = Math.max(0, Math.floor(Number(event.tool_failures)));
            var prevFails = parseInt(card.dataset.procLiveToolFails || '0', 10) || 0;
            card.dataset.procLiveToolFails = String(Math.max(prevFails, liveFails));
        }
    }
}

function uiEventReactIter(ev) {
    if (!ev || ev.react_iter == null) return null;
    var n = Number(ev.react_iter);
    if (!Number.isFinite(n) || n < 1) return null;
    return n;
}

function applyCacheStatsFromEvent(ctx, event, runSessionId) {
    if (!event || typeof event !== 'object') return;
    var agg = resolveSubagentAggFromCtx(ctx);
    if (!agg || !agg.isConnected) {
        agg = ctx && ctx.currentProcessGroup;
        if (!agg || !agg.isConnected) {
            var st = (ctx && ctx.stream) ? ctx.stream : getVisibleChatStream();
            if (st) agg = st.querySelector('.process-aggregate:last-of-type');
        }
    }
    if (!agg) return;
    if (event.cache_hit != null) agg.dataset.procCacheHit = String(Math.max(0, Math.floor(Number(event.cache_hit))));
    if (event.cache_miss != null) agg.dataset.procCacheMiss = String(Math.max(0, Math.floor(Number(event.cache_miss))));
    if (event.hit_rate != null) agg.dataset.procCacheRate = String(Math.max(0, Number(event.hit_rate)));
    if (event.model != null) agg.dataset.procCacheModel = String(event.model);
    if (event.input_tokens != null) agg.dataset.procCacheInput = String(Math.max(0, Math.floor(Number(event.input_tokens))));
    if (event.output_tokens != null) agg.dataset.procCacheOutput = String(Math.max(0, Math.floor(Number(event.output_tokens))));
    if (event.tokens_per_sec != null) agg.dataset.procCacheTps = String(Math.max(0, Number(event.tokens_per_sec)));
    var tokenSessionId = runSessionId || event.session_id || event.sessionId || '';
    var eventTokenMode = String(event.context_token_mode || event.token_mode || '').toLowerCase();
    var allowApiTokenStats = eventTokenMode !== 'calculated';
    if (allowApiTokenStats && tokenSessionId && event.input_tokens != null && Number.isFinite(Number(event.input_tokens))) {
        recordContextTokens(tokenSessionId, Math.max(0, Math.floor(Number(event.input_tokens))), event.threshold);
    }
    refreshAggregateStatsSmart(agg);
}

function applyProcessMetricsFromEvent(ctx, event) {
    if (!event || typeof event !== 'object') return;
    var subCard = resolveSubagentAggFromCtx(ctx);
    if (subCard && subCard.isConnected) {
        applySubagentProcessMetricsToCard(subCard, event);
        scheduleSubagentCardStats(subCard);
        return;
    }
    var agg = ctx && ctx.currentProcessGroup;
    if (!agg || !agg.isConnected) {
        var st = (ctx && ctx.stream) ? ctx.stream : getVisibleChatStream();
        if (st) agg = st.querySelector('.process-aggregate:last-of-type');
    }
    if (!agg) return;
    if (event.duration_ms != null && Number.isFinite(Number(event.duration_ms))) {
        if (!replayingMessages && agg.dataset.procStartedAt) {
            agg.dataset.procEndedAt = String(procNow());
            delete agg.dataset.procDurationMs;
        } else {
            agg.dataset.procDurationMs = String(Math.max(0, Math.round(Number(event.duration_ms))));
        }
    }
    if (event.react_loops != null && Number.isFinite(Number(event.react_loops))) {
        agg.dataset.procReactLoops = String(Math.max(0, Math.floor(Number(event.react_loops))));
    }
    if (event.tool_calls != null && Number.isFinite(Number(event.tool_calls))) {
        agg.dataset.procToolCalls = String(Math.max(0, Math.floor(Number(event.tool_calls))));
    }
    if (event.tool_failures != null && Number.isFinite(Number(event.tool_failures))) {
        agg.dataset.procToolFails = String(Math.max(0, Math.floor(Number(event.tool_failures))));
    }
    refreshAggregateStatsSmart(agg);
    if (processAggregateNeedsLiveStats(agg)) scheduleLiveProcessAggregateStats();
    else if (!refreshLiveProcessAggregateStats()) stopLiveProcessAggregateStats();
}

function refreshAggregateStatsSmart(agg) {
    if (agg && agg.classList && agg.classList.contains('subagent-grid-card')) refreshSubagentCardStats(agg);
    else refreshProcessAggregateStats(agg);
}

function renderProcessAggregateStats(el, sourceText, tailText) {
    if (!el) return;
    el.textContent = '';
    var head = document.createElement('span');
    if (typeof setUiRuntimeText === 'function') setUiRuntimeText(head, sourceText);
    else head.textContent = typeof translateUiString === 'function' ? translateUiString(sourceText) : sourceText;
    var tail = document.createElement('span');
    // Model/profile names and cache values are data, not UI copy.
    tail.setAttribute('data-i18n-skip', 'true');
    tail.textContent = String(tailText == null ? '' : tailText);
    el.appendChild(head);
    el.appendChild(tail);
}

function refreshSubagentCardStats(card) {
    if (!card) return;
    var el = card.querySelector('.process-aggregate-stats');
    if (!el) return;
    var body = card.querySelector('.subagent-card-body');
    var pDur = card.dataset.procDurationMs != null && card.dataset.procDurationMs !== ''
        ? parseInt(card.dataset.procDurationMs, 10) : NaN;
    var pLoops = card.dataset.procReactLoops != null && card.dataset.procReactLoops !== ''
        ? parseInt(card.dataset.procReactLoops, 10) : NaN;
    var pTools = card.dataset.procToolCalls != null && card.dataset.procToolCalls !== ''
        ? parseInt(card.dataset.procToolCalls, 10) : NaN;
    var pFails = card.dataset.procToolFails != null && card.dataset.procToolFails !== ''
        ? parseInt(card.dataset.procToolFails, 10) : NaN;
    var maxFromRows = 0;
    var bodyLoaded = subagentBodyIsLoaded(body) && body.dataset.stashed !== '1';
    if (bodyLoaded) {
        body.querySelectorAll('.subagent-turn-process .feed-item[data-react-iter]').forEach(function (row) {
            var v = parseInt(row.getAttribute('data-react-iter'), 10);
            if (Number.isFinite(v) && v > maxFromRows) maxFromRows = v;
        });
    }
    var dsRi = card.dataset.maxReactIter ? parseInt(card.dataset.maxReactIter, 10) : 0;
    var reactLoops = Math.max(maxFromRows, dsRi);
    if (!reactLoops && bodyLoaded) {
        reactLoops = body.querySelectorAll('.subagent-turn-process .feed-item[data-log-type="llm-response"]').length;
    }
    if (Number.isFinite(pLoops) && pLoops > 0) reactLoops = pLoops;
    var sessionTools = Number.isFinite(pTools) && pTools >= 0 ? pTools : 0;
    var liveTools = parseInt(card.dataset.procLiveToolCalls || '0', 10) || 0;
    var toolN = sessionTools + liveTools;
    if (!toolN && bodyLoaded) {
        toolN = body.querySelectorAll('.subagent-turn-process .feed-item[data-log-type="tool-call"]').length;
    }
    var sessionFails = Number.isFinite(pFails) && pFails >= 0 ? pFails : 0;
    var liveFails = parseInt(card.dataset.procLiveToolFails || '0', 10) || 0;
    var failN = sessionFails + liveFails;
    if (!failN && bodyLoaded) {
        body.querySelectorAll('.subagent-turn-process .feed-item[data-log-type="tool-call"]').forEach(function (row) {
            var sc = row.querySelector('.feed-chunk-scroller');
            var txt = sc ? String(sc.textContent || '') : '';
            if (/Error:|失败|异常|error executing command:/i.test(txt)) failN += 1;
        });
    }
    var t0s = card.dataset.procStartedAt;
    var t0 = (t0s != null && t0s !== '') ? Number(t0s) : NaN;
    var parts = [];
    var durStr = null;
    if (Number.isFinite(pDur) && pDur >= 0) durStr = formatProcDurationMs(pDur);
    else if (Number.isFinite(t0)) {
        var t1s = card.dataset.procEndedAt;
        var t1 = (t1s != null && t1s !== '') ? Number(t1s) : procNow();
        durStr = formatProcDurationMs(t1 - t0);
    }
    if (durStr) parts.push(durStr);
    parts.push(String(reactLoops) + ' 轮');
    parts.push('工具 ' + String(toolN) + ' 次');
    parts.push('失败 ' + String(failN) + ' 次');
    var modelStr = card.dataset.procCacheModel || card.dataset.executorModel || '—';
    var est = card.dataset.procCtxEstimated;
    var thr = card.dataset.procCtxThreshold;
    var pctStr = '—';
    if (est != null && est !== '' && thr != null && thr !== '' && Number(thr) > 0) {
        pctStr = (Math.round(Number(est) / Number(thr) * 1000) / 10) + '%';
    }
    renderProcessAggregateStats(el, parts.join(' · '), modelStr + ' · ' + pctStr);
}

function refreshProcessAggregateStats(agg) {
    if (!agg) return;
    var el = agg.querySelector('.process-aggregate-stats');
    if (!el) return;
    var body = agg.querySelector('.process-aggregate-body');
    if (!body) { el.textContent = ''; return; }
    var pDur = agg.dataset.procDurationMs != null && agg.dataset.procDurationMs !== ''
        ? parseInt(agg.dataset.procDurationMs, 10) : NaN;
    var pLoops = agg.dataset.procReactLoops != null && agg.dataset.procReactLoops !== ''
        ? parseInt(agg.dataset.procReactLoops, 10) : NaN;
    var pTools = agg.dataset.procToolCalls != null && agg.dataset.procToolCalls !== ''
        ? parseInt(agg.dataset.procToolCalls, 10) : NaN;
    var pFails = agg.dataset.procToolFails != null && agg.dataset.procToolFails !== ''
        ? parseInt(agg.dataset.procToolFails, 10) : NaN;
    var maxFromRows = 0;
    body.querySelectorAll('.feed-item[data-react-iter]').forEach(function (row) {
        var v = parseInt(row.getAttribute('data-react-iter'), 10);
        if (Number.isFinite(v) && v > maxFromRows) maxFromRows = v;
    });
    var dsRi = agg.dataset.maxReactIter ? parseInt(agg.dataset.maxReactIter, 10) : 0;
    var reactLoops = Math.max(maxFromRows, dsRi);
    if (!reactLoops) {
        reactLoops = body.querySelectorAll('.feed-item[data-log-type="llm-response"]').length;
    }
    if (Number.isFinite(pLoops) && pLoops >= 0) reactLoops = pLoops;
    var toolN = body.querySelectorAll('.feed-item[data-log-type="tool-call"]').length;
    if (Number.isFinite(pTools) && pTools >= 0) toolN = pTools;
    var failN = 0;
    if (Number.isFinite(pFails) && pFails >= 0) failN = pFails;
    var t0s = agg.dataset.procStartedAt;
    var t0 = (t0s != null && t0s !== '') ? Number(t0s) : NaN;
    var parts = [];
    var durStr = null;
    if (Number.isFinite(pDur) && pDur >= 0) durStr = formatProcDurationMs(pDur);
    else if (Number.isFinite(t0)) {
        var t1s = agg.dataset.procEndedAt;
        var t1 = (t1s != null && t1s !== '') ? Number(t1s) : procNow();
        durStr = formatProcDurationMs(t1 - t0);
    }
    if (durStr) parts.push(durStr);
    parts.push(String(reactLoops) + ' 轮');
    parts.push('工具 ' + String(toolN) + ' 次');
        parts.push('失败 ' + String(failN) + ' 次');
    var ch = agg.dataset.procCacheHit != null && agg.dataset.procCacheHit !== '' ? parseInt(agg.dataset.procCacheHit, 10) : 0;
    var cm = agg.dataset.procCacheMiss != null && agg.dataset.procCacheMiss !== '' ? parseInt(agg.dataset.procCacheMiss, 10) : 0;
    var cr = agg.dataset.procCacheRate != null && agg.dataset.procCacheRate !== '' ? parseFloat(agg.dataset.procCacheRate) : 0;
    var modelStr = agg.dataset.procCacheModel || '';
    var inputStr = agg.dataset.procCacheInput || '0';
    var outputStr = agg.dataset.procCacheOutput || '0';
    var tps = agg.dataset.procCacheTps;
    var cacheParts = [];
    if (modelStr) cacheParts.push(modelStr);
    cacheParts.push('input=' + inputStr);
    cacheParts.push('output=' + outputStr);
    if (tps && tps !== '0') cacheParts.push(tps + ' tok/s');
    var rateStr = (ch + cm > 0) ? (cr % 1 === 0 ? cr.toFixed(0) : cr.toFixed(1)) + '%' : '0%';
    cacheParts.push('hit_rate=' + rateStr);
    var cacheLine = cacheParts.join(' · ');
    renderProcessAggregateStats(el, parts.join(' · '), cacheLine);
}

function ensureProcessGroup(ctx) {
    if (!ctx || !ctx.stream) return null;
    /* DocumentFragment 或未挂上 document 的节点 isConnected 为 false；回放或「加载更早消息」预挂载时需保留同一执行过程框 */
    if (ctx.currentProcessGroup && !ctx.currentProcessGroup.isConnected && !replayingMessages) ctx.currentProcessGroup = null;
    if (ctx.currentProcessGroup) return ctx.currentProcessGroup;
    stripWelcome(ctx);
    const wrap = document.createElement('div');
    wrap.className = 'process-aggregate';
    var replayCollapsed = !!replayingMessages;
    if (replayCollapsed) wrap.classList.add('is-collapsed');
    if (!replayingMessages) wrap.classList.add('is-running');
    wrap.innerHTML = '<div class="process-aggregate-top" role="button" tabindex="0" aria-expanded="' + (replayCollapsed ? 'false' : 'true') + '">'
        + '<div class="process-aggregate-top-line">'
        + '<span class="process-aggregate-title-wrap">'
        + '<span class="process-aggregate-title">执行过程</span>'
        + '<span class="process-aggregate-stats" aria-live="polite"></span>'
        + '</span>'
        + '<span class="process-chev" aria-hidden="true">▼</span></div>'
        + '<div class="process-aggregate-brief"></div></div>'
        + '<div class="process-aggregate-body"></div>'
        + '<button type="button" class="process-aggregate-resize" aria-label="展开执行过程高度" aria-expanded="false" data-ui-tip="展开执行过程高度" hidden>'
        + '<span class="process-aggregate-chevron" aria-hidden="true"></span></button>';
    if (!replayingMessages) {
        if (ctx.runStartedAt) applyRunStartedAtToProcessGroup(wrap, ctx.runStartedAt);
        else {
            wrap.dataset.procStartedAt = String(procNow());
        }
    }
    delete wrap.dataset.maxReactIter;
    (ctx.stream || chatContainer).appendChild(wrap);
    bindProcessAggregate(wrap);
    ctx.currentProcessGroup = wrap;
    refreshProcessAggregateStats(wrap);
    if (processAggregateNeedsLiveStats(wrap)) scheduleLiveProcessAggregateStats();
    return wrap;
}

function sealProcessGroup(ctx) {
    if (!ctx) return;
    if (!ctx.currentProcessGroup) return;
    const agg = ctx.currentProcessGroup;
    if (agg.isConnected) {
        agg.classList.remove('is-running');
        updateProcessBrief(agg);
        if (agg.dataset.procStartedAt) agg.dataset.procEndedAt = String(procNow());
        refreshProcessAggregateStats(agg);
        if (!refreshLiveProcessAggregateStats()) stopLiveProcessAggregateStats();
    }
    ctx.currentProcessGroup = null;
    ctx.progressScrollers = {};
    resetKeyContextStreamFilter(ctx);
    finalizeProgressStreamChunks(ctx);
}

function getProcessBody(ctx) {
    if (ctx && ctx._subagentTurnProcess && ctx._subagentTurnProcess.isConnected) return ctx._subagentTurnProcess;
    if (ctx && ctx.currentTurn && ctx.currentTurn.isConnected) {
        var subProc = ctx.currentTurn.querySelector('.subagent-turn-process');
        if (subProc) {
            ctx._subagentTurnProcess = subProc;
            return subProc;
        }
    }
    if (ctx && ctx._subagentBody && ctx._subagentBody.isConnected) return null;
    const w = ensureProcessGroup(ctx);
    if (!w) return null;
    return w.querySelector('.process-aggregate-body');
}

function getExistingProcessBody(ctx) {
    if (!ctx) return null;
    if (ctx._subagentTurnProcess && ctx._subagentTurnProcess.isConnected) return ctx._subagentTurnProcess;
    if (ctx.currentTurn && ctx.currentTurn.isConnected) {
        var subProc = ctx.currentTurn.querySelector('.subagent-turn-process');
        if (subProc) {
            ctx._subagentTurnProcess = subProc;
            return subProc;
        }
    }
    if (ctx._subagentBody && ctx._subagentBody.isConnected) return null;
    var current = ctx.currentProcessGroup;
    if (!current || !current.isConnected) return null;
    return current.querySelector('.process-aggregate-body');
}

function autoResizeTextarea() {
    messageInput.style.height = 'auto';
    messageInput.style.height = Math.min(messageInput.scrollHeight, Math.floor(window.innerHeight * 0.5)) + 'px';
    repinStreamScrollAfterComposerResize();
}

/** 输入框增高会压缩工作区高度；若正在跟随底部，立即把聊天区/执行过程区重新钉到底部，避免与流式滚动互相拉扯。 */
function repinStreamScrollAfterComposerResize() {
    if (!liveAutoFollow || !chatContainer) return;
    if (typeof setScrollTopImmediate === 'function') {
        setScrollTopImmediate(chatContainer, chatContainer.scrollHeight);
    }
    var pb = typeof getProcessBodyElForCurrentRun === 'function' ? getProcessBodyElForCurrentRun() : null;
    if (pb) pb.scrollTop = pb.scrollHeight;
}
messageInput.addEventListener('input', autoResizeTextarea);
messageInput.addEventListener('input', rewriteInputWorkspacePaths);
messageInput.addEventListener('input', function () {
    if (currentSessionId) persistInputDraft(currentSessionId, messageInput.value);
    if (typeof setSendButtonState === 'function') setSendButtonState();
});
autoResizeTextarea();
refreshInputPathChips();

function escapeHtml(str) {
    if (!str) return '';
    return str.replace(/[&<>]/g, function(m) {
        if (m === '&') return '&amp;';
        if (m === '<') return '&lt;';
        if (m === '>') return '&gt;';
        return m;
    });
}

function escapeHtmlAttr(str) {
    return escapeHtml(String(str || '')).replace(/"/g, '&quot;').replace(/'/g, '&#39;');
}

function scrollToBottom(opts) {
    opts = opts || {};
    if (!chatContainer) return;
    if (opts.smooth && typeof chatContainer.scrollTo === 'function') {
        chatContainer.scrollTo({ top: chatContainer.scrollHeight, behavior: 'smooth' });
        return;
    }
    setScrollTopImmediate(chatContainer, chatContainer.scrollHeight);
    requestAnimationFrame(function () {
        if (chatContainer) chatContainer.scrollTop = chatContainer.scrollHeight;
    });
}

// 滚动位置存储
const LS_SCROLL_POSITION_PREFIX = 'myagent-scroll-';
const LS_SCROLL_ANCHOR_PREFIX = 'myagent-scroll-anchor-';
const LS_SCROLL_ANCHOR_OFFSET_PREFIX = 'myagent-scroll-anchor-offset-';

function getScrollPositionKey(sessionId) {
    return LS_SCROLL_POSITION_PREFIX + sessionId;
}

function getScrollAnchorKey(sessionId) {
    return LS_SCROLL_ANCHOR_PREFIX + sessionId;
}

function getScrollAnchorOffsetKey(sessionId) {
    return LS_SCROLL_ANCHOR_OFFSET_PREFIX + sessionId;
}

function saveScrollPosition(sessionId, scrollTop) {
    if (!sessionId) return;
    try {
        localStorage.setItem(getScrollPositionKey(sessionId), String(Math.round(scrollTop)));
    } catch (e) { /* ignore */ }
}

function saveScrollAnchorPosition(sessionId) {
    if (!chatContainer || !sessionId) return;
    try {
        if (isNearBottom(chatContainer, STREAM_CHAT_NEAR_BOTTOM_PX)) {
            localStorage.removeItem(getScrollAnchorKey(sessionId));
            localStorage.removeItem(getScrollAnchorOffsetKey(sessionId));
            return;
        }
        var rect = chatContainer.getBoundingClientRect();
        var wraps = chatContainer.querySelectorAll('.msg-wrap--user[data-event-index]');
        var best = null;
        var bestWrap = null;
        for (var i = 0; i < wraps.length; i += 1) {
            var wr = wraps[i];
            var ei = Number(wr.getAttribute('data-event-index'));
            if (!Number.isFinite(ei)) continue;
            var top = wr.getBoundingClientRect().top;
            if (top <= rect.top + 8) {
                best = ei;
                bestWrap = wr;
            }
            else if (best == null) {
                best = ei;
                bestWrap = wr;
                break;
            }
        }
        if (best != null && bestWrap) {
            localStorage.setItem(getScrollAnchorKey(sessionId), String(best));
            localStorage.setItem(
                getScrollAnchorOffsetKey(sessionId),
                String(Math.round(bestWrap.getBoundingClientRect().top - rect.top))
            );
        } else {
            localStorage.removeItem(getScrollAnchorKey(sessionId));
            localStorage.removeItem(getScrollAnchorOffsetKey(sessionId));
        }
    } catch (e) { /* ignore */ }
}

function getSavedScrollAnchorPosition(sessionId) {
    if (!sessionId) return null;
    try {
        var saved = localStorage.getItem(getScrollAnchorKey(sessionId));
        if (saved == null || saved === '') return null;
        var n = Number(saved);
        return Number.isFinite(n) ? n : null;
    } catch (e) { return null; }
}

function getSavedScrollAnchorOffset(sessionId) {
    if (!sessionId) return null;
    try {
        var saved = localStorage.getItem(getScrollAnchorOffsetKey(sessionId));
        if (saved == null || saved === '') return null;
        var n = Number(saved);
        return Number.isFinite(n) ? n : null;
    } catch (e) { return null; }
}

function getSavedScrollPosition(sessionId) {
    if (!sessionId) return null;
    try {
        var saved = localStorage.getItem(getScrollPositionKey(sessionId));
        return saved ? parseInt(saved, 10) : null;
    } catch (e) { return null; }
}

function saveChatScrollForSession(sid) {
    if (!chatContainer || !sid) return;
    saveScrollPosition(sid, chatContainer.scrollTop);
    saveScrollAnchorPosition(sid);
}

function clampChatScrollTop(y) {
    if (!chatContainer) return 0;
    const max = Math.max(0, chatContainer.scrollHeight - chatContainer.clientHeight);
    return Math.min(Math.max(0, y), max);
}

var historySmoothScrollSessionId = '';

function beginHistorySmoothScroll(sessionId) {
    historySmoothScrollSessionId = String(sessionId || '');
}

function endHistorySmoothScroll(sessionId) {
    var sid = String(sessionId || '');
    if (!sid || historySmoothScrollSessionId === sid) historySmoothScrollSessionId = '';
}

function isHistorySmoothScrollActive() {
    return !!(
        historySmoothScrollSessionId
        && historySmoothScrollSessionId === String(currentSessionId || '')
    );
}

/**
 * @param {string} sessionId
 * @param {'saved-or-bottom'|'saved-smooth-or-bottom'|'bottom'|'smooth-bottom'} mode
 */
function applyChatScrollAfterHistoryLoad(sessionId, mode) {
    if (!chatContainer || !sessionId) return;
    if (mode === 'smooth-bottom') beginHistorySmoothScroll(sessionId);
    else endHistorySmoothScroll();
    var running = isSessionRunning(sessionId)
        || (typeof isServerStreamActive === 'function' && isServerStreamActive(sessionId));

    // Running sessions always show the newest generated content.
    if (running) {
        endHistorySmoothScroll(sessionId);
        if (typeof scrollCurrentRunningProcessToBottom === 'function') {
            scrollCurrentRunningProcessToBottom(sessionId);
        }
        streamChatNearBottom = true;
        streamProcNearBottom = true;
        liveAutoFollow = true;
        scrollToBottom();
        return;
    }

    if (mode === 'saved-or-bottom' || mode === 'saved-smooth-or-bottom') {
        var smoothRestore = mode === 'saved-smooth-or-bottom';
        var savedPosition = getSavedScrollPosition(sessionId);
        var savedAnchor = getSavedScrollAnchorPosition(sessionId);
        var savedAnchorOffset = getSavedScrollAnchorOffset(sessionId);
        if (savedAnchor != null && typeof scrollToUserTurnOrLoadOlder === 'function') {
            requestAnimationFrame(function () {
                if (sessionId !== currentSessionId) return;
                void scrollToUserTurnOrLoadOlder(savedAnchor, {
                    silent: true,
                    allowFullReload: false,
                    maxOlderLoads: 2,
                    instant: !smoothRestore,
                    viewportOffset: savedAnchorOffset,
                }).then(function (ok) {
                    if (ok || sessionId !== currentSessionId || !chatContainer) return;
                    if (savedPosition !== null && Number.isFinite(Number(savedPosition))) {
                        var fallbackTop = clampChatScrollTop(Number(savedPosition));
                        if (smoothRestore && typeof chatContainer.scrollTo === 'function') {
                            chatContainer.scrollTo({ top: fallbackTop, behavior: 'smooth' });
                        } else {
                            setScrollTopImmediate(chatContainer, fallbackTop);
                        }
                        streamChatNearBottom = isNearBottom(chatContainer, STREAM_CHAT_NEAR_BOTTOM_PX);
                        liveAutoFollow = streamChatNearBottom;
                    } else {
                        scrollToBottom();
                    }
                });
            });
            streamChatNearBottom = false;
            streamProcNearBottom = true;
            liveAutoFollow = false;
            return;
        }
        if (savedPosition !== null && Number.isFinite(Number(savedPosition))) {
            var targetTop = clampChatScrollTop(Number(savedPosition));
            if (smoothRestore && typeof chatContainer.scrollTo === 'function') {
                chatContainer.scrollTo({ top: targetTop, behavior: 'smooth' });
            } else {
                setScrollTopImmediate(chatContainer, targetTop);
            }
            streamChatNearBottom = isNearBottom(chatContainer, STREAM_CHAT_NEAR_BOTTOM_PX);
            streamProcNearBottom = true;
            liveAutoFollow = streamChatNearBottom;
            return;
        }
    }
    
    streamChatNearBottom = true;
    streamProcNearBottom = true;
    liveAutoFollow = true;
    scrollToBottom({ smooth: mode === 'smooth-bottom' });
}

window.addEventListener('beforeunload', function () {
    saveChatScrollForSession(currentSessionId);
});
document.addEventListener('visibilitychange', function () {
    if (document.visibilityState === 'hidden') saveChatScrollForSession(currentSessionId);
    else if (typeof reconcileRunStateFromServer === 'function') {
        void reconcileRunStateFromServer({ silent: true });
    }
});
window.addEventListener('pageshow', function () {
    if (typeof reconcileRunStateFromServer === 'function') {
        void reconcileRunStateFromServer({ silent: true });
    }
});
window.addEventListener('focus', function () {
    if (typeof reconcileRunStateFromServer === 'function') {
        void reconcileRunStateFromServer({ silent: true });
    }
});

const WELCOME_HTML = \`<div class="welcome" role="status"><div class="welcome-icon" aria-hidden="true"><img src="/assets/sugar-logo.png" alt="" draggable="false"></div><strong>开始一段新的对话</strong><p>在左侧侧栏新建或选择会话。Enter 发送，Ctrl+Enter / Shift+Enter 换行。</p></div>\`;

function historyLoadScrollsToBottom(sessionId, mode) {
    if (mode === 'bottom') return true;
    if (mode === 'saved-or-bottom' || mode === 'saved-smooth-or-bottom') {
        var savedAnchor = getSavedScrollAnchorPosition(sessionId);
        if (savedAnchor != null) return false;
        var savedPosition = getSavedScrollPosition(sessionId);
        if (savedPosition !== null && Number.isFinite(Number(savedPosition))) return false;
    }
    return true;
}

function waitForChatScrollAfterHistoryLoad(sessionId, mode) {
    if (!chatContainer || !sessionId) return Promise.resolve(false);
    if (sessionId !== currentSessionId) return Promise.resolve(false);
    if (mode === 'smooth-bottom') {
        return new Promise(function (resolve) {
            var settled = false;
            var raf = 0;
            var startedAt = performance.now();
            var lastMovementAt = startedAt;
            var lastTop = chatContainer.scrollTop;
            var retargetCount = 0;
            var userEvents = ['wheel', 'touchstart', 'pointerdown'];
            function cleanup(reachedBottom) {
                if (settled) return;
                settled = true;
                if (raf) cancelAnimationFrame(raf);
                chatContainer.removeEventListener('scrollend', onScrollEnd);
                userEvents.forEach(function (eventName) {
                    chatContainer.removeEventListener(eventName, onUserInterrupt);
                });
                endHistorySmoothScroll(sessionId);
                resolve(!!reachedBottom);
            }
            function isAtBottom() {
                if (!chatContainer) return false;
                var maxTop = Math.max(0, chatContainer.scrollHeight - chatContainer.clientHeight);
                return maxTop - chatContainer.scrollTop <= 2;
            }
            function onScrollEnd() {
                if (sessionId !== currentSessionId) {
                    cleanup(false);
                    return;
                }
                if (isAtBottom()) {
                    cleanup(true);
                    return;
                }
                if (retargetCount < 3) {
                    retargetCount += 1;
                    lastMovementAt = performance.now();
                    chatContainer.scrollTo({ top: chatContainer.scrollHeight, behavior: 'smooth' });
                }
            }
            function onUserInterrupt() {
                cleanup(false);
            }
            function check(now) {
                if (settled) return;
                if (!chatContainer || sessionId !== currentSessionId) {
                    cleanup(false);
                    return;
                }
                var top = chatContainer.scrollTop;
                if (Math.abs(top - lastTop) > 0.5) {
                    lastTop = top;
                    lastMovementAt = now;
                }
                if (isAtBottom() && now - lastMovementAt >= 96) {
                    cleanup(true);
                    return;
                }
                if (!isAtBottom() && now - lastMovementAt >= 160 && retargetCount < 3) {
                    retargetCount += 1;
                    lastMovementAt = now;
                    chatContainer.scrollTo({ top: chatContainer.scrollHeight, behavior: 'smooth' });
                }
                if (now - startedAt >= 5000) {
                    cleanup(isAtBottom());
                    return;
                }
                raf = requestAnimationFrame(check);
            }
            chatContainer.addEventListener('scrollend', onScrollEnd);
            userEvents.forEach(function (eventName) {
                chatContainer.addEventListener(eventName, onUserInterrupt, { passive: true });
            });
            raf = requestAnimationFrame(check);
        });
    }
    if (historyLoadScrollsToBottom(sessionId, mode)) {
        return new Promise(function (resolve) {
            requestAnimationFrame(function () {
                resolve(true);
            });
        });
    }
    return Promise.resolve(false);
}

function setWelcome() {
    resetSessionHistoryPaging();
    const vs = getVisibleChatStream();
    if (vs) {
        emptyChatStreamKeepingStrip(vs);
        vs.insertAdjacentHTML('beforeend', WELCOME_HTML);
    } else {
        chatContainer.innerHTML = '';
        ensureVisibleChatStreamSlot();
        const vs2 = getVisibleChatStream();
        if (vs2) vs2.insertAdjacentHTML('beforeend', WELCOME_HTML);
        else chatContainer.innerHTML = WELCOME_HTML;
    }
    rebuildToc();
    renderTodoPlanForCurrentSession();
}

function stripWelcome(ctx) {
    if (ctx && ctx._subagentBody) return;
    const root = (ctx && ctx.stream) ? ctx.stream : (getVisibleChatStream() || chatContainer);
    if (root) root.querySelector('.welcome')?.remove();
}

function clearChat() { setWelcome(); }

function pathJoinBaseName(baseDir, name) {
    if (!baseDir) return name || '';
    if (!name) return baseDir;
    var d = String(baseDir).replace(/[\\\\/]+$/, '');
    var useBack = d.indexOf('\\\\') !== -1;
    return d + (useBack ? '\\\\' : '/') + name;
}

/** 将「工作区绝对路径」转为 file:// URL（Windows / Unix）；分段编码以支持空格、中文等。 */
function fileUrlFromFsPath(fsPath) {
    var norm = String(fsPath || '').replace(/\\\\/g, '/');
    if (/^\\/\\//.test(norm)) return 'file:' + norm.replace(/\\//g, '/');
    var encRest = function (rel) {
        if (!rel) return '';
        return rel.split('/').map(function (seg) {
            return encodeURIComponent(seg);
        }).join('/');
    };
    if (/^[A-Za-z]:\\//.test(norm)) {
        return 'file:///' + norm.slice(0, 3) + encRest(norm.slice(3));
    }
    return 'file:///' + encRest(norm.replace(/^\\/+/, ''));
}

/**
 * 助手常写「保存至：📄 /报告.md」——以 / 开头表示相对工作区根目录的路径（非 URL）。
 */
function joinWorkDirAndRelativeSlashPath(workDir, slashPath) {
    var rel = String(slashPath || '').replace(/^\\/+/, '');
    if (!rel || !workDir) return null;
    var d = String(workDir).replace(/[\\\\/]+$/, '');
    var useBack = d.indexOf('\\\\') !== -1;
    var segs = rel.split(/\\/+/).filter(Boolean);
    if (!segs.length) return null;
    var tail = segs.join(useBack ? '\\\\' : '/');
    return d + (useBack ? '\\\\' : '/') + tail;
}

function trimTrailingPathPunct(s) {
    return String(s || '').replace(/[，。、；：）】』」\\]\\)\\.,;:!?'"」]+$/g, '').trim();
}

function stripPathWrappingQuotes(s) {
    var t = String(s || '').trim();
    if (t.length >= 2) {
        var a = t.charAt(0);
        var b = t.charAt(t.length - 1);
        if ((a === '"' && b === '"') || (a === "'" && b === "'") || (a === '\`' && b === '\`')) {
            return t.slice(1, -1).trim();
        }
    }
    return t;
}

function stripPathLineSuffix(s) {
    var t = String(s || '').trim();
    return t.replace(new RegExp('(\\\\.(' + LINKIFY_EXT_FRAGMENT + ')):(\\\\d+)(?::\\\\d+)?$', 'i'), '.$2');
}

function decodePathPercentEscapes(s) {
    var t = String(s || '');
    if (t.indexOf('%') < 0) return t;
    return t.replace(/(?:%[0-9A-Fa-f]{2})+/g, function (part) {
        try {
            return decodeURIComponent(part);
        } catch (e) {
            return part;
        }
    });
}

function cleanPathTokenForLink(s) {
    var t = linkifyNormalizePathToken(String(s || '').trim());
    if (!/^https?:\\/\\//i.test(t)) t = decodePathPercentEscapes(t);
    if (!t) return '';
    var a = t.charAt(0);
    var b = t.charAt(t.length - 1);
    if (t.length >= 2 && ((a === '"' && b === '"') || (a === "'" && b === "'") || (a === '\`' && b === '\`'))) {
        return stripPathLineSuffix(trimTrailingPathPunct(t.slice(1, -1).trim()));
    }
    return stripPathLineSuffix(stripPathWrappingQuotes(trimTrailingPathPunct(t)));
}

/** 统一全角标点/数字等，便于识别「．xlsx」「路径：／」等变体 */
function linkifyNormalizePathToken(s) {
    return String(s || '')
        .replace(/\\uFF0F/g, '/')
        .replace(/\\uFF3C/g, '\\\\')
        .replace(/\\uFF1A/g, ':')
        .replace(/\\uFF0E/g, '.')
        .replace(/[\\u2018\\u2019\\u201B\\u2032\\uFF07]/g, "'")
        .replace(/[\\u201C\\u201D\\u201E\\u2033\\uFF02]/g, '"');
}

/** 可链转「工作区下文件」的已知后缀（与 linkify / 虚拟路径规则共用） */
var LINKIFY_EXT_FRAGMENT = (
    'md|markdown|txt|py|jsx?|tsx?|mjs|cjs|json|ya?ml|toml|xml|html?|htm|css|s?css|less|sass|scss|' +
    'xlsx?|xlsm?|xlsb?|xlt|csv|tsv|ods|numbers|et|' +
    'pdf|docx?|docm?|dotx?|rtf|odt|pages|' +
    'pptx?|pptm?|potx?|odp|key|' +
    'png|jpe?g|gif|webp|svg|ico|bmp|tiff?|heic|avif|jfif|raw|' +
    'zip|7z|rar|gz|tgz|tar|bz2|xz|lz4|zst|' +
    'mp3|mp4|m4a|aac|flac|wav|ogg|webm|mov|avi|mkv|' +
    'log|ini|env|cfg|conf|properties|plist|' +
    'sh|bash|zsh|fish|bat|cmd|ps1|' +
    'rs|go|java|kt|kts|swift|scala|rb|php|pl|pm|' +
    '[ch]pp?|cc|hh|mm|hpp|cs|fs|fsx|vb|' +
    'vue|svelte|elm|dart|ex|exs|erl|hrl|' +
    'ipynb|rmd|qmd|tex|bib|cls|sty|rst|adoc|org|' +
    'sql|graphql|proto|thrift|cmake|gradle|mk|' +
    'wasm|wat|lock|patch|diff|rej|har|drawio|vsix|' +
    'sqlite3?|db|duckdb|mdb|accdb|parquet|feather|arrow|orc|ndjson|' +
    'ttf|otf|woff2?|eot|apk|ipa|exe|msi|dmg|iso|pkg|deb|rpm|bin|so|dylib|dll|lib|o|a|map|' +
    'epub|mobi|azw3|chm|cert|pem|crt|cer|pub|asc|p12|pfx|keystore'
);

var _linkifyKnownExtRe = null;
function linkifyKnownExtRegex() {
    if (!_linkifyKnownExtRe) {
        _linkifyKnownExtRe = new RegExp('\\\\.(' + LINKIFY_EXT_FRAGMENT + ')\\\\b', 'i');
    }
    return _linkifyKnownExtRe;
}

/**
 * 以 / 开头的「工作区相对路径」是否做成可点击链接。
 * 仅允许带常见文件后缀的路径，避免 ARPU/DOU/MOU、日期 2024/01 等内联斜杠被当成目录。
 * （仍排除明显的 POSIX/Git Bash 根路径，以免误链。）
 */
function workspaceRelativePathAutoLinkOk(slashPath) {
    var t = linkifyNormalizePathToken(String(slashPath || '').trim());
    if (!t || t.charAt(0) !== '/' || t.charAt(1) === '/') return false;
    var posixTop = /^\\/(mingw\\d*|usr|bin|etc|proc|dev|sys|opt|var|run|lib|lib64|snap|sbin|boot|srv|tmp|media|mnt)(\\/|$)/i;
    var msysDrive = /^\\/[a-z](\\/|$)/i;
    var webish = /^\\/(api|v\\d+|static|assets|node_modules)(\\/|$)/i;
    if (posixTop.test(t) || msysDrive.test(t) || webish.test(t)) return false;
    return linkifyKnownExtRegex().test(t);
}

function workspaceRelativePathNoSlashAutoLinkOk(relPath) {
    var t = linkifyNormalizePathToken(String(relPath || '').trim());
    if (!t || t.charAt(0) === '/' || t.charAt(0) === '\\\\' || /^https?:\\/\\//i.test(t)) return false;
    if (/^([A-Za-z]):[\\\\/]/.test(t) || /^\\\\\\\\/.test(t)) return false;
    if (!/[\\\\/]/.test(t)) return false;
    if (/[<>:'"|\\r\\n]/.test(t)) return false;
    if (/(^|[\\\\/])\\.{1,2}([\\\\/]|$)/.test(t)) return false;
    return linkifyKnownExtRegex().test(t);
}

function workspaceRelFromNormalizedAbs(absNorm, workDir) {
    if (!absNorm || !workDir) return null;
    var base = String(workDir).replace(/\\\\/g, '/').replace(/\\/+$/, '');
    var absLower = absNorm.toLowerCase();
    var baseLower = base.toLowerCase();
    if (absLower === baseLower) return '';
    if (absLower.indexOf(baseLower + '/') === 0) {
        return absNorm.slice(base.length).replace(/^\\/+/, '');
    }
    return null;
}

function workspaceRelFromForeignWorkspaceAbs(absNorm, workDir) {
    if (!absNorm || !workDir) return null;
    var baseName = String(workDir || '').replace(/\\\\/g, '/').replace(/\\/+$/, '').split('/').filter(Boolean).pop();
    if (!baseName) return null;
    var parts = String(absNorm || '').replace(/\\\\/g, '/').split('/').filter(Boolean);
    for (var i = parts.length - 2; i >= 0; i -= 1) {
        if (parts[i].toLowerCase() === baseName.toLowerCase()) {
            return parts.slice(i + 1).join('/');
        }
    }
    return null;
}

function stripWorkspaceRootPrefixFromRelPath(relPath) {
    var t = String(relPath || '').replace(/\\\\/g, '/').replace(/^\\/+/, '');
    var w = (typeof window.__WORK_DIR__ === 'string') ? window.__WORK_DIR__ : '';
    var baseName = String(w || '').replace(/\\\\/g, '/').replace(/\\/+$/, '').split('/').filter(Boolean).pop();
    if (baseName && t.toLowerCase().indexOf(baseName.toLowerCase() + '/') === 0) {
        return t.slice(baseName.length + 1);
    }
    return t;
}

function getCurrentSessionDataPath() {
    var sdir = (typeof window.__SESSIONS_DIR__ === 'string') ? window.__SESSIONS_DIR__ : '';
    if (sdir && currentSessionId) return pathJoinBaseName(sdir, currentSessionId);
    var w = (typeof window.__WORK_DIR__ === 'string') ? window.__WORK_DIR__ : '';
    if (w && currentSessionId) return pathJoinBaseName(pathJoinBaseName(w, 'sessions'), currentSessionId);
    return '';
}

/** 标题栏与侧栏：工作目录绝对路径与会话 ID（与服务端 window.__WORK_DIR__ 一致） */
function buildSessionWorkspaceSubtitle(sessionId) {
    var w = (typeof window.__WORK_DIR__ === 'string') ? window.__WORK_DIR__ : '';
    if (!sessionId) return w || '';
    if (w) {
        var workspaceLink = '<a href="#" data-workspace-open="' + w + '" class="msg-link-workspace-open" style="color:inherit;text-decoration:inherit;cursor:pointer;" data-ui-tip="打开工作目录">' + w + '</a>';
        var sessionPath = 'sessions/' + sessionId;
        var sessionLink = '<a href="#" data-workspace-open="' + sessionPath + '" class="msg-link-workspace-open" style="color:inherit;text-decoration:inherit;cursor:pointer;" data-ui-tip="打开会话目录">' + sessionId + '</a>';
        return workspaceLink + ' | ' + sessionLink;
    }
    return String(sessionId);
}

/** 侧栏每条会话标题下方：最近一次用户提问（服务端字段 last_user_preview） */
function formatSessionListSubtitle(sess) {
    if (!sess) return '暂无提问';
    var t = sess.last_user_preview != null ? String(sess.last_user_preview).trim() : '';
    return t || '暂无提问';
}

/** 侧栏每条会话标题下方第二行：最后修改日期时间 */
function formatSessionListDate(sess) {
    if (!sess) return '';
    var raw = sess.last_activity_at || sess.updated_at || sess.created_at || '';
    var ts = Date.parse(String(raw));
    if (!Number.isFinite(ts)) {
        var numeric = Number(raw);
        if (Number.isFinite(numeric) && numeric > 0) ts = numeric;
    }
    if (!Number.isFinite(ts) || ts <= 0) return '';
    var d = new Date(ts);
    var now = new Date();
    var pad = function (v) { return String(v).padStart(2, '0'); };
    var time = pad(d.getHours()) + ':' + pad(d.getMinutes());
    if (d.toDateString() === now.toDateString()) return '今天 ' + time;
    var yesterday = new Date(now.getTime() - 86400000);
    if (d.toDateString() === yesterday.toDateString()) return '昨天 ' + time;
    var prefix = d.getFullYear() === now.getFullYear() ? '' : (d.getFullYear() + '年');
    return prefix + (d.getMonth() + 1) + '月' + d.getDate() + '日 ' + time;
}

function sessionDateIcon() {
    return '<svg viewBox="0 0 24 24" width="11" height="11" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/></svg>';
}

/** 与服务端 _normalize_sidebar_preview_text 对齐：折叠空白、180 字符、省略号 */
function normalizeSidebarPreviewText(text, maxLen) {
    maxLen = maxLen || 180;
    var s = String(text || '').trim();
    if (!s) return '';
    var oneLine = s.split(/\\s+/).join(' ');
    if (oneLine.length > maxLen) return oneLine.slice(0, maxLen - 1) + '\\u2026';
    return oneLine;
}

/** 发送后立即更新侧栏「最近提问」（与服务器摘要规则一致）；稍后 refreshSingleSessionRow 仍会校正 */
function updateSidebarLastUserPreviewImmediate(sessionId, questionText) {
    if (!sessionId || !sessionsList) return;
    var nameEl = sessionsList.querySelector('.session-name[data-id="' + sessionId + '"]');
    var div = nameEl && nameEl.closest('.session-item');
    if (!div) return;
    var wsEl = div.querySelector('.session-last-query');
    if (!wsEl) return;
    var line = normalizeSidebarPreviewText(questionText, 180);
    if (!line) line = '暂无提问';
    wsEl.textContent = line;
    wsEl.setAttribute('data-ui-tip', line);
    bindUiHoverTip(wsEl);
    var dateEl = div.querySelector('.session-item-date');
    if (dateEl) {
        var dateLine = formatSessionListDate({ last_activity_at: new Date().toISOString() });
        if (dateLine) {
            dateEl.innerHTML = sessionDateIcon() + dateLine;
            dateEl.setAttribute('data-ui-tip', dateLine);
            bindUiHoverTip(dateEl);
        } else {
            dateEl.textContent = '';
        }
    }
}

function updateSessionTitle() {
    const br = document.getElementById('breadcrumb-text');
    const sub = document.getElementById('breadcrumb-sub');
    if (!br || !sub) return;
    if (!currentSessionId) {
        br.textContent = '未选择会话';
        sub.textContent = '';
        setContextTokenLabel(null, null);
        return;
    }
    const sess = selectCurrentSession();
    const el = document.querySelector('.session-name[data-id="' + currentSessionId + '"]');
    const raw = sess && sess.name != null ? String(sess.name) : (el ? (el.getAttribute('data-original') || el.textContent || '') : '');
    const name = (raw && raw.trim()) ? raw.trim() : 'Session';
    br.textContent = name;
    sub.innerHTML = buildSessionWorkspaceSubtitle(currentSessionId);
    initUiHoverTips(sub);
}

function ensureMermaidInitialized(api) {
    var mermaidApi = api || window.mermaid;
    if (mermaidInitialized || !mermaidApi) return;
    try {
        var light = document.documentElement.classList.contains('theme-light');
        mermaidApi.initialize({
            startOnLoad: false,
            theme: light ? 'neutral' : 'dark',
            securityLevel: 'loose',
            themeVariables: {
                fontSize: '11px',
                fontFamily: 'Plus Jakarta Sans, system-ui, sans-serif',
            },
            flowchart: { htmlLabels: true, curve: 'basis' },
            sequence: { useMaxWidth: true },
        });
        mermaidInitialized = true;
    } catch (e) { /* ignore */ }
}

/**
 * flowchart 节点 E[文本] 内若含 <br> 且又含裸引号 "，Mermaid 10.9 会报 got 'STR'。
 * 将此类标签整体包成 ["..."] 并转义内部 ASCII 引号。
 */
function fixFlowchartBracketLabelsWithLineBreak(text) {
    return text.replace(/\\[[^\\]\\n\\r]*<br\\s*\\/?[^\\]\\n\\r]*\\]/gi, function (match) {
        var inner = match.slice(1, -1);
        var s = inner.trim();
        if (!s) return match;
        if (s.charAt(0) === '"' && s.charAt(s.length - 1) === '"') return match;
        var escaped = s.replace(/\\\\/g, '\\\\\\\\').replace(/"/g, '\\\\"');
        return '["' + escaped + '"]';
    });
}

/** 未用引号包裹的 [] 节点里出现裸 " 时同样会触发词法错误 */
function fixFlowchartBracketLabelsWithRawQuotes(text) {
    return text.replace(/\\[[^\\]\\n\\r]*"[^\\]\\n\\r]*\\]/g, function (match) {
        var inner = match.slice(1, -1);
        var s = inner.trim();
        if (!s) return match;
        if (s.charAt(0) === '"' && s.charAt(s.length - 1) === '"') return match;
        var escaped = s.replace(/\\\\/g, '\\\\\\\\').replace(/"/g, '\\\\"');
        return '["' + escaped + '"]';
    });
}

/** 去除 LLM/粘贴带来的杂讯，减少 Mermaid 10.9+ 报 Syntax error in text */
function normalizeMermaidSource(raw) {
    var t = String(raw || '')
        .replace(/^\\uFEFF/, '')
        .replace(/\\u200b|\\u200c|\\u200d/g, '')
        .replace(/\\r\\n/g, '\\n')
        .replace(/\\r/g, '\\n');
    t = t.replace(/^\\s*\`\`\`(?:mermaid)?\\s*\\n/i, '');
    t = t.replace(/\\n\\s*\`\`\`\\s*$/i, '');
    t = t.replace(/[\\u201C\\u201D\\u201E\\u00AB\\u00BB]/g, '"');
    t = t.replace(/<br\\s*\\/?>/gi, '<br/>');
    t = fixFlowchartBracketLabelsWithLineBreak(t);
    t = fixFlowchartBracketLabelsWithRawQuotes(t);
    var lines = t.split('\\n');
    if (lines.length && lines[0]) {
        lines[0] = lines[0].replace(/\\s*[\\uFF1A：]\\s*$/, '');
    }
    t = lines.map(function (line) { return line.replace(/\\s+$/g, ''); }).join('\\n').trim();
    return t;
}

function showMermaidRenderError(el, source, err) {
    el.classList.add('mermaid-error');
    el.removeAttribute('data-processed');
    var msg = 'Mermaid 无法解析此图';
    if (err) {
        if (typeof err === 'string') msg = err;
        else if (err.str) msg = String(err.str);
        else if (err.message) msg = String(err.message);
    }
    el.innerHTML = '<div class="mermaid-error-msg">' + escapeHtml(msg) + '</div>'
        + '<pre class="mermaid-raw">' + escapeHtml(source) + '</pre>';
}

var MERMAID_DOWNLOAD_SVG = '<svg viewBox="0 0 24 24" width="15" height="15" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><path d="M7 10l5 5 5-5"/><path d="M12 15V3"/></svg>';
var MERMAID_ZOOM_SVG = '<svg viewBox="0 0 24 24" width="15" height="15" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M15 3h6v6"/><path d="M21 3l-7 7"/><path d="M9 21H3v-6"/><path d="M3 21l7-7"/></svg>';
var mermaidZoomKeyHandler = null;

function closeMermaidZoom() {
    var root = document.getElementById('mermaid-zoom-root');
    if (!root) return;
    root.classList.remove('is-open');
    root.setAttribute('aria-hidden', 'true');
    root.innerHTML = '';
    if (mermaidZoomKeyHandler) {
        document.removeEventListener('keydown', mermaidZoomKeyHandler);
        mermaidZoomKeyHandler = null;
    }
}

function ensureMermaidZoomRoot() {
    var root = document.getElementById('mermaid-zoom-root');
    if (root) return root;
    root = document.createElement('div');
    root.id = 'mermaid-zoom-root';
    root.className = 'mermaid-zoom-overlay';
    root.setAttribute('aria-hidden', 'true');
    document.body.appendChild(root);
    return root;
}

function openMermaidZoom(sourceEl) {
    if (!sourceEl) return;
    var svg = sourceEl.querySelector('svg');
    if (!svg) return;
    var root = ensureMermaidZoomRoot();
    var clone = svg.cloneNode(true);
    clone.removeAttribute('style');
    clone.setAttribute('preserveAspectRatio', 'xMidYMid meet');
    clone.classList.add('mermaid-zoom-svg');
    root.innerHTML = '';

    var panel = document.createElement('div');
    panel.className = 'mermaid-zoom-panel';
    panel.setAttribute('role', 'dialog');
    panel.setAttribute('aria-modal', 'true');
    panel.setAttribute('aria-label', 'Mermaid 流程图放大预览');

    var closeBtn = document.createElement('button');
    closeBtn.type = 'button';
    closeBtn.className = 'mermaid-zoom-close';
    closeBtn.setAttribute('aria-label', '关闭放大预览');
    closeBtn.setAttribute('data-ui-tip', '关闭');
    closeBtn.innerHTML = '<svg viewBox="0 0 24 24" width="17" height="17" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M18 6 6 18"/><path d="m6 6 12 12"/></svg>';

    var stage = document.createElement('div');
    stage.className = 'mermaid-zoom-stage';
    stage.appendChild(clone);
    panel.appendChild(closeBtn);
    panel.appendChild(stage);
    root.appendChild(panel);

    closeBtn.onclick = closeMermaidZoom;
    root.onclick = function (e) {
        if (e.target === root) closeMermaidZoom();
    };
    mermaidZoomKeyHandler = function (e) {
        if (e.key === 'Escape') {
            e.preventDefault();
            closeMermaidZoom();
        }
    };
    document.addEventListener('keydown', mermaidZoomKeyHandler);
    root.classList.add('is-open');
    root.setAttribute('aria-hidden', 'false');
    initUiHoverTips(root);
    requestAnimationFrame(function () { closeBtn.focus(); });
}

function getMermaidSvgSize(svg) {
    var box = svg && svg.viewBox && svg.viewBox.baseVal ? svg.viewBox.baseVal : null;
    var w = box && box.width ? box.width : 0;
    var h = box && box.height ? box.height : 0;
    if (!w || !h) {
        var rect = svg.getBoundingClientRect ? svg.getBoundingClientRect() : null;
        w = rect && rect.width ? rect.width : w;
        h = rect && rect.height ? rect.height : h;
    }
    w = Math.max(1, Math.ceil(w || 1200));
    h = Math.max(1, Math.ceil(h || 800));
    return { width: w, height: h };
}

function triggerDownloadBlob(blob, filename) {
    if (!blob) return;
    var url = URL.createObjectURL(blob);
    var a = document.createElement('a');
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    a.remove();
    setTimeout(function () { URL.revokeObjectURL(url); }, 1000);
}

function downloadMermaidPng(sourceEl) {
    if (!sourceEl) return;
    var svg = sourceEl.querySelector('svg');
    if (!svg) return;
    var size = getMermaidSvgSize(svg);
    var clone = svg.cloneNode(true);
    clone.setAttribute('xmlns', 'http://www.w3.org/2000/svg');
    clone.setAttribute('width', String(size.width));
    clone.setAttribute('height', String(size.height));
    if (!clone.getAttribute('viewBox')) clone.setAttribute('viewBox', '0 0 ' + size.width + ' ' + size.height);
    var xml = new XMLSerializer().serializeToString(clone);
    var svgBlob = new Blob([xml], { type: 'image/svg+xml;charset=utf-8' });
    var url = URL.createObjectURL(svgBlob);
    var img = new Image();
    img.onload = function () {
        try {
            var scale = Math.min(3, Math.max(1, window.devicePixelRatio || 1));
            var canvas = document.createElement('canvas');
            canvas.width = Math.ceil(size.width * scale);
            canvas.height = Math.ceil(size.height * scale);
            var ctx = canvas.getContext('2d');
            if (!ctx) throw new Error('canvas unavailable');
            ctx.scale(scale, scale);
            ctx.fillStyle = document.documentElement.classList.contains('theme-light') ? '#ffffff' : '#1e1e2e';
            ctx.fillRect(0, 0, size.width, size.height);
            ctx.drawImage(img, 0, 0, size.width, size.height);
            canvas.toBlob(function (blob) {
                triggerDownloadBlob(blob, 'mermaid-' + new Date().toISOString().replace(/[:.]/g, '-') + '.png');
            }, 'image/png');
        } catch (e) {
            triggerDownloadBlob(svgBlob, 'mermaid-' + new Date().toISOString().replace(/[:.]/g, '-') + '.svg');
        } finally {
            URL.revokeObjectURL(url);
        }
    };
    img.onerror = function () {
        URL.revokeObjectURL(url);
        triggerDownloadBlob(svgBlob, 'mermaid-' + new Date().toISOString().replace(/[:.]/g, '-') + '.svg');
    };
    img.src = url;
}

function enhanceMermaidZoom(el) {
    if (!el || el.classList.contains('mermaid-error')) return;
    if (el.querySelector('.mermaid-zoom-btn')) return;
    if (!el.querySelector('svg')) return;
    el.classList.add('mermaid-has-zoom');
    var downloadBtn = document.createElement('button');
    downloadBtn.type = 'button';
    downloadBtn.className = 'mermaid-download-btn';
    downloadBtn.setAttribute('aria-label', '下载保存 Mermaid 流程图为图片');
    downloadBtn.setAttribute('data-ui-tip', '下载图片');
    downloadBtn.innerHTML = MERMAID_DOWNLOAD_SVG;
    downloadBtn.addEventListener('click', function (e) {
        e.preventDefault();
        e.stopPropagation();
        downloadMermaidPng(el);
    });
    var btn = document.createElement('button');
    btn.type = 'button';
    btn.className = 'mermaid-zoom-btn';
    btn.setAttribute('aria-label', '放大显示 Mermaid 流程图');
    btn.setAttribute('data-ui-tip', '放大显示');
    btn.innerHTML = MERMAID_ZOOM_SVG;
    btn.addEventListener('click', function (e) {
        e.preventDefault();
        e.stopPropagation();
        openMermaidZoom(el);
    });
    el.appendChild(downloadBtn);
    el.appendChild(btn);
    initUiHoverTips(el);
}

function upgradeMermaidBlocks(root) {
    if (!root) return;
    root.querySelectorAll('pre > code').forEach(function (codeEl) {
        var cls = codeEl.getAttribute('class') || '';
        if (!/\\bmermaid\\b/.test(cls)) return;
        var pre = codeEl.parentNode;
        if (!pre || pre.tagName !== 'PRE') return;
        var div = document.createElement('div');
        div.className = 'mermaid';
        div.textContent = normalizeMermaidSource(codeEl.textContent || '');
        pre.parentNode.replaceChild(div, pre);
    });
}

/** 无盘符、无路径分隔符的「纯文件名 + 已知后缀」→ 相对工作区根解析 */
function makeHrefFromAutoLinkToken(s) {
    var t = cleanPathTokenForLink(s);
    if (!t) return null;
    if (/^https?:\\/\\//i.test(t)) return t;
    var m = /^([A-Za-z]):[\\\\/](.*)$/.exec(t);
    if (m) {
        var rest = (m[2] || '').replace(/\\\\/g, '/');
        return fileUrlFromFsPath(m[1].toUpperCase() + ':/' + rest);
    }
    if (t.charAt(0) === '/' && t.charAt(1) !== '/') {
        var unixWorkDir = (typeof window.__WORK_DIR__ === 'string') ? window.__WORK_DIR__.replace(/\\/+$/, '') : '';
        if (unixWorkDir.charAt(0) === '/' && (t === unixWorkDir || t.indexOf(unixWorkDir + '/') === 0)) {
            return fileUrlFromFsPath(t);
        }
        if (!workspaceRelativePathAutoLinkOk(t)) return null;
        var w = (typeof window.__WORK_DIR__ === 'string') ? window.__WORK_DIR__ : '';
        var abs = joinWorkDirAndRelativeSlashPath(w, t);
        if (abs) return fileUrlFromFsPath(abs);
    }
    if (workspaceRelativePathNoSlashAutoLinkOk(t)) {
        var wr = (typeof window.__WORK_DIR__ === 'string') ? window.__WORK_DIR__ : '';
        if (!wr) return null;
        var absRel = pathJoinBaseName(wr, t.replace(/\\\\/g, '/'));
        if (absRel) return fileUrlFromFsPath(absRel);
    }
    return null;
}

/**
 * 解析为可交给 /api/open-workspace-file 的路径：工作区相对、Windows/UNC 绝对路径（均由服务端校验须在 WORK_DIR 内）。
 */
function pathTokenToWorkspaceOpenRel(token) {
    var t = cleanPathTokenForLink(token);
    if (!t || /^https?:\\/\\//i.test(t)) return null;
    var w = (typeof window.__WORK_DIR__ === 'string') ? window.__WORK_DIR__ : '';
    var uncFlat = t.replace(/\\//g, '\\\\');
    if (/^\\\\\\\\([^\\\\]+)\\\\([^\\\\]+)/i.test(uncFlat)) {
        return uncFlat;
    }
    var win = /^([A-Za-z]):[\\\\/](.*)$/.exec(t);
    if (win) {
        var rest = (win[2] || '').replace(/\\\\/g, '/');
        var absNorm = (win[1].toUpperCase() + ':/' + rest).replace(/\\/+/g, '/');
        if (w) {
            var absRel = workspaceRelFromNormalizedAbs(absNorm, w);
            if (absRel != null) return absRel;
            var foreignRel = workspaceRelFromForeignWorkspaceAbs(absNorm, w);
            if (foreignRel != null) return foreignRel;
        }
        return absNorm;
    }
    if (!w) return null;
    var slashRooted = t.replace(/\\\\/g, '/');
    if (slashRooted.charAt(0) === '/' && slashRooted.charAt(1) !== '/') {
        var unixRoot = String(w || '').replace(/\\\\/g, '/').replace(/\\/+$/, '');
        if (unixRoot.charAt(0) === '/'
            && (slashRooted === unixRoot || slashRooted.indexOf(unixRoot + '/') === 0)) {
            return slashRooted;
        }
        var wDrive = /^([A-Za-z]):[\\\\/]/.exec(String(w || ''));
        if (wDrive) {
            var rootedAbs = (wDrive[1].toUpperCase() + ':' + slashRooted).replace(/\\/+/g, '/');
            var rootedRel = workspaceRelFromNormalizedAbs(rootedAbs, w);
            if (rootedRel != null) return rootedRel;
        }
        if (!workspaceRelativePathAutoLinkOk(slashRooted)) return null;
        return slashRooted.replace(/^\\/+/, '');
    }
    if (t === '.env' && typeof window.__APP_DOTENV_PATH__ === 'string' && window.__APP_DOTENV_PATH__) {
        return window.__APP_DOTENV_PATH__;
    }
    var relPath = stripWorkspaceRootPrefixFromRelPath(t);
    if (workspaceRelativePathNoSlashAutoLinkOk(relPath)) return relPath;
    return null;
}

function decodeMarkdownHrefPathTarget(href) {
    var raw = String(href || '').trim();
    if (!raw) return '';
    try { raw = decodeURI(raw); } catch (e) { /* keep raw */ }
    raw = decodePathPercentEscapes(raw);
    try { raw = decodeURIComponent(raw); } catch (e2) { /* keep partially decoded raw */ }
    return stripPathWrappingQuotes(trimTrailingPathPunct(raw));
}

function markdownHrefToWorkspaceOpenRel(href) {
    var raw = decodeMarkdownHrefPathTarget(href);
    if (!raw || raw.charAt(0) === '#') return null;
    if (/^(https?|mailto|tel|javascript|data|blob):/i.test(raw)) return null;
    if (/^[A-Za-z][A-Za-z0-9+.-]*:/i.test(raw) && !/^[A-Za-z]:[\\\\/]/.test(raw) && !/^file:\\/\\//i.test(raw)) {
        return null;
    }
    var rel = pathTokenToWorkspaceOpenRel(raw);
    if (rel) return rel;
    if (/^file:\\/\\//i.test(raw)) {
        var fsPath = raw.replace(/^file:\\/\\/\\/?/i, '');
        fsPath = decodePathPercentEscapes(fsPath);
        if (/^[A-Za-z]:[\\\\/]/.test(fsPath)) return fsPath.replace(/\\\\/g, '/');
        return '/' + fsPath.replace(/^\\/+/, '').replace(/\\\\/g, '/');
    }
    if (/^[A-Za-z]:[\\\\/]/.test(raw) || /^\\\\\\\\/.test(raw)) return raw.replace(/\\\\/g, '/');
    if (/[\\\\/]/.test(raw)) return stripWorkspaceRootPrefixFromRelPath(raw);
    return stripWorkspaceRootPrefixFromRelPath(raw);
}

function workspaceOpenDisplayLabel(original, wsRel) {
    var rel = String(wsRel || '').replace(/\\\\/g, '/').replace(/\\/+$/, '');
    var name = rel.split('/').filter(Boolean).pop();
    if (name) return '@' + name;
    var raw = stripPathWrappingQuotes(trimTrailingPathPunct(original || ''));
    name = raw.replace(/\\\\/g, '/').replace(/\\/+$/, '').split('/').filter(Boolean).pop();
    return name ? ('@' + name) : raw;
}

function normalizeInputPathTokenIdentity(path) {
    var s = stripPathWrappingQuotes(String(path || '').trim()).replace(/\\\\/g, '/').replace(/\\/+$/, '');
    if (/^[A-Za-z]:\\//.test(s) || /^\\/\\//.test(s)) return s.toLowerCase();
    return s;
}

function uniqueInputPathDisplayLabel(original, wsRel, preferredLabel) {
    var stored = stripPathWrappingQuotes(original || '');
    var storedIdentity = normalizeInputPathTokenIdentity(stored);
    if (!preferredLabel) preferredLabel = workspaceOpenDisplayLabel(original, wsRel);
    if (!preferredLabel) return '';
    if (!inputPathTokenMap[preferredLabel]
        || normalizeInputPathTokenIdentity(inputPathTokenMap[preferredLabel]) === storedIdentity) {
        return preferredLabel;
    }

    var rel = String(wsRel || '').replace(/\\\\/g, '/').replace(/^\\/+/, '').replace(/\\/+$/, '');
    var parts = rel.split('/').filter(Boolean);
    var candidates = [];
    if (parts.length >= 2) candidates.push('@' + parts.slice(-2).join('/'));
    if (parts.length >= 3) candidates.push('@' + parts.join('/'));
    candidates.push(preferredLabel + '#' + String(Object.keys(inputPathTokenMap).length + 1));

    for (var i = 0; i < candidates.length; i += 1) {
        var label = candidates[i];
        if (!inputPathTokenMap[label]
            || normalizeInputPathTokenIdentity(inputPathTokenMap[label]) === storedIdentity) {
            return label;
        }
    }
    return candidates[candidates.length - 1];
}

function workspaceOpenTipPath(original, wsRel) {
    var raw = cleanPathTokenForLink(original || '');
    if (/^[A-Za-z]:[\\\\/]/.test(raw) || /^\\\\\\\\/.test(raw)) return raw;
    if (raw.charAt(0) === '/' && raw.charAt(1) !== '/') return raw;
    var rel = String(wsRel || raw || '').replace(/\\\\/g, '/').replace(/^\\/+/, '');
    if (/^[A-Za-z]:\\//.test(rel) || /^\\\\\\\\/.test(rel)) return rel.replace(/\\//g, '\\\\');
    var w = (typeof window.__WORK_DIR__ === 'string') ? window.__WORK_DIR__ : '';
    if (!w || !rel) return rel || raw;
    var joined = pathJoinBaseName(w, rel);
    return String(w).charAt(0) === '/' ? joined : joined.replace(/\\//g, '\\\\');
}

function escapeRegExpLiteral(s) {
    return String(s || '').replace(/[.*+?^\${}()|[\\]\\\\]/g, '\\\\$&');
}

function quotePromptPath(p) {
    var t = stripPathWrappingQuotes(String(p || '').trim());
    if (!t) return '';
    return '"' + t.replace(/"/g, '\\\\"') + '"';
}

function inputQuotedWindowsPathRegex() {
    return /(["'])([A-Za-z]:[\\\\/][^"'\\r\\n]+)\\1/g;
}

var _inputKnownExtWinPathRe = null;
function inputKnownExtWindowsPathRegex() {
    if (!_inputKnownExtWinPathRe) {
        _inputKnownExtWinPathRe = new RegExp('(^|[\\\\s(（\\\\[])([A-Za-z]:[\\\\\\\\/][^\\\\r\\\\n"\\\\\\'<>|]+?\\\\.(' + LINKIFY_EXT_FRAGMENT + '))(?=$|[\\\\s,，。;；:：)）\\\\]】])', 'gi');
    }
    _inputKnownExtWinPathRe.lastIndex = 0;
    return _inputKnownExtWinPathRe;
}

function inputSimpleWindowsPathRegex() {
    return /(^|[\\s(（\\[])([A-Za-z]:(?:\\\\|\\/)(?:(?:[^\\\\/:*?"<>|\\s\\r\\n]+)(?:\\\\|\\/))*[^\\\\/:*?"<>|\\s\\r\\n]+)(?=$|[\\s,，。;；:：)）\\]】])/g;
}

function ensureInputPathChipHost() {
    var host = document.getElementById('input-path-chips');
    if (host || !messageInput) return host;
    var wrapper = messageInput.closest ? messageInput.closest('.input-wrapper') : null;
    var panel = wrapper && wrapper.parentNode;
    if (!panel || !wrapper) return null;
    host = document.createElement('div');
    host.id = 'input-path-chips';
    host.className = 'input-path-chips';
    panel.insertBefore(host, wrapper);
    return host;
}

function clearInputPathTokens() {
    Object.keys(inputPathTokenMap).forEach(function (k) { delete inputPathTokenMap[k]; });
    refreshInputPathChips();
}

function removeInputPathToken(label) {
    if (!label || !messageInput) return;
    delete inputPathTokenMap[label];
    var text = String(messageInput.value || '');
    var re = new RegExp('(?:\\\\s*)' + escapeRegExpLiteral(label), 'g');
    messageInput.value = text.replace(re, '').replace(/[ \\t]{2,}/g, ' ').trimStart();
    refreshInputPathChips();
    autoResizeTextarea();
    try { messageInput.focus(); } catch (e) {}
}

function refreshInputPathChips() {
    var host = ensureInputPathChipHost();
    if (!host || !messageInput) return;
    var text = String(messageInput.value || '');
    var labels = Object.keys(inputPathTokenMap).filter(function (label) {
        return label && text.indexOf(label) >= 0;
    });
    if (!labels.length) {
        host.innerHTML = '';
        host.classList.remove('is-visible');
        return;
    }
    host.innerHTML = '';
    labels.forEach(function (label) {
        var stored = inputPathTokenMap[label];
        var rel = pathTokenToWorkspaceOpenRel(stored);
        if (!rel) return;
        var chip = document.createElement('span');
        chip.className = 'input-path-chip';
        var a = document.createElement('a');
        a.href = '#';
        a.className = 'input-path-chip-link msg-link-workspace-open';
        a.dataset.workspaceOpen = rel;
        a.textContent = label;
        a.setAttribute('data-ui-tip', String(stored || rel));
        var rm = document.createElement('button');
        rm.type = 'button';
        rm.className = 'input-path-chip-remove';
        rm.setAttribute('aria-label', '移除 ' + label);
        rm.setAttribute('data-ui-tip', '移除文件路径');
        rm.textContent = '×';
        rm.addEventListener('click', function (ev) {
            ev.preventDefault();
            ev.stopPropagation();
            removeInputPathToken(label);
        });
        chip.appendChild(a);
        chip.appendChild(rm);
        host.appendChild(chip);
    });
    host.classList.toggle('is-visible', !!host.children.length);
}

function rewriteInputWorkspacePaths() {
    if (!messageInput || inputPathRewriteGuard) return;
    var raw = String(messageInput.value || '');
    var changed = false;
    function replacePathToken(match, prefix, path) {
        var rel = pathTokenToWorkspaceOpenRel(path);
        if (!rel) return match;
        var label = uniqueInputPathDisplayLabel(path, rel, workspaceOpenDisplayLabel(path, rel));
        if (!label) return match;
        inputPathTokenMap[label] = stripPathWrappingQuotes(path);
        changed = true;
        return (prefix || '') + label;
    }
    var next = raw.replace(inputQuotedWindowsPathRegex(), function (match, q, path) {
        return replacePathToken(match, '', path);
    });
    next = next.replace(inputKnownExtWindowsPathRegex(), function (match, prefix, path) {
        return replacePathToken(match, prefix, path);
    });
    next = next.replace(inputSimpleWindowsPathRegex(), function (match, prefix, path) {
        return replacePathToken(match, prefix, path);
    });
    if (changed && next !== raw) {
        var wasFocused = document.activeElement === messageInput;
        inputPathRewriteGuard = true;
        messageInput.value = next;
        if (wasFocused) {
            var pos = next.length;
            try { messageInput.setSelectionRange(pos, pos); } catch (e) {}
        }
        inputPathRewriteGuard = false;
    }
    refreshInputPathChips();
}

function expandInputPathTokens(text) {
    var out = String(text || '');
    Object.keys(inputPathTokenMap)
        .sort(function (a, b) { return b.length - a.length; })
        .forEach(function (label) {
            var stored = inputPathTokenMap[label];
            if (!stored || out.indexOf(label) < 0) return;
            out = out.replace(new RegExp(escapeRegExpLiteral(label), 'g'), quotePromptPath(stored));
        });
    return out;
}

/** 整段文本是否仅为可链转的 Windows 绝对路径（用于行内 code 内路径） */
function isEntireTextNodeWindowsPath(raw) {
    var t = cleanPathTokenForLink(raw);
    if (!t) return false;
    return /^([A-Za-z]):[\\\\/](?:(?:[^\\\\/:*?"<>|\\r\\n]+)(?:\\\\|\\/))*[^\\\\/:*?"<>|\\r\\n]+$/i.test(t);
}


/** 行内 code 内整段为 \`/工作区相对/路径.ext\` 时亦允许链转（否则反引号路径永不可点） */
function isEntireWorkspaceSlashPathLinkable(raw) {
    var t = cleanPathTokenForLink(raw);
    return workspaceRelativePathAutoLinkOk(t);
}

function isEntireWorkspaceRelativePathLinkable(raw) {
    var t = cleanPathTokenForLink(raw);
    return workspaceRelativePathNoSlashAutoLinkOk(t);
}

/** 行内 code 内整段为 UNC \\\\server\\share\\... 时允许「本机打开」链转 */
function isEntireTextNodeUncPath(raw) {
    var t = cleanPathTokenForLink(raw);
    if (!t) return false;
    var u = t.replace(/\\//g, '\\\\');
    return /^\\\\\\\\[^\\\\]+\\\\[^\\\\]+(?:\\\\[^\\\\]*)*$/i.test(u);
}

var _assistMsgLinkifyRe = null;
function getAssistMsgLinkifyRegex() {
    if (!_assistMsgLinkifyRe) {
        // 「/路径」前仅排除 ASCII 字母，避免 2023/文件、中文后接 / 等无法匹配；仍可抑制 ARPU/DOU（U 为字母）
        _assistMsgLinkifyRe = new RegExp(
            '((["\\'])(?:(?:[A-Za-z]:(?:\\\\\\\\|\\\\/)|\\\\\\\\\\\\\\\\|\\\\/(?![\\\\s\\\\/]))|(?=[^"\\'\\\\r\\\\n]*[\\\\\\\\/]))[^"\\'\\\\r\\\\n]+?\\\\.(?:' + LINKIFY_EXT_FRAGMENT + ')\\\\b\\\\2|' +
            'https?:\\\\/\\\\/[^\\\\s<>\\'"]+|' +
            '\\\\\\\\\\\\\\\\(?:(?:[^\\\\\\\\\\\\/:*?"<>|\\\\r\\\\n]+)\\\\\\\\)+(?:[^\\\\\\\\\\\\/:*?"<>|\\\\r\\\\n]+)|' +
            '[A-Za-z]:(?:\\\\\\\\|\\\\/)(?:(?:[^\\\\\\\\/:*?"<>|\\\\r\\\\n]+)(?:\\\\\\\\|\\\\/))*[^\\\\\\\\/:*?"<>|\\\\r\\\\n]+|' +
            '(?<![A-Za-z])\\\\/(?![\\\\s\\\\/])[^\\\\s<>\\'"]+|' +
            '(?<![A-Za-z0-9./\\\\\\\\])(?:[^\\\\s<>\\'"/\\\\\\\\:]+(?:[\\\\\\\\/][^\\\\s<>\\'"/\\\\\\\\:]+)+\\\\.(' + LINKIFY_EXT_FRAGMENT + ')\\\\b))',
            'gi'
        );
    }
    return _assistMsgLinkifyRe;
}

function tryLinkifyEntirePathTextNode(textNode, raw) {
    var token = String(raw || '').trim();
    if (!token) return false;
    var wsRel = pathTokenToWorkspaceOpenRel(token);
    var href = wsRel ? null : makeHrefFromAutoLinkToken(token);
    if (!wsRel && !href) return false;
    var a = document.createElement('a');
    a.className = wsRel ? 'msg-link-auto msg-link-workspace-open' : 'msg-link-auto';
    a.textContent = cleanPathTokenForLink(token) || token;
    if (wsRel) {
        a.href = '#';
        a.setAttribute('data-workspace-open', wsRel);
        a.setAttribute('data-ui-tip', workspaceOpenTipPath(token, wsRel));
        bindUiHoverTip(a);
    } else {
        a.href = href;
        a.target = '_blank';
        a.rel = 'noopener noreferrer';
    }
    textNode.parentNode.replaceChild(a, textNode);
    return true;
}

function linkifySingleTextNode(textNode) {
    var raw = textNode.nodeValue;
    if (!raw) return;
    var parent = textNode.parentElement;
    if (!parent || parent.closest('a, pre, script, style, textarea, svg')) return;
    var inInlineCode = !!parent.closest('code');
    if (inInlineCode) {
        if (!isEntireTextNodeWindowsPath(raw) && !isEntireWorkspaceSlashPathLinkable(raw) && !isEntireWorkspaceRelativePathLinkable(raw) && !isEntireTextNodeUncPath(raw)) return;
        if (tryLinkifyEntirePathTextNode(textNode, raw)) return;
    }
    var rawForLink = linkifyNormalizePathToken(raw);
    var re = getAssistMsgLinkifyRegex();
    re.lastIndex = 0;
    var parts = [];
    var last = 0;
    var m;
    while ((m = re.exec(rawForLink)) !== null) {
        var matchStart = m.index;
        var matchEnd = m.index + m[0].length;
        var qBefore = rawForLink.charAt(matchStart - 1);
        var qAfter = rawForLink.charAt(matchEnd);
        if ((qBefore === '"' || qBefore === "'") && qAfter === qBefore) {
            matchStart -= 1;
            matchEnd += 1;
        }
        if (matchStart > last) parts.push({ k: 't', s: rawForLink.slice(last, matchStart) });
        parts.push({ k: 'l', s: m[0] });
        last = matchEnd;
    }
    if (last < rawForLink.length) parts.push({ k: 't', s: rawForLink.slice(last) });
    var hasLink = false;
    for (var pi = 0; pi < parts.length; pi++) {
        if (parts[pi].k === 'l') { hasLink = true; break; }
    }
    if (!hasLink) return;
    var frag = document.createDocumentFragment();
    parts.forEach(function (p) {
        if (p.k === 't') frag.appendChild(document.createTextNode(p.s));
        else {
            var wsRel = pathTokenToWorkspaceOpenRel(p.s);
            var show = cleanPathTokenForLink(p.s);
            if (wsRel) {
                var aw = document.createElement('a');
                aw.href = '#';
                aw.setAttribute('data-workspace-open', wsRel);
                aw.className = 'msg-link-auto msg-link-workspace-open';
                aw.setAttribute('data-ui-tip', workspaceOpenTipPath(p.s, wsRel));
                bindUiHoverTip(aw);
                aw.textContent = show || p.s;
                frag.appendChild(aw);
            } else {
                var href = makeHrefFromAutoLinkToken(p.s);
                if (!href) frag.appendChild(document.createTextNode(p.s));
                else {
                    var ah = document.createElement('a');
                    ah.href = href;
                    ah.target = '_blank';
                    ah.rel = 'noopener noreferrer';
                    ah.className = 'msg-link-auto';
                    ah.textContent = show || p.s;
                    frag.appendChild(ah);
                }
            }
        }
    });
    textNode.parentNode.replaceChild(frag, textNode);
}

function upgradeWorkspacePathMarkdownLinks(root) {
    if (!root) return;
    root.querySelectorAll('span[data-ga-workspace-link]').forEach(function (span) {
        var rel = span.getAttribute('data-ga-workspace-link') || '';
        var raw = span.getAttribute('data-ga-workspace-raw') || rel;
        if (!rel) return;
        var a = document.createElement('a');
        a.href = '#';
        a.setAttribute('data-workspace-open', rel);
        a.className = 'msg-link-workspace-open';
        a.setAttribute('data-ui-tip', workspaceOpenTipPath(raw, rel));
        a.textContent = span.textContent || raw || rel;
        bindUiHoverTip(a);
        if (span.parentNode) span.parentNode.replaceChild(a, span);
    });
    root.querySelectorAll('a[href]').forEach(function (a) {
        if (!a || a.classList.contains('msg-link-workspace-open')) return;
        var href = a.getAttribute('href') || '';
        var originalPathForTip = '';
        var marker = /^#ga-workspace-path=(.+)$/i.exec(href);
        if (marker) {
            var markerValue = marker[1];
            var rawIdx = markerValue.indexOf('&raw=');
            if (rawIdx >= 0) {
                var relPart = markerValue.slice(0, rawIdx);
                var rawPart = markerValue.slice(rawIdx + 5);
                try { href = decodeURIComponent(relPart); } catch (e0) { href = relPart; }
                try { originalPathForTip = decodeURIComponent(rawPart); } catch (e1) { originalPathForTip = rawPart; }
            } else {
                try { href = decodeURIComponent(markerValue); } catch (e2) { href = markerValue; }
            }
        }
        var raw = href;
        try { raw = decodeURI(raw); } catch (e) {}
        var rel = markdownHrefToWorkspaceOpenRel(href);
        if (!rel && /^file:\\/\\//i.test(raw)) {
            var fsPath = raw.replace(/^file:\\/\\/\\/?/i, '');
            try { fsPath = decodeURIComponent(fsPath); } catch (e2) {}
            if (/^[A-Za-z]:\\//.test(fsPath)) rel = pathTokenToWorkspaceOpenRel(fsPath);
            else rel = pathTokenToWorkspaceOpenRel('/' + fsPath.replace(/^\\/+/, ''));
        }
        if (!rel) return;
        a.href = '#';
        a.setAttribute('data-workspace-open', rel);
        a.classList.add('msg-link-workspace-open');
        a.setAttribute('data-ui-tip', workspaceOpenTipPath(originalPathForTip || raw, rel));
        bindUiHoverTip(a);
    });
}

var _workspaceImageExtRe = null;
function workspaceImageExtRegex() {
    if (!_workspaceImageExtRe) {
        _workspaceImageExtRe = /\\.(png|jpe?g|gif|webp|bmp|svg|ico|tiff?|avif|jfif)(?:[?#].*)?$/i;
    }
    return _workspaceImageExtRe;
}

function workspaceImageRelFromMarker(value) {
    var raw = String(value || '').trim();
    var marker = /^#ga-workspace-path=(.+)$/i.exec(raw);
    if (marker) {
        var markerValue = marker[1];
        var rawIdx = markerValue.indexOf('&raw=');
        if (rawIdx >= 0) markerValue = markerValue.slice(0, rawIdx);
        try { raw = decodeURIComponent(markerValue); } catch (e) { raw = markerValue; }
    }
    var rel = markdownHrefToWorkspaceOpenRel(raw);
    if (!rel || !workspaceImageExtRegex().test(String(rel).replace(/\\\\/g, '/'))) return '';
    return rel;
}

function workspaceImageUrl(rel) {
    return '/api/workspace-image?rel=' + encodeURIComponent(String(rel || ''));
}

function wrapWorkspaceImageElement(img, rel) {
    if (!img || !rel || img.dataset.workspaceImageReady === '1') return;
    img.dataset.workspaceImageReady = '1';
    img.classList.add('msg-workspace-image');
    img.loading = 'lazy';
    img.decoding = 'async';
    img.src = workspaceImageUrl(rel);
    img.setAttribute('data-workspace-open', rel);
    img.setAttribute('data-ui-tip', '点击查看图片');
    bindUiHoverTip(img);
    var parent = img.parentElement;
    if (!parent || (parent.tagName === 'A' && parent.classList.contains('msg-workspace-image-link'))) return;
    var link = document.createElement('a');
    link.href = workspaceImageUrl(rel);
    link.target = '_blank';
    link.rel = 'noopener noreferrer';
    link.className = 'msg-workspace-image-link';
    link.setAttribute('data-workspace-open', rel);
    if (img.parentNode) img.parentNode.insertBefore(link, img);
    link.appendChild(img);
}

function standaloneImageLinkHost(a) {
    if (!a) return null;
    var host = a.parentElement;
    if (!host || !/^(P|DIV|LI)$/i.test(host.tagName || '')) return null;
    var linkText = String(a.textContent || '').trim();
    var hostText = String(host.textContent || '').trim();
    if (!linkText || hostText !== linkText) return null;
    return host;
}

function createWorkspaceImagePreview(rel, label) {
    var figure = document.createElement('figure');
    figure.className = 'msg-workspace-image-figure';
    var link = document.createElement('a');
    link.href = workspaceImageUrl(rel);
    link.target = '_blank';
    link.rel = 'noopener noreferrer';
    link.className = 'msg-workspace-image-link';
    link.setAttribute('data-workspace-open', rel);
    var img = document.createElement('img');
    img.className = 'msg-workspace-image';
    img.src = workspaceImageUrl(rel);
    img.loading = 'lazy';
    img.decoding = 'async';
    img.alt = String(label || rel || 'image');
    link.appendChild(img);
    figure.appendChild(link);
    var caption = document.createElement('figcaption');
    caption.textContent = String(label || rel || '');
    figure.appendChild(caption);
    return figure;
}

function upgradeWorkspaceImages(root) {
    if (!root) return;
    root.querySelectorAll('img[src]').forEach(function (img) {
        var rel = workspaceImageRelFromMarker(img.getAttribute('src') || '');
        if (rel) wrapWorkspaceImageElement(img, rel);
    });
    root.querySelectorAll('a.msg-link-workspace-open[data-workspace-open]').forEach(function (a) {
        if (a.dataset.workspaceImagePreview === '1') return;
        var rel = a.getAttribute('data-workspace-open') || '';
        if (!workspaceImageExtRegex().test(String(rel).replace(/\\\\/g, '/'))) return;
        var host = standaloneImageLinkHost(a);
        if (!host || host.querySelector('.msg-workspace-image-figure')) return;
        a.dataset.workspaceImagePreview = '1';
        var figure = createWorkspaceImagePreview(rel, a.textContent || rel);
        host.parentNode.insertBefore(figure, host.nextSibling);
    });
}

function linkifyAssistantTextNodes(root) {
    if (!root) return;
    upgradeWorkspacePathMarkdownLinks(root);
    var walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT);
    var batch = [];
    var n;
    while ((n = walker.nextNode())) {
        var p = n.parentElement;
        if (!p || p.closest('a, pre, script, style, textarea, .mermaid')) continue;
        if (p.closest('code') && !isEntireTextNodeWindowsPath(n.nodeValue) && !isEntireWorkspaceSlashPathLinkable(n.nodeValue) && !isEntireWorkspaceRelativePathLinkable(n.nodeValue) && !isEntireTextNodeUncPath(n.nodeValue)) continue;
        var nv = n.nodeValue;
        var nvNorm = linkifyNormalizePathToken(nv);
        if (!nv || (!/https?:\\/\\/|["'][A-Za-z]:[\\\\/]|[A-Za-z]:[\\\\/]|\\/\\S/.test(nvNorm) && !nvNorm.startsWith('\\\\\\\\') && !linkifyKnownExtRegex().test(nvNorm))) continue;
        batch.push(n);
    }
    batch.forEach(linkifySingleTextNode);
}

function ensureExternalMessageLinksOpenInNewTab(root) {
    if (!root || !root.querySelectorAll) return;
    root.querySelectorAll('a[href]').forEach(function (a) {
        if (!a || a.hasAttribute('data-workspace-open')) return;
        var href = String(a.getAttribute('href') || '').trim();
        if (!/^(https?:)?\\/\\//i.test(href)) return;
        a.target = '_blank';
        var rel = String(a.getAttribute('rel') || '').trim();
        var tokens = rel ? rel.split(/\\s+/) : [];
        ['noopener', 'noreferrer'].forEach(function (token) {
            if (tokens.indexOf(token) < 0) tokens.push(token);
        });
        a.setAttribute('rel', tokens.join(' '));
    });
}

function scheduleMermaidRun(root) {
    registerMermaidLazy(root);
}

async function runMermaidElementOnce(el) {
    if (!el || !el.isConnected) return;
    if (el.getAttribute('data-processed') === 'true'
        || el.getAttribute('data-mermaid-loading') === 'true'
        || el.classList.contains('mermaid-error')) return;
    el.setAttribute('data-mermaid-loading', 'true');
    try {
        var mermaidApi = window.mermaid;
        if (!mermaidApi) {
            if (typeof globalThis.loadMyAgentMermaid !== 'function') {
                throw new Error('Mermaid renderer is unavailable');
            }
            mermaidApi = await globalThis.loadMyAgentMermaid();
        }
        if (!el.isConnected) return;
        ensureMermaidInitialized(mermaidApi);
        var cleaned = normalizeMermaidSource(el.textContent || '');
        if (!cleaned) return;
        el.textContent = cleaned;
        if (!el.id) el.id = 'mermaid-embed-' + (++mermaidIdSeq);
        try {
            await mermaidApi.parse(cleaned);
        } catch (errParse) {
            showMermaidRenderError(el, cleaned, errParse);
            return;
        }
        try {
            await mermaidApi.run({ nodes: [el], suppressErrors: false });
            enhanceMermaidZoom(el);
        } catch (errRun) {
            showMermaidRenderError(el, cleaned, errRun);
        }
    } catch (errLoad) {
        showMermaidRenderError(el, normalizeMermaidSource(el.textContent || ''), errLoad);
    } finally {
        el.removeAttribute('data-mermaid-loading');
    }
}

function ensureMermaidIoObserver() {
    if (mermaidIoObserver || typeof IntersectionObserver === 'undefined') return null;
    mermaidIoObserver = new IntersectionObserver(function (entries) {
        entries.forEach(function (en) {
            if (!en.isIntersecting) return;
            var el = en.target;
            if (!el.classList.contains('mermaid') || el.getAttribute('data-processed') === 'true') {
                if (mermaidIoObserver) mermaidIoObserver.unobserve(el);
                return;
            }
            if (mermaidIoObserver) mermaidIoObserver.unobserve(el);
            runMermaidElementOnce(el);
        });
    }, { root: null, rootMargin: '100px 0px 160px 0px', threshold: 0 });
    return mermaidIoObserver;
}

function registerMermaidLazy(root) {
    if (!root) return;
    var nodes = Array.from(root.querySelectorAll('.mermaid:not([data-processed]):not(.mermaid-error)'));
    if (!nodes.length) return;
    var obs = ensureMermaidIoObserver();
    if (!obs) {
        requestAnimationFrame(function () {
            (async function () {
                for (var i = 0; i < nodes.length; i += 1) {
                    await runMermaidElementOnce(nodes[i]);
                }
            })();
        });
        return;
    }
    nodes.forEach(function (el) {
        try {
            obs.observe(el);
        } catch (e) {
            runMermaidElementOnce(el);
        }
    });
}

function wrapMessageTables(container) {
    if (!container) return;
    container.querySelectorAll('table').forEach(function (table) {
        var parent = table.parentElement;
        if (parent && parent.classList && parent.classList.contains('msg-table-scroll')) return;
        var wrap = document.createElement('div');
        wrap.className = 'msg-table-scroll';
        if (table.parentNode) table.parentNode.insertBefore(wrap, table);
        wrap.appendChild(table);
    });
}

function unwrapMarkdownDelTags(container) {
    if (!container) return;
    container.querySelectorAll('del').forEach(function (el) {
        var parent = el.parentNode;
        if (!parent) return;
        while (el.firstChild) parent.insertBefore(el.firstChild, el);
        parent.removeChild(el);
    });
}

function enhanceAssistantMessageContent(div) {
    if (!div) return;
    unwrapMarkdownDelTags(div);
    wrapMessageTables(div);
    upgradeMermaidBlocks(div);
    linkifyAssistantTextNodes(div);
    upgradeWorkspaceImages(div);
    ensureExternalMessageLinksOpenInNewTab(div);
    scheduleMermaidRun(div);
}

let markedOptionsApplied = false;
function encodeMarkdownWorkspacePathLinkMatch(match, label, dest) {
    var rawDest = String(dest || '').trim();
    if (!rawDest || rawDest.charAt(0) === '#') return match;
    var decodedDest = decodeMarkdownHrefPathTarget(rawDest);
    if (!decodedDest || /^(https?|mailto|tel|javascript|data|blob):/i.test(decodedDest)) return match;
    if (/^[A-Za-z][A-Za-z0-9+.-]*:/i.test(decodedDest) && !/^[A-Za-z]:[\\\\/]/.test(decodedDest) && !/^file:\\/\\//i.test(decodedDest)) return match;
    var rel = markdownHrefToWorkspaceOpenRel(decodedDest);
    if (!rel) return match;
    return '<span data-ga-workspace-link="' + escapeHtmlAttr(rel) + '" data-ga-workspace-raw="' + escapeHtmlAttr(decodedDest) + '">' + escapeHtml(label) + '</span>';
}

function stripMarkdownPathLinkWrapper(s) {
    var t = String(s || '').trim();
    var changed = true;
    var pairs = [
        ['**', '**'],
        ['__', '__'],
        ['~~', '~~'],
        ['\`', '\`'],
        ['*', '*'],
        ['_', '_'],
        ['"', '"'],
        ["'", "'"],
        ['“', '”'],
        ['‘', '’']
    ];
    while (changed && t.length >= 2) {
        changed = false;
        for (var i = 0; i < pairs.length; i += 1) {
            var open = pairs[i][0];
            var close = pairs[i][1];
            if (t.length > open.length + close.length && t.indexOf(open) === 0 && t.slice(-close.length) === close) {
                t = t.slice(open.length, t.length - close.length).trim();
                changed = true;
                break;
            }
        }
    }
    return t;
}

function normalizeExplicitMarkdownPathLinkMatch(match, label, dest) {
    var cleanLabel = stripMarkdownPathLinkWrapper(label);
    var cleanDest = stripMarkdownPathLinkWrapper(dest);
    if (!cleanDest || !markdownHrefToWorkspaceOpenRel(cleanDest)) return match;
    return '[' + cleanLabel + '](' + cleanDest + ')';
}

function normalizeExplicitMarkdownPathLinksInPlainText(text) {
    return String(text || '')
        .replace(/([\`*_~]{1,2})\\[([^\\]\\r\\n]+)\\]\\(([^)\\r\\n]+)\\)\\1/g, function (match, wrap, label, dest) {
            return normalizeExplicitMarkdownPathLinkMatch(match, label, dest);
        })
        .replace(/([\`*_~]{1,2})\\[([^\\]\\r\\n]+)\\]\\1\\(([^)\\r\\n]+)\\)/g, function (match, wrap, label, dest) {
            return normalizeExplicitMarkdownPathLinkMatch(match, label, dest);
        })
        .replace(/\\[([^\\]\\r\\n]+)\\]([\`*_~]{1,2})\\(([^)\\r\\n]+)\\)\\2/g, function (match, label, wrap, dest) {
            return normalizeExplicitMarkdownPathLinkMatch(match, label, dest);
        })
        .replace(/\\[([^\\]\\r\\n]+)\\]\\(([^)\\r\\n]+)\\)/g, normalizeExplicitMarkdownPathLinkMatch);
}

function normalizeExplicitMarkdownPathLinksOutsideFences(text) {
    var src = String(text || '');
    var out = '';
    var buf = '';
    var inFence = false;
    var fenceMarker = '';
    var lineStart = true;
    function flushPlain() {
        if (buf) {
            out += normalizeExplicitMarkdownPathLinksInPlainText(buf);
            buf = '';
        }
    }
    for (var i = 0; i < src.length; i += 1) {
        var ch = src.charAt(i);
        var rest = src.slice(i);
        if (lineStart) {
            var fence = /^([ \\t]{0,3})(\`{3,}|~{3,})/.exec(rest);
            if (fence) {
                flushPlain();
                var fenceText = fence[0];
                var marker = fence[2].charAt(0);
                if (!inFence) {
                    inFence = true;
                    fenceMarker = marker;
                } else if (marker === fenceMarker) {
                    inFence = false;
                    fenceMarker = '';
                }
                out += fenceText;
                i += fenceText.length - 1;
                lineStart = false;
                continue;
            }
        }
        if (inFence) out += ch;
        else buf += ch;
        lineStart = ch === '\\n' || ch === '\\r';
    }
    flushPlain();
    return out;
}

function encodeMarkdownWorkspacePathLinksInPlainText(text) {
    return normalizeExplicitMarkdownPathLinksInPlainText(text)
        .replace(/\\[([^\\]\\r\\n]+)\\]\\(([^)\\r\\n]+)\\)/g, encodeMarkdownWorkspacePathLinkMatch);
}

function encodeMarkdownWorkspacePathLinks(text) {
    var src = normalizeExplicitMarkdownPathLinksOutsideFences(text);
    var out = '';
    var buf = '';
    var inFence = false;
    var fenceMarker = '';
    var inCode = false;
    var lineStart = true;
    function flushPlain() {
        if (buf) {
            out += encodeMarkdownWorkspacePathLinksInPlainText(buf);
            buf = '';
        }
    }
    for (var i = 0; i < src.length; i += 1) {
        var ch = src.charAt(i);
        var rest = src.slice(i);
        if (lineStart) {
            var fence = /^([ \\t]{0,3})(\`{3,}|~{3,})/.exec(rest);
            if (fence) {
                flushPlain();
                var fenceText = fence[0];
                var marker = fence[2].charAt(0);
                if (!inFence) {
                    inFence = true;
                    fenceMarker = marker;
                } else if (marker === fenceMarker) {
                    inFence = false;
                    fenceMarker = '';
                }
                out += fenceText;
                i += fenceText.length - 1;
                lineStart = false;
                continue;
            }
        }
        if (!inFence && ch === '\`') {
            flushPlain();
            var tickEnd = i + 1;
            while (tickEnd < src.length && src.charAt(tickEnd) === '\`') tickEnd += 1;
            out += src.slice(i, tickEnd);
            i = tickEnd - 1;
            inCode = !inCode;
            lineStart = false;
            continue;
        }
        if (inFence || inCode) out += ch;
        else buf += ch;
        lineStart = ch === '\\n' || ch === '\\r';
    }
    flushPlain();
    return out;
}

function escapeMarkdownSingleTildes(text) {
    var src = String(text || '');
    var out = '';
    var inFence = false;
    var fenceMarker = '';
    var inCode = false;
    var lineStart = true;
    for (var i = 0; i < src.length; i += 1) {
        var ch = src.charAt(i);
        var rest = src.slice(i);
        if (lineStart) {
            var fence = /^([ \\t]{0,3})(\`{3,}|~{3,})/.exec(rest);
            if (fence) {
                var marker = fence[2].charAt(0);
                if (!inFence) {
                    inFence = true;
                    fenceMarker = marker;
                } else if (marker === fenceMarker) {
                    inFence = false;
                    fenceMarker = '';
                }
            }
        }
        if (!inFence && ch === '\`') {
            var tickEnd = i + 1;
            while (tickEnd < src.length && src.charAt(tickEnd) === '\`') tickEnd += 1;
            out += src.slice(i, tickEnd);
            i = tickEnd - 1;
            inCode = !inCode;
            lineStart = false;
            continue;
        }
        if (!inFence && !inCode && ch === '~') {
            out += '&#126;';
        } else {
            out += ch;
        }
        lineStart = ch === '\\n' || ch === '\\r';
    }
    return out;
}

function renderMarkdown(text) {
    if (!text) return '';
    var markdownParser = globalThis.marked;
    if (!markdownParser || typeof markdownParser.parse !== 'function') {
        return '<pre class="markdown-fallback">' + escapeHtml(String(text)) + '</pre>';
    }
    if (!markedOptionsApplied) {
        markedOptionsApplied = true;
        try {
            markdownParser.setOptions({ breaks: true, mangle: false, headerIds: false });
        } catch (e) { /* ignore */ }
    }
    try {
        return markdownParser.parse(escapeMarkdownSingleTildes(encodeMarkdownWorkspacePathLinks(text)), { mangle: false, headerIds: false });
    } catch (e) {
        return '<pre class="markdown-fallback">' + escapeHtml(String(text)) + '</pre>';
    }
}

const THINK_OPEN_TAG = '<think>';
const THINK_CLOSE_TAG = '</think>';

function appendThinkReasoning(parts, text) {
    var t = String(text || '').trim();
    if (t) parts.push(t);
}

function findTagOutsideBackticks(text, tag, start) {
    var src = String(text || '');
    var target = String(tag || '').toLowerCase();
    var lower = src.toLowerCase();
    var i = Math.max(0, Number(start) || 0);
    var codeTickLen = 0;
    while (i < src.length) {
        if (src.charAt(i) === '\`') {
            var j = i + 1;
            while (j < src.length && src.charAt(j) === '\`') j += 1;
            var runLen = j - i;
            if (!codeTickLen) codeTickLen = runLen;
            else if (runLen >= codeTickLen) codeTickLen = 0;
            i = j;
            continue;
        }
        if (!codeTickLen && lower.slice(i, i + target.length) === target) return i;
        i += 1;
    }
    return -1;
}

function removeTagOutsideBackticks(text, tag) {
    var src = String(text || '');
    var out = '';
    var pos = 0;
    while (pos < src.length) {
        var idx = findTagOutsideBackticks(src, tag, pos);
        if (idx < 0) {
            out += src.slice(pos);
            break;
        }
        out += src.slice(pos, idx);
        pos = idx + String(tag || '').length;
    }
    return out;
}

function splitThinkTagsForUi(raw) {
    var text = String(raw || '');
    var reasoning = [];
    var content = '';
    var pos = 0;
    while (pos < text.length) {
        var openIdx = findTagOutsideBackticks(text, THINK_OPEN_TAG, pos);
        if (openIdx < 0) {
            content += text.slice(pos);
            break;
        }
        content += text.slice(pos, openIdx);
        var bodyStart = openIdx + THINK_OPEN_TAG.length;
        var closeIdx = findTagOutsideBackticks(text, THINK_CLOSE_TAG, bodyStart);
        if (closeIdx < 0) {
            appendThinkReasoning(reasoning, text.slice(bodyStart));
            pos = text.length;
            break;
        }
        appendThinkReasoning(reasoning, text.slice(bodyStart, closeIdx));
        pos = closeIdx + THINK_CLOSE_TAG.length;
    }
    return {
        content: content,
        reasoning: reasoning.join('\\n\\n'),
        changed: reasoning.length > 0 || content !== text,
    };
}

function stripOrphanThinkCloseForFinalCard(raw) {
    return removeTagOutsideBackticks(raw, THINK_CLOSE_TAG);
}

function tagSuffixPrefixLen(text, tag) {
    var max = Math.min(String(text || '').length, tag.length - 1);
    for (var n = max; n > 0; n -= 1) {
        if (tag.indexOf(text.slice(text.length - n)) === 0) return n;
    }
    return 0;
}

function feedThinkTaggedResponseDelta(llmState, delta) {
    var l = llmState || {};
    if (!l.llmThinkTagMode) l.llmThinkTagMode = 'response';
    if (typeof l.llmThinkTagAllowLeading !== 'boolean') l.llmThinkTagAllowLeading = true;
    l.llmThinkTagCarry = (l.llmThinkTagCarry || '') + String(delta || '');
    var out = [];
    while (l.llmThinkTagCarry) {
        if (l.llmThinkTagMode === 'reasoning') {
            var closeIdx = findTagOutsideBackticks(l.llmThinkTagCarry, THINK_CLOSE_TAG, 0);
            if (closeIdx >= 0) {
                var reasoningText = l.llmThinkTagCarry.slice(0, closeIdx);
                if (reasoningText) out.push({ part: 'reasoning', text: reasoningText });
                l.llmThinkTagCarry = l.llmThinkTagCarry.slice(closeIdx + THINK_CLOSE_TAG.length);
                l.llmThinkTagMode = 'response';
                continue;
            }
            var lowerReasoning = l.llmThinkTagCarry.toLowerCase();
            var keepReasoning = tagSuffixPrefixLen(lowerReasoning, THINK_CLOSE_TAG);
            var emitReasoning = keepReasoning ? l.llmThinkTagCarry.slice(0, l.llmThinkTagCarry.length - keepReasoning) : l.llmThinkTagCarry;
            l.llmThinkTagCarry = l.llmThinkTagCarry.slice(emitReasoning.length);
            if (emitReasoning) out.push({ part: 'reasoning', text: emitReasoning });
            break;
        }
        var openIdx = findTagOutsideBackticks(l.llmThinkTagCarry, THINK_OPEN_TAG, 0);
        if (openIdx >= 0 && l.llmThinkTagAllowLeading && !l.llmThinkTagCarry.slice(0, openIdx).trim()) {
            var responseText = l.llmThinkTagCarry.slice(0, openIdx);
            if (responseText) out.push({ part: 'response', text: responseText });
            l.llmThinkTagCarry = l.llmThinkTagCarry.slice(openIdx + THINK_OPEN_TAG.length);
            l.llmThinkTagMode = 'reasoning';
            continue;
        }
        var lowerResponse = l.llmThinkTagCarry.toLowerCase();
        var keepResponse = l.llmThinkTagAllowLeading ? tagSuffixPrefixLen(lowerResponse, THINK_OPEN_TAG) : 0;
        var emitResponse = keepResponse ? l.llmThinkTagCarry.slice(0, l.llmThinkTagCarry.length - keepResponse) : l.llmThinkTagCarry;
        l.llmThinkTagCarry = l.llmThinkTagCarry.slice(emitResponse.length);
        if (emitResponse) {
            out.push({ part: 'response', text: emitResponse });
            if (emitResponse.trim()) l.llmThinkTagAllowLeading = false;
        }
        break;
    }
    return out;
}

function flushThinkTagCarry(ctx) {
    if (!ctx || !ctx.llm || !ctx.llm.llmThinkTagCarry) return;
    var l = ctx.llm;
    if (l.llmThinkTagMode === 'reasoning') l.llmPendingReasoningDelta = (l.llmPendingReasoningDelta || '') + l.llmThinkTagCarry;
    else {
        l.llmPendingResponseDelta = (l.llmPendingResponseDelta || '') + l.llmThinkTagCarry;
        if (String(l.llmThinkTagCarry || '').trim()) l.llmThinkTagAllowLeading = false;
    }
    l.llmThinkTagCarry = '';
}

const TRACE_ROW = {
    'log-entry':   { label: '信息', c: 'feed--log' },
    'tool-call':   { label: '工具', c: 'feed--tool' },
    'error-log':   { label: '错误', c: 'feed--err' },
    'llm-response':{ label: '回复', c: 'feed--llm2' },
    'llm-reasoning':{ label: '思考', c: 'feed--llm' },
    'compact-summary': { label: '压缩', c: 'feed--cmp' },
    'context-trim': { label: '裁剪', c: 'feed--trim' },
    'context-summary': { label: '压缩', c: 'feed--cmp' },
    'key-context': { label: '要点', c: 'feed--key' },
    'user-steer':  { label: '追问', c: 'feed--answer' },
    'status':      { label: '状态', c: 'feed--st' },
};

const envKeepLines = Number(window.__UI_LOG_TRUNCATE_KEEP_LINES__);
const LOG_TRUNCATE_KEEP_LINES = Number.isFinite(envKeepLines) && envKeepLines > 0 ? Math.floor(envKeepLines) : 100;
const LOG_TRUNCATE_HEAD_LINES = LOG_TRUNCATE_KEEP_LINES;
const LOG_TRUNCATE_TAIL_LINES = LOG_TRUNCATE_KEEP_LINES;
const LOG_TRUNCATE_HEAD_CHARS = 12000;
const LOG_TRUNCATE_TAIL_CHARS = 12000;

function reactGenerationForContext(ctx) {
    return Math.max(0, Math.floor(Number(ctx && ctx.reactGeneration) || 0));
}

function toolCallDraftKey(ctx, parsed) {
    var generation = reactGenerationForContext(ctx);
    var ri = parsed && parsed.react_iter != null ? String(parsed.react_iter) : '';
    var idx = parsed && parsed.tool_call_index != null ? String(parsed.tool_call_index) : (parsed && parsed.index != null ? String(parsed.index) : '0');
    return generation + ':' + ri + ':' + idx;
}

function findToolDraftRow(ctx, parsed) {
    var key = toolCallDraftKey(ctx, parsed);
    if (!key) return null;
    var body = getProcessBody(ctx);
    if (!body || typeof CSS === 'undefined' || !CSS.escape) return null;
    try { return body.querySelector('.feed-item.feed--tool[data-tool-draft-key="' + CSS.escape(key) + '"]'); } catch (e) { return null; }
}

function deltaDedupeKey(ctx, parsed, scope) {
    if (!parsed || parsed.delta_seq == null) return '';
    var ds = Number(parsed.delta_seq);
    if (!Number.isFinite(ds) || ds <= 0) return '';
    var ss = Number(parsed.stream_seq || 0);
    var ri = parsed.react_iter != null ? String(parsed.react_iter) : '';
    var part = String(scope || parsed.type || '');
    var id = String(parsed.tool_call_id || parsed.id || parsed.index || parsed.tool_call_index || '');
    return reactGenerationForContext(ctx) + ':' + part + ':' + (Number.isFinite(ss) ? Math.floor(ss) : 0) + ':' + ri + ':' + id + ':' + Math.floor(ds);
}

function hasSeenStreamDelta(ctx, parsed, scope) {
    if (!ctx) return false;
    var key = deltaDedupeKey(ctx, parsed, scope);
    if (!key) return false;
    if (!ctx._seenStreamDeltaKeys) ctx._seenStreamDeltaKeys = new Set();
    if (ctx._seenStreamDeltaKeys.has(key)) return true;
    ctx._seenStreamDeltaKeys.add(key);
    return false;
}

function setToolRowText(row, text, ctx, runSessionId) {
    if (!row) return;
    var sc = row.querySelector('.feed-chunk-scroller');
    if (sc) {
        var nextText = truncateLogTextForUi(text);
        if (typeof setUiRuntimeText === 'function') setUiRuntimeText(sc, nextText);
        else sc.textContent = nextText;
    }
    var ch = row.querySelector('.feed-chunk');
    if (ch) {
        // 工具条目流式生成时也放开高度限制
        ch.classList.add('is-streaming');
        refreshFeedChunkOverflow(ch);
    }
    // 遵守自动跟随，不强制拖拽
    if (!replayingMessages) scrollContentAreaIfFollow(ctx, runSessionId);
}

// 移除临时状态消息（移除整个 feed-item 条目）
function removeTemporaryStatus(ctx) {
    // Cleanup must never create a new process group. Terminal signals can be
    // delivered more than once (final, run_finished, and [DONE]).
    var body = getExistingProcessBody(ctx);
    if (!body) return;
    var tempStatuses = body.querySelectorAll('[data-temporary-status="1"]');
    tempStatuses.forEach(function(el) {
        var row = el.closest ? el.closest('.feed-item') : null;
        if (row) row.remove(); else el.remove();
    });
}

function appendToolCallDelta(ctx, parsed, runSessionId) {
    if (hasSeenStreamDelta(ctx, parsed, 'tool_call_delta')) return;
    var key = toolCallDraftKey(ctx, parsed);
    if (!key) return;
    var row = findToolDraftRow(ctx, parsed);
    if (!row) {
        var so = null;
        if (parsed.react_iter != null && Number.isFinite(Number(parsed.react_iter))) so = { reactIter: Number(parsed.react_iter) };
        var scNew = createProcessFeedRow(ctx, 'tool-call', '工具调用生成中...', so, runSessionId, '');
        row = scNew && scNew.closest ? scNew.closest('.feed-item') : null;
        if (row) row.setAttribute('data-tool-draft-key', key);
    }
    if (!row) return;
    // A valid call may start executing before the provider finishes emitting
    // metadata-only deltas. Never let those late deltas revert the row to
    // "generating" or create a duplicate draft.
    if (row.getAttribute('data-tool-pending') === '1') return;
    if (parsed.id) row.dataset.pendingToolCallId = String(parsed.id);
    
    // Tool-call generation should still reveal the process group; only the later
    // "executing" placeholder should avoid forcing expand/collapse changes.
    removeTemporaryStatus(ctx);
    var agg = row.closest('.process-aggregate');
    if (agg && agg.classList.contains('is-collapsed')) {
        agg.classList.remove('is-collapsed');
        var topN = agg.querySelector('.process-aggregate-top');
        if (topN) topN.setAttribute('aria-expanded', 'true');
    }
    
    // 累积工具名称和参数
    if (parsed.name_delta) {
        row.dataset.pendingToolName = (row.dataset.pendingToolName || '') + String(parsed.name_delta);
    }
    if (parsed.arguments_delta) {
        row.dataset.pendingToolArgs = (row.dataset.pendingToolArgs || '') + String(parsed.arguments_delta);
    }
    
    // 生成显示文本
    var toolName = row.dataset.pendingToolName || '';
    var argsRaw = row.dataset.pendingToolArgs || '';
    var displayText = '工具调用生成中...';
    
    if (toolName) {
        // 流式显示：工具名 + 参数原始文本（逐步增长）
        var argsPreview = argsRaw;
        displayText = toolName + '(' + argsPreview + '\\n生成中...';
    }
    setToolRowText(row, displayText, ctx, runSessionId);
}

function removeAbortedToolDraftRows(ctx, ev) {
    // Like temporary-status cleanup, this may run after the final response has
    // already sealed the process group, so only inspect an existing body.
    var body = getExistingProcessBody(ctx);
    if (!body) return;
    var iter = ev && ev.react_iter != null && Number.isFinite(Number(ev.react_iter))
        ? Math.max(1, Math.floor(Number(ev.react_iter)))
        : null;
    var runId = String((ev && (ev.run_id || ev.runId)) || '');
    var hasScopedAbort = !!(iter != null || runId || (ev && ev.react_generation != null));
    var generation = ev && ev.react_generation != null && Number.isFinite(Number(ev.react_generation))
        ? Math.max(0, Math.floor(Number(ev.react_generation)))
        : (hasScopedAbort ? reactGenerationForContext(ctx) : null);
    var rows = body.querySelectorAll('.feed-item.feed--tool[data-tool-draft-key], .feed-item.feed--tool[data-tool-pending="1"]');
    rows.forEach(function (row) {
        if (iter != null) {
            var rowIter = Number(row.getAttribute('data-react-iter'));
            if (!Number.isFinite(rowIter) || Math.floor(rowIter) !== iter) return;
        }
        if (generation != null) {
            var rowGeneration = Math.max(0, Math.floor(Number(row.getAttribute('data-react-generation')) || 0));
            if (rowGeneration !== generation) return;
        }
        var rowRunId = String(row.getAttribute('data-run-id') || '');
        if (runId && rowRunId && rowRunId !== runId) return;
        row.remove();
    });
    var agg = body.closest('.process-aggregate');
    if (agg) refreshAggregateStatsSmart(agg);
}

function formatToolCommandLine(tool, args, commandPreview) {
    if (commandPreview != null && String(commandPreview).trim()) return String(commandPreview).trim();
    var name = String(tool || 'tool');
    var a = args && typeof args === 'object' && !Array.isArray(args) ? args : {};
    function j(v) { try { return JSON.stringify(v); } catch (e) { return String(v); } }
    function pair(k, v) {
        if ((k === 'content' || k === 'contents' || k === 'patch') && typeof v === 'string' && v.length > 240) v = '<' + v.length + ' chars>';
        return j(k) + ': ' + j(v);
    }
    var preferred = ['path','target_directory','file_path','directory','root','command','args','url','start_line','end_line','pattern','query','search','replace','old_string','new_string','workdir','timeout_ms','login','working_dir','timeout','temporary','patch','content','contents'];
    var keys = [];
    // 路径参数去重：只保留第一个存在的路径参数
    var pathKeys = ['path', 'target_directory', 'file_path', 'directory', 'root'];
    var firstPathKey = null;
    pathKeys.forEach(function (k) {
        if (!firstPathKey && Object.prototype.hasOwnProperty.call(a, k)) firstPathKey = k;
    });
    preferred.forEach(function (k) {
        if (Object.prototype.hasOwnProperty.call(a, k)) {
            if (pathKeys.indexOf(k) >= 0) {
                if (k === firstPathKey) keys.push(k);
            } else {
                keys.push(k);
            }
        }
    });
    Object.keys(a).sort().forEach(function (k) { if (keys.indexOf(k) < 0) keys.push(k); });
    if (name === 'run_shell') {
        var b = {};
        Object.keys(a).forEach(function (k) { b[k] = a[k]; });
        var cmd = b.command != null ? String(b.command) : '';
        if (Array.isArray(b.args) && b.args.length) cmd += ' ' + b.args.map(function (x) { return String(x); }).join(' ');
        b.command = cmd.trim();
        delete b.args;
        a = b;
        keys = [];
        preferred.forEach(function (k) { if (Object.prototype.hasOwnProperty.call(a, k)) keys.push(k); });
        Object.keys(a).sort().forEach(function (k) { if (keys.indexOf(k) < 0) keys.push(k); });
    }
    return name + '(' + keys.map(function (k) { return pair(k, a[k]); }).join(', ') + ')';
}

function formatToolPendingLine(tool, args, commandPreview) {
    var cmd = commandPreview != null ? String(commandPreview).trim() : '';
    if (!cmd) return '执行中...';
    return cmd + '\\n执行中...';
}

function formatToolDoneLine(tool, args, result, commandPreview) {
    return formatToolCommandLine(tool, args, commandPreview) + '\\n执行结果\\n' + String(result != null ? result : '');
}

function appendToolPendingRow(ctx, parsed, runSessionId) {
    var line = formatToolPendingLine(parsed.tool, parsed.args, parsed.command_preview);
    var so = null;
    if (parsed.react_iter != null && Number.isFinite(Number(parsed.react_iter))) so = { reactIter: Number(parsed.react_iter) };
    var draft = findToolDraftRow(ctx, parsed);
    if (draft) {
        if (parsed.tool_call_id != null && String(parsed.tool_call_id) !== '') draft.setAttribute('data-tool-call-id', String(parsed.tool_call_id));
        draft.setAttribute('data-tool-pending', '1');
        draft.dataset.commandPreview = parsed.command_preview != null ? String(parsed.command_preview) : '';
        var draftScroller = draft.querySelector('.feed-chunk-scroller');
        if (draftScroller) {
            var draftText = truncateLogTextForUi(line);
            if (typeof setUiRuntimeText === 'function') setUiRuntimeText(draftScroller, draftText);
            else draftScroller.textContent = draftText;
        }
        var draftChunk = draft.querySelector('.feed-chunk');
        if (draftChunk) {
            draftChunk.classList.remove('is-streaming');
            refreshFeedChunkOverflow(draftChunk);
        }
        if (!replayingMessages) scrollContentAreaIfFollow(ctx, runSessionId);
        if (typeof attachHumanInteractionCardsForToolCall === 'function') {
            attachHumanInteractionCardsForToolCall(ctx && ctx.stream, parsed.tool_call_id);
        }
        return;
    }
    var sc = createProcessFeedRow(ctx, 'tool-call', line, so, runSessionId, parsed.tool_call_id);
    var row = sc && sc.closest ? sc.closest('.feed-item') : null;
    if (row) {
        row.setAttribute('data-tool-draft-key', toolCallDraftKey(ctx, parsed));
        row.setAttribute('data-tool-pending', '1');
        row.dataset.commandPreview = parsed.command_preview != null ? String(parsed.command_preview) : '';
        var chunk = row.querySelector('.feed-chunk');
        if (chunk) {
            chunk.classList.remove('is-streaming');
            refreshFeedChunkOverflow(chunk);
        }
        if (typeof attachHumanInteractionCardsForToolCall === 'function') {
            attachHumanInteractionCardsForToolCall(ctx && ctx.stream, parsed.tool_call_id);
        }
    }
}

function appendToolCommandDelta(ctx, parsed, runSessionId) {
    if (hasSeenStreamDelta(ctx, parsed, 'tool_command_delta')) return;
    var tid = parsed.tool_call_id != null ? String(parsed.tool_call_id) : '';
    if (!tid) return;
    var body = getProcessBody(ctx);
    var row = null;
    if (body && typeof CSS !== 'undefined' && CSS.escape) {
        try { row = body.querySelector('.feed-item.feed--tool[data-tool-call-id="' + CSS.escape(tid) + '"]'); } catch (e) { row = null; }
    }
    if (!row) return;
    row.dataset.commandPreview = (row.dataset.commandPreview || '') + String(parsed.delta || '');
    var text = formatToolPendingLine(parsed.tool, parsed.args, row.dataset.commandPreview);
    var sc = row.querySelector('.feed-chunk-scroller');
    if (sc) {
        var pendingText = truncateLogTextForUi(text);
        if (typeof setUiRuntimeText === 'function') setUiRuntimeText(sc, pendingText);
        else sc.textContent = pendingText;
    }
    var ch = row.querySelector('.feed-chunk');
    if (ch) refreshFeedChunkOverflow(ch);
    if (!replayingMessages) scrollContentAreaIfFollow(ctx, runSessionId);
}
function upsertToolCallResult(ctx, parsed, runSessionId) {
    var tid = parsed.tool_call_id != null ? String(parsed.tool_call_id) : '';
    var body = getProcessBody(ctx);
    var row = null;
    if (tid && body && typeof CSS !== 'undefined' && CSS.escape) {
        try { row = body.querySelector('.feed-item.feed--tool[data-tool-call-id="' + CSS.escape(tid) + '"]'); } catch (e) { row = null; }
    }
    if (!row) row = findToolDraftRow(ctx, parsed);
    var cmdPreview = parsed.command_preview;
    if ((!cmdPreview || !String(cmdPreview).trim()) && row && row.dataset.commandPreview) cmdPreview = row.dataset.commandPreview;
    var rawContent = parsed.raw_content != null ? String(parsed.raw_content) : '';
    var text = rawContent ? rawContent : formatToolDoneLine(parsed.tool, parsed.args, parsed.result, cmdPreview);
    if (row) {
        if (tid) row.setAttribute('data-tool-call-id', tid);
        row.removeAttribute('data-tool-draft-key');
        row.removeAttribute('data-tool-pending');
        row.setAttribute('data-event-committed', '1');
        row.dataset.commandPreview = cmdPreview != null ? String(cmdPreview) : '';
        var sc = row.querySelector('.feed-chunk-scroller');
        if (sc) {
            var doneText = truncateLogTextForUi(text);
            if (typeof setUiRuntimeText === 'function') setUiRuntimeText(sc, doneText);
            else sc.textContent = doneText;
        }
        var ch = row.querySelector('.feed-chunk');
        if (ch) refreshFeedChunkOverflow(ch);
        var agg = body.closest('.process-aggregate');
        refreshAggregateStatsSmart(agg);
        if (!replayingMessages) scrollContentAreaIfFollow(ctx, runSessionId);
        if (typeof attachHumanInteractionCardsForToolCall === 'function') {
            attachHumanInteractionCardsForToolCall(ctx && ctx.stream, tid);
        }
        autoCollapseToolRowAfterResult(row);
        return;
    }
    var ri = uiEventReactIter(parsed);
    var so = null;
    if (ri != null && Number.isFinite(Number(ri))) so = { reactIter: ri };
    var scNew = createProcessFeedRow(ctx, 'tool-call', text, so, runSessionId, tid);
    var newRow = scNew && scNew.closest ? scNew.closest('.feed-item') : null;
    if (newRow && tid && typeof attachHumanInteractionCardsForToolCall === 'function') {
        attachHumanInteractionCardsForToolCall(ctx && ctx.stream, tid);
    }
    if (newRow) autoCollapseToolRowAfterResult(newRow);
}

function autoCollapseToolRowAfterResult(row) {
    if (!row || row.dataset.manualToggle === '1') return;
    if (row.querySelector('.human-interaction-card[data-kind="approval"][data-status="pending"]')) return;
    row.classList.add('is-collapsed');
    var btn = row.querySelector('.feed-row-collapse');
    if (btn) {
        btn.setAttribute('aria-expanded', 'false');
        btn.setAttribute('aria-label', '展开工具行');
    }
}

/** 去掉首尾「空白行」（整行仅空格/制表也不保留），保留首行正文缩进与中间空行 */
function trimSurroundingBlankLines(raw) {
    var text = (raw == null) ? '' : String(raw);
    if (!text) return text;
    var lines = text.split('\\n');
    var start = 0;
    var end = lines.length;
    while (start < end && lines[start].trim() === '') start++;
    while (end > start && lines[end - 1].trim() === '') end--;
    if (start >= end) return '';
    return lines.slice(start, end).join('\\n');
}

function truncateLogTextForUi(raw) {
    const text = (raw == null) ? '' : String(raw);
    if (!text) return text;
    const lines = text.split('\\n');
    if (lines.length > LOG_TRUNCATE_HEAD_LINES + LOG_TRUNCATE_TAIL_LINES) {
        const head = lines.slice(0, LOG_TRUNCATE_HEAD_LINES).join('\\n');
        const tail = lines.slice(-LOG_TRUNCATE_TAIL_LINES).join('\\n');
        const omitted = lines.length - LOG_TRUNCATE_HEAD_LINES - LOG_TRUNCATE_TAIL_LINES;
        return head + '\\n\\n... [中间省略 ' + omitted + ' 行] ...\\n\\n' + tail;
    }
    if (text.length > LOG_TRUNCATE_HEAD_CHARS + LOG_TRUNCATE_TAIL_CHARS) {
        const head = text.slice(0, LOG_TRUNCATE_HEAD_CHARS);
        const tail = text.slice(-LOG_TRUNCATE_TAIL_CHARS);
        const omitted = text.length - LOG_TRUNCATE_HEAD_CHARS - LOG_TRUNCATE_TAIL_CHARS;
        return head + '\\n\\n... [中间省略约 ' + omitted + ' 字符] ...\\n\\n' + tail;
    }
    return text;
}

function reactFeedPhase(type) {
    if (type === 'llm-reasoning') return 0;
    if (type === 'llm-response') return 1;
    if (type === 'tool-call') return 2;
    return null;
}

function appendProcessRowBeforePendingAppendSteer(body, row, type) {
    if (!body || !row) return;
    // An accepted append-mode follow-up is the visual boundary between the
    // current round and the next one.  Keep its pending row at the tail while
    // the current LLM/tool round finishes; once the server commits user_steer,
    // data-steer-pending is removed and subsequent rows naturally append below.
    if (type !== 'user-steer') {
        var pendingAppendSteer = body.querySelector(
            '.feed-item[data-log-type="user-steer"]'
            + '[data-steer-mode="append"][data-steer-pending="1"]'
        );
        if (pendingAppendSteer) {
            body.insertBefore(row, pendingAppendSteer);
            return;
        }
    }
    body.appendChild(row);
}

function insertReactOrderedFeedRow(body, row, type, reactIter, reactGeneration) {
    var phase = reactFeedPhase(type);
    var iter = Number(reactIter);
    if (phase == null || !Number.isFinite(iter)) {
        appendProcessRowBeforePendingAppendSteer(body, row, type);
        return;
    }
    iter = Math.max(1, Math.floor(iter));
    var generation = Math.max(0, Math.floor(Number(reactGeneration) || 0));
    row.setAttribute('data-react-iter', String(iter));
    row.setAttribute('data-react-generation', String(generation));
    var rows = body.querySelectorAll('.feed-item[data-react-iter]');
    for (var i = 0; i < rows.length; i += 1) {
        var existing = rows[i];
        var existingPhase = reactFeedPhase(existing.getAttribute('data-log-type'));
        var existingIter = Number(existing.getAttribute('data-react-iter'));
        var existingGeneration = Math.max(0, Number(existing.getAttribute('data-react-generation')) || 0);
        if (existingPhase == null || !Number.isFinite(existingIter)) continue;
        if (existingGeneration > generation
            || (existingGeneration === generation
                && (existingIter > iter || (existingIter === iter && existingPhase > phase)))) {
            body.insertBefore(row, existing);
            return;
        }
    }
    appendProcessRowBeforePendingAppendSteer(body, row, type);
}

function createProcessFeedRow(ctx, type, initialText, streamOpts, runSessionId, toolCallIdOpt) {
    streamOpts = streamOpts || {};
    if (type == null) type = 'log-entry';
    stripWelcome(ctx);
    const body = getProcessBody(ctx);
    if (!body) return;
    const meta = TRACE_ROW[type] || TRACE_ROW['log-entry'];
    const row = document.createElement('div');
    row.className = 'feed-item ' + meta.c;
    row.setAttribute('data-log-type', type);
    row.setAttribute('data-react-generation', String(reactGenerationForContext(ctx)));
    if (ctx && ctx.runId) row.setAttribute('data-run-id', String(ctx.runId));
    if (toolCallIdOpt != null && String(toolCallIdOpt) !== '') row.setAttribute('data-tool-call-id', String(toolCallIdOpt));
    var toolCollapseBtn = type === 'tool-call'
        ? '<button type="button" class="feed-row-collapse" aria-expanded="true" aria-label="收起工具行">'
            + '<span class="feed-row-collapse-chevron" aria-hidden="true"></span></button>'
        : '';
    row.innerHTML = '<div class="feed-row">'
        + '<span class="feed-label">' + meta.label + '</span>'
        + '<div class="feed-chunk">'
        + '<div class="feed-chunk-scroller"></div></div>'
        + toolCollapseBtn
        + '</div>';
    const chunk = row.querySelector('.feed-chunk');
    const sc = row.querySelector('.feed-chunk-scroller');
    if (type === 'tool-call') {
        const collapseBtn = row.querySelector('.feed-row-collapse');
        if (collapseBtn) {
            collapseBtn.addEventListener('click', function (e) {
                e.preventDefault();
                e.stopPropagation();
                row.classList.toggle('is-collapsed');
                var isCollapsed = row.classList.contains('is-collapsed');
                collapseBtn.setAttribute('aria-expanded', isCollapsed ? 'false' : 'true');
                collapseBtn.setAttribute('aria-label', isCollapsed ? '展开工具行' : '收起工具行');
                row.dataset.manualToggle = '1';
            });
        }
    }
    var txtForUi = initialText;
    if (type === 'llm-reasoning' || type === 'llm-response') txtForUi = trimSurroundingBlankLines(txtForUi);
    if (type === 'llm-response') row._processBriefRawText = String(txtForUi || '');
    var initialUiText = truncateLogTextForUi(txtForUi);
    if (type === 'status' || type === 'error-log' || type === 'tool-call'
        || type === 'compact-summary' || type === 'context-trim'
        || type === 'context-summary' || type === 'key-context') {
        if (typeof setUiRuntimeText === 'function') setUiRuntimeText(sc, initialUiText);
        else sc.textContent = initialUiText;
    } else {
        sc.textContent = initialUiText;
    }
    if (streamOpts.streaming && (type === 'llm-reasoning' || type === 'llm-response')) {
        chunk.classList.add('is-streaming');
        row.setAttribute('data-llm-live-row', '1');
    }
    bindFeedChunkInteraction(chunk);
    bindFeedChunkScrollChain(sc);
    insertReactOrderedFeedRow(body, row, type, streamOpts.reactIter, reactGenerationForContext(ctx));
    if (typeof translateUiNode === 'function') translateUiNode(row);
    if (ctx && ctx.currentTurn && body.classList && body.classList.contains('subagent-turn-process')) {
        markSubagentTurnHasProcess(ctx.currentTurn);
    }
    if (type === 'error-log') {
        var errHint = document.createElement('div');
        errHint.className = 'feed-error-contact-hint';
        errHint.textContent = '如需帮助或反馈，请联系GitHub @sugarfreeecho';
        body.appendChild(errHint);
    }
    const agg = body.closest('.process-aggregate');
    if (streamOpts.reactIter != null && Number.isFinite(Number(streamOpts.reactIter))) {
        var ri = Math.max(1, Math.floor(Number(streamOpts.reactIter)));
        bumpAggregateMaxReactIter(agg, ri);
    }
    if (agg && agg.classList.contains('is-collapsed')) {
        updateProcessBrief(agg);
    }
    else requestAnimationFrame(function () { scheduleFeedChunkOverflowRefresh(chunk); });
    refreshAggregateStatsSmart(agg);
    if (!streamOpts.streaming) scrollContentAreaIfFollow(ctx, runSessionId);
    return sc;
}

function appendLlmStreamDelta(ctx, ev, runSessionId) {
    if (!ctx || !ctx.llm) return;
    // 收到 reasoning/content 增量时，移除"正在思考中..."条目
    removeTemporaryStatus(ctx);
    const l = ctx.llm;
    const iter = ev.react_iter;
    const seq = Number(ev.stream_seq || 0);
    if (Number.isFinite(seq) && seq > 0) {
        if (l.llmDeltaLastSeq !== null && seq < l.llmDeltaLastSeq) finalizeLlmStreamChunks(ctx);
        l.llmDeltaLastSeq = seq;
    }
    const part = ev.type === 'llm_reasoning_delta' ? 'reasoning' : 'response';
    if (hasSeenStreamDelta(ctx, ev, 'llm_' + part)) return;
    const delta = String(ev.delta || '');
    if (!delta) return;
    const replayedSnapshot = !!ev.replayed_snapshot;
    if (replayedSnapshot && part === 'response') {
        l.llmThinkTagMode = 'response';
        l.llmThinkTagCarry = '';
        l.llmThinkTagAllowLeading = true;
    }
    if (iter != null) {
        var body0 = getProcessBody(ctx);
        if (body0) bumpAggregateMaxReactIter(body0.closest('.process-aggregate'), iter);
    }
    const streamOpt = { streaming: true };
    if (iter != null && Number.isFinite(Number(iter))) streamOpt.reactIter = Number(iter);
    var pieces = part === 'response' ? feedThinkTaggedResponseDelta(l, delta) : [{ part: 'reasoning', text: delta }];
    for (var pi = 0; pi < pieces.length; pi += 1) {
        var piece = pieces[pi] || {};
        var piecePart = piece.part === 'reasoning' ? 'reasoning' : 'response';
        var pieceText = String(piece.text || '');
        if (!pieceText) continue;
        if (piecePart === 'reasoning') {
        if (l.llmStreamReasoningScroller && !l.llmStreamReasoningScroller.isConnected) {
            l.llmStreamReasoningScroller = null;
        }
        if (l.llmStreamReasoningIter !== iter) {
            flushLlmDeltaText(ctx);
            l.llmStreamReasoningIter = iter;
            var existingReasoning = findExistingLlmFeedRow(ctx, 'llm-reasoning', Number.isFinite(Number(iter)) ? Math.max(1, Math.floor(Number(iter))) : null, { liveOnly: true });
            l.llmStreamReasoningScroller = existingReasoning
                ? existingReasoning.querySelector('.feed-chunk-scroller')
                : createProcessFeedRow(ctx, 'llm-reasoning', '', streamOpt, runSessionId);
        }
        if (!l.llmStreamReasoningScroller) {
            var recoveredReasoning = findExistingLlmFeedRow(ctx, 'llm-reasoning', Number.isFinite(Number(iter)) ? Math.max(1, Math.floor(Number(iter))) : null, { liveOnly: true });
            l.llmStreamReasoningScroller = recoveredReasoning
                ? recoveredReasoning.querySelector('.feed-chunk-scroller')
                : createProcessFeedRow(ctx, 'llm-reasoning', '', streamOpt, runSessionId);
        }
        if (!l.llmStreamReasoningScroller) return;
        if (replayedSnapshot) {
            l.llmPendingReasoningDelta = '';
            l.llmStreamReasoningScroller.textContent = truncateLogTextForUi(pieceText);
        } else {
            l.llmPendingReasoningDelta = (l.llmPendingReasoningDelta || '') + pieceText;
        }
        } else {
        if (l.llmStreamResponseScroller && !l.llmStreamResponseScroller.isConnected) {
            l.llmStreamResponseScroller = null;
        }
        if (l.llmStreamResponseIter !== iter) {
            flushLlmDeltaText(ctx);
            l.llmStreamResponseIter = iter;
            var existingResponse = findExistingLlmFeedRow(ctx, 'llm-response', Number.isFinite(Number(iter)) ? Math.max(1, Math.floor(Number(iter))) : null, { liveOnly: true });
            l.llmStreamResponseScroller = existingResponse
                ? existingResponse.querySelector('.feed-chunk-scroller')
                : createProcessFeedRow(ctx, 'llm-response', '', streamOpt, runSessionId);
        }
        if (!l.llmStreamResponseScroller) {
            var recoveredResponse = findExistingLlmFeedRow(ctx, 'llm-response', Number.isFinite(Number(iter)) ? Math.max(1, Math.floor(Number(iter))) : null, { liveOnly: true });
            l.llmStreamResponseScroller = recoveredResponse
                ? recoveredResponse.querySelector('.feed-chunk-scroller')
                : createProcessFeedRow(ctx, 'llm-response', '', streamOpt, runSessionId);
        }
        if (!l.llmStreamResponseScroller) return;
        if (replayedSnapshot) {
            l.llmPendingResponseDelta = '';
            l.llmStreamResponseScroller.textContent = truncateLogTextForUi(pieceText);
        } else {
            l.llmPendingResponseDelta = (l.llmPendingResponseDelta || '') + pieceText;
        }
        }
    }
    scheduleLlmDeltaFlush(ctx, runSessionId);
}

function upsertLlmFeedRow(ctx, content, logType, runSessionId, reactIter) {
    if (!ctx) return null;
    if (logType === 'llm-response') {
        var split = splitThinkTagsForUi(content);
        if (split.reasoning && split.reasoning.trim()) upsertLlmFeedRow(ctx, split.reasoning, 'llm-reasoning', runSessionId, reactIter);
        content = split.content;
    }
    var ri = reactIter != null && Number.isFinite(Number(reactIter)) ? Math.max(1, Math.floor(Number(reactIter))) : null;
    var rawText = trimSurroundingBlankLines(String(content || ''));
    var txt = truncateLogTextForUi(rawText);
    if (!txt.trim()) return null;
    var existing = findExistingLlmFeedRow(ctx, logType, ri);
    if (existing) {
        var sc = existing.querySelector('.feed-chunk-scroller');
        var ch = existing.querySelector('.feed-chunk');
        if (logType === 'llm-response') existing._processBriefRawText = rawText;
        if (sc) sc.textContent = txt;
        if (ch) {
            ch.classList.remove('is-streaming');
            scheduleFeedChunkOverflowRefresh(ch);
        }
        existing.removeAttribute('data-llm-live-row');
        existing.setAttribute('data-event-committed', '1');
        removeDuplicateLlmFeedRows(ctx, existing, logType, ri);
        if (ctx.llm) resetLlmState(ctx);
        var agg = existing.closest && existing.closest('.process-aggregate');
        if (agg) {
            refreshAggregateStatsSmart(agg);
            if (!ctx.currentProcessGroup || !ctx.currentProcessGroup.isConnected) ctx.currentProcessGroup = agg;
        }
        scrollContentAreaIfFollow(ctx, runSessionId);
        return sc;
    }
    if (ctx.llm) resetLlmState(ctx);
    return appendLog(ctx, content, logType, runSessionId, ri);
}

function findExistingLlmFeedRow(ctx, logType, reactIter, opts) {
    if (!ctx) return null;
    opts = opts || {};
    var selector = '.feed-item[data-log-type="' + logType + '"]';
    selector += '[data-react-generation="' + reactGenerationForContext(ctx) + '"]';
    if (reactIter != null) selector += '[data-react-iter="' + reactIter + '"]';
    else selector += '[data-llm-live-row="1"]';
    if (opts.liveOnly) selector += '[data-llm-live-row="1"]';
    var roots = [];
    if (ctx.currentProcessGroup && ctx.currentProcessGroup.isConnected) {
        // react_iter restarts at 1 for a replacement run. Once a new process
        // block exists, never reuse an identically numbered LLM row from an
        // older block or reasoning and response will be split across runs.
        roots.push(ctx.currentProcessGroup);
    } else if (!replayingMessages && ctx.stream && ctx.stream.querySelectorAll) {
        roots.push(ctx.stream);
    }
    for (var r = 0; r < roots.length; r += 1) {
        var matches = roots[r].querySelectorAll(selector);
        if (matches && matches.length) return matches[matches.length - 1];
    }
    return null;
}

function removeDuplicateLlmFeedRows(ctx, keepRow, logType, reactIter) {
    if (!ctx || !ctx.stream || !ctx.stream.querySelectorAll || !keepRow) return;
    var selector = '.feed-item[data-log-type="' + logType + '"]';
    selector += '[data-react-generation="' + reactGenerationForContext(ctx) + '"]';
    if (reactIter != null) selector += '[data-react-iter="' + reactIter + '"]';
    var rows = ctx.stream.querySelectorAll(selector);
    if (!rows || rows.length <= 1) return;
    rows.forEach(function (row) {
        if (row !== keepRow && row.getAttribute('data-llm-live-row') === '1') row.remove();
    });
}

function parseMessageTimestamp(value) {
    if (value == null || value === '') return null;
    if (typeof value === 'number' && isFinite(value)) {
        return new Date(value > 100000000000 ? value : value * 1000);
    }
    var d = new Date(String(value));
    return isNaN(d.getTime()) ? null : d;
}

function formatUserMessageTimestamp(value) {
    var d = parseMessageTimestamp(value);
    if (!d) return '';
    try {
        return new Intl.DateTimeFormat(undefined, {
            year: 'numeric',
            month: '2-digit',
            day: '2-digit',
            hour: '2-digit',
            minute: '2-digit',
            timeZoneName: 'short',
            hour12: false,
        }).format(d);
    } catch (e) {
        return d.toLocaleString();
    }
}

function refreshUserMessageTimes(root) {
    var scope = root || document;
    if (!scope || !scope.querySelectorAll) return;
    scope.querySelectorAll('.user-message-time[data-created-at]').forEach(function (el) {
        var raw = el.getAttribute('data-created-at') || '';
        var txt = formatUserMessageTimestamp(raw);
        if (txt) el.textContent = txt;
    });
}

function ensureUserMessageTimeAutoRefresh() {
    if (window.__userMessageTimeAutoRefreshBound) return;
    window.__userMessageTimeAutoRefreshBound = true;
    window.addEventListener('focus', function () { refreshUserMessageTimes(document); });
    document.addEventListener('visibilitychange', function () {
        if (!document.hidden) refreshUserMessageTimes(document);
    });
    setInterval(function () { refreshUserMessageTimes(document); }, 60000);
}

function appendMessage(ctx, role, content, meta, runSessionId) {
    meta = meta || {};
    ensureUserMessageTimeAutoRefresh();
    stripWelcome(ctx);
    if (role === 'user' && meta.eventIndex != null && Number.isFinite(Number(meta.eventIndex))) {
        var streamRoot = (ctx && ctx.stream) || chatContainer;
        var existingUser = null;
        if (streamRoot && streamRoot.querySelector && typeof CSS !== 'undefined' && CSS.escape) {
            try {
                existingUser = streamRoot.querySelector('.msg-wrap--user[data-event-index="' + CSS.escape(String(meta.eventIndex)) + '"]');
            } catch (e) { existingUser = null; }
        }
        if (existingUser) {
            var existingMessage = existingUser.querySelector('.message');
            var rawStrExisting = content == null ? '' : String(content);
            if (existingMessage && messageRawMarkdown.get(existingUser) !== rawStrExisting) {
                messageRawMarkdown.set(existingUser, rawStrExisting);
                existingMessage.textContent = rawStrExisting;
                linkifyAssistantTextNodes(existingMessage);
                renderUserMessageContent(existingUser, existingMessage, rawStrExisting, linkifyAssistantTextNodes);
            }
            if (meta.runtimeSeq != null && Number.isFinite(Number(meta.runtimeSeq)) && Number(meta.runtimeSeq) > 0) {
                existingUser.setAttribute('data-runtime-seq', String(Math.floor(Number(meta.runtimeSeq))));
            }
            if (meta.runtimeEventType) {
                existingUser.setAttribute('data-runtime-event-type', String(meta.runtimeEventType));
            }
            if (meta.createdAt || meta.created_at || meta.timestamp) {
                existingUser.setAttribute('data-created-at', String(meta.createdAt || meta.created_at || meta.timestamp));
            }
            if (!replayingMessages) rebuildToc({ localOnly: true });
            return existingUser;
        }
    }
    const wrap = document.createElement('div');
    wrap.className = 'msg-wrap msg-wrap--' + (role === 'user' ? 'user' : 'assistant');
    if (role === 'assistant') wrap.classList.add('msg-wrap--answer-frame');
    if (meta.eventIndex != null) wrap.setAttribute('data-event-index', String(meta.eventIndex));
    if (meta.runtimeSeq != null && Number.isFinite(Number(meta.runtimeSeq)) && Number(meta.runtimeSeq) > 0) {
        wrap.setAttribute('data-runtime-seq', String(Math.floor(Number(meta.runtimeSeq))));
    }
    if (meta.runtimeEventType) {
        wrap.setAttribute('data-runtime-event-type', String(meta.runtimeEventType));
    }
    if (meta.truncateBeforeSeq != null && Number.isFinite(Number(meta.truncateBeforeSeq)) && Number(meta.truncateBeforeSeq) > 0) {
        wrap.setAttribute('data-truncate-before-seq', String(Math.floor(Number(meta.truncateBeforeSeq))));
    }
    var tTrunc = meta.turnTruncateIdx;
    if (tTrunc == null) { if (role === 'user' && meta.eventIndex != null) tTrunc = meta.eventIndex; }
    if (tTrunc != null && tTrunc >= 0) wrap.setAttribute('data-truncate-from', String(tTrunc));
    if (role === 'user') {
        if (meta.eventIndex != null && meta.eventIndex >= 0) {
            wrap.id = 'user-msg-' + meta.eventIndex;
        } else {
            const n = (ctx.stream || chatContainer).querySelectorAll('.msg-wrap--user').length;
            wrap.id = 'user-msg-' + n;
        }
    }
    const div = document.createElement('div');
    div.className = 'message ' + (role === 'user' ? 'user' : 'assistant');
    var rawStr = content == null ? '' : String(content);
    var displayStr = rawStr;
    if (role === 'assistant') {
        var assistantSplit = splitThinkTagsForUi(rawStr);
        displayStr = stripOrphanThinkCloseForFinalCard(assistantSplit.content);
    }
    messageRawMarkdown.set(wrap, displayStr);
    if (role === 'user') {
        if (userMessageShouldCollapse(rawStr)) {
            wrap.classList.add('has-turn-process');
            div.classList.add('is-collapsible');
            // 摘要
            var sum = document.createElement('div');
            sum.className = 'user-msg-summary';
            if (typeof renderSelectedSkillsUiMessage === 'function') renderSelectedSkillsUiMessage(sum, buildUserMessageSummary(rawStr), linkifyAssistantTextNodes);
            else {
                sum.textContent = buildUserMessageSummary(rawStr);
                linkifyAssistantTextNodes(sum);
            }
            // 完整
            var ful = document.createElement('div');
            ful.className = 'user-msg-full';
            if (typeof renderSelectedSkillsUiMessage === 'function') renderSelectedSkillsUiMessage(ful, rawStr, linkifyAssistantTextNodes);
            else {
                ful.textContent = rawStr;
                linkifyAssistantTextNodes(ful);
            }
            // chevron
            var ch = document.createElement('div');
            ch.className = 'user-msg-chevron';
            var arrow = document.createElement('span');
            arrow.className = 'chevron-arrow';
            ch.appendChild(arrow);
            ch.addEventListener('click', function(e) {
                e.stopPropagation();
                wrap.classList.toggle('user-msg-expanded');
            });
            div.appendChild(sum);
            div.appendChild(ful);
            div.appendChild(ch);
        } else {
            div.textContent = rawStr;
            linkifyAssistantTextNodes(div);
        }
    } else if (role === 'assistant' && meta.uiRuntimeText && typeof setUiRuntimeText === 'function') {
        // System terminal statuses are plain text, not model markdown. Keep
        // their source in the runtime i18n store so language toggles restore
        // the original Chinese text exactly.
        setUiRuntimeText(div, displayStr);
    } else {
        div.innerHTML = renderMarkdown(displayStr);
        enhanceAssistantMessageContent(div);
    }
    wrap.appendChild(div);
    if (role === 'user') {
        var createdAt = meta.createdAt || meta.created_at || meta.timestamp || new Date().toISOString();
        wrap.setAttribute('data-created-at', String(createdAt));
    }
    if (role === 'user' && !div.classList.contains('is-collapsible')) {
        renderUserMessageContent(wrap, div, rawStr, linkifyAssistantTextNodes);
    }
    attachMessageToolbar(wrap, role);
    (ctx.stream || chatContainer).appendChild(wrap);
    if (role === 'assistant') {
        if (ctx.currentProcessGroup) {
            ctx.currentProcessGroup._processFinalResponseComparable = normalizeProcessBriefComparableText(displayStr);
            if (ctx.currentProcessGroup.isConnected) {
                ctx.currentProcessGroup.classList.add('is-collapsed');
                const ttop = ctx.currentProcessGroup.querySelector('.process-aggregate-top');
                if (ttop) ttop.setAttribute('aria-expanded', 'false');
                updateProcessBrief(ctx.currentProcessGroup);
            }
        }
        sealProcessGroup(ctx);
    }
    if (role === 'user' && !replayingMessages) rebuildToc({ localOnly: true });
    if (!replayingMessages) {
        if (role === 'user') scrollChatToBottomIfFollow(runSessionId, { force: true });
        else scrollChatToBottomIfFollow(runSessionId, {});
    }
}

function handleTraceChunkClick(e) {
    if (e) e.stopPropagation();
    this.classList.toggle('expanded');
    var self = this;
    requestAnimationFrame(function () {
        refreshFeedChunkOverflow(self);
        registerMermaidLazy(self);
    });
}

function handleToolRowChunkClick(e) {
    if (e) e.stopPropagation();
    var row = this.closest ? this.closest('.feed-item') : null;
    if (!row) return;
    row.classList.toggle('is-collapsed');
    row.dataset.manualToggle = '1';
    var btn = row.querySelector('.feed-row-collapse');
    if (btn) {
        var isCollapsed = row.classList.contains('is-collapsed');
        btn.setAttribute('aria-expanded', isCollapsed ? 'false' : 'true');
        btn.setAttribute('aria-label', isCollapsed ? '展开工具行' : '收起工具行');
    }
}

function bindFeedChunkInteraction(ch) {
    ch.removeEventListener('click', handleTraceChunkClick);
    ch.removeEventListener('click', handleToolRowChunkClick);
    // Tool rows use the row-level fold (feed-row-collapse) as their single
    // collapse affordance; clicking the command text toggles the same fold.
    // Keep the content-height expand for LLM/log/etc. rows.
    var row = ch.closest ? ch.closest('.feed-item') : null;
    if (row && row.classList.contains('feed--tool')) {
        ch.addEventListener('click', handleToolRowChunkClick);
        return;
    }
    ch.addEventListener('click', handleTraceChunkClick);
}

function bindExistingLogInteractions(root) {
    const el = root || getVisibleChatStream() || chatContainer;
    if (!el) return;
    el.querySelectorAll('.feed-chunk').forEach(function (ch) {
        bindFeedChunkInteraction(ch);
        const sc = ch.querySelector('.feed-chunk-scroller');
        if (sc) bindFeedChunkScrollChain(sc);
    });
    el.querySelectorAll('.process-aggregate').forEach(function (agg) {
        bindProcessAggregateInteractions(agg);
    });
    el.querySelectorAll('.process-aggregate-brief').forEach(bindProcessBriefScrollChain);
}

function finalizeExistingLogLayout(root) {
    const el = root || getVisibleChatStream() || chatContainer;
    if (!el) return;
    el.querySelectorAll('.feed-chunk').forEach(function (ch) {
        scheduleFeedChunkOverflowRefresh(ch);
    });
    el.querySelectorAll('.process-aggregate').forEach(function (agg) {
        if (!agg.classList.contains('subagent-grid-card')) bindProcessAggregateHeightButton(agg);
        if (agg.classList.contains('is-collapsed')) updateProcessBrief(agg);
        refreshAggregateStatsSmart(agg);
    });
}

function bindExistingLogs(root) {
    bindExistingLogInteractions(root);
    finalizeExistingLogLayout(root);
}

function appendLog(ctx, content, type, runSessionId, reactIter) {
    if (type == null) type = 'log-entry';
    const tStr = (content == null) ? '' : String(content);
    if ((type === 'llm-reasoning' || type === 'llm-response') && !trimSurroundingBlankLines(tStr).trim()) return null;
    var so = null;
    if (reactIter != null && Number.isFinite(Number(reactIter))) so = { reactIter: Number(reactIter) };
    return createProcessFeedRow(ctx, type, tStr, so, runSessionId);
}

function getLastProcessFeedItem(body) {
    if (!body || !body.querySelectorAll) return null;
    var rows = body.querySelectorAll('.feed-item');
    return rows && rows.length ? rows[rows.length - 1] : null;
}

function appendModelSwitchStatus(ctx, event, runSessionId) {
    if (!ctx) return null;
    var content = String((event && event.content) || '').trim();
    if (!content) return null;
    var sc = ctx._modelSwitchStatusScroller;
    var body = getProcessBody(ctx);
    var lastRow = getLastProcessFeedItem(body);
    var row = sc && sc.isConnected && sc.closest ? sc.closest('.feed-item') : null;
    var canReuse = !!(row && row === lastRow && row.getAttribute('data-model-switch-status') === '1');
    if (!canReuse && lastRow && lastRow.getAttribute('data-model-switch-status') === '1') {
        sc = lastRow.querySelector('.feed-chunk-scroller');
        row = lastRow;
        canReuse = !!(sc && sc.isConnected);
    }
    if (!canReuse) {
        sc = appendLog(ctx, content, 'status', runSessionId);
        var newRow = sc && sc.closest ? sc.closest('.feed-item') : null;
        if (newRow) newRow.setAttribute('data-model-switch-status', '1');
        ctx._modelSwitchStatusScroller = sc;
        return sc;
    }
    var prev = (typeof getUiRuntimeText === 'function' ? getUiRuntimeText(sc) : String(sc.textContent || '')).trim();
    if (prev.indexOf(content) < 0) {
        var merged = truncateLogTextForUi(prev ? (prev + '\\n' + content) : content);
        if (typeof setUiRuntimeText === 'function') setUiRuntimeText(sc, merged);
        else sc.textContent = merged;
    }
    var ch = sc.closest && sc.closest('.feed-chunk');
    if (ch) {
        refreshFeedChunkOverflow(ch);
        requestAnimationFrame(function () { refreshFeedChunkOverflow(ch); });
    }
    scrollContentAreaIfFollow(ctx, runSessionId);
    return sc;
}

function flushProgressDeltaText(ctx, logType) {
    if (!ctx || !ctx.progressStream) return;
    var st = ctx.progressStream[logType];
    if (!st) return;
    if (st.flushRaf) {
        cancelAnimationFrame(st.flushRaf);
        st.flushRaf = 0;
    }
    if (st.pending && st.scroller && st.scroller.isConnected) {
        var current = typeof getUiRuntimeText === 'function' ? getUiRuntimeText(st.scroller) : String(st.scroller.textContent || '');
        var merged = truncateLogTextForUi(current + st.pending);
        if (typeof setUiRuntimeText === 'function') setUiRuntimeText(st.scroller, merged);
        else st.scroller.textContent = merged;
        var ch = st.scroller.closest('.feed-chunk');
        if (ch) refreshFeedChunkOverflow(ch);
    }
    st.pending = '';
}

function finalizeProgressStreamChunks(ctx) {
    if (!ctx) return;
    var types = ctx.progressStream ? Object.keys(ctx.progressStream) : [];
    for (var i = 0; i < types.length; i += 1) flushProgressDeltaText(ctx, types[i]);
    var streamRoot = (ctx._subagentBody && ctx._subagentBody.isConnected) ? ctx._subagentBody : ctx.stream;
    if (streamRoot) {
        streamRoot.querySelectorAll('.feed-item .feed-chunk.is-streaming').forEach(function (ch) {
            ch.classList.remove('is-streaming');
            refreshFeedChunkOverflow(ch);
        });
    }
    ctx.progressStream = {};
}

function discardProgressStreamChunks(ctx) {
    if (!ctx) return;
    var streamRoot = (ctx._subagentBody && ctx._subagentBody.isConnected) ? ctx._subagentBody : ctx.stream;
    var rows = [];
    var types = ctx.progressStream ? Object.keys(ctx.progressStream) : [];
    for (var i = 0; i < types.length; i += 1) {
        var st = ctx.progressStream[types[i]];
        if (!st) continue;
        if (st.flushRaf) cancelAnimationFrame(st.flushRaf);
        var row = st.scroller && st.scroller.closest ? st.scroller.closest('.feed-item') : null;
        if (row && rows.indexOf(row) < 0) rows.push(row);
    }
    if (streamRoot) {
        streamRoot.querySelectorAll(
            '.feed-item[data-log-type="context-trim"] .feed-chunk.is-streaming, '
            + '.feed-item[data-log-type="context-summary"] .feed-chunk.is-streaming, '
            + '.feed-item[data-log-type="key-context"] .feed-chunk.is-streaming'
        ).forEach(function (chunk) {
            var row = chunk.closest('.feed-item');
            if (row && rows.indexOf(row) < 0) rows.push(row);
        });
    }
    rows.forEach(function (row) {
        if (row && row.parentNode) row.remove();
    });
    ctx.progressStream = {};
    if (ctx.progressScrollers) {
        ['context-trim', 'context-summary', 'key-context'].forEach(function (type) {
            var scroller = ctx.progressScrollers[type];
            if (!scroller || !scroller.isConnected) delete ctx.progressScrollers[type];
        });
    }
}

function scheduleProgressDeltaFlush(ctx, runSessionId, logType) {
    if (!ctx || !ctx.progressStream) return;
    var st = ctx.progressStream[logType];
    if (!st || st.flushRaf) return;
    st.flushRaf = requestAnimationFrame(function () {
        st.flushRaf = 0;
        flushProgressDeltaText(ctx, logType);
        followStreamProcessScroll(ctx, runSessionId);
    });
}

/** 每个压缩阶段（裁剪/压缩/要点）共用一条 feed，状态行与正文在同一 scroller */
function ensureProgressScroller(ctx, logType, runSessionId) {
    if (!ctx) return null;
    if (!ctx.progressScrollers) ctx.progressScrollers = {};
    var sc = ctx.progressScrollers[logType];
    if (sc && sc.isConnected) return sc;
    sc = appendLog(ctx, '', logType, runSessionId);
    if (sc) ctx.progressScrollers[logType] = sc;
    return sc;
}

/** 落盘正文：替换流式段或追加到状态行后，与刷新后 ui_events 回放一致 */
function applyProgressPersistedBody(ctx, content, logType, runSessionId) {
    if (!ctx) return;
    var text = String(content || '').trim();
    if (!text) return;
    var st = ctx.progressStream && ctx.progressStream[logType];
    var bodyOffset = st && typeof st.bodyOffset === 'number' ? st.bodyOffset : null;
    var hadStream = bodyOffset != null;
    finalizeProgressStreamForType(ctx, logType);
    var sc = ensureProgressScroller(ctx, logType, runSessionId);
    if (!sc) return;
    var prevTxt = typeof getUiRuntimeText === 'function' ? getUiRuntimeText(sc) : (sc.textContent || '');
    var merged;
    if (hadStream) {
        merged = prevTxt.slice(0, bodyOffset).replace(/\\s+$/, '') + '\\n\\n' + text;
    } else if (prevTxt.trim()) {
        merged = prevTxt.trim() + '\\n\\n' + text;
    } else {
        merged = text;
    }
    var persistedText = truncateLogTextForUi(merged);
    if (typeof setUiRuntimeText === 'function') setUiRuntimeText(sc, persistedText);
    else sc.textContent = persistedText;
    var chSet = sc.closest('.feed-chunk');
    if (chSet) {
        chSet.classList.remove('is-streaming');
        refreshFeedChunkOverflow(chSet);
        requestAnimationFrame(function () { refreshFeedChunkOverflow(chSet); });
    }
    ctx.progressScrollers[logType] = sc;
    scrollContentAreaIfFollow(ctx, runSessionId);
}

/** 压缩/要点执行端输出：在同一 feed 内流式追加正文（不另起 feed 块） */
function appendProgressStreamDelta(ctx, delta, logType, runSessionId) {
    if (!ctx || !delta) return;
    if (!ctx.progressStream) ctx.progressStream = {};
    var piece = String(delta);
    if (!piece) return;
    var sc = ensureProgressScroller(ctx, logType, runSessionId);
    if (!sc) return;
    var chunk = sc.closest('.feed-chunk');
    if (chunk) chunk.classList.add('is-streaming');
    var st = ctx.progressStream[logType];
    if (!st) {
        var sourceText = typeof getUiRuntimeText === 'function' ? getUiRuntimeText(sc) : (sc.textContent || '');
        var head = sourceText.trim();
        var bodyOffset = sourceText.length;
        if (head) {
            var streamHead = head + '\\n\\n';
            if (typeof setUiRuntimeText === 'function') setUiRuntimeText(sc, streamHead);
            else sc.textContent = streamHead;
            bodyOffset = streamHead.length;
        }
        st = { scroller: sc, pending: '', flushRaf: 0, bodyOffset: bodyOffset };
        ctx.progressStream[logType] = st;
    }
    st.pending += piece;
    scheduleProgressDeltaFlush(ctx, runSessionId, logType);
}

/** 同类型进度行合并追加，实现裁剪/压缩/要点分轨流式展示 */
function appendProgressLog(ctx, content, logType, runSessionId) {
    if (!ctx) return;
    finalizeProgressStreamForType(ctx, logType);
    if (!ctx.progressScrollers) ctx.progressScrollers = {};
    var line = String(content || '');
    if (!line.trim()) return;
    var prev = ctx.progressScrollers[logType];
    if (prev && prev.isConnected) {
        var prevTxt = typeof getUiRuntimeText === 'function' ? getUiRuntimeText(prev) : (prev.textContent || '');
        var progressText = truncateLogTextForUi(prevTxt ? (prevTxt + '\\n' + line) : line);
        if (typeof setUiRuntimeText === 'function') setUiRuntimeText(prev, progressText);
        else prev.textContent = progressText;
        var chMerge = prev.closest('.feed-chunk');
        if (chMerge) {
            refreshFeedChunkOverflow(chMerge);
            requestAnimationFrame(function () { refreshFeedChunkOverflow(chMerge); });
        }
        scrollContentAreaIfFollow(ctx, runSessionId);
        return;
    }
    var sc = ensureProgressScroller(ctx, logType, runSessionId);
    if (!sc) return;
    var firstProgressText = truncateLogTextForUi(line);
    if (typeof setUiRuntimeText === 'function') setUiRuntimeText(sc, firstProgressText);
    else sc.textContent = firstProgressText;
    var chNew = sc.closest('.feed-chunk');
    if (chNew) {
        refreshFeedChunkOverflow(chNew);
        requestAnimationFrame(function () { refreshFeedChunkOverflow(chNew); });
    }
    scrollContentAreaIfFollow(ctx, runSessionId);
}

function finalizeProgressStreamForType(ctx, logType) {
    if (!ctx || !logType) return;
    flushProgressDeltaText(ctx, logType);
    if (ctx.progressStream && ctx.progressStream[logType]) {
        var st = ctx.progressStream[logType];
        if (st.scroller && st.scroller.isConnected) {
            var ch = st.scroller.closest('.feed-chunk');
            if (ch) {
                ch.classList.remove('is-streaming');
                refreshFeedChunkOverflow(ch);
            }
        }
        delete ctx.progressStream[logType];
    }
}

/* ── Subagent 浮层 / 过程块 ── */
`,Gt=`var subagentPanelOpen = false;
var subagentPanelBound = false;
var subagentDockExpanded = false;

var subagentPanelRefreshSeq = 0;

function shouldStreamSubagentSummaryDom(card) {
    return !!(subagentPanelOpen && card);
}

function shouldStreamSubagentProcessDom(card) {
    if (!card || !subagentPanelOpen) return false;
    return card.classList.contains('is-expanded');
}

function shouldStreamSubagentCardDom(card) {
    return shouldStreamSubagentProcessDom(card);
}

function subagentBodyIsLoaded(body) {
    return !!(body && body.dataset.loaded === '1' && body.dataset.stashed !== '1'
        && body.innerHTML.trim() && !body.querySelector('.subagent-detail-empty')
        && !body.querySelector('.subagent-card-summary'));
}

function buildSubagentCardSummaryHtml(previewText, muted) {
    var t = formatSubagentSummaryText(previewText);
    if (!t) {
        return '<div class="subagent-card-summary subagent-card-summary--muted">'
            + escapeHtml(muted ? String(muted) : '展开查看执行过程') + '</div>';
    }
    if (t.length > 1200) t = t.slice(0, 1199) + '\\u2026';
    return '<div class="subagent-card-summary">' + escapeHtml(t) + '</div>';
}

function formatSubagentSummaryText(text) {
    var t = String(text || '').replace(/\\r\\n/g, '\\n').trim();
    if (!t) return '';
    t = t.replace(/\`\`\`[\\s\\S]*?\`\`\`/g, function (m) {
        return m.replace(/^\`\`\`[^\\n]*\\n?/, '').replace(/\\n?\`\`\`$/, '');
    });
    t = t.replace(/^\\s{0,3}#{1,6}\\s+/gm, '');
    t = t.replace(/^\\s{0,3}[-*_]{3,}\\s*$/gm, '');
    t = t.replace(/\\[([^\\]]+)\\]\\(([^)]+)\\)/g, '$1');
    t = t.replace(/\`([^\`]+)\`/g, '$1');
    t = t.replace(/(\\*\\*|__)(.*?)\\1/g, '$2');
    t = t.replace(/(\\*|_)(.*?)\\1/g, '$2');
    t = t.replace(/^\\s{0,3}>\\s?/gm, '');
    t = t.replace(/^\\s{0,3}[-*+]\\s+/gm, '• ');
    t = t.replace(/\\n{3,}/g, '\\n\\n');
    return t.trim();
}

function updateSubagentCardSummaryOnly(card, previewText) {
    if (!card) return;
    var body = card.querySelector('.subagent-card-body');
    if (!body) return;
    var p = previewText != null ? String(previewText) : String(card.dataset.resultPreview || '');
    card.dataset.resultPreview = p;
    if (subagentBodyIsLoaded(body)) return;
}

function stashSubagentCardBodyForCollapse(card) {
    if (!card) return;
    var body = card.querySelector('.subagent-card-body');
    if (!body || body.dataset.stashed === '1') return;
    if (subagentBodyIsLoaded(body) && body.dataset.finalOnly !== '1') {
        var aid = card.getAttribute('data-agent-id');
        if (currentSessionId && aid) {
            var hasCleanCache = body.dataset.cacheClean === '1' && !!readSubagentBodyCache(currentSessionId, aid);
            if (!hasCleanCache) {
                rememberSubagentBodyCache(currentSessionId, aid, body.innerHTML);
                body.dataset.cacheClean = '1';
            }
        }
    }
    body.dataset.stashed = '1';
    delete body.dataset.renderToken;
    delete body.dataset.rendering;
    body.innerHTML = '';
    delete body.dataset.loaded;
    delete body.dataset.streamReady;
    delete body._subagentStreamCtx;
}

function restoreSubagentCardBodyFromStash(card, sessionId) {
    if (!card) return false;
    var body = card.querySelector('.subagent-card-body');
    var aid = card.getAttribute('data-agent-id');
    if (!body) return false;
    var cached = readSubagentBodyCache(sessionId, aid);
    if (cached && isSubagentBodyCacheComplete(cached)) {
        body.innerHTML = cached;
        body.dataset.loaded = '1';
        body.dataset.cacheClean = '1';
        delete body.dataset.stashed;
        rebindSubagentCardBody(body, card, aid);
        return true;
    }
    if (body.dataset.stashed === '1') {
        delete body.dataset.stashed;
        body.innerHTML = '';
    }
    return false;
}

function stashSubagentInactiveBodies(grid, keepCard) {
    if (!grid) return;
    grid.querySelectorAll('.subagent-grid-card').forEach(function (card) {
        if (keepCard && card === keepCard) return;
        if (card.classList.contains('is-expanded')) return;
        stashSubagentCardBodyForCollapse(card);
    });
}

function openSubagentPanel() {
    var dock = document.getElementById('subagent-dock');
    var btn = document.getElementById('subagent-toggle-btn');
    if (!dock || (btn && btn.classList.contains('hidden'))) return;
    dock.classList.remove('hidden');
    subagentPanelOpen = true;
    syncSubagentDockResizeUi();
    if (btn) {
        btn.classList.add('is-active');
        btn.setAttribute('aria-expanded', 'true');
    }
    var grid = document.getElementById('subagent-grid');
    if (grid) {
        ensureSubagentCardViewportObserver(grid);
        stashSubagentInactiveBodies(grid, grid.querySelector('.subagent-grid-card.is-expanded'));
        requestAnimationFrame(function () {
            if (subagentPanelOpen) loadVisibleSubagentCardBodies(grid, currentSessionId);
        });
        if (countRunningSubagentCards() > 0) scheduleSubagentIncrementalSync();
    }
}

function resetSubagentPanelForSession() {
    if (currentSessionId) clearSubagentStateForSession(currentSessionId);
    cancelScheduledSubagentTreeRefresh();
    disconnectSubagentCardViewportObserver();
    if (subagentContinueBannerTimer) {
        clearTimeout(subagentContinueBannerTimer);
        subagentContinueBannerTimer = null;
    }
    hideSubagentContinueBanner();
    subagentPanelRefreshSeq += 1;
    closeSubagentPanel();
    stopSubagentIncrementalSync();
    var grid = document.getElementById('subagent-grid');
    if (grid) {
        grid.innerHTML = '';
        delete grid.dataset.sessionId;
        grid.classList.remove('subagent-grid--expanded');
    }
    var toggleBtn = document.getElementById('subagent-toggle-btn');
    var toggleBadge = document.getElementById('subagent-toggle-badge');
    if (toggleBtn) toggleBtn.classList.add('hidden');
    if (toggleBadge) toggleBadge.textContent = '';
}

function closeSubagentPanel() {
    var dock = document.getElementById('subagent-dock');
    var btn = document.getElementById('subagent-toggle-btn');
    if (dock) {
        var grid = document.getElementById('subagent-grid');
        if (grid) stashSubagentInactiveBodies(grid, null);
        dock.classList.add('hidden');
    }
    subagentPanelOpen = false;
    subagentDockExpanded = false;
    syncSubagentDockResizeUi();
    if (btn) {
        btn.classList.remove('is-active');
        btn.setAttribute('aria-expanded', 'false');
    }
}

function getSubagentCardStreamCtx(body, card, agentId) {
    if (!body) return null;
    if (body._subagentStreamCtx && body._subagentStreamCtx._subagentBody === body) return body._subagentStreamCtx;
    var ctx = {
        _subagentBody: body,
        currentProcessGroup: card || null,
        stream: null,
        lastUserEventIndex: null,
        progressStream: {},
        progressScrollers: {},
        keyContextStreamFilter: { phase: 'seek', carry: '' },
        llm: newLlmState(),
        currentTurn: null,
        _subagentTurnProcess: null,
        _subagentTurnFinalSlot: null
    };
    body._subagentStreamCtx = ctx;
    return ctx;
}

function resetSubagentTurnStreamState(ctx) {
    if (!ctx) return;
    resetLlmState(ctx);
    finalizeProgressStreamChunks(ctx);
    ctx.currentTurn = null;
    ctx._subagentTurnProcess = null;
    ctx._subagentTurnFinalSlot = null;
}

function sealSubagentTurn(ctx) {
    if (!ctx || !ctx.currentTurn) return;
    resetSubagentTurnStreamState(ctx);
}

function markSubagentTurnHasProcess(turn) {
    if (!turn) return;
    var processEl = turn.querySelector('.subagent-turn-process');
    var userWrap = turn.querySelector('.msg-wrap--user');
    var hasDeferred = !!(turn._deferredProcessEvents && turn._deferredProcessEvents.length) || turn.dataset.processDeferred === '1';
    if ((processEl && processEl.children.length) || hasDeferred) {
        if (userWrap) userWrap.classList.add('has-turn-process');
    }
}

function shouldSkipSubagentProcessEvent(event) {
    if (!event || typeof event !== 'object') return true;
    var t = String(event.type || '');
    var c = String(event.content || '').trim();
    if (t === 'status' && (!c || c === 'New Agent Loop Start' || c === 'Loop finished' || c === 'Subagent Continuation Start' || c === '任务已恢复，流程重启')) return true;
    if ((t === 'warning' || t === 'error') && !c) return true;
    return false;
}

function syncSubagentTurnProcessFlags(root) {
    if (!root) return;
    root.querySelectorAll('.subagent-turn').forEach(function (turn) {
        markSubagentTurnHasProcess(turn);
    });
}

function bindSubagentCardBodyInteractions(body) {
    if (!body) return;
    bindSubagentCardBodyScrollFollow(body);
    if (body.dataset.subagentBodyBound) return;
    body.dataset.subagentBodyBound = '1';
    body.addEventListener('click', function (e) {
        var userWrap = e.target.closest('.msg-wrap--user');
        if (!userWrap || !body.contains(userWrap)) return;
        if (!userWrap.classList.contains('has-turn-process')) return;
        var turn = userWrap.closest('.subagent-turn');
        if (!turn) return;
        e.preventDefault();
        e.stopPropagation();
        toggleSubagentTurnProcess(turn, body, userWrap);
    });
}

function bindSubagentTurnUserToggle(turn, userWrap) {
    /* 统一由 bindSubagentCardBodyInteractions 委托处理，避免重复 toggle */
}

function dispatchSubagentCardEvent(ctx, card, event, eventIndex, agentId) {
    if (!event || typeof event !== 'object') return;
    if (shouldSkipSubagentProcessEvent(event)) return;
    applySessionEvent(event, {
        sessionId: agentId,
        eventIndex: eventIndex,
        source: 'subagent-stream',
    });
    var t = event.type;
    if (t === 'subagent_start' || t === 'subagent_finish') return;
    if (t === 'user') {
        openSubagentTurn(ctx, event.content || '', eventIndex, event.created_at || event.createdAt || event.timestamp);
        if (typeof eventIndex === 'number') ctx.lastUserEventIndex = eventIndex;
        return;
    }
    if (t === 'final') {
        appendSubagentFinalToTurn(ctx, event.content || '', eventIndex);
        if (ctx.currentTurn) {
            ctx._subagentTurnProcess = ctx.currentTurn.querySelector('.subagent-turn-process');
            ctx._subagentTurnFinalSlot = ctx.currentTurn.querySelector('.subagent-turn-final-slot');
        }
        resetLlmState(ctx);
        finalizeProgressStreamChunks(ctx);
        return;
    }
    ensureSubagentTurnForProcess(ctx, eventIndex);
    if (shouldDeferSubagentProcessDom(ctx)) {
        deferSubagentProcessEvent(ctx.currentTurn, event, eventIndex);
        markSubagentTurnHasProcess(ctx.currentTurn);
        return;
    }
    renderEvent(ctx, event, eventIndex, agentId);
    markSubagentTurnHasProcess(ctx.currentTurn);
}


function restoreSubagentTurnCtxFromBody(ctx, body) {
    if (!ctx || !body) return;
    var turns = body.querySelectorAll('.subagent-turn');
    if (!turns.length) {
        resetSubagentTurnStreamState(ctx);
        return;
    }
    var last = turns[turns.length - 1];
    var finalSlot = last.querySelector('.subagent-turn-final-slot');
    var hasFinal = finalSlot && finalSlot.querySelector('.msg-wrap--assistant');
    if (hasFinal) {
        resetSubagentTurnStreamState(ctx);
        return;
    }
    ctx.currentTurn = last;
    ctx._subagentTurnProcess = last.querySelector('.subagent-turn-process');
    ctx._subagentTurnFinalSlot = finalSlot;
}

function rebindSubagentCardBody(body, card, agentId) {
    if (!body) return;
    bindSubagentCardBodyInteractions(body);
    body.querySelectorAll('.subagent-turn').forEach(function (turn) {
        markSubagentTurnHasProcess(turn);
    });
    bindSubagentCardFeedInteractionsLightly(body);
    var ctx = body._subagentStreamCtx || (card ? getSubagentCardStreamCtx(body, card, agentId) : null);
    if (ctx) restoreSubagentTurnCtxFromBody(ctx, body);
    if (card) {
        refreshSubagentCardStats(card);
    }
}

function bindSubagentCardFeedInteractionsLightly(root) {
    if (!root || !root.querySelectorAll) return;
    root.querySelectorAll('.feed-chunk').forEach(function (ch, idx) {
        bindFeedChunkInteraction(ch);
        var sc = ch.querySelector('.feed-chunk-scroller');
        if (sc) bindFeedChunkScrollChain(sc);
        if (idx < 24) scheduleFeedChunkOverflowRefresh(ch);
    });
}

function finalizeSubagentCardStream(agentId, card) {
    if (!card) return;
    var body = card.querySelector('.subagent-card-body');
    if (!body) return;
    var ctx = getSubagentCardStreamCtx(body, card, agentId);
    finalizeLlmStreamChunks(ctx);
    finalizeProgressStreamChunks(ctx);
}

function ensureSubagentCardStreamReady(card, aid) {
    if (!card || !aid) return;
    var body = card.querySelector('.subagent-card-body');
    if (!body || body.dataset.loading === '1') return;
    if (!card.dataset.procStartedAt) card.dataset.procStartedAt = String(procNow());
    if (body.querySelector('.subagent-detail-empty')) body.innerHTML = '';
    body.dataset.streamReady = '1';
    if (!body.dataset.loaded) body.dataset.loaded = '1';
    delete body.dataset.loading;
    bindSubagentCardBodyInteractions(body);
    getSubagentCardStreamCtx(body, card, aid);
}

function upsertSubagentCardFromStartEvent(event) {
    /* 历史回放阶段：一律不亮按钮 / 不写 grid，避免把别会话遗留的 subagent_start 闪出来；
       真实状态由稍后的 refreshSubagentTreePanel(/sessions/{sid}/subagents) 单一来源决定。 */
    if (replayingMessages) return null;
    var grid = document.getElementById('subagent-grid');
    if (!grid) return null;
    if (currentSessionId && grid.dataset.sessionId && grid.dataset.sessionId !== currentSessionId) {
        return null;
    }
    if (currentSessionId) grid.dataset.sessionId = currentSessionId;
    var aid = String(event.agent_id || event.run_id || '');
    if (!aid) return null;
    var node = {
        id: aid,
        running: !event.background ? true : true,
        description: event.description || aid.slice(0, 8),
        subagent_type: event.subagent_type || 'subagent',
        background: !!event.background,
    };
    var card = grid.querySelector('.subagent-grid-card[data-agent-id="' + aid + '"]');
    if (!card) card = appendSubagentGridCardFromNode(grid, node);
    else applySubagentNodeMetaToCard(card, node);
    if (currentSessionId) bindSubagentGridActions(grid, currentSessionId);
    var toggleBtn = document.getElementById('subagent-toggle-btn');
    var toggleBadge = document.getElementById('subagent-toggle-badge');
    if (toggleBtn) {
        toggleBtn.classList.remove('hidden');
        toggleBtn.classList.add('is-running');
    }
    var cardCount = grid.querySelectorAll('.subagent-grid-card').length;
    var runCount = grid.querySelectorAll('.subagent-status-dot.is-running').length;
    if (toggleBadge) toggleBadge.textContent = String(cardCount) + (runCount ? (' · ' + runCount) : '');
    if (toggleBtn && cardCount > 0) toggleBtn.classList.remove('hidden');
    if (shouldStreamSubagentSummaryDom(card)) ensureSubagentCardStreamReady(card, aid);
    return card;
}

function applySubagentFinishToCard(card, event) {
    if (!card || !event) return;
    card.dataset.subagentRunning = '0';
    var aidFin = card.getAttribute('data-agent-id') || '';
    var preview = String(event.result_preview || card.dataset.resultPreview || '').trim();
    if (preview) card.dataset.resultPreview = preview;
    if (Object.prototype.hasOwnProperty.call(event, 'has_final')) card.dataset.hasFinal = event.has_final ? '1' : '0';
    var hasFinal = card.dataset.hasFinal === '1'
        || !!card.querySelector('.subagent-turn-final-slot .msg-wrap--assistant, .message.assistant');
    var ok = event.ok !== false && (hasFinal || !!preview);
    markSubagentCardCompleted(card, ok, ok ? '' : String(event.error || 'missing final').trim());
    var body = card.querySelector('.subagent-card-body');
    if (currentSessionId && aidFin) forgetSubagentBodyCache(currentSessionId, aidFin);
    if (body && aidFin) {
        delete body.dataset.loaded;
        delete body.dataset.streamReady;
        delete body.dataset.loading;
        delete body.dataset.stashed;
        if (subagentPanelOpen && card.classList.contains('is-expanded')) {
            if (shouldStreamSubagentProcessDom(card)) {
                loadSubagentDetailInto(body, aidFin, card, currentSessionId);
            } else {
                queueSubagentCardBodyLoad(card, currentSessionId);
            }
        } else if (subagentPanelOpen) {
            updateSubagentCardSummaryOnly(card, preview);
        } else {
            body.innerHTML = '';
        }
    }
    if (aidFin) void refreshSubagentContextForCard(card, aidFin, true);
    scheduleSubagentCardStats(card);
}

function markSubagentCardCompleted(card, ok, errTxt) {
    if (!card) return;
    card.dataset.subagentRunning = '0';
    var dot = card.querySelector('.subagent-status-dot');
    if (dot) {
        dot.classList.remove('is-running', 'is-done', 'is-error');
        dot.classList.add(ok ? 'is-done' : 'is-error');
        var tip = ok ? '完成' : (/interrupt/i.test(String(errTxt || '')) ? '已中断' : '失败');
        dot.setAttribute('data-ui-tip', tip);
    }
    card.dataset.procEndedAt = String(procNow());
    var stopBtn = card.querySelector('.subagent-card-stop');
    if (stopBtn) stopBtn.remove();
    var toggleBtn = document.getElementById('subagent-toggle-btn');
    if (toggleBtn) toggleBtn.classList.remove('is-running');
}

function setSubagentCardExpanded(card, expand) {
    var grid = document.getElementById('subagent-grid');
    if (!grid || !card) return;
    if (expand) {
        grid.classList.add('is-resizing');
        stashSubagentInactiveBodies(grid, card);
        grid.querySelectorAll('.subagent-grid-card.is-expanded').forEach(function (c) {
            if (c !== card) {
                c.classList.remove('is-expanded');
                stashSubagentCardBodyForCollapse(c);
            }
        });
        card.classList.add('is-expanded');
        grid.classList.add('subagent-grid--expanded');
        var expandedBody = card.querySelector('.subagent-card-body');
        if (expandedBody && expandedBody.dataset.finalOnly === '1') {
            delete expandedBody.dataset.loaded;
            delete expandedBody.dataset.finalOnly;
            expandedBody.classList.remove('is-final-only');
            expandedBody.innerHTML = '';
        }
    } else {
        stashSubagentCardBodyForCollapse(card);
        card.classList.remove('is-expanded');
        if (!grid.querySelector('.subagent-grid-card.is-expanded')) {
            grid.classList.remove('subagent-grid--expanded');
        }
    }
    syncSubagentExpandButtons(grid);
    if (expand) {
        card.dataset.viewportVisible = '1';
        card.classList.add('is-viewport-visible');
        setTimeout(function () {
            grid.classList.remove('is-resizing');
            if (!card.classList.contains('is-expanded')) return;
            scheduleSubagentDetailWork(function () {
                if (!card.classList.contains('is-expanded')) return;
                if (!restoreSubagentCardBodyFromStash(card, currentSessionId)) {
                    queueSubagentCardBodyLoad(card, currentSessionId);
                }
            });
        }, 80);
    } else {
        requestAnimationFrame(function () {
            grid.classList.remove('is-resizing');
            if (card.isConnected && cardIntersectsGridViewport(card, grid)) {
                card.dataset.viewportVisible = '1';
                card.classList.add('is-viewport-visible');
                queueSubagentCardBodyLoad(card, currentSessionId);
            }
        });
    }
}

function syncSubagentExpandButtons(grid) {
    if (!grid) return;
    grid.querySelectorAll('.subagent-card-expand').forEach(function (btn) {
        var card = btn.closest('.subagent-grid-card');
        var on = !!(card && card.classList.contains('is-expanded'));
        btn.classList.toggle('is-active', on);
        btn.setAttribute('aria-pressed', on ? 'true' : 'false');
        btn.setAttribute('aria-label', on ? '退出全屏' : '放大显示');
        btn.setAttribute('data-ui-tip', on ? '退出全屏' : '在浮窗内全屏显示');
    });
}

function toggleSubagentCardExpanded(card) {
    if (!card) return;
    setSubagentCardExpanded(card, !card.classList.contains('is-expanded'));
}

function appendSubagentStreamEvent(agentId, event, eventIndex) {
    if (!agentId || !event || typeof event !== 'object') return false;
    var t = event.type;
    if (t === 'subagent_start') {
        if (currentSessionId) applySubagentLifecycleToStore(currentSessionId, event);
        upsertSubagentCardFromStartEvent(event);
        if (!replayingMessages) {
            hideSubagentContinueBanner();
            scheduleSubagentIncrementalSync();
        }
        return true;
    }
    if (t === 'subagent_finish') {
        if (currentSessionId) applySubagentLifecycleToStore(currentSessionId, event);
        var cardFin = document.querySelector('.subagent-grid-card[data-agent-id="' + agentId + '"]');
        if (cardFin) {
            if (event.result_preview) cardFin.dataset.resultPreview = String(event.result_preview);
            applySubagentFinishToCard(cardFin, event);
            finalizeSubagentCardStream(agentId, cardFin);
        }
        if (currentSessionId && !replayingMessages) {
            scheduleRefreshSubagentTreePanel(currentSessionId);
            updateSubagentContinueBanner(currentSessionId);
        }
        return true;
    }
    var grid = document.getElementById('subagent-grid');
    var card = grid && grid.querySelector('.subagent-grid-card[data-agent-id="' + agentId + '"]');
    if (!card) {
        if (event._subagent_forward) upsertSubagentCardFromStartEvent({ agent_id: agentId, description: agentId.slice(0, 8), running: true });
        card = grid && grid.querySelector('.subagent-grid-card[data-agent-id="' + agentId + '"]');
    }
    if (!card) return false;
    var body = card.querySelector('.subagent-card-body');
    if (!body) return false;
    if (t === 'user' || t === 'final') {
        if (!shouldStreamSubagentSummaryDom(card)) {
            trackSubagentStreamEventLightweight(card, agentId, event, eventIndex);
            return true;
        }
        if (body.dataset.loading === '1' && t !== 'user' && t !== 'final') return true;
        ensureSubagentCardStreamReady(card, agentId);
        if (body.dataset.loaded !== '1' && body.querySelector('.subagent-detail-empty')) {
            body.innerHTML = '';
        }
        if (body.dataset.loaded !== '1') body.dataset.loaded = '1';
        delete body.dataset.loading;
        var ctxSummary = getSubagentCardStreamCtx(body, card, agentId);
        dispatchSubagentCardEvent(ctxSummary, card, event, eventIndex, agentId);
        if (t === 'final') {
            card.dataset.hasFinal = '1';
            finalizeLlmStreamChunks(ctxSummary);
            markSubagentCardCompleted(card, true);
            refreshFeedChunksInCtx(ctxSummary);
            syncSubagentTurnProcessFlags(body);
            if (shouldStreamSubagentProcessDom(card)) {
                scrollSubagentCardBodyToBottom(ctxSummary);
                body.querySelectorAll('.feed-chunk').forEach(scheduleFeedChunkOverflowRefresh);
            }
            if (currentSessionId && agentId && body) {
                rememberSubagentBodyCache(currentSessionId, agentId, body.innerHTML);
                body.dataset.cacheClean = '1';
            }
        }
        bumpSubagentCardEventCount(agentId, eventIndex, !event.ephemeral);
        scheduleSubagentCardStats(card);
        return true;
    }
    if (!shouldStreamSubagentProcessDom(card)) {
        trackSubagentStreamEventLightweight(card, agentId, event, eventIndex);
        return true;
    }
    if (body.dataset.loading === '1' && !event.ephemeral && t !== 'user' && t !== 'final') return true;
    ensureSubagentCardStreamReady(card, agentId);
    if (body.dataset.loaded !== '1' && body.querySelector('.subagent-detail-empty')) {
        body.innerHTML = '';
    }
    if (body.dataset.loaded !== '1') body.dataset.loaded = '1';
    delete body.dataset.loading;
    var ctx = getSubagentCardStreamCtx(body, card, agentId);
    if (t === 'subagent_start' || t === 'subagent_finish') return true;
    if (event.ephemeral) {
        ensureSubagentTurnForProcess(ctx, eventIndex);
        if (shouldDeferSubagentProcessDom(ctx)) {
            deferSubagentProcessEvent(ctx.currentTurn, event, eventIndex);
            if (event.type === 'context_tokens') {
                card.dataset.procCtxEstimated = String(event.estimated);
                card.dataset.procCtxThreshold = String(event.threshold);
            } else if (event.type === 'process_metrics') {
                applySubagentProcessMetricsToCard(card, event);
            } else if (event.type === 'cache_stats') {
                if (event.model != null) card.dataset.procCacheModel = String(event.model);
            }
            if (event.react_iter != null) bumpAggregateMaxReactIter(card, event.react_iter);
            markSubagentTurnHasProcess(ctx.currentTurn);
            bumpSubagentCardEventCount(agentId, eventIndex, false);
            scheduleSubagentCardStats(card);
            return true;
        }
        if (event.type === 'llm_reasoning_delta' || event.type === 'llm_response_delta') {
            appendLlmStreamDelta(ctx, event, agentId);
        } else if (event.type === 'context_summary_delta') {
            appendProgressStreamDelta(ctx, event.delta, 'context-summary', agentId);
        } else if (event.type === 'key_context_delta') {
            appendKeyContextStreamDelta(ctx, event.delta, agentId);
        } else if (event.type === 'context_tokens') {
            card.dataset.procCtxEstimated = String(event.estimated);
            card.dataset.procCtxThreshold = String(event.threshold);
            scheduleSubagentCardStats(card);
        } else if (event.type === 'process_metrics') {
            applyProcessMetricsFromEvent(ctx, event);
        } else if (event.type === 'cache_stats') {
            applyCacheStatsFromEvent(ctx, event);
            scheduleSubagentCardStats(card);
        }
        markSubagentTurnHasProcess(ctx.currentTurn);
        bumpSubagentCardEventCount(agentId, eventIndex, false);
        scheduleSubagentCardStats(card);
        followStreamProcessScroll(ctx, agentId);
        return true;
    } else {
        dispatchSubagentCardEvent(ctx, card, event, eventIndex, agentId);
    }
    bumpSubagentCardEventCount(agentId, eventIndex, true);
    scheduleSubagentCardStats(card);
    followStreamProcessScroll(ctx, agentId);
    return true;
}

function handleSubagentStreamEvent(event, eventIndex, runSessionId) {
    if (!event || typeof event !== 'object') return false;
    var aid = String(event.agent_id || '');
    if (!aid) return false;
    /* fail-closed：父会话切走后，子 agent 事件不得 fall-through 到主对话区。
       数据已写入子 agent 自己的 ui_events，切回后由 refreshSubagentTreePanel 渲染。 */
    if (runSessionId && currentSessionId && runSessionId !== currentSessionId) {
        if (!replayingMessages && event.type === 'subagent_finish') {
            void tryMarkSessionUnreadComplete(runSessionId);
        }
        return true;
    }
    return appendSubagentStreamEvent(aid, event, eventIndex);
}

function handleSubagentLifecycleEvent(event) {
    if (!event || !currentSessionId) return;
    applySubagentLifecycleToStore(currentSessionId, event);
    /* 历史回放：不亮按钮 / 不写 grid / 不触发 schedule，全部交给 refreshSubagentTreePanel。 */
    if (replayingMessages) return;
    if (event.type === 'subagent_start') {
        upsertSubagentCardFromStartEvent(event);
        hideSubagentContinueBanner();
        scheduleSubagentIncrementalSync();
    } else if (event.type === 'subagent_finish') {
        var aid = String(event.agent_id || event.run_id || '');
        var card = aid && document.querySelector('.subagent-grid-card[data-agent-id="' + aid + '"]');
        if (card) {
            if (event.result_preview) card.dataset.resultPreview = String(event.result_preview);
            applySubagentFinishToCard(card, event);
            finalizeSubagentCardStream(aid, card);
        }
        scheduleRefreshSubagentTreePanel(currentSessionId);
        updateSubagentContinueBanner(currentSessionId);
    }
}

function collectSubagentGridState(grid) {
    var detailCache = {};
    if (!grid) return { detailCache: detailCache };
    if (grid.dataset.sessionId && currentSessionId && grid.dataset.sessionId !== currentSessionId) {
        return { detailCache: detailCache };
    }
    var sid = currentSessionId;
    grid.querySelectorAll('.subagent-grid-card').forEach(function (card) {
        var id = card.getAttribute('data-agent-id');
        if (!id) return;
        var body = card.querySelector('.subagent-card-body');
        if (body && body.dataset.loaded === '1' && body.dataset.loading !== '1' && body.dataset.finalOnly !== '1') {
            var html = body.innerHTML;
            if (isSubagentBodyCacheComplete(html)) {
                detailCache[id] = html;
                if (sid) rememberSubagentBodyCache(sid, id, html);
            }
        }
    });
    return { detailCache: detailCache };
}

function restoreSubagentGridState(grid, detailCache, sessionId) {
    if (!grid) return;
    grid.querySelectorAll('.subagent-grid-card').forEach(function (card) {
        var id = card.getAttribute('data-agent-id');
        if (!id) return;
        var body = card.querySelector('.subagent-card-body');
        if (!body) return;
        if (!shouldLoadSubagentCardBodies()) {
            delete body.dataset.loaded;
            delete body.dataset.loading;
            body.innerHTML = '';
            return;
        }
        var shouldMount = card.classList.contains('is-expanded') || card.dataset.viewportVisible === '1';
        if (!shouldMount) {
            delete body.dataset.loaded;
            delete body.dataset.loading;
            delete body.dataset.streamReady;
            delete body.dataset.stashed;
            body.innerHTML = '';
            return;
        }
        var cached = (detailCache && detailCache[id]) || readSubagentBodyCache(sessionId, id);
        if (card.classList.contains('is-expanded') && cached && isSubagentBodyCacheComplete(cached)) {
            body.innerHTML = cached;
            body.dataset.loaded = '1';
            body.dataset.cacheClean = '1';
            delete body.dataset.finalOnly;
            body.classList.remove('is-final-only');
            delete body.dataset.loading;
            rebindSubagentCardBody(body, card, id);
            body._subagentStreamCtx = getSubagentCardStreamCtx(body, card, id);
            requestAnimationFrame(function () { refreshAllFeedChunksUnder(body); });
        } else {
            delete body.dataset.loaded;
            delete body.dataset.loading;
            queueSubagentCardBodyLoad(card, sessionId);
        }
    });
}

function ensureSubagentBlock(ctx, event) {
    var body = getProcessBody(ctx);
    if (!body) return null;
    var aid = String(event.agent_id || event.run_id || '');
    if (!aid) return null;
    if (!ctx.subagentBlocks) ctx.subagentBlocks = {};
    var blk = ctx.subagentBlocks[aid];
    if (blk && blk.isConnected) return blk;
    blk = createSubagentBlockElement(event);
    if (!blk) return null;
    body.appendChild(blk);
    var head = blk.querySelector('.subagent-block-head');
    if (head) {
        head.addEventListener('click', function () {
            blk.classList.toggle('is-open');
            var det = blk.querySelector('.subagent-block-body');
            if (blk.classList.contains('is-open') && det && det.dataset.loaded !== '1' && det.dataset.loading !== '1') {
                loadSubagentDetailInto(det, aid, blk);
            }
        });
    }
    ctx.subagentBlocks[aid] = blk;
    handleSubagentLifecycleEvent({ type: 'subagent_start', agent_id: aid, description: event.description, subagent_type: event.subagent_type, background: event.background });
    return blk;
}

function updateSubagentBlockFinish(ctx, event) {
    var aid = String(event.agent_id || event.run_id || '');
    if (!aid) return;
    var blk = (ctx.subagentBlocks && ctx.subagentBlocks[aid]) || null;
    if (!blk || !blk.isConnected) {
        var body = getProcessBody(ctx);
        if (body) blk = body.querySelector('.subagent-block[data-agent-id="' + aid + '"]');
    }
    if (!blk) {
        handleSubagentLifecycleEvent(event);
        return;
    }
    applySubagentBlockFinish(blk, event);
    handleSubagentLifecycleEvent(event);
}
`,$t=`const humanInteractionStoreBySession = Object.create(null);
const HUMAN_INTERACTION_DRAFT_PREFIX = 'myagent-human-interaction-draft:';

function humanInteractionSessionState(sessionId) {
    var sid = String(sessionId || '');
    if (!humanInteractionStoreBySession[sid]) {
        humanInteractionStoreBySession[sid] = {
            interactions: Object.create(null),
            approvals: Object.create(null),
            loaded: false,
        };
    }
    return humanInteractionStoreBySession[sid];
}

function isHumanInteractionEventType(type) {
    var t = String(type || '');
    return t.indexOf('interaction_') === 0 || t.indexOf('approval_') === 0;
}

function humanInteractionKindForEvent(event) {
    return String((event && event.type) || '').indexOf('approval_') === 0 ? 'approval' : 'question';
}

function humanInteractionId(event, kind) {
    return String(kind === 'approval' ? (event.approval_id || '') : (event.interaction_id || ''));
}

function humanInteractionStatusFromEvent(event) {
    var explicit = String((event && event.status) || '');
    if (explicit) return explicit;
    var type = String((event && event.type) || '');
    if (type.endsWith('_resolved')) return 'resolved';
    if (type.endsWith('_cancelled')) return 'cancelled';
    if (type.endsWith('_expired')) return 'expired';
    return 'pending';
}

function applyHumanInteractionEvent(sessionId, event) {
    if (!event || !isHumanInteractionEventType(event.type)) return null;
    var sid = String(sessionId || event.session_id || '');
    if (!sid) return null;
    var kind = humanInteractionKindForEvent(event);
    var id = humanInteractionId(event, kind);
    if (!id) return null;
    var state = humanInteractionSessionState(sid);
    var collection = kind === 'approval' ? state.approvals : state.interactions;
    var previous = collection[id] || {};
    var terminalStatuses = { resolved: true, cancelled: true, expired: true };
    var incomingStatus = humanInteractionStatusFromEvent(event);
    var previousVersion = Number(previous.request_version || 0);
    var incomingVersion = Number(event.request_version || previousVersion || 0);
    if (previousVersion && incomingVersion && incomingVersion < previousVersion) return previous;
    if (terminalStatuses[previous.status] && incomingStatus === 'pending') return previous;
    var record = Object.assign({}, previous, event, {
        kind: kind,
        status: incomingStatus,
    });
    collection[id] = record;
    state.loaded = true;
    syncHumanInteractionSessionSummary(sid);
    updateHumanInteractionBanner(currentSessionId);
    return record;
}

function pendingHumanInteractionRecords(sessionId) {
    var state = humanInteractionSessionState(sessionId);
    var rows = [];
    Object.keys(state.interactions).forEach(function (id) {
        var row = state.interactions[id];
        if (row && row.status === 'pending') rows.push(row);
    });
    Object.keys(state.approvals).forEach(function (id) {
        var row = state.approvals[id];
        if (row && row.status === 'pending') rows.push(row);
    });
    rows.sort(function (a, b) {
        var kindOrder = (a.kind === 'approval' ? 0 : 1) - (b.kind === 'approval' ? 0 : 1);
        if (kindOrder) return kindOrder;
        return String(a.created_at || '').localeCompare(String(b.created_at || ''));
    });
    return rows;
}

function humanInteractionPendingCounts(sessionId) {
    var rows = pendingHumanInteractionRecords(sessionId);
    var questions = rows.filter(function (row) { return row.kind === 'question'; }).length;
    return { questions: questions, approvals: rows.length - questions, total: rows.length };
}

function pendingHumanQuestions(sessionId) {
    return pendingHumanInteractionRecords(sessionId).filter(function (row) { return row.kind === 'question'; });
}

async function confirmAndCancelPendingHumanQuestionsForMessage(sessionId) {
    var sid = String(sessionId || '');
    var rows = pendingHumanQuestions(sid);
    if (!rows.length) return true;
    var confirmed = typeof openUiModal === 'function'
        ? await openUiModal({
            title: '发送新消息并取消当前问题？',
            message: 'Agent 正在等待你的回答。发送新消息会取消当前问题，并用新消息接管当前任务。',
            confirmText: '取消问题并发送',
            cancelText: '返回回答问题',
        })
        : false;
    if (!confirmed) return false;
    try {
        var resolved = await Promise.all(rows.map(async function (row) {
            var response = await fetch('/sessions/' + encodeURIComponent(sid) + '/interactions/' + encodeURIComponent(row.interaction_id) + '/cancel', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ reason: 'superseded_by_user_message' }),
            });
            var data = await response.json();
            if (!response.ok || !data.ok) throw new Error(data.error || ('HTTP ' + response.status));
            return data.interaction || row;
        }));
        resolved.forEach(function (row) {
            clearHumanInteractionDraft(sid, row.interaction_id, row.request_version);
            var record = applyHumanInteractionEvent(sid, Object.assign({ type: 'interaction_cancelled' }, row));
            renderHumanInteractionRecord(record, sid);
        });
        return true;
    } catch (err) {
        if (typeof showUiAlert === 'function') {
            showUiAlert({
                title: '无法发送新消息',
                message: '取消当前问题失败：' + String(err && err.message ? err.message : err),
                variant: 'error',
            });
        }
        return false;
    }
}

function syncHumanInteractionSessionSummary(sessionId) {
    var sid = String(sessionId || '');
    var counts = humanInteractionPendingCounts(sid);
    var session = typeof sessionStore !== 'undefined' ? sessionStore.get(sid) : null;
    if (session) session.pending_human_interactions = counts;
    updateHumanInteractionSessionBadge(sid);
    updateHumanInteractionBanner(currentSessionId);
}

function sessionPendingHumanCounts(sessionId) {
    var sid = String(sessionId || '');
    var state = humanInteractionStoreBySession[sid];
    if (state && state.loaded) return humanInteractionPendingCounts(sid);
    var session = typeof sessionStore !== 'undefined' ? sessionStore.get(sid) : null;
    var pending = session && session.pending_human_interactions;
    var questions = Math.max(0, Number(pending && pending.questions) || 0);
    var approvals = Math.max(0, Number(pending && pending.approvals) || 0);
    var total = Math.max(questions + approvals, Number(pending && pending.total) || 0);
    return { questions: questions, approvals: approvals, total: total };
}

function sessionListForPendingCounts() {
    if (typeof sessionStore !== 'undefined' && sessionStore && typeof sessionStore.list === 'function') {
        return sessionStore.list();
    }
    return [];
}

function globalHumanInteractionPendingCounts() {
    var questions = 0;
    var approvals = 0;
    sessionListForPendingCounts().forEach(function (session) {
        if (!session || !session.id) return;
        var counts = sessionPendingHumanCounts(session.id);
        questions += counts.questions;
        approvals += counts.approvals;
    });
    return { questions: questions, approvals: approvals, total: questions + approvals };
}

function firstSessionWithPendingHumanInteractions() {
    var sessions = sessionListForPendingCounts();
    for (var i = 0; i < sessions.length; i += 1) {
        var session = sessions[i];
        if (session && session.id && sessionPendingHumanCounts(session.id).total > 0) return session;
    }
    return null;
}

function pendingCountDetailText(counts) {
    var parts = [];
    if (counts.approvals > 0) parts.push(counts.approvals + ' 个审批');
    if (counts.questions > 0) parts.push(counts.questions + ' 个回答');
    return parts.join('、') || '无待办';
}

function updateHumanInteractionSessionBadge(sessionId) {
    var sid = String(sessionId || '');
    if (!sid || !sessionsList) return;
    var row = sessionsList.querySelector('.session-item[data-session-id="' + (window.CSS && CSS.escape ? CSS.escape(sid) : sid.replace(/"/g, '\\\\"')) + '"]');
    if (!row) return;
    var head = row.querySelector('.session-item-head');
    if (!head) return;
    var badge = head.querySelector('.session-human-badge');
    var counts = sessionPendingHumanCounts(sid);
    var count = counts.total;
    if (count <= 0) {
        if (badge) badge.remove();
        row.classList.remove('has-human-pending');
        return;
    }
    if (!badge && count > 0) {
        badge = document.createElement('span');
        badge.className = 'session-human-badge';
        badge.setAttribute('aria-label', '待处理的人机交互');
        var more = head.querySelector('.session-more-wrap');
        head.insertBefore(badge, more || null);
    }
    if (badge) {
        var hasQuestions = counts.questions > 0;
        var hasApprovals = counts.approvals > 0;
        badge.textContent = hasQuestions && hasApprovals
            ? String(count)
            : ((hasQuestions ? '?' : '!') + (count > 1 ? String(count) : ''));
        var badgeLabel = hasQuestions && hasApprovals
            ? ('有 ' + count + ' 项待处理')
            : (hasQuestions ? ('有 ' + count + ' 个问题待回答') : ('有 ' + count + ' 个审批待处理'));
        badge.setAttribute('aria-label', badgeLabel);
        badge.setAttribute('data-ui-tip', badgeLabel);
        if (typeof bindUiHoverTip === 'function') bindUiHoverTip(badge);
    }
    row.classList.add('has-human-pending');
}

function updateAllHumanInteractionSessionBadges() {
    if (!sessionsList) return;
    sessionsList.querySelectorAll('.session-item[data-session-id]').forEach(function (row) {
        updateHumanInteractionSessionBadge(row.dataset.sessionId || '');
    });
    updateHumanInteractionBanner(currentSessionId);
}

function updateHumanInteractionBanner(sessionId) {
    var sid = String(sessionId || currentSessionId || '');
    var banner = document.getElementById('human-interaction-banner');
    if (!banner) return;
    var globalCounts = globalHumanInteractionPendingCounts();
    var sessionCounts = sid ? sessionPendingHumanCounts(sid) : { questions: 0, approvals: 0, total: 0 };
    var visible = globalCounts.total > 0;
    banner.classList.toggle('is-on', visible);
    banner.classList.toggle('hidden', !visible);
    var globalCountEl = banner.querySelector('.human-todo-count[data-scope="global"]');
    var globalDetailEl = banner.querySelector('.human-todo-detail[data-scope="global"]');
    var sessionCountEl = banner.querySelector('.human-todo-count[data-scope="session"]');
    var sessionDetailEl = banner.querySelector('.human-todo-detail[data-scope="session"]');
    if (globalCountEl) globalCountEl.textContent = globalCounts.total + ' 项';
    if (globalDetailEl) globalDetailEl.textContent = pendingCountDetailText(globalCounts);
    if (sessionCountEl) sessionCountEl.textContent = sessionCounts.total + ' 项';
    if (sessionDetailEl) sessionDetailEl.textContent = pendingCountDetailText(sessionCounts);
}

function focusFirstPendingHumanInteraction() {
    var stream = typeof getVisibleChatStream === 'function' ? getVisibleChatStream() : document.getElementById('chat-stream');
    var card = stream && stream.querySelector('.human-interaction-card[data-status="pending"]');
    if (!card) return;
    var needsLayout = false;
    var collapsedRow = card.closest ? card.closest('.feed-item.is-collapsed') : null;
    if (collapsedRow) {
        collapsedRow.classList.remove('is-collapsed');
        collapsedRow.dataset.manualToggle = '1';
        var rowBtn = collapsedRow.querySelector('.feed-row-collapse');
        if (rowBtn) {
            rowBtn.setAttribute('aria-expanded', 'true');
            rowBtn.setAttribute('aria-label', '收起工具行');
        }
        needsLayout = true;
    }
    var collapsedAgg = card.closest ? card.closest('.process-aggregate.is-collapsed') : null;
    if (collapsedAgg) {
        collapsedAgg.classList.remove('is-collapsed');
        var aggTop = collapsedAgg.querySelector('.process-aggregate-top');
        if (aggTop) aggTop.setAttribute('aria-expanded', 'true');
        needsLayout = true;
    }
    if (needsLayout && collapsedAgg) {
        requestAnimationFrame(function () {
            requestAnimationFrame(function () {
                if (typeof syncProcessAggregateHeightUi === 'function') syncProcessAggregateHeightUi(collapsedAgg);
                collapsedAgg.querySelectorAll('.process-aggregate-body .feed-chunk').forEach(function (ch) {
                    if (typeof refreshFeedChunkOverflow === 'function') refreshFeedChunkOverflow(ch);
                });
                if (typeof registerMermaidLazy === 'function') registerMermaidLazy(collapsedAgg);
            });
        });
    }
    requestAnimationFrame(function () {
        card.scrollIntoView({ behavior: 'smooth', block: 'center' });
        var focusTarget = card.querySelector('input:not(:disabled), textarea:not(:disabled), button:not(:disabled)');
        if (focusTarget) focusTarget.focus({ preventScroll: true });
        else {
            card.setAttribute('tabindex', '-1');
            card.focus({ preventScroll: true });
        }
    });
    card.classList.add('is-highlighted');
    setTimeout(function () { card.classList.remove('is-highlighted'); }, 1200);
}

async function handleHumanTodoFloaterAction() {
    var current = String(currentSessionId || '');
    var currentCounts = current ? sessionPendingHumanCounts(current) : { total: 0 };
    if (currentCounts.total > 0) {
        focusFirstPendingHumanInteraction();
        return;
    }
    var target = firstSessionWithPendingHumanInteractions();
    if (!target) return;
    if (typeof switchSession === 'function') {
        await switchSession(target.id, { forceReload: false });
    }
    requestAnimationFrame(function () { focusFirstPendingHumanInteraction(); });
}

function humanInteractionDraftKey(sessionId, interactionId, requestVersion) {
    return HUMAN_INTERACTION_DRAFT_PREFIX + String(sessionId || '') + ':' + String(interactionId || '') + ':' + String(requestVersion || 1);
}

function humanInteractionToolSlot(stream, toolCallId) {
    var tid = String(toolCallId || '');
    if (!stream || !tid || typeof CSS === 'undefined' || !CSS.escape) return null;
    var row = null;
    try {
        row = stream.querySelector('.feed-item.feed--tool[data-tool-call-id="' + CSS.escape(tid) + '"]');
    } catch (e) { row = null; }
    if (!row) return null;
    var slot = row.querySelector('.human-interaction-tool-slot');
    if (!slot) {
        slot = document.createElement('div');
        slot.className = 'human-interaction-tool-slot';
        row.appendChild(slot);
    }
    return slot;
}

function attachHumanInteractionCardsForToolCall(stream, toolCallId) {
    var tid = String(toolCallId || '');
    var slot = humanInteractionToolSlot(stream, tid);
    if (!slot) return false;
    var escaped = (window.CSS && CSS.escape) ? CSS.escape(tid) : tid.replace(/"/g, '\\\\"');
    var cards = Array.from(stream.querySelectorAll('.human-interaction-card[data-tool-call-id="' + escaped + '"]'));
    cards.forEach(function (card) {
        if (card.parentNode !== slot) slot.appendChild(card);
    });
    return true;
}

function attachAllHumanInteractionCards(stream) {
    if (!stream || !stream.querySelectorAll) return;
    Array.from(stream.querySelectorAll('.human-interaction-card[data-tool-call-id]')).forEach(function (card) {
        var tid = card.getAttribute('data-tool-call-id') || '';
        if (!tid) return;
        var slot = humanInteractionToolSlot(stream, tid);
        if (slot && card.parentNode !== slot) slot.appendChild(card);
    });
}

function autoReviewStatusElement(stream, toolCallId) {
    var slot = humanInteractionToolSlot(stream, toolCallId);
    if (!slot) return null;
    var el = slot.querySelector('.auto-review-status');
    if (!el) {
        el = humanElement('div', 'auto-review-status');
        slot.insertBefore(el, slot.firstChild);
    }
    return el;
}

function renderAutoReviewStatusEvent(ctx, event, runSessionId) {
    var stream = ctx && ctx.stream
        ? ctx.stream
        : (typeof getVisibleChatStream === 'function'
            ? getVisibleChatStream()
            : document.getElementById('chat-stream'));
    var tid = String((event && event.tool_call_id) || '');
    var status = String((event && event.status) || '');
    if (!stream || !tid) {
        var fallback = String((event && event.content) || '');
        if (fallback && typeof appendLog === 'function') appendLog(ctx, fallback, 'status', runSessionId);
        return;
    }
    var el = autoReviewStatusElement(stream, tid);
    if (!el) return;
    el.className = 'auto-review-status';
    el.setAttribute('data-status', status);
    if (status === 'in_progress') {
        el.classList.add('is-in-progress');
        el.appendChild(humanElement('span', 'auto-review-spin'));
        el.appendChild(humanElement(
            'span',
            'auto-review-text',
            '自动审查中：审查 Agent 正在核对你的任务意图与请求风险。'
        ));
        return;
    }
    var approved = status === 'approved';
    var risk = String((event && event.risk) || 'unknown');
    var reason = String((event && event.reason) || '');
    var unknown = risk === 'unknown' || risk === 'timed_out';
    el.classList.add(approved ? 'is-approved' : (unknown ? 'is-timedout' : 'is-denied'));
    var text = humanElement('span', 'auto-review-text');
    var title = humanElement(
        'span',
        'auto-review-title',
        approved
            ? '自动审批已批准'
            : (unknown ? '自动审查不可用（已转人工确认）' : '自动审批已拒绝')
    );
    if (!approved && !unknown) {
        title.appendChild(humanElement('span', 'auto-review-risk', risk));
    }
    text.appendChild(title);
    if (reason) {
        text.appendChild(document.createTextNode('：'));
        text.appendChild(humanElement('span', 'auto-review-reason', reason));
    }
    if (!approved && !unknown) {
        text.appendChild(humanElement(
            'div',
            'auto-review-hint',
            '可人工覆盖本次请求（只此一次，不沉淀规则）'
        ));
    }
    el.appendChild(text);
}

function persistHumanInteractionDraft(card) {
    if (!card || card.dataset.kind !== 'question') return;
    var draft = { selections: {}, others: {}, step: Number(card.dataset.step || 0), updatedAt: Date.now() };
    card.querySelectorAll('.human-question-pane').forEach(function (pane) {
        var qid = pane.dataset.questionId || '';
        draft.selections[qid] = Array.from(pane.querySelectorAll('input[data-option-id]:checked')).map(function (input) {
            return input.dataset.optionId;
        });
        var other = pane.querySelector('.human-other-input');
        draft.others[qid] = other ? other.value : '';
    });
    try { sessionStorage.setItem(humanInteractionDraftKey(card.dataset.sessionId, card.dataset.interactionId, card.dataset.requestVersion), JSON.stringify(draft)); } catch (e) { /* ignore */ }
}

function restoreHumanInteractionDraft(card) {
    if (!card || card.dataset.kind !== 'question') return null;
    var draft = null;
    try { draft = JSON.parse(sessionStorage.getItem(humanInteractionDraftKey(card.dataset.sessionId, card.dataset.interactionId, card.dataset.requestVersion)) || 'null'); } catch (e) { draft = null; }
    if (!draft) return null;
    card.querySelectorAll('.human-question-pane').forEach(function (pane) {
        var qid = pane.dataset.questionId || '';
        var selected = (draft.selections && draft.selections[qid]) || [];
        pane.querySelectorAll('input[data-option-id]').forEach(function (input) {
            input.checked = selected.indexOf(input.dataset.optionId) >= 0;
        });
        var other = pane.querySelector('.human-other-input');
        if (other && draft.others) {
            other.value = draft.others[qid] || '';
            var otherMark = pane.querySelector('.human-other-mark');
            if (otherMark && other.value) otherMark.checked = true;
        }
    });
    return draft;
}

function clearHumanInteractionDraft(sessionId, interactionId, requestVersion) {
    try { sessionStorage.removeItem(humanInteractionDraftKey(sessionId, interactionId, requestVersion)); } catch (e) { /* ignore */ }
}

function humanElement(tag, className, text) {
    var el = document.createElement(tag);
    if (className) el.className = className;
    if (text != null) el.textContent = String(text);
    return el;
}

function appendHumanCardHeader(card, record, kind) {
    var head = humanElement('div', 'human-card-head');
    var icon = humanElement('span', 'human-card-icon', kind === 'approval' ? '!' : '?');
    icon.setAttribute('aria-hidden', 'true');
    var copy = humanElement('div', 'human-card-head-copy');
    copy.appendChild(humanElement('div', 'human-card-kicker', kind === 'approval' ? '安全审批' : '需要你的回答'));
    var title = humanElement('h3', 'human-card-title', kind === 'approval'
        ? (record.title || 'Agent 请求执行操作')
        : ((record.questions && record.questions.length > 1) ? (record.questions.length + ' 个问题待确认') : ((record.questions && record.questions[0] && record.questions[0].header) || '确认下一步')));
    var recordId = String(kind === 'approval' ? (record.approval_id || '') : (record.interaction_id || ''));
    title.id = 'human-card-title-' + recordId.replace(/[^a-zA-Z0-9_-]/g, '-');
    copy.appendChild(title);
    card.setAttribute('aria-labelledby', title.id);
    var statusText = record.status === 'pending'
        ? (kind === 'approval' ? '待审批' : '待回答')
        : ({ resolved: kind === 'approval' ? '已处理' : '已回答', cancelled: '已取消', expired: '已过期' }[record.status] || record.status);
    var status = humanElement('span', 'human-card-status', statusText);
    head.appendChild(icon);
    head.appendChild(copy);
    head.appendChild(status);
    card.appendChild(head);
}

function humanQuestionPaneState(pane) {
    var selected = Array.from(pane.querySelectorAll('input[data-option-id]:checked'));
    var otherMark = pane.querySelector('.human-other-mark');
    var otherInput = pane.querySelector('.human-other-input');
    var otherSelected = !!(otherMark && otherMark.checked);
    var otherText = otherSelected && otherInput ? otherInput.value.trim() : '';
    return {
        selected: selected,
        otherSelected: otherSelected,
        otherText: otherText,
        answered: selected.length > 0 || !!otherText,
        invalidOther: otherSelected && !otherText,
    };
}

function validateHumanQuestionPane(card, pane) {
    var error = card.querySelector('.human-card-error');
    var state = humanQuestionPaneState(pane);
    if (state.invalidOther) {
        if (error) error.textContent = '请输入其他答案。';
        var other = pane.querySelector('.human-other-input');
        if (other) other.focus();
        return false;
    }
    if (!state.answered) {
        if (error) error.textContent = pane.querySelector('input[type="checkbox"]') ? '请至少选择一个选项。' : '请选择一个选项。';
        var firstControl = pane.querySelector('input');
        if (firstControl) firstControl.focus();
        return false;
    }
    if (error) error.textContent = '';
    return true;
}

function setHumanQuestionStep(card, index) {
    var panes = Array.from(card.querySelectorAll('.human-question-pane'));
    if (!panes.length) return;
    var next = Math.max(0, Math.min(Number(index) || 0, panes.length - 1));
    card.dataset.review = '0';
    card.dataset.step = String(next);
    panes.forEach(function (pane, idx) { pane.classList.toggle('is-active', idx === next); });
    card.querySelectorAll('.human-question-tab').forEach(function (tab, idx) {
        tab.classList.toggle('is-active', idx === next);
        tab.classList.toggle('is-answered', humanQuestionPaneState(panes[idx]).answered);
        tab.setAttribute('aria-selected', idx === next ? 'true' : 'false');
        tab.setAttribute('tabindex', idx === next ? '0' : '-1');
    });
    var tabs = card.querySelector('.human-question-tabs');
    if (tabs) tabs.classList.remove('hidden');
    var body = card.querySelector('.human-card-body');
    if (body) body.classList.remove('hidden');
    var review = card.querySelector('.human-question-review');
    if (review) review.classList.add('hidden');
    var progress = card.querySelector('.human-question-progress');
    if (progress) progress.textContent = '问题 ' + (next + 1) + '/' + panes.length + ' · ' + String(panes[next].dataset.questionHeader || '');
    var back = card.querySelector('.human-back-btn');
    var nextBtn = card.querySelector('.human-next-btn');
    var reviewBtn = card.querySelector('.human-review-btn');
    var submit = card.querySelector('.human-submit-btn');
    if (back) {
        back.textContent = '上一步';
        back.classList.toggle('hidden', panes.length === 1);
        back.disabled = next === 0;
    }
    if (nextBtn) nextBtn.classList.toggle('hidden', next >= panes.length - 1);
    if (reviewBtn) reviewBtn.classList.toggle('hidden', panes.length === 1 || next < panes.length - 1);
    if (submit) submit.classList.toggle('hidden', panes.length > 1);
    if (card.dataset.draftReady === '1') persistHumanInteractionDraft(card);
}

function showHumanQuestionReview(card) {
    var panes = Array.from(card.querySelectorAll('.human-question-pane'));
    var invalidIndex = panes.findIndex(function (pane) { return !validateHumanQuestionPane(card, pane); });
    if (invalidIndex >= 0) {
        setHumanQuestionStep(card, invalidIndex);
        return false;
    }
    var review = card.querySelector('.human-question-review');
    if (!review) return false;
    review.innerHTML = '';
    review.appendChild(humanElement('h4', 'human-review-title', '确认回答'));
    panes.forEach(function (pane) {
        var state = humanQuestionPaneState(pane);
        var row = humanElement('div', 'human-review-row');
        row.appendChild(humanElement('div', 'human-review-label', pane.dataset.questionHeader || '问题'));
        var labels = state.selected.map(function (input) {
            var option = input.closest('.human-option');
            var label = option && option.querySelector('.human-option-label');
            return label ? label.textContent : input.dataset.optionId;
        });
        if (state.otherText) labels.push(state.otherText);
        row.appendChild(humanElement('div', 'human-review-value', labels.join('、')));
        review.appendChild(row);
    });
    card.dataset.review = '1';
    var tabs = card.querySelector('.human-question-tabs');
    if (tabs) tabs.classList.add('hidden');
    var body = card.querySelector('.human-card-body');
    if (body) body.classList.add('hidden');
    review.classList.remove('hidden');
    var back = card.querySelector('.human-back-btn');
    if (back) {
        back.classList.remove('hidden');
        back.disabled = false;
        back.textContent = '返回修改';
    }
    var nextBtn = card.querySelector('.human-next-btn');
    if (nextBtn) nextBtn.classList.add('hidden');
    var reviewBtn = card.querySelector('.human-review-btn');
    if (reviewBtn) reviewBtn.classList.add('hidden');
    var submit = card.querySelector('.human-submit-btn');
    if (submit) submit.classList.remove('hidden');
    review.setAttribute('tabindex', '-1');
    review.focus();
    persistHumanInteractionDraft(card);
    return true;
}

function createHumanQuestionCard(record, sessionId) {
    var card = humanElement('article', 'human-interaction-card human-question-card');
    card.dataset.kind = 'question';
    card.dataset.sessionId = sessionId;
    card.dataset.interactionId = String(record.interaction_id || '');
    card.dataset.requestVersion = String(record.request_version || 1);
    appendHumanCardHeader(card, record, 'question');
    var questions = Array.isArray(record.questions) ? record.questions : [];
    if (questions.length > 1) {
        var tabs = humanElement('div', 'human-question-tabs');
        tabs.setAttribute('role', 'tablist');
        questions.forEach(function (question, index) {
            var tab = humanElement('button', 'human-question-tab', question.header || ('问题 ' + (index + 1)));
            tab.type = 'button';
            tab.id = 'human-tab-' + record.interaction_id + '-' + index;
            tab.setAttribute('role', 'tab');
            tab.setAttribute('aria-controls', 'human-pane-' + record.interaction_id + '-' + index);
            tab.addEventListener('click', function () {
                var current = Number(card.dataset.step || 0);
                if (index > current && !validateHumanQuestionPane(card, card.querySelectorAll('.human-question-pane')[current])) return;
                setHumanQuestionStep(card, index);
            });
            tab.addEventListener('keydown', function (event) {
                if (event.key !== 'ArrowLeft' && event.key !== 'ArrowRight') return;
                event.preventDefault();
                var target = index + (event.key === 'ArrowRight' ? 1 : -1);
                target = Math.max(0, Math.min(target, questions.length - 1));
                var current = Number(card.dataset.step || 0);
                if (target > current && !validateHumanQuestionPane(card, card.querySelectorAll('.human-question-pane')[current])) return;
                setHumanQuestionStep(card, target);
                var targetTab = card.querySelectorAll('.human-question-tab')[target];
                if (targetTab) targetTab.focus();
            });
            tabs.appendChild(tab);
        });
        card.appendChild(tabs);
        card.appendChild(humanElement('div', 'human-question-progress'));
    }
    var body = humanElement('div', 'human-card-body');
    questions.forEach(function (question, qIndex) {
        var pane = humanElement('fieldset', 'human-question-pane');
        pane.id = 'human-pane-' + record.interaction_id + '-' + qIndex;
        pane.setAttribute('role', 'tabpanel');
        if (questions.length > 1) pane.setAttribute('aria-labelledby', 'human-tab-' + record.interaction_id + '-' + qIndex);
        pane.dataset.questionId = String(question.question_id || ('q' + (qIndex + 1)));
        pane.dataset.questionHeader = String(question.header || ('问题 ' + (qIndex + 1)));
        pane.appendChild(humanElement('legend', 'human-question-text', question.question || ''));
        pane.appendChild(humanElement('div', 'human-question-hint', question.multi_select ? '可多选' : '单选'));
        var options = humanElement('div', 'human-options');
        (question.options || []).forEach(function (option, optionIndex) {
            var label = humanElement('label', 'human-option');
            var input = document.createElement('input');
            input.type = question.multi_select ? 'checkbox' : 'radio';
            input.name = 'human-' + record.interaction_id + '-' + pane.dataset.questionId;
            input.dataset.optionId = String(option.option_id || '');
            var copy = humanElement('span', 'human-option-copy');
            copy.appendChild(humanElement('span', 'human-option-label', option.label || ''));
            var description = humanElement('span', 'human-option-description', option.description || '');
            description.id = 'human-option-desc-' + record.interaction_id + '-' + qIndex + '-' + optionIndex;
            input.setAttribute('aria-describedby', description.id);
            copy.appendChild(description);
            if (option.preview) {
                var details = humanElement('details', 'human-option-preview');
                details.appendChild(humanElement('summary', '', '查看预览'));
                details.appendChild(humanElement('pre', '', option.preview));
                copy.appendChild(details);
            }
            label.appendChild(input);
            label.appendChild(copy);
            options.appendChild(label);
        });
        var other = humanElement('label', 'human-option human-option-other');
        var otherMark = document.createElement('input');
        otherMark.type = question.multi_select ? 'checkbox' : 'radio';
        otherMark.name = 'human-' + record.interaction_id + '-' + pane.dataset.questionId;
        otherMark.className = 'human-other-mark';
        var otherCopy = humanElement('span', 'human-option-copy');
        otherCopy.appendChild(humanElement('span', 'human-option-label', '其他'));
        var otherInput = document.createElement('textarea');
        otherInput.className = 'human-other-input';
        otherInput.rows = 2;
        otherInput.maxLength = 2000;
        otherInput.placeholder = '输入你的答案…';
        otherInput.setAttribute('aria-label', '其他答案');
        otherInput.addEventListener('focus', function () { otherMark.checked = true; persistHumanInteractionDraft(card); });
        otherCopy.appendChild(otherInput);
        other.appendChild(otherMark);
        other.appendChild(otherCopy);
        options.appendChild(other);
        options.addEventListener('change', function () { persistHumanInteractionDraft(card); });
        options.addEventListener('input', function () { persistHumanInteractionDraft(card); });
        pane.appendChild(options);
        body.appendChild(pane);
    });
    card.appendChild(body);
    var review = humanElement('section', 'human-question-review hidden');
    review.setAttribute('aria-label', '回答摘要');
    card.appendChild(review);
    var error = humanElement('div', 'human-card-error');
    error.setAttribute('role', 'alert');
    card.appendChild(error);
    var actions = humanElement('div', 'human-card-actions');
    var cancel = humanElement('button', 'human-secondary-btn', '不回答');
    cancel.type = 'button';
    cancel.title = '取消当前问题并让 Agent 继续';
    cancel.addEventListener('click', function () { void cancelHumanQuestion(card); });
    var nav = humanElement('div', 'human-card-nav');
    var back = humanElement('button', 'human-secondary-btn human-back-btn', '上一步');
    back.type = 'button';
    back.addEventListener('click', function () {
        if (card.dataset.review === '1') setHumanQuestionStep(card, questions.length - 1);
        else setHumanQuestionStep(card, Number(card.dataset.step || 0) - 1);
    });
    var next = humanElement('button', 'human-primary-btn human-next-btn', '下一步');
    next.type = 'button';
    next.addEventListener('click', function () {
        var current = Number(card.dataset.step || 0);
        var pane = card.querySelectorAll('.human-question-pane')[current];
        if (validateHumanQuestionPane(card, pane)) setHumanQuestionStep(card, current + 1);
    });
    var reviewButton = humanElement('button', 'human-primary-btn human-review-btn', '确认回答');
    reviewButton.type = 'button';
    reviewButton.addEventListener('click', function () { showHumanQuestionReview(card); });
    var submit = humanElement('button', 'human-primary-btn human-submit-btn', '提交答案');
    submit.type = 'button';
    submit.addEventListener('click', function () { void submitHumanQuestion(card); });
    nav.appendChild(back);
    nav.appendChild(next);
    nav.appendChild(reviewButton);
    nav.appendChild(submit);
    actions.appendChild(cancel);
    actions.appendChild(nav);
    card.appendChild(actions);
    var draft = restoreHumanInteractionDraft(card);
    setHumanQuestionStep(card, draft && Number.isFinite(Number(draft.step)) ? Number(draft.step) : 0);
    card.dataset.draftReady = '1';
    card.addEventListener('keydown', function (event) {
        if (event.key !== 'Enter' || (!event.ctrlKey && !event.metaKey)) return;
        event.preventDefault();
        if (questions.length > 1 && card.dataset.review !== '1') showHumanQuestionReview(card);
        else void submitHumanQuestion(card);
    });
    return card;
}

function collectHumanQuestionAnswers(card) {
    var answers = [];
    var invalidPane = null;
    card.querySelectorAll('.human-question-pane').forEach(function (pane) {
        var selected = Array.from(pane.querySelectorAll('input[data-option-id]:checked')).map(function (input) { return input.dataset.optionId; });
        var otherMark = pane.querySelector('.human-other-mark');
        var otherInput = pane.querySelector('.human-other-input');
        var otherText = otherMark && otherMark.checked && otherInput ? otherInput.value.trim() : '';
        if ((!selected.length && !otherText || (otherMark && otherMark.checked && !otherText)) && !invalidPane) invalidPane = pane;
        answers.push({
            question_id: pane.dataset.questionId || '',
            selected_option_ids: selected,
            other_text: otherText || null,
            notes: null,
        });
    });
    return { answers: answers, invalidPane: invalidPane };
}

function setHumanInteractionSubmitting(card, submitting, label) {
    if (!card) return;
    card.dataset.submitting = submitting ? '1' : '0';
    card.classList.toggle('is-submitting', !!submitting);
    card.setAttribute('aria-busy', submitting ? 'true' : 'false');
    var status = card.querySelector('.human-card-status');
    if (status) {
        if (!status.dataset.defaultLabel) status.dataset.defaultLabel = status.textContent || '';
        status.textContent = submitting ? (label || '正在提交…') : status.dataset.defaultLabel;
    }
    var primary = card.querySelector('.human-submit-btn, .human-allow-btn');
    if (!primary) return;
    if (!primary.dataset.defaultLabel) primary.dataset.defaultLabel = primary.textContent || '';
    primary.textContent = submitting ? (label || '正在提交…') : primary.dataset.defaultLabel;
}

async function submitHumanQuestion(card) {
    if (!card || card.dataset.submitting === '1') return;
    var collected = collectHumanQuestionAnswers(card);
    var error = card.querySelector('.human-card-error');
    if (collected.invalidPane) {
        var panes = Array.from(card.querySelectorAll('.human-question-pane'));
        setHumanQuestionStep(card, panes.indexOf(collected.invalidPane));
        if (error) error.textContent = '请完成当前问题后再提交。';
        return;
    }
    setHumanInteractionSubmitting(card, true, '正在提交…');
    if (error) error.textContent = '';
    try {
        var response = await fetch('/sessions/' + encodeURIComponent(card.dataset.sessionId) + '/interactions/' + encodeURIComponent(card.dataset.interactionId) + '/resolve', {
            method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ answers: collected.answers }),
        });
        var data = await response.json();
        if (!response.ok || !data.ok) throw new Error(data.error || ('HTTP ' + response.status));
        clearHumanInteractionDraft(card.dataset.sessionId, card.dataset.interactionId, card.dataset.requestVersion);
        var record = applyHumanInteractionEvent(card.dataset.sessionId, Object.assign({ type: 'interaction_resolved' }, data.interaction || {}));
        renderHumanInteractionRecord(record, card.dataset.sessionId, card.parentNode);
    } catch (err) {
        setHumanInteractionSubmitting(card, false);
        if (error) error.textContent = '提交失败：' + String(err && err.message ? err.message : err);
    }
}

async function cancelHumanQuestion(card) {
    if (!card || card.dataset.submitting === '1') return;
    setHumanInteractionSubmitting(card, true, '正在取消…');
    try {
        var response = await fetch('/sessions/' + encodeURIComponent(card.dataset.sessionId) + '/interactions/' + encodeURIComponent(card.dataset.interactionId) + '/cancel', {
            method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ reason: 'user_cancelled' }),
        });
        var data = await response.json();
        if (!response.ok || !data.ok) throw new Error(data.error || ('HTTP ' + response.status));
        clearHumanInteractionDraft(card.dataset.sessionId, card.dataset.interactionId, card.dataset.requestVersion);
        var record = applyHumanInteractionEvent(card.dataset.sessionId, Object.assign({ type: 'interaction_cancelled' }, data.interaction || {}));
        renderHumanInteractionRecord(record, card.dataset.sessionId, card.parentNode);
    } catch (err) {
        setHumanInteractionSubmitting(card, false);
        var error = card.querySelector('.human-card-error');
        if (error) error.textContent = '取消失败：' + String(err && err.message ? err.message : err);
    }
}

function createHumanApprovalCard(record, sessionId) {
    var danger = record.approval_level === 'danger';
    var forced = !!record.force_approval;
    var card = humanElement('article', 'human-interaction-card human-approval-card' + (danger ? ' is-danger' : ''));
    card.dataset.kind = 'approval';
    card.dataset.sessionId = sessionId;
    card.dataset.interactionId = String(record.approval_id || '');
    appendHumanCardHeader(card, record, 'approval');
    var body = humanElement('div', 'human-card-body');
    if (record.subtitle) body.appendChild(humanElement('div', 'human-approval-subtitle', record.subtitle));
    body.appendChild(humanElement('div', 'human-approval-message', record.message || '是否允许 Agent 执行此操作？'));
    if (danger && record.consequence) {
        body.appendChild(humanElement('div', 'human-approval-consequence', record.consequence));
    }
    if (record.tool) {
        var detail = humanElement('div', 'human-approval-detail');
        detail.appendChild(humanElement('span', '', '工具'));
        detail.appendChild(humanElement('code', '', record.tool));
        body.appendChild(detail);
    }
    if (!forced && record.rule_pattern) {
        body.appendChild(
            humanElement(
                'div',
                'human-approval-rule-hint',
                '“始终允许此类操作”将保存为长期规则：' + record.rule_pattern
            )
        );
    }
    card.appendChild(body);
    var error = humanElement('div', 'human-card-error');
    error.setAttribute('role', 'alert');
    card.appendChild(error);
    var actions = humanElement('div', 'human-card-actions human-approval-actions');
    var deny = humanElement('button', 'human-secondary-btn human-deny-btn', danger ? '拒绝执行' : '拒绝');
    deny.type = 'button';
    deny.addEventListener('click', function () { void resolveHumanApproval(card, 'deny'); });
    actions.appendChild(deny);
    if (!forced) {
        var sessionAllow = humanElement('button', 'human-secondary-btn', '本任务内允许相同请求');
        sessionAllow.type = 'button';
        sessionAllow.title = '仅在当前任务中，对命令、参数、路径和工作目录完全相同的请求自动放行';
        sessionAllow.addEventListener('click', function () { void resolveHumanApproval(card, 'allow_session'); });
        actions.appendChild(sessionAllow);
    }
    if (!forced && record.allow_always_available && record.rule_pattern) {
        var always = humanElement('button', 'human-secondary-btn', '始终允许此类操作');
        always.type = 'button';
        if (record.rule_pattern) always.title = '保存为长期规则，后续匹配时自动放行：' + record.rule_pattern;
        always.addEventListener('click', function () { void resolveHumanApproval(card, 'allow_always'); });
        actions.appendChild(always);
    }
    if (!forced && record.external_workspace_grantable) {
        var externalGrant = humanElement('button', 'human-secondary-btn human-external-grant-btn', '允许工作区外处理（写/删/Shell）');
        externalGrant.type = 'button';
        externalGrant.title = '一次性授权：写、删除和 Shell 在工作区外的操作以后自动放行，直到你在设置中关闭';
        externalGrant.addEventListener('click', function () { void resolveHumanApproval(card, 'allow_external_workspace'); });
        actions.appendChild(externalGrant);
    }
    var allow = humanElement('button', 'human-primary-btn human-allow-btn', '允许一次');
    allow.type = 'button';
    allow.title = '仅放行这一次；执行后授权立即失效';
    allow.addEventListener('click', function () { void resolveHumanApproval(card, 'allow_once'); });
    actions.appendChild(allow);
    card.appendChild(actions);
    return card;
}

async function resolveHumanApproval(card, decision) {
    if (!card || card.dataset.submitting === '1') return;
    setHumanInteractionSubmitting(card, true, '正在处理…');
    try {
        var response = await fetch('/sessions/' + encodeURIComponent(card.dataset.sessionId) + '/approvals/' + encodeURIComponent(card.dataset.interactionId) + '/resolve', {
            method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ decision: decision }),
        });
        var data = await response.json();
        if (!response.ok || !data.ok) {
            if (data.approval) {
                var staleRecord = applyHumanInteractionEvent(card.dataset.sessionId, Object.assign({ type: 'approval_cancelled' }, data.approval));
                renderHumanInteractionRecord(staleRecord, card.dataset.sessionId, card.parentNode);
                return;
            }
            throw new Error(data.error || ('HTTP ' + response.status));
        }
        var record = applyHumanInteractionEvent(card.dataset.sessionId, Object.assign({ type: 'approval_resolved' }, data.approval || {}));
        renderHumanInteractionRecord(record, card.dataset.sessionId, card.parentNode);
    } catch (err) {
        setHumanInteractionSubmitting(card, false);
        var error = card.querySelector('.human-card-error');
        if (error) error.textContent = '处理失败：' + String(err && err.message ? err.message : err);
    }
}

function createHumanTerminalCard(record, sessionId) {
    var kind = record.kind === 'approval' ? 'approval' : 'question';
    var card = humanElement('article', 'human-interaction-card is-terminal');
    card.dataset.kind = kind;
    card.dataset.sessionId = sessionId;
    card.dataset.interactionId = String(kind === 'approval' ? record.approval_id : record.interaction_id);
    appendHumanCardHeader(card, record, kind);
    var summary = humanElement('div', 'human-terminal-summary');
    if (record.status === 'cancelled') {
        summary.textContent = record.reason || '该请求已取消。';
    } else if (record.status === 'expired') {
        summary.textContent = '该请求已过期。';
    } else if (kind === 'approval') {
        summary.textContent = record.decision === 'deny'
            ? '你已拒绝本次操作。'
            : (record.decision === 'allow_always'
                ? ('已保存长期规则，后续匹配的操作将自动放行。' + (record.rule_pattern ? '（规则：' + record.rule_pattern + '）' : ''))
                : (record.decision === 'allow_session'
                    ? '当前任务内将自动允许完全相同的请求。'
                    : '已允许这一次；执行后授权失效。'));
    } else {
        var answers = Array.isArray(record.answers) ? record.answers : [];
        var questionsById = Object.create(null);
        (record.questions || []).forEach(function (question) {
            questionsById[String(question.question_id || '')] = question;
        });
        answers.forEach(function (answer) {
            var line = humanElement('div', 'human-terminal-answer');
            var values = (answer.selected_labels || []).slice();
            if (answer.other_text) values.push(answer.other_text);
            var question = questionsById[String(answer.question_id || '')] || {};
            line.appendChild(humanElement('span', 'human-terminal-answer-label', question.header || '回答'));
            line.appendChild(humanElement('span', 'human-terminal-answer-value', values.join('、') || '已回答'));
            summary.appendChild(line);
        });
    }
    card.appendChild(summary);
    return card;
}

function renderHumanInteractionRecord(record, sessionId, stream) {
    if (!record) return null;
    var sid = String(sessionId || record.session_id || '');
    var kind = record.kind === 'approval' ? 'approval' : 'question';
    var id = String(kind === 'approval' ? (record.approval_id || '') : (record.interaction_id || ''));
    if (!id) return null;
    stream = stream && stream.querySelectorAll ? stream : (typeof getVisibleChatStream === 'function' ? getVisibleChatStream() : document.getElementById('chat-stream'));
    if (!stream) return null;
    var existing = Array.from(stream.querySelectorAll('.human-interaction-card')).find(function (card) {
        return card.dataset.kind === kind && card.dataset.interactionId === id;
    });
    var restoreFocus = !!(existing && existing.contains(document.activeElement));
    var card = record.status === 'pending'
        ? (kind === 'approval' ? createHumanApprovalCard(record, sid) : createHumanQuestionCard(record, sid))
        : createHumanTerminalCard(record, sid);
    card.dataset.status = record.status || 'pending';
    var toolCallId = String(record.tool_call_id || '');
    if (toolCallId) card.dataset.toolCallId = toolCallId;
    if (existing && existing.parentNode) existing.parentNode.replaceChild(card, existing);
    else {
        var slot = humanInteractionToolSlot(stream, toolCallId);
        (slot || stream).appendChild(card);
    }
    if (toolCallId) {
        attachHumanInteractionCardsForToolCall(stream, toolCallId);
    }
    if (restoreFocus && record.status !== 'pending') {
        card.setAttribute('tabindex', '-1');
        requestAnimationFrame(function () { card.focus({ preventScroll: true }); });
    }
    return card;
}

function renderHumanInteractionEvent(ctx, event, runSessionId) {
    var sid = String(runSessionId || event.session_id || currentSessionId || '');
    var record = applyHumanInteractionEvent(sid, event);
    var stream = ctx && ctx.stream ? ctx.stream : null;
    return renderHumanInteractionRecord(record, sid, stream);
}

function renderPendingHumanInteractions(sessionId) {
    var sid = String(sessionId || '');
    if (!sid || sid !== String(currentSessionId || '')) return;
    var stream = typeof getVisibleChatStream === 'function' ? getVisibleChatStream() : document.getElementById('chat-stream');
    pendingHumanInteractionRecords(sid).forEach(function (record) { renderHumanInteractionRecord(record, sid, stream); });
    if (typeof attachAllHumanInteractionCards === 'function') attachAllHumanInteractionCards(stream);
    updateHumanInteractionBanner(sid);
}

async function refreshHumanInteractions(sessionId, options) {
    var sid = String(sessionId || '');
    if (!sid) return false;
    options = options || {};
    try {
        var responses = await Promise.all([
            fetch('/sessions/' + encodeURIComponent(sid) + '/interactions?status=pending'),
            fetch('/sessions/' + encodeURIComponent(sid) + '/approvals?status=pending'),
        ]);
        if (!responses[0].ok || !responses[1].ok) throw new Error('HTTP ' + responses[0].status + '/' + responses[1].status);
        var payloads = await Promise.all([responses[0].json(), responses[1].json()]);
        var state = humanInteractionSessionState(sid);
        state.interactions = Object.create(null);
        state.approvals = Object.create(null);
        (payloads[0].interactions || []).forEach(function (row) {
            row.kind = 'question';
            state.interactions[String(row.interaction_id || '')] = row;
        });
        (payloads[1].approvals || []).forEach(function (row) {
            row.kind = 'approval';
            state.approvals[String(row.approval_id || '')] = row;
        });
        state.loaded = true;
        syncHumanInteractionSessionSummary(sid);
        if (options.render !== false && sid === String(currentSessionId || '')) renderPendingHumanInteractions(sid);
        return true;
    } catch (err) {
        console.error('加载待处理交互失败:', err);
        return false;
    }
}

(function bindHumanInteractionBanner() {
    var button = document.getElementById('human-interaction-banner-btn');
    if (button) button.addEventListener('click', function () { void handleHumanTodoFloaterAction(); });
})();
`,zt=`var permissionModeBusy = false;
var currentPermissionStatus = null;
var mcpRegistrationPromptBusy = false;
var mcpRegistrationPrompted = new Set();

var PERMISSION_MODE_ICONS = {
    ask_for_approval: '<path d="M12 3l7 3v5c0 4.5-3 8.3-7 10-4-1.7-7-5.5-7-10V6z"/>',
    approve_for_me: '<path d="M12 3l7 3v5c0 4.5-3 8.3-7 10-4-1.7-7-5.5-7-10V6z"/><path d="M9.2 11.8l2 2 3.8-4"/>',
    full_access: '<rect x="4" y="10" width="16" height="10" rx="2"/><path d="M8 10V7a4 4 0 0 1 7.6-1.6"/><circle cx="12" cy="15" r="1" fill="currentColor"/>',
};

function permissionModeLabel(mode) {
    if (mode === 'approve_for_me') return '替我审批';
    if (mode === 'full_access') return '完全访问权限';
    return '请求批准';
}

function permissionControlsEnabled(status) {
    if (status && status.security_enabled === false) return false;
    var flags = typeof window !== 'undefined' ? window.__MYAGENT_FEATURES__ : null;
    return !(flags && flags.security === false);
}

function syncPermissionControlVisibility(status) {
    var control = document.getElementById('permission-mode-control');
    var enabled = permissionControlsEnabled(status);
    if (control) control.hidden = !enabled;
    var menu = document.getElementById('permission-mode-menu');
    var trigger = document.getElementById('permission-mode-trigger');
    if (!enabled && menu) menu.classList.remove('is-open');
    if (!enabled && trigger) {
        trigger.classList.remove('is-open');
        trigger.setAttribute('aria-expanded', 'false');
    }
    return enabled;
}

function maybeShowGlobalFullAccessNotice(status) {
    if (!status || status.mode !== 'full_access' || status.security_enabled === false) return;
    var key = 'myagent-full-access-notice:' + String(status.updated_at || 'legacy');
    try {
        if (window.sessionStorage.getItem(key) === '1') return;
        window.sessionStorage.setItem(key, '1');
    } catch (_) {}
    var notice = document.createElement('div');
    notice.className = 'permission-global-warning-toast';
    notice.textContent = '完全访问已开启：Agent 可以直接读写文件、执行命令和联网，不再逐项询问。重启后依然有效，直到你手动切回“请求批准”。';
    var host = document.querySelector('.chat-stage') || document.querySelector('.main-center') || document.body;
    host.appendChild(notice);
    window.setTimeout(function () { notice.remove(); }, 9000);
}

function renderPermissionMode(status) {
    currentPermissionStatus = status || null;
    var controlsEnabled = syncPermissionControlVisibility(status);
    maybeShowGlobalFullAccessNotice(status);
    var trigger = document.getElementById('permission-mode-trigger');
    var label = document.getElementById('permission-mode-current');
    var triggerIco = document.getElementById('permission-mode-ico');
    var menu = document.getElementById('permission-mode-menu');
    if (label) label.textContent = permissionModeLabel(status && status.mode);
    if (trigger) trigger.setAttribute('data-mode', String((status && status.mode) || 'ask_for_approval'));
    if (trigger) {
        var fullAccess = !!status && status.mode === 'full_access';
        trigger.classList.toggle('is-global-full-access', fullAccess);
        trigger.title = fullAccess
            ? '完全访问已开启；Agent 可读写文件、执行命令和联网，不会自动关闭。'
            : '更改权限';
    }
    var settingsStatus = document.getElementById('settings-security-status');
    if (settingsStatus && status) {
        settingsStatus.textContent = status.mode === 'full_access'
            ? '警告：完全访问已开启，Agent 可直接操作文件、终端和网络，重启后不会自动关闭，直到你手动切换。'
            : permissionModeLabel(status.mode) + '（全局统一，对所有任务生效）';
    }
    if (triggerIco) {
        var mode = status && status.mode;
        triggerIco.innerHTML = PERMISSION_MODE_ICONS[mode] || PERMISSION_MODE_ICONS.ask_for_approval;
    }
    if (trigger) trigger.disabled = !controlsEnabled || permissionModeBusy || !currentSessionId;
    if (!menu) return;
    var available = (status && status.available_modes) || { ask_for_approval: true };
    Array.from(menu.querySelectorAll('[data-permission-mode]')).forEach(function (button) {
        var mode = button.getAttribute('data-permission-mode');
        button.disabled = permissionModeBusy || available[mode] !== true;
        var active = !!status && status.mode === mode;
        button.classList.toggle('is-active', active);
        button.classList.toggle('is-disabled', button.disabled);
        button.setAttribute('aria-selected', active ? 'true' : 'false');
    });
}

async function refreshPermissionModeSelector(sessionId) {
    var sid = String(sessionId || currentSessionId || '');
    var previousPermissionStatus = currentPermissionStatus;
    if (!sid) {
        renderPermissionMode(null);
        return;
    }
    try {
        var response = await fetch('/sessions/' + encodeURIComponent(sid) + '/permissions', { cache: 'no-store' });
        var data = await response.json();
        if (!response.ok || !data.ok) throw new Error(data.error || ('HTTP ' + response.status));
        if (sid === String(currentSessionId || '')) renderPermissionMode(data);
    } catch (error) {
        // A read failure is not a global mode transition. Restore the last
        // known badge instead of presenting the fallback as a real downgrade.
        renderPermissionMode(previousPermissionStatus);
    }
}

async function selectPermissionMode(mode) {
    if (permissionModeBusy || !currentSessionId) return;
    if (mode === 'full_access') {
        var accepted = await openUiModal({
            title: '完全访问权限',
            subtitle: '仅在信任 Agent 时才建议开启',
            message: '完全访问开启后，Agent 可以直接读写文件、执行命令和联网，不再逐项征求你的同意。它拥有你当前账号能做的权限，可能会读取凭据、修改系统或删除文件。此设置对所有会话生效，重启后也不会自动关闭，直到你手动切回“请求批准”。是否继续？',
            danger: true,
            confirmText: '确认切换',
            cancelText: '取消',
        });
        if (!accepted) return;
    }
    permissionModeBusy = true;
    renderPermissionMode(currentPermissionStatus);
    try {
        var response = await fetch('/sessions/' + encodeURIComponent(currentSessionId) + '/permissions', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ mode: mode }),
        });
        var data = await response.json();
        if (!response.ok || !data.ok) throw new Error(data.error || ('HTTP ' + response.status));
        renderPermissionMode(data);
    } catch (error) {
        showUiAlert({
            title: '切换权限失败',
            message: String(error && error.message ? error.message : error),
            confirmText: '知道了',
        });
    } finally {
        permissionModeBusy = false;
        renderPermissionMode(currentPermissionStatus);
    }
}

function securityRulesContext() {
    var win = typeof window !== 'undefined' ? window : globalThis;
    return {
        sessionId: String(currentSessionId || ''),
        workspace: String((win && win.__WORK_DIR__) || ''),
    };
}

function securityRuleLabel(rule) {
    var action = String(rule.action || '');
    var pattern = String(rule.pattern || '');
    if (action === 'process.exec') return 'Shell ' + pattern;
    if (action === 'fs.read') return '读取 ' + pattern;
    if (action === 'fs.write') return '写入 ' + pattern;
    if (action === 'fs.delete') return '删除 ' + pattern;
    if (action === 'network.connect') return '网络 ' + pattern;
    if (action === 'web.search') return '联网搜索 ' + pattern;
    if (action === 'mcp.call' || action === 'plugin.call') return (action === 'mcp.call' ? 'MCP ' : '插件 ') + pattern;
    return action + ' ' + pattern;
}

async function refreshWebFetchDomains() {
    var editor = document.getElementById('settings-security-web-fetch-domains');
    var statusEl = document.getElementById('settings-security-web-fetch-status');
    if (!editor) return;
    try {
        var response = await fetch('/api/security/web-fetch-domains', { cache: 'no-store' });
        var data = await response.json();
        if (!response.ok || !data.ok) throw new Error(data.error || ('HTTP ' + response.status));
        editor.value = (Array.isArray(data.domains) ? data.domains : []).join('\\n');
        if (statusEl) statusEl.textContent = '已加载 ' + editor.value.split('\\n').filter(Boolean).length + ' 个自定义域名（内置清单始终生效）。';
    } catch (error) {
        if (statusEl) statusEl.textContent = '读取预批准域名失败：' + String(error && error.message ? error.message : error);
    }
}

function extensionTrustLabel(item) {
    var kind = item.kind === 'mcp' ? 'MCP' : '插件';
    return kind + ' / ' + String(item.name || item.extension_id || 'unknown');
}

function mcpRegistrationMessage(item) {
    var capabilities = item && item.capabilities ? item.capabilities : {};
    var lines = [
        '连接前需要确认一次当前 MCP 配置。确认仅允许启动或连接服务器并发现工具；每次工具调用仍按当前权限模式审批。',
        '',
        '类型：' + String(item.runtime || capabilities.transport || 'unknown'),
        '命令或地址：' + String(item.source || '未提供'),
    ];
    if (capabilities.working_directory) lines.push('工作目录：' + String(capabilities.working_directory));
    var envNames = Array.isArray(capabilities.configured_environment)
        ? capabilities.configured_environment
        : [];
    if (envNames.length) lines.push('配置环境变量：' + envNames.join(', '));
    lines.push('', '该服务器以当前操作系统用户权限运行，不是硬隔离。');
    return lines.join('\\n');
}

async function submitMcpRegistration(item, approved) {
    var response = await fetch(
        '/api/security/mcp/' + encodeURIComponent(item.extension_id) + '/registration',
        {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                approved: !!approved,
                config_digest: String(item.config_digest || ''),
            }),
        }
    );
    var data = await response.json();
    if (!response.ok || !data.ok) throw new Error(data.error || ('HTTP ' + response.status));
    return data.registration;
}

async function confirmMcpRegistration(item) {
    var accepted = await openUiModal({
        title: '注册 MCP 服务器',
        subtitle: extensionTrustLabel(item),
        message: mcpRegistrationMessage(item),
        danger: true,
        confirmText: '确认并连接',
        cancelText: '暂不连接',
    });
    if (!accepted) return false;
    await submitMcpRegistration(item, true);
    return true;
}

async function promptPendingMcpRegistrations(rows) {
    if (mcpRegistrationPromptBusy) return;
    var pending = (Array.isArray(rows) ? rows : []).filter(function (item) {
        var digestKey = String(item.extension_id || '') + ':' + String(item.config_digest || '');
        return item.kind === 'mcp'
            && item.registration_status === 'pending'
            && !mcpRegistrationPrompted.has(digestKey);
    });
    if (!pending.length) return;
    mcpRegistrationPromptBusy = true;
    var changed = false;
    try {
        for (var i = 0; i < pending.length; i += 1) {
            var item = pending[i];
            var digestKey = String(item.extension_id || '') + ':' + String(item.config_digest || '');
            mcpRegistrationPrompted.add(digestKey);
            try {
                changed = (await confirmMcpRegistration(item)) || changed;
            } catch (error) {
                showUiAlert({
                    title: 'MCP 注册失败',
                    message: String(error && error.message ? error.message : error),
                    confirmText: '知道了',
                });
            }
        }
    } finally {
        mcpRegistrationPromptBusy = false;
    }
    if (changed) await refreshSecurityExtensions();
}

async function setExtensionTrust(item, trust) {
    var statusEl = document.getElementById('settings-security-extensions-status');
    if (item.kind === 'mcp' && trust) {
        try {
            var confirmed = await confirmMcpRegistration(item);
            if (statusEl && confirmed) statusEl.textContent = 'MCP 已注册并连接；工具调用继续正常审批。';
            if (confirmed) await refreshSecurityExtensions();
        } catch (error) {
            if (statusEl) statusEl.textContent = 'MCP 注册失败：' + String(error && error.message ? error.message : error);
        }
        return;
    }
    if (trust) {
        var accepted = await openUiModal({
            title: '信任可执行扩展',
            subtitle: extensionTrustLabel(item),
            message: '该扩展将以当前操作系统用户权限运行。能力声明只用于审批分类，不能阻止扩展代码读取文件或联网。确认信任当前内容摘要？',
            danger: true,
            confirmText: '信任当前版本',
            cancelText: '取消',
        });
        if (!accepted) return;
    }
    try {
        var base = '/api/security/extensions/' + encodeURIComponent(item.kind) + '/' + encodeURIComponent(item.extension_id) + '/trust';
        var response = await fetch(base, { method: trust ? 'POST' : 'DELETE' });
        var data = await response.json();
        if (!response.ok || !data.ok) throw new Error(data.error || ('HTTP ' + response.status));
        if (statusEl) {
            statusEl.textContent = trust
                ? '扩展已信任；当前摘要可以启动。'
                : (item.kind === 'mcp'
                    ? 'MCP 注册已撤销，运行中的服务器已停止。'
                    : '扩展信任已撤销，运行中的 worker 已停止。');
        }
        await refreshSecurityExtensions();
    } catch (error) {
        if (statusEl) statusEl.textContent = '更新扩展信任失败：' + String(error && error.message ? error.message : error);
    }
}

async function refreshSecurityExtensions() {
    var listEl = document.getElementById('settings-security-extensions-list');
    var statusEl = document.getElementById('settings-security-extensions-status');
    if (!listEl) return;
    listEl.textContent = '正在读取…';
    try {
        var response = await fetch('/api/security/extensions', { cache: 'no-store' });
        var data = await response.json();
        if (!response.ok || !data.ok) throw new Error(data.error || ('HTTP ' + response.status));
        listEl.textContent = '';
        var rows = Array.isArray(data.extensions) ? data.extensions : [];
        if (!rows.length) {
            listEl.textContent = '没有已安装或已配置的可执行扩展。';
            return;
        }
        rows.forEach(function (item) {
            var row = document.createElement('div');
            row.className = 'settings-security-rule-row';
            var badge = document.createElement('span');
            var mcpStatus = String(item.registration_status || '');
            badge.className = item.trusted ? 'settings-security-rule-allow' : 'settings-security-rule-ask';
            badge.textContent = item.kind === 'mcp'
                ? (mcpStatus === 'registered' ? '已注册' : (mcpStatus === 'rejected' ? '已拒绝' : '待确认'))
                : (item.trusted ? '已信任' : '待信任');
            var label = document.createElement('span');
            label.className = 'settings-security-rule-label';
            label.textContent = extensionTrustLabel(item) + ' · ' + String(item.runtime || 'runtime');
            label.title = String(item.source || '') + '\\n摘要：' + String(item.content_digest || '');
            var action = document.createElement('button');
            action.type = 'button';
            action.className = 'settings-security-rule-delete';
            action.textContent = item.trusted
                ? '撤销'
                : (item.kind === 'mcp' ? '确认注册' : '信任');
            action.addEventListener('click', function () { void setExtensionTrust(item, !item.trusted); });
            row.appendChild(badge);
            row.appendChild(label);
            row.appendChild(action);
            listEl.appendChild(row);
        });
        if (statusEl) statusEl.textContent = '';
        void promptPendingMcpRegistrations(rows);
    } catch (error) {
        listEl.textContent = '';
        if (statusEl) statusEl.textContent = '读取扩展信任失败：' + String(error && error.message ? error.message : error);
    }
}

async function saveWebFetchDomains() {
    var editor = document.getElementById('settings-security-web-fetch-domains');
    var statusEl = document.getElementById('settings-security-web-fetch-status');
    if (!editor) return;
    var saveBtn = document.getElementById('settings-security-web-fetch-save');
    if (saveBtn) saveBtn.disabled = true;
    try {
        var domains = editor.value.split(/\\r?\\n/).map(function (line) { return line.trim(); }).filter(Boolean);
        var response = await fetch('/api/security/web-fetch-domains', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ domains: domains }),
        });
        var data = await response.json();
        if (!response.ok || !data.ok) throw new Error(data.error || ('HTTP ' + response.status));
        editor.value = (Array.isArray(data.domains) ? data.domains : []).join('\\n');
        if (statusEl) statusEl.textContent = '已保存 ' + editor.value.split('\\n').filter(Boolean).length + ' 个自定义域名，新会话立即生效。';
    } catch (error) {
        if (statusEl) statusEl.textContent = '保存失败：' + String(error && error.message ? error.message : error);
    } finally {
        if (saveBtn) saveBtn.disabled = false;
    }
}

async function refreshSecurityRules() {
    var listEl = document.getElementById('settings-security-rules-list');
    var statusEl = document.getElementById('settings-security-rules-status');
    if (!listEl) return;
    listEl.textContent = '正在读取…';
    try {
        var ctx = securityRulesContext();
        var query = new URLSearchParams();
        if (ctx.sessionId) query.set('session_id', ctx.sessionId);
        if (ctx.workspace) query.set('workspace', ctx.workspace);
        var response = await fetch('/api/security/rules?' + query.toString(), { cache: 'no-store' });
        var data = await response.json();
        if (!response.ok || !data.ok) throw new Error(data.error || ('HTTP ' + response.status));
        listEl.textContent = '';
        var rules = Array.isArray(data.rules) ? data.rules : [];
        if (rules.length === 0) {
            var empty = document.createElement('div');
            empty.className = 'settings-feature-status';
            empty.textContent = '暂无长期规则。审批时选择“始终允许此类操作”会自动添加。';
            listEl.appendChild(empty);
            return;
        }
        rules.forEach(function (rule) {
            var row = document.createElement('div');
            row.className = 'settings-security-rule-row';
            var badge = document.createElement('span');
            badge.className = 'settings-security-rule-' + String(rule.behavior || 'allow');
            var behaviorText = rule.behavior === 'deny' ? '拒绝' : (rule.behavior === 'ask' ? '必问' : '允许');
            badge.textContent = behaviorText + (rule.source === 'session' ? '·本会话' : (rule.source === 'project' ? '·项目' : ''));
            var label = document.createElement('span');
            label.className = 'settings-security-rule-label';
            label.title = String(rule.pattern || '');
            label.textContent = securityRuleLabel(rule);
            var del = document.createElement('button');
            del.type = 'button';
            del.className = 'settings-security-rule-delete';
            del.textContent = '删除';
            del.addEventListener('click', function () { void deleteSecurityRule(rule); });
            row.appendChild(badge);
            row.appendChild(label);
            row.appendChild(del);
            listEl.appendChild(row);
        });
        if (statusEl) statusEl.textContent = '';
    } catch (error) {
        listEl.textContent = '';
        if (statusEl) statusEl.textContent = '读取规则失败：' + String(error && error.message ? error.message : error);
    }
}

async function addSecurityRule() {
    var statusEl = document.getElementById('settings-security-rules-status');
    var actionEl = document.getElementById('settings-security-rule-action');
    var behaviorEl = document.getElementById('settings-security-rule-behavior');
    var patternEl = document.getElementById('settings-security-rule-pattern');
    if (!actionEl || !behaviorEl || !patternEl) return;
    var action = String(actionEl.value || 'process.exec');
    var behavior = String(behaviorEl.value || 'allow');
    var pattern = String(patternEl.value || '').trim();
    if (!pattern) {
        if (statusEl) statusEl.textContent = '请输入规则内容。';
        return;
    }
    if (statusEl) statusEl.textContent = '正在添加…';
    try {
        var ctx = securityRulesContext();
        var body = { behavior: behavior, action: action, pattern: pattern, source: 'user', session_id: ctx.sessionId, workspace: ctx.workspace };
        var response = await fetch('/api/security/rules', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(body),
        });
        var data = await response.json();
        if (!response.ok || !data.ok) throw new Error(data.error || ('HTTP ' + response.status));
        patternEl.value = '';
        if (statusEl) statusEl.textContent = '规则已添加。';
        await refreshSecurityRules();
    } catch (error) {
        if (statusEl) statusEl.textContent = '添加失败：' + String(error && error.message ? error.message : error);
    }
}

async function deleteSecurityRule(rule) {
    var statusEl = document.getElementById('settings-security-rules-status');
    try {
        var response = await fetch('/api/security/rules/' + encodeURIComponent(String(rule.id)), { method: 'DELETE' });
        var data = await response.json();
        if (!response.ok || !data.ok) throw new Error(data.error || ('HTTP ' + response.status));
        if (statusEl) statusEl.textContent = '规则已删除。';
        await refreshSecurityRules();
    } catch (error) {
        if (statusEl) statusEl.textContent = '删除失败：' + String(error && error.message ? error.message : error);
    }
}

async function clearSessionSecurityRules() {
    var statusEl = document.getElementById('settings-security-rules-status');
    var ctx = securityRulesContext();
    if (!ctx.sessionId) {
        if (statusEl) statusEl.textContent = '未选择会话。';
        return;
    }
    var accepted = await openUiModal({
        title: '清除本会话规则',
        message: '清除当前会话的所有权限规则？用户级“始终允许”规则不受影响。',
        danger: true,
        confirmText: '确认清除',
        cancelText: '取消',
    });
    if (!accepted) return;
    try {
        var response = await fetch('/api/security/rules?session_id=' + encodeURIComponent(ctx.sessionId), { method: 'DELETE' });
        var data = await response.json();
        if (!response.ok || !data.ok) throw new Error(data.error || ('HTTP ' + response.status));
        if (statusEl) statusEl.textContent = '已清除本会话规则（' + String(data.deleted || 0) + ' 条）。';
        await refreshSecurityRules();
    } catch (error) {
        if (statusEl) statusEl.textContent = '清除失败：' + String(error && error.message ? error.message : error);
    }
}

async function refreshExternalWorkspaceOpsSetting() {
    var off = document.getElementById('settings-external-ops-off');
    var on = document.getElementById('settings-external-ops-on');
    var statusEl = document.getElementById('settings-external-ops-status');
    if (!off || !on) return;
    try {
        var response = await fetch('/api/security/settings', { cache: 'no-store' });
        var data = await response.json();
        if (!response.ok || !data.ok) throw new Error(data.error || ('HTTP ' + response.status));
        var enabled = data.allow_external_workspace_ops === true;
        off.classList.toggle('is-active', !enabled);
        on.classList.toggle('is-active', enabled);
        off.setAttribute('aria-pressed', enabled ? 'false' : 'true');
        on.setAttribute('aria-pressed', enabled ? 'true' : 'false');
        if (statusEl) {
            statusEl.textContent = enabled
                ? '已开启：写/删/Shell 工作区外操作自动放行。'
                : '已关闭：工作区外操作恢复逐次审批。';
        }
    } catch (error) {
        if (statusEl) statusEl.textContent = '读取设置失败：' + String(error && error.message ? error.message : error);
    }
}

async function setExternalWorkspaceOpsSetting(enabled) {
    var statusEl = document.getElementById('settings-external-ops-status');
    if (enabled) {
        var accepted = await openUiModal({
            title: '开启工作区外处理权限？',
            message: '开启后，Agent 可在工作区外执行写入、删除和 Shell 操作而不再逐次询问。破坏性/动态命令、网络、凭据导出与安全策略篡改仍会被拦截或审批。',
            danger: true,
            confirmText: '确认开启',
            cancelText: '取消',
        });
        if (!accepted) return;
    }
    try {
        var response = await fetch('/api/security/settings', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ allow_external_workspace_ops: enabled }),
        });
        var data = await response.json();
        if (!response.ok || !data.ok) throw new Error(data.error || ('HTTP ' + response.status));
        await refreshExternalWorkspaceOpsSetting();
    } catch (error) {
        if (statusEl) statusEl.textContent = '保存失败：' + String(error && error.message ? error.message : error);
    }
}

function initPermissionControls() {
    syncPermissionControlVisibility(currentPermissionStatus);
    var trigger = document.getElementById('permission-mode-trigger');
    var menu = document.getElementById('permission-mode-menu');
    if (trigger && menu) {
        if (typeof bindUiHoverTip === 'function') bindUiHoverTip(trigger);
        trigger.addEventListener('click', function () {
            menu.classList.toggle('is-open');
            trigger.classList.toggle('is-open', menu.classList.contains('is-open'));
            trigger.setAttribute('aria-expanded', menu.classList.contains('is-open') ? 'true' : 'false');
        });
        Array.from(menu.querySelectorAll('[data-permission-mode]')).forEach(function (button) {
            button.addEventListener('click', function () {
                menu.classList.remove('is-open');
                trigger.classList.remove('is-open');
                trigger.setAttribute('aria-expanded', 'false');
                void selectPermissionMode(button.getAttribute('data-permission-mode'));
            });
        });
        document.addEventListener('click', function (event) {
            if (!menu.contains(event.target) && !trigger.contains(event.target)) {
                menu.classList.remove('is-open');
                trigger.classList.remove('is-open');
                trigger.setAttribute('aria-expanded', 'false');
            }
        });
    }
    var rulesRefresh = document.getElementById('settings-security-rules-refresh');
    if (rulesRefresh) rulesRefresh.addEventListener('click', function () { void refreshSecurityRules(); });
    var rulesClear = document.getElementById('settings-security-rules-clear-session');
    if (rulesClear) rulesClear.addEventListener('click', function () { void clearSessionSecurityRules(); });
    var rulesAdd = document.getElementById('settings-security-rule-add');
    if (rulesAdd) rulesAdd.addEventListener('click', function () { void addSecurityRule(); });
    var webFetchSave = document.getElementById('settings-security-web-fetch-save');
    if (webFetchSave) webFetchSave.addEventListener('click', function () { void saveWebFetchDomains(); });
    var webFetchReload = document.getElementById('settings-security-web-fetch-reload');
    if (webFetchReload) webFetchReload.addEventListener('click', function () { void refreshWebFetchDomains(); });
    var extensionsRefresh = document.getElementById('settings-security-extensions-refresh');
    if (extensionsRefresh) extensionsRefresh.addEventListener('click', function () { void refreshSecurityExtensions(); });
    var externalOpsOff = document.getElementById('settings-external-ops-off');
    if (externalOpsOff) externalOpsOff.addEventListener('click', function () { void setExternalWorkspaceOpsSetting(false); });
    var externalOpsOn = document.getElementById('settings-external-ops-on');
    if (externalOpsOn) externalOpsOn.addEventListener('click', function () { void setExternalWorkspaceOpsSetting(true); });
    void refreshExternalWorkspaceOpsSetting();
    void refreshSecurityRules();
    void refreshSecurityExtensions();
    void refreshWebFetchDomains();
    void refreshPermissionModeSelector(currentSessionId);
}

if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initPermissionControls);
} else {
    initPermissionControls();
}
`,Wt=`function renderEvent(ctx, event, eventIndex, runSessionId) {
    if (!event || typeof event !== 'object') return;
    var eventSessionId = runSessionId || currentSessionId || '';
    if (event.type === 'permission_mode_changed') {
        if (typeof renderPermissionMode === 'function') renderPermissionMode(event);
        return;
    }
    if (typeof isHumanInteractionEventType === 'function' && isHumanInteractionEventType(event.type)) {
        renderHumanInteractionEvent(ctx, event, eventSessionId);
        return;
    }
    if (eventSessionId && !event.__storeApplied) {\r
        applyMessageEvent(eventSessionId, event, eventIndex, replayingMessages ? 'history' : 'stream');\r
        if (event.type === 'subagent_start' || event.type === 'subagent_finish'\r
            || event.type === 'subagent_started' || event.type === 'subagent_finished') {\r
            applySubagentLifecycleToStore(eventSessionId, event);\r
        }\r
    }\r
    if (event.type === 'user') {\r
        if (typeof eventIndex === 'number') ctx.lastUserEventIndex = eventIndex;\r
        if (Number.isFinite(Number(event.runtime_seq || event.runtimeSeq))) {\r
            ctx.lastUserRuntimeSeq = Math.floor(Number(event.runtime_seq || event.runtimeSeq));\r
        }\r
        sealProcessGroup(ctx);\r
        appendMessage(ctx, 'user', event.content || '', {\r
            eventIndex: eventIndex,\r
            turnTruncateIdx: eventIndex,\r
            runtimeSeq: event.runtime_seq || event.runtimeSeq,\r
            createdAt: event.created_at || event.createdAt || event.timestamp,\r
        }, runSessionId);\r
    } else if (event.type === 'user_steer') {
        var steerOperationId = event.client_id || event.steer_id || '';
        if (typeof prepareSteerProcessBoundary === 'function') {
            prepareSteerProcessBoundary(ctx, event.steer_mode || 'interrupt', steerOperationId);
        }
        if (typeof markSteerEventPosition === 'function') {
            markSteerEventPosition(ctx, eventIndex, event.runtime_seq || event.runtimeSeq);
        }
        if (typeof appendSteerProcessMessage === 'function' && (event.client_id || event.steer_id)) {
            appendSteerProcessMessage(
                eventSessionId,
                ctx,
                event.content || '',
                steerOperationId,
                event.steer_mode || 'interrupt',
                false
            );
        } else {
            appendLog(ctx, event.content || '', 'user-steer', runSessionId);
        }
    } else if (event.type === 'final') {
        var finalStream = ctx && ctx.stream ? ctx.stream : getVisibleChatStream();
        var userIdx = (ctx && Number.isFinite(Number(ctx.lastUserEventIndex))) ? Number(ctx.lastUserEventIndex) : latestVisibleUserEventIndex(finalStream);
        if (typeof hasDuplicateVisibleFinal === 'function' && hasDuplicateVisibleFinal(finalStream, userIdx, event.content)) return;
        var finalContent = event.content || '';
        if (typeof splitThinkTagsForUi === 'function') {
            var finalThinkSplit = splitThinkTagsForUi(finalContent);
            if (finalThinkSplit.reasoning && finalThinkSplit.reasoning.trim()) {
                upsertLlmFeedRow(ctx, finalThinkSplit.reasoning, 'llm-reasoning', runSessionId, uiEventReactIter(event));
            }
        }
        appendMessage(ctx, 'assistant', finalContent, {
            eventIndex: eventIndex,
            turnTruncateIdx: ctx.lastUserEventIndex,
            runtimeSeq: event.runtime_seq || event.runtimeSeq,
            runtimeEventType: event.runtime_event_type || event.runtimeEventType,
            truncateBeforeSeq: ctx.lastUserRuntimeSeq,
            uiRuntimeText: typeof isUiRuntimeFinalText === 'function' && isUiRuntimeFinalText(finalContent),
        }, runSessionId);
    } else if (event.type === 'process_metrics') {\r
        applyProcessMetricsFromEvent(ctx, event);\r
    } else if (event.type === 'cache_stats') {\r
        applyCacheStatsFromEvent(ctx, event, runSessionId);\r
    } else if (event.type === 'tool_call') {
        // Replay through the same upsert path as live SSE so the tool row
        // carries data-tool-call-id. Pending approval cards rendered earlier in
        // the replay can then be anchored into that row by
        // attachAllHumanInteractionCards().
        upsertToolCallResult(ctx, event, runSessionId);
    } else if (event.type === 'validate_final') {\r
        appendLog(ctx, '验证：' + event.result + (event.reason ? '\\n' + event.reason : ''), 'status', runSessionId);\r
    } else if (event.type === 'llm_reasoning') {\r
        upsertLlmFeedRow(ctx, event.content || '', 'llm-reasoning', runSessionId, uiEventReactIter(event));\r
    } else if (event.type === 'llm_response') {\r
        upsertLlmFeedRow(ctx, event.content || '', 'llm-response', runSessionId, uiEventReactIter(event));\r
    } else if (event.type === 'llm_history_rollup' || event.type === 'compact_summary') {\r
        appendLog(ctx, String(event.content || ''), 'compact-summary', runSessionId);\r
    } else if (event.type === 'context_trim_progress') {\r
        appendProgressLog(ctx, event.content, 'context-trim', runSessionId);\r
    } else if (event.type === 'context_summary_progress') {\r
        appendProgressLog(ctx, event.content, 'context-summary', runSessionId);\r
    } else if (event.type === 'context_summary_delta') {\r
        appendProgressStreamDelta(ctx, event.delta, 'context-summary', runSessionId);\r
    } else if (event.type === 'context_summary_body') {\r
        applyProgressPersistedBody(ctx, event.content, 'context-summary', runSessionId);\r
    } else if (event.type === 'key_context_progress') {\r
        var keyProg = String(event.content || '');\r
        if (keyProg.indexOf('正在根据对话更新要点') >= 0) {\r
            finalizeProgressStreamForType(ctx, 'context-summary');\r
            resetKeyContextStreamFilter(ctx);\r
        }\r
        appendProgressLog(ctx, keyProg, 'key-context', runSessionId);\r
    } else if (event.type === 'key_context_delta') {\r
        appendKeyContextStreamDelta(ctx, event.delta, runSessionId);\r
    } else if (event.type === 'key_context_body') {\r
        applyProgressPersistedBody(ctx, event.content, 'key-context', runSessionId);\r
    } else if (event.type === 'error') {\r
        appendLog(ctx, String(event.content || ''), 'error-log', runSessionId);\r
    } else if (event.type === 'status') {\r
        var statusContent = String(event.content || '');\r
        if (event.model_switch) {\r
            appendModelSwitchStatus(ctx, event, runSessionId);\r
            return;\r
        }\r
        if (statusContent.indexOf('【上下文窗口已满，开始压缩】') >= 0 || statusContent.indexOf('【上下文压缩已完成】') >= 0) {\r
            finalizeProgressStreamChunks(ctx);\r
            resetKeyContextStreamFilter(ctx);\r
        }\r
        if (event.compress_progress) {\r
            var legacyLogType = 'context-trim';\r
            if (statusContent.indexOf('【上下文摘要】') >= 0) legacyLogType = 'context-summary';\r
            else if (statusContent.indexOf('【要点】') >= 0) legacyLogType = 'key-context';\r
            appendProgressLog(ctx, statusContent, legacyLogType, runSessionId);\r
            return;\r
        }\r
        // 临时状态消息处理：标记"正在思考中..."为临时状态\r
        var isTemporaryStatus = statusContent.indexOf('正在思考中...') >= 0;\r
        if (isTemporaryStatus) removeTemporaryStatus(ctx);\r
        var statusRow = appendLog(ctx, statusContent, 'status', runSessionId);
        if (isTemporaryStatus && statusRow) {
            statusRow.dataset.temporaryStatus = '1';
        }
    } else if (event.type === 'auto_review_status') {
        renderAutoReviewStatusEvent(ctx, event, runSessionId);
    } else if (event.type === 'approval_required') {
        var leg = (event.tool_name ? String(event.tool_name) + ' ' : '') + (event.message || '');\r
        appendLog(ctx, '[历史/旧版事件] ' + leg.trim(), 'status', runSessionId);\r
    } else if (event.type === 'warning') {\r
        appendLog(ctx, String(event.content || ''), 'status', runSessionId);\r
    } else if (event.type === 'subagent_start' || event.type === 'subagent_finish') {\r
        if (!ctx._subagentBody) {\r
            handleSubagentLifecycleEvent(event);\r
            return;\r
        }\r
        if (event.type === 'subagent_start') ensureSubagentBlock(ctx, event);\r
        else updateSubagentBlockFinish(ctx, event);\r
    } else {\r
        var fallbackContent = String(event.content || '');\r
        if (fallbackContent.trim()) appendLog(ctx, fallbackContent, 'log-entry', runSessionId);\r
    }\r
}\r
`,Vt=`\uFEFFfunction setSendButtonState() {\r
    syncMessageInputPlaceholder();
    sendBtn.disabled = false;
    const uploadBusy = isChatFileUploadBusy();
    const newSessionPreflight = !currentSessionId && optimisticNewSessionRun;
    if (isSessionRunning(currentSessionId) || newSessionPreflight) {
        const run = newSessionPreflight || (typeof getSessionRunState === 'function' ? getSessionRunState(currentSessionId) : null);
        const suppressFollowup = !!(run && run.suppressFollowupButton);
        const hasDraft = (typeof inputHasSendableText === 'function')
            ? inputHasSendableText()\r
            : !!(messageInput && String(messageInput.value || '').trim());\r
        const followupEnabled = (typeof isMyAgentFeatureEnabled === 'function') && isMyAgentFeatureEnabled('followupRestart', false);\r
        sendBtn.innerHTML = (followupEnabled && hasDraft && !suppressFollowup && !uploadBusy) ? '追问' : '停止 <span class="loader" aria-hidden="true"></span>';
        sendBtn.classList.add('is-stop');\r
        sendBtn.classList.toggle('is-followup', followupEnabled && hasDraft && !suppressFollowup && !uploadBusy);
    } else {\r
        sendBtn.textContent = '发送';\r
        sendBtn.classList.remove('is-stop');
        sendBtn.classList.remove('is-followup');
        sendBtn.disabled = uploadBusy;
    }
}

const MESSAGE_INPUT_PLACEHOLDER_DEFAULT = '说说你想做什么…（Shift/Ctrl+Enter换行）';
const MESSAGE_INPUT_PLACEHOLDER_RUNNING = 'Agent运行中，输入后续任务';
const MESSAGE_INPUT_PLACEHOLDER_QUEUED = '点击\`立即发送\`插入提示';

function syncMessageInputPlaceholder() {
    if (!messageInput) return;
    var queue = currentSessionId && typeof getFollowupQueue === 'function'
        ? getFollowupQueue(currentSessionId)
        : [];
    var running = !!(optimisticNewSessionRun || isSessionRunning(currentSessionId));
    var value = queue.length
        ? MESSAGE_INPUT_PLACEHOLDER_QUEUED
        : (running ? MESSAGE_INPUT_PLACEHOLDER_RUNNING : MESSAGE_INPUT_PLACEHOLDER_DEFAULT);
    messageInput.placeholder = typeof translateUiString === 'function'
        ? translateUiString(value)
        : value;
}

function isChatFileUploadBusy() {
    return !!(messageInput && messageInput.dataset.fileUploadBusy === '1');
}

document.addEventListener('myagent:language-change', syncMessageInputPlaceholder);
\r
async function requestInterrupt(sessionId, runId, reason) {\r
    if (!sessionId) return;\r
    try {\r
        await fetch('/sessions/' + sessionId + '/interrupt', {\r
            method: 'POST',\r
            headers: { 'Content-Type': 'application/json' },\r
            body: JSON.stringify({ run_id: runId || '', reason: reason || '' }),\r
        });\r
    }\r
    catch (e) { /* ignore */ }\r
}\r
\r
function pauseCurrentRun() {
    if (!currentSessionId) {
        if (optimisticNewSessionRun) {
            markRunAbortReason(optimisticNewSessionRun, 'user');
            try { optimisticNewSessionRun.controller.abort(); } catch (e) { /* ignore */ }
            optimisticNewSessionRun = null;
            setSendButtonState();
        }
        return;
    }
    const run = getSessionRunState(currentSessionId);\r
    const sid = currentSessionId;\r
    const activeInfo = sessionStore.getActiveRunInfo(sid) || {};
    const runId = run && run.runId ? run.runId : (activeInfo.run_id || activeInfo.runId || '');
    if (typeof markFollowupQueueManualOnly === 'function') markFollowupQueueManualOnly(sid);
    suppressSessionServerStreamActive(sid);
    if (!run) {\r
        setSendButtonState();\r
        syncSessionListIndicatorClasses();\r
        renderSessionListIfChanged(false);\r
        void requestInterrupt(sid, runId, 'user_button');
        setTimeout(function () { reconcileRunStateFromServer({ silent: true, respectStopSuppress: true }); }, 3000);\r
        return;\r
    }\r
    const ctx = run.ctx;
    const reachedServer = run.submitted !== false;
    /* 先同步 abort 本地 fetch 与从 sessionStore 摘除，UI 立即反映「已停止」状态；\r
       后端 interrupt 走 fire-and-forget，避免被主线程阻塞时按钮响应卡顿。*/\r
    abortSessionRun(sid, 'user');\r
    setSendButtonState();\r
    syncSessionListIndicatorClasses();\r
    renderSessionListIfChanged(false);\r
    appendLog(ctx, '已请求停止当前任务', 'status', sid);\r
    sealProcessGroup(ctx);\r
    if (reachedServer) void requestInterrupt(sid, runId, 'user_button');
    setTimeout(function () { reconcileRunStateFromServer({ silent: true, respectStopSuppress: true }); }, 3000);\r
}\r
\r
/** 在当前会话中定位最近一条用户消息并重新发送。返回 true 表示已触发展开发送。*/\r
function resendLastUserMessage() {\r
    if (!currentSessionId) return false;\r
    if (isSessionRunning(currentSessionId)) return false;\r
    var lastMsg = lastUserMessageBySession[currentSessionId];\r
    if (!lastMsg || !String(lastMsg).trim()) {\r
        var chatStream = getVisibleChatStream();\r
        if (chatStream) {\r
            var wraps = chatStream.querySelectorAll('.msg-wrap--user');\r
            if (wraps.length) {\r
                var lastWrap = wraps[wraps.length - 1];\r
                lastMsg = messageRawMarkdown.get(lastWrap) || (lastWrap.querySelector('.message.user') && lastWrap.querySelector('.message.user').textContent);\r
            }\r
        }\r
    }\r
    if (!lastMsg || !String(lastMsg).trim()) {\r
        lastMsg = draftBySession[currentSessionId];\r
    }\r
    if (!lastMsg || !String(lastMsg).trim()) return false;\r
    messageInput.value = String(lastMsg);\r
    rewriteInputWorkspacePaths();\r
    autoResizeTextarea();\r
    sendMessage();\r
    return true;\r
}\r
\r
function showLoading() {\r
    resetSessionHistoryPaging();\r
    clearTocForSessionLoad();\r
    if (!getVisibleChatStream()) ensureVisibleChatStreamSlot();\r
    const vs = getVisibleChatStream();\r
    if (vs) emptyChatStreamKeepingStrip(vs);\r
    const box = document.createElement('div');\r
    box.className = 'skeleton';\r
    box.id = 'chat-loading';\r
    box.setAttribute('role', 'status');\r
    box.innerHTML = ''\r
        + '<div class="skeleton-page" aria-hidden="true">'\r
        + '<div class="skeleton-mast"><span></span><span></span></div>'\r
        + '<div class="skeleton-hero"><div class="skeleton-image"></div><div class="skeleton-column"><span></span><span></span><span></span><span></span></div></div>'\r
        + '<div class="skeleton-grid"><div><span></span><span></span><span></span></div><div><span></span><span></span><span></span></div><div><span></span><span></span><span></span></div></div>'\r
        + '</div><div class="skeleton-copy">加载中...</div>';\r
    box.setAttribute('data-ui-tip', '加载会话');\r
    bindUiHoverTip(box);\r
    (getVisibleChatStream() || chatContainer).appendChild(box);\r
    scrollToBottom();\r
}\r
\r
function hideLoading() { const loader = document.getElementById('chat-loading'); if (loader) loader.remove(); }\r
\r
/** 根据 sessionStore / 服务端 stream_active / sessionUnreadComplete 更新红点、绿点 */\r
function applySessionItemIndicators(itemDiv, sessionId, opts) {\r
    opts = opts || {};\r
    if (!itemDiv || !sessionId) return;\r
    itemDiv.classList.remove('is-generating', 'is-unread-result', 'is-unread-failed');\r
    var nameEl = itemDiv.querySelector('.session-name');\r
    if (nameEl) nameEl.removeAttribute('data-ui-tip');\r
    if (isSessionRunning(sessionId)) {\r
        itemDiv.classList.add('is-generating');\r
        if (nameEl) nameEl.setAttribute('data-ui-tip', '生成中');\r
    } else {\r
        var sess = sessionStore.get(sessionId);\r
        var localUnreadResult = sessionUnreadComplete.has(sessionId);\r
        var hasUnreadResult = sess ? !!sess.unread_result : localUnreadResult;\r
        if (!hasUnreadResult) return;\r
        var failed = !!(sess && sess.unread_result_status === 'failed');\r
        itemDiv.classList.add(failed ? 'is-unread-failed' : 'is-unread-result');\r
        if (nameEl) nameEl.setAttribute('data-ui-tip', failed ? '任务失败，点击查看' : '有新回复，点击查看');\r
    }\r
    if (nameEl) bindUiHoverTip(nameEl);\r
}\r
\r
/** 立即刷新侧栏全部指示点与当前选中项；不依赖 loadSessions 网络回流，与是否切换会话无关 */\r
function syncSessionListIndicatorClasses() {
    if (!sessionsList) return;\r
    sessionsList.querySelectorAll('.session-item').forEach(function (div) {\r
        var el = div.querySelector('.session-name[data-id]');\r
        if (!el) return;\r
        var sid = el.getAttribute('data-id');\r
        div.classList.toggle('active', !!sid && sid === currentSessionId);\r
        applySessionItemIndicators(div, sid);
    });
    if (typeof updateAllHumanInteractionSessionBadges === 'function') updateAllHumanInteractionSessionBadges();
}\r
\r
function sessionSectionExpanded(key) {\r
    try {\r
        return localStorage.getItem(LS_SESSION_SECTION_PREFIX + key) !== '0';\r
    } catch (e) {\r
        return true;\r
    }\r
}\r
function persistSessionSectionExpanded(key, expanded) {\r
    try {\r
        localStorage.setItem(LS_SESSION_SECTION_PREFIX + key, expanded ? '1' : '0');\r
    } catch (e) { /* ignore */ }\r
}\r
function closeAllSessionMenus() {\r
    document.querySelectorAll('.session-more-wrap.is-open').forEach(function (w) {\r
        w.classList.remove('is-open');\r
        var b = w.querySelector('.session-more-btn');\r
        if (b) b.setAttribute('aria-expanded', 'false');\r
    });\r
}\r
(function bindSessionMenuDocumentCloserOnce() {\r
    if (window.__myAgentSessionMenuCloser) return;\r
    window.__myAgentSessionMenuCloser = true;\r
    document.addEventListener('click', closeAllSessionMenus);\r
})();\r
\r
(function bindSessionListDelegatedSwitcherOnce() {\r
    if (!sessionsList || window.__myAgentSessionListSwitcher) return;\r
    window.__myAgentSessionListSwitcher = true;\r
    sessionsList.addEventListener('click', function (e) {\r
        var target = e.target;\r
        if (!target || !target.closest) return;\r
        if (target.closest('button, .session-more-wrap, .session-more-menu, input, textarea, a')) return;\r
        if (target.isContentEditable) return;\r
        var row = target.closest('.session-item');\r
        if (!row || !sessionsList.contains(row)) return;\r
        var sid = row.dataset.sessionId;\r
        if (!sid) {\r
            var nameEl = row.querySelector('.session-name[data-id]');\r
            sid = nameEl ? nameEl.getAttribute('data-id') : '';\r
        }\r
        if (sid && sid !== currentSessionId) {\r
            Promise.resolve(switchSession(sid)).catch(function (err) {\r
                console.error('切换会话失败:', err);\r
            });\r
        }\r
    });\r
})();\r
\r
/**\r
 * 创建并绑定单条会话（更多菜单：置顶 → 删除 → 归档 在末尾）\r
 */\r
function buildAndBindSessionRow(sess, allSessions, nextStreamMap) {
    const div = document.createElement('div');\r
    div.className = 'session-item';\r
    div.dataset.sessionId = sess.id || '';\r
    if (currentSessionId === sess.id) div.classList.add('active');\r
    if (sess.id) nextStreamMap[sess.id] = !!sess.stream_active;
    if (sess.id) scheduleTitleGenerationRefresh(sess.id, !!sess.title_generation_pending);
    div.innerHTML = '<div class="session-item-head">'
        + '<div class="session-item-main">'
        + '<div class="session-item-title-row">'
        + '<span class="session-name" data-id="' + sess.id + '" data-original="' + escapeHtml(sess.name) + '">' + escapeHtml(sess.name) + '</span>'
        + '<span class="session-item-date"></span>'
        + '</div>'
        + '<div class="session-last-query"></div>'
        + '</div>'
        + '<div class="session-more-wrap">'
        + '<button type="button" class="session-more-btn" aria-label="更多操作" aria-expanded="false" aria-haspopup="true" data-ui-tip="更多">'
        + '<span class="session-more-dots" aria-hidden="true"><span></span><span></span><span></span></span></button>'
        + '<div class="session-more-menu" role="menu">'
        + '<button type="button" class="session-menu-pin" role="menuitem"></button>'
        + '<button type="button" class="session-menu-delete" role="menuitem">删除</button>'
        + '<button type="button" class="session-menu-archive" role="menuitem"></button>'
        + '</div></div>'
        + '</div>';
    if (typeof updateHumanInteractionSessionBadge === 'function') {
        setTimeout(function () { updateHumanInteractionSessionBadge(sess.id); }, 0);
    }
    var pinMi = div.querySelector('.session-menu-pin');\r
    var archMi = div.querySelector('.session-menu-archive');\r
    if (pinMi) pinMi.textContent = sess.pinned ? '取消置顶' : '置顶';\r
    if (archMi) archMi.textContent = sess.archived ? '取消归档' : '归档';\r
    var wsLine = formatSessionListSubtitle(sess);
    var wsEl = div.querySelector('.session-last-query');
    if (wsEl) {
        wsEl.textContent = wsLine;
        wsEl.setAttribute('data-ui-tip', wsLine);
        bindUiHoverTip(wsEl);
    }
    var dateEl = div.querySelector('.session-item-date');
    if (dateEl) {
        var dateLine = typeof formatSessionListDate === 'function' ? formatSessionListDate(sess) : '';
        if (dateLine) {
            dateEl.innerHTML = (typeof sessionDateIcon === 'function' ? sessionDateIcon() : '') + dateLine;
            dateEl.setAttribute('data-ui-tip', dateLine);
            bindUiHoverTip(dateEl);
        } else {
            dateEl.textContent = '';
        }
    }
    var moreWrap = div.querySelector('.session-more-wrap');\r
    var moreBtn = div.querySelector('.session-more-btn');\r
    if (moreBtn) bindUiHoverTip(moreBtn);\r
    if (moreWrap && moreBtn) {\r
        moreBtn.addEventListener('click', function (e) {\r
            e.stopPropagation();\r
            var wasOpen = moreWrap.classList.contains('is-open');\r
            closeAllSessionMenus();\r
            if (pinMi) pinMi.textContent = sess.pinned ? '取消置顶' : '置顶';\r
            if (archMi) archMi.textContent = sess.archived ? '取消归档' : '归档';\r
            if (!wasOpen) {\r
                moreWrap.classList.add('is-open');\r
                moreBtn.setAttribute('aria-expanded', 'true');\r
            }\r
        });\r
    }\r
    if (pinMi) {\r
        pinMi.addEventListener('click', async function (e) {\r
            e.stopPropagation();\r
            closeAllSessionMenus();\r
            try {\r
                const formData = new FormData();\r
                const nextPinned = !sess.pinned;\r
                const previous = applyOptimisticSessionUpdate(sess.id, { pinned: nextPinned });\r
                formData.append('pinned', nextPinned ? 'true' : 'false');\r
                const response = await fetch('/sessions/' + encodeURIComponent(sess.id) + '/pin', { method: 'PUT', body: formData });\r
                if (!response.ok) {\r
                    if (previous) applyOptimisticSessionUpdate(sess.id, previous);\r
                    throw new Error('pin failed: ' + response.status);\r
                }\r
                void refreshSingleSessionRow(sess.id);\r
            } catch (err) { console.error('置顶失败', err); }\r
        });\r
    }\r
    if (archMi) {\r
        archMi.addEventListener('click', async function (e) {\r
            e.stopPropagation();\r
            closeAllSessionMenus();\r
            try {\r
                const formData = new FormData();\r
                const nextArchived = !sess.archived;\r
                const previous = applyOptimisticSessionUpdate(sess.id, { archived: nextArchived });\r
                formData.append('archived', nextArchived ? 'true' : 'false');\r
                const response = await fetch('/sessions/' + encodeURIComponent(sess.id) + '/archive', { method: 'PUT', body: formData });\r
                if (!response.ok) {\r
                    if (previous) applyOptimisticSessionUpdate(sess.id, previous);\r
                    throw new Error('archive failed: ' + response.status);\r
                }\r
                void refreshSingleSessionRow(sess.id);\r
            } catch (err) { console.error('归档失败', err); }\r
        });\r
    }\r
    var delMi = div.querySelector('.session-menu-delete');\r
    if (delMi) {\r
        delMi.addEventListener('click', async function (e) {\r
            e.stopPropagation();\r
            closeAllSessionMenus();\r
            const okDel = await openUiModal({\r
                title: '删除会话',\r
                subtitle: '此操作不可恢复',\r
                message: '确定删除会话「' + String(sess.name || '未命名') + '」吗？其中的消息与记录将被移除。',\r
                danger: true,\r
                confirmText: '删除会话',\r
                cancelText: '取消',\r
            });\r
            if (!okDel) return;\r
            const wasArchivedLoaded = sessionStore.archivedLoaded;\r
            const deletedSessionId = String(sess.id || '');\r
            const nextSession = sessionStore.list().find(function (s) {
                return s && s.id && String(s.id) !== deletedSessionId && !s.archived;
            }) || null;
            sessionStore.markDeletedSession(deletedSessionId);
            if (wasArchivedLoaded && sess.archived) {
                const archivedBeforeDelete = sessionStore.archivedSessions || [];
                const deletedArchiveIndex = archivedBeforeDelete.findIndex(function (s) {
                    return s && String(s.id) === deletedSessionId;
                });
                sessionStore.setArchivedLoaded(archivedBeforeDelete.filter(function (s) {
                    return s && String(s.id) !== deletedSessionId;
                }), {
                    visibleCount: Math.max(
                        0,
                        sessionStore.archivedVisibleCount
                            - (deletedArchiveIndex >= 0 && deletedArchiveIndex < sessionStore.archivedVisibleCount ? 1 : 0)
                    ),
                    totalCount: Math.max(0, sessionStore.archivedCount - 1),
                });
                syncArchivedSessionStateFromStore();
            }
            renderSessionListIfChanged(true);\r
            if (div && div.parentNode) div.remove();\r
            sessionUnreadComplete.delete(deletedSessionId);
            scheduleTitleGenerationRefresh(deletedSessionId, false);
            persistSessionUnread();
            delete draftBySession[deletedSessionId];\r
            removeStoredInputDraft(deletedSessionId);\r
            if (typeof removeStoredFollowupQueue === 'function') removeStoredFollowupQueue(deletedSessionId);\r
            delete lastUserMessageBySession[deletedSessionId];\r
            clearContextStateForSession(deletedSessionId);\r
            if (typeof discardCachedSessionStream === 'function') discardCachedSessionStream(deletedSessionId);\r
            if (isSessionRunning(sess.id)) {\r
                const r = abortSessionRun(sess.id, 'delete');\r
                if (r && r.ctx && r.ctx.stream && r.ctx.stream.parentNode) r.ctx.stream.remove();\r
                setSendButtonState();\r
                syncSessionListIndicatorClasses();\r
            }\r
            if (currentSessionId === deletedSessionId) {\r
                if (nextSession) await switchSession(nextSession.id);\r
                else await createNewSession();\r
            }\r
            void requestInterrupt(deletedSessionId, '', 'session_deleted');
            void fetch('/sessions/' + encodeURIComponent(deletedSessionId), { method: 'DELETE' })\r
                .then(function (resp) {\r
                    if (!resp.ok) throw new Error('delete failed: ' + resp.status);\r
                })\r
                .catch(function (err) {\r
                    console.error('删除会话失败:', err);\r
                    sessionStore.clearDeletedSessionTombstone(deletedSessionId);\r
                    void loadSessions({ skipArchivedRefresh: true });\r
                    if (wasArchivedLoaded) void loadArchivedSessions({ background: true });\r
                });\r
        });\r
    }\r
    const nameSpan = div.querySelector('.session-name');\r
    if (nameSpan) {\r
        nameSpan.addEventListener('dblclick', function (e) {\r
            e.stopPropagation();\r
            if (nameSpan.classList.contains('editing')) return;\r
            nameSpan.classList.add('editing');\r
            nameSpan.contentEditable = 'true';\r
            nameSpan.focus();\r
            const range = document.createRange();\r
            range.selectNodeContents(nameSpan);\r
            const sel = window.getSelection();\r
            sel.removeAllRanges();\r
            sel.addRange(range);\r
        });\r
        nameSpan.addEventListener('blur', async function () {\r
            if (!nameSpan.classList.contains('editing')) return;\r
            nameSpan.classList.remove('editing');\r
            nameSpan.contentEditable = 'false';\r
            const newName = nameSpan.innerText.trim();\r
            if (newName && newName !== nameSpan.dataset.original) {\r
                const oldName = nameSpan.dataset.original;\r
                const previous = applyOptimisticSessionUpdate(sess.id, { name: newName });\r
                nameSpan.dataset.original = newName;\r
                if (currentSessionId === sess.id) updateSessionTitle();\r
                try {\r
                    const formData = new FormData();\r
                    formData.append('name', newName);\r
                    const response = await fetch('/sessions/' + encodeURIComponent(sess.id) + '/name', { method: 'PUT', body: formData });\r
                    if (!response.ok) throw new Error('rename failed: ' + response.status);\r
                    if (currentSessionId === sess.id) updateSessionTitle();\r
                } catch (err) {\r
                    console.error('重命名失败', err);\r
                    if (previous) applyOptimisticSessionUpdate(sess.id, previous);\r
                    nameSpan.innerText = oldName;\r
                    nameSpan.dataset.original = oldName;\r
                    if (currentSessionId === sess.id) updateSessionTitle();\r
                }\r
            } else nameSpan.innerText = nameSpan.dataset.original;
        });
        nameSpan.addEventListener('keydown', function (e) { if (e.key === 'Enter') { e.preventDefault(); nameSpan.blur(); } });\r
    }\r
    applySessionItemIndicators(div, sess.id, { serverStreamActive: !!sess.stream_active });\r
    return div;\r
}\r
\r
const sessionTitleRefreshState = Object.create(null);

function scheduleTitleGenerationRefresh(sessionId, pending) {
    const sid = String(sessionId || '');
    if (!sid) return;
    let state = sessionTitleRefreshState[sid];
    if (!pending) {
        if (state && state.timer) clearTimeout(state.timer);
        delete sessionTitleRefreshState[sid];
        return;
    }
    if (!state) state = sessionTitleRefreshState[sid] = { attempts: 0, timer: null };
    if (state.timer || state.attempts >= 60) return;
    const delayMs = Math.min(10000, Math.round(1000 * Math.pow(1.45, state.attempts)));
    state.timer = setTimeout(function () {
        state.timer = null;
        state.attempts += 1;
        void refreshSingleSessionRow(sid);
    }, delayMs);
}

async function refreshSingleSessionRow(sessionId) {
    if (!sessionId || !sessionsList) return;\r
    try {\r
        const response = await fetch('/sessions/' + encodeURIComponent(sessionId));\r
        if (!response.ok) return;\r
        const sess = await response.json();
        if (!sess || !sess.id) return;
        scheduleTitleGenerationRefresh(sess.id, !!sess.title_generation_pending);
        applySessionPatch({
            session: sess,
            session_id: sess.id,\r
            stream_active: !!sess.stream_active,\r
        });\r
        setSessionServerStreamActive(sess.id, !!sess.stream_active);\r
        if (sess.unread_result) {\r
            if (!sessionUnreadComplete.has(sess.id)) {\r
                sessionUnreadComplete.add(sess.id);\r
                persistSessionUnread();\r
            }\r
        } else if (sessionUnreadComplete.delete(sess.id)) {\r
            persistSessionUnread();\r
        }\r
        if (Number(sess.subagent_running || 0) > 0) {\r
            sessionUnreadComplete.delete(sess.id);\r
            persistSessionUnread();\r
        }
        renderSessionListIfChanged(false);
        if (typeof maybeAutoResumeInterruptedReact === 'function') {
            maybeAutoResumeInterruptedReact(sessionId, sess);
        }
    } catch (e) {
        console.error('刷新会话摘要失败:', e);\r
    }\r
}\r
\r
let sessionListLoadEpoch = 0;\r
let sessionListLoadPromise = null;\r
let sessionListRenderKey = '';\r
let createNewSessionQueue = Promise.resolve();\r
let archivedSessionsLoaded = false;\r
let archivedSessionsCache = null;\r
let archivedSessionsCount = 0;\r
let archivedSessionsLoadEpoch = 0;\r
\r
function syncArchivedSessionStateFromStore() {\r
    archivedSessionsLoaded = !!sessionStore.archivedLoaded;\r
    archivedSessionsCache = sessionStore.archivedSessions;\r
    archivedSessionsCount = sessionStore.archivedCount;\r
}\r
\r
function computeSessionListRenderKey() {
    const sessions = sessionStore.list();
    const parts = [
        'archivedLoaded=' + (sessionStore.archivedLoaded ? '1' : '0'),
        'archivedCount=' + String(sessionStore.archivedCount || 0),
    ];\r
    for (let i = 0; i < sessions.length; i += 1) {\r
        const s = sessions[i];\r
        if (!s || !s.id) continue;\r
        parts.push([\r
            s.id,\r
            s.name || '',
            s.pinned ? 'p' : '',
            s.archived ? 'a' : '',
            s.last_activity_at || s.updated_at || '',
            s.last_user_preview || '',
        ].join('\\u001f'));
    }\r
    const archived = sessionStore.archivedList();\r
    for (let j = 0; j < archived.length; j += 1) {\r
        const a = archived[j];\r
        if (!a || !a.id) continue;\r
        parts.push('arch=' + [\r
            a.id,
            a.name || '',
            a.pinned ? 'p' : '',
            a.last_activity_at || a.updated_at || '',
            a.last_user_preview || '',
        ].join('\\u001f'));
    }\r
    return parts.join('\\u001e');
}

function renderSessionListIfChanged(force) {
    const nextKey = computeSessionListRenderKey();
    if (!force && nextKey === sessionListRenderKey) {\r
        syncSessionListIndicatorClasses();\r
        renderSessionTitleFromStore();\r
        return;\r
    }\r
    sessionListRenderKey = nextKey;\r
    const nextStreamMap = renderSessionListFromStore();\r
    applyServerStreamActiveMap(nextStreamMap);\r
    renderSessionTitleFromStore();\r
}\r
\r
function clearSessionListError() {\r
    if (!sessionsList) return;\r
    sessionsList.classList.remove('sessions-list--error');\r
    if (sessionsList.dataset.loadError === '1') delete sessionsList.dataset.loadError;\r
}\r
\r
function renderSessionListError(message) {\r
    if (!sessionsList) return;\r
    sessionListRenderKey = '';\r
    sessionsList.classList.add('sessions-list--error');\r
    sessionsList.dataset.loadError = '1';\r
    sessionsList.innerHTML = '';\r
    const row = document.createElement('div');\r
    row.className = 'session-list-error';\r
    row.setAttribute('role', 'status');\r
    row.textContent = message || '加载会话列表失败';\r
    sessionsList.appendChild(row);\r
}\r
\r
function applyOptimisticSessionUpdate(sessionId, patch) {
    const sid = String(sessionId || '');\r
    const current = sessionStore.get(sid);\r
    if (!current) return null;\r
    const prev = Object.assign({}, current);\r
    const next = Object.assign({}, current, patch || {});\r
    if (Object.prototype.hasOwnProperty.call(patch || {}, 'pinned')) {\r
        next.pinned_at = next.pinned ? (next.pinned_at || new Date().toISOString()) : null;\r
    }
    sessionStore.upsert(next);
    if (prev.archived || next.archived) {
        if (sessionStore.archivedLoaded) {
            const archivedList = (sessionStore.archivedSessions || []).slice();
            const archivedIndex = archivedList.findIndex(function (s) {
                return s && String(s.id) === sid;
            });
            let visibleCount = sessionStore.archivedVisibleCount;
            let totalCount = sessionStore.archivedCount;
            if (prev.archived && next.archived) {
                if (archivedIndex >= 0) archivedList[archivedIndex] = next;
            } else if (prev.archived) {
                if (archivedIndex >= 0) archivedList.splice(archivedIndex, 1);
                if (archivedIndex >= 0 && archivedIndex < visibleCount) visibleCount -= 1;
                totalCount = Math.max(0, totalCount - 1);
            } else if (next.archived) {
                archivedList.unshift(next);
                visibleCount += 1;
                totalCount += 1;
            }
            sessionStore.setArchivedLoaded(archivedList, {
                visibleCount: visibleCount,
                totalCount: totalCount,
            });
            syncArchivedSessionStateFromStore();
        } else if (!!prev.archived !== !!next.archived) {
            sessionStore.setArchivedCount(Math.max(
                0,
                sessionStore.archivedCount + (next.archived ? 1 : -1)
            ));
        }
    }
    renderSessionListIfChanged(true);\r
    return prev;\r
}\r
\r
// Event count cache for optimistic UI updates.\r
const uiEventCountCache = {
    cache: new Map(),
    maxAgeMs: 10000,
    
    get(sessionId) {
        var entry = this.cache.get(sessionId);
        if (entry && typeof entry === 'object') return Number(entry.count) || 0;
        return Number(entry) || 0;
    },

    has(sessionId) {
        return this.cache.has(sessionId);
    },

    isFresh(sessionId, maxAgeMs) {
        var entry = this.cache.get(sessionId);
        if (!entry || typeof entry !== 'object') return false;
        var age = Date.now() - Number(entry.updatedAt || 0);
        var limit = Number(maxAgeMs) > 0 ? Number(maxAgeMs) : this.maxAgeMs;
        return age >= 0 && age <= limit;
    },
    
    set(sessionId, count) {
        this.cache.set(sessionId, {
            count: Math.max(0, Number(count) || 0),
            updatedAt: Date.now(),
        });
    },
    \r
    increment(sessionId) {\r
        const current = this.get(sessionId);\r
        this.set(sessionId, current + 1);\r
        return current + 1;\r
    },\r
    \r
    updateFromServer(sessionId, count) {\r
        this.set(sessionId, count);\r
    }\r
};\r
\r
async function fetchSessionsStateSnapshot(opts) {\r
    opts = opts || {};\r
    const url = '/sessions/state' + (opts.includeArchived ? '?include_archived=true' : '');\r
    const response = await fetchWithTimeout(url, {}, 12000);\r
    if (!response.ok) throw new Error('sessions state failed: ' + response.status);\r
    const snapshot = await response.json();\r
    if (!snapshot || !Array.isArray(snapshot.sessions)) {\r
        throw new Error('invalid sessions state response');\r
    }\r
    snapshot.include_archived = !!opts.includeArchived;\r
    return snapshot;\r
}\r
\r
async function fetchWithTimeout(url, options, timeoutMs) {\r
    options = options || {};\r
    const ms = Number(timeoutMs) > 0 ? Number(timeoutMs) : 15000;\r
    if (options.signal) return fetch(url, options);\r
    const controller = new AbortController();\r
    const timer = setTimeout(function () { controller.abort(); }, ms);\r
    const nextOptions = Object.assign({}, options, { signal: controller.signal });\r
    try {\r
        return await fetch(url, nextOptions);\r
    } finally {\r
        clearTimeout(timer);\r
    }\r
}\r
\r
async function fetchArchivedSessionPage(offset, limit) {
    const url = '/sessions?include_archived=true&archived_only=true&offset=' + String(offset)
        + '&limit=' + String(limit);
    const response = await fetchWithTimeout(url, {}, 15000);
    if (!response.ok) throw new Error('archived sessions failed: ' + response.status);
    const sessions = await response.json();
    const countHeader = response.headers.get('X-Archived-Count');
    const parsedCount = Number(countHeader);
    return {
        sessions: Array.isArray(sessions) ? sessions : [],
        totalCount: Number.isFinite(parsedCount) && parsedCount >= 0
            ? parsedCount
            : Math.max(offset + (Array.isArray(sessions) ? sessions.length : 0), sessionStore.archivedCount),
    };
}

function appendArchivedSessionPage(page, visibleCount) {
    const combined = (sessionStore.archivedSessions || []).concat(page.sessions || []);
    const seen = new Set();
    const deduplicated = combined.filter(function (s) {
        const sid = s && s.id ? String(s.id) : '';
        if (!sid || seen.has(sid)) return false;
        seen.add(sid);
        return true;
    });
    sessionStore.setArchivedLoaded(deduplicated, {
        visibleCount: visibleCount,
        totalCount: page.totalCount,
    });
}

async function prefetchNextArchivedPage(loadEpoch) {
    const cachedCount = Array.isArray(sessionStore.archivedSessions)
        ? sessionStore.archivedSessions.length
        : 0;
    const wantedCount = Math.min(
        sessionStore.archivedCount,
        sessionStore.archivedVisibleCount + ARCHIVED_SESSIONS_PAGE_SIZE
    );
    if (cachedCount >= wantedCount) return;
    const page = await fetchArchivedSessionPage(cachedCount, wantedCount - cachedCount);
    if (loadEpoch !== archivedSessionsLoadEpoch) return;
    appendArchivedSessionPage(page, sessionStore.archivedVisibleCount);
}

async function loadArchivedSessions(opts) {
    opts = opts || {};
    const loadEpoch = ++archivedSessionsLoadEpoch;
    try {
        if (!sessionStore.archivedLoaded) {
            const initialPage = await fetchArchivedSessionPage(0, ARCHIVED_SESSIONS_PAGE_SIZE * 2);
            if (loadEpoch !== archivedSessionsLoadEpoch) return;
            sessionStore.setArchivedLoaded(initialPage.sessions, {
                visibleCount: ARCHIVED_SESSIONS_PAGE_SIZE,
                totalCount: initialPage.totalCount,
            });
        } else if (opts.background || opts.refresh || !sessionStore.hasMoreArchivedSessions()) {
            const refreshLimit = Math.max(
                ARCHIVED_SESSIONS_PAGE_SIZE * 2,
                sessionStore.archivedVisibleCount + ARCHIVED_SESSIONS_PAGE_SIZE
            );
            const refreshedPage = await fetchArchivedSessionPage(0, refreshLimit);
            if (loadEpoch !== archivedSessionsLoadEpoch) return;
            sessionStore.setArchivedLoaded(refreshedPage.sessions, {
                visibleCount: sessionStore.archivedVisibleCount,
                totalCount: refreshedPage.totalCount,
            });
        } else {
            if (sessionStore.revealNextArchivedPage() === 0) {
                const cachedCount = Array.isArray(sessionStore.archivedSessions)
                    ? sessionStore.archivedSessions.length
                    : 0;
                const nextPage = await fetchArchivedSessionPage(cachedCount, ARCHIVED_SESSIONS_PAGE_SIZE);
                if (loadEpoch !== archivedSessionsLoadEpoch) return;
                appendArchivedSessionPage(nextPage, sessionStore.archivedVisibleCount);
                sessionStore.revealNextArchivedPage();
            }
            syncArchivedSessionStateFromStore();
            renderSessionListIfChanged(true);
            clearSessionListError();
            try {
                await prefetchNextArchivedPage(loadEpoch);
            } catch (prefetchErr) {
                console.error('预加载下一批归档目录失败:', prefetchErr);
            }
        }
        if (loadEpoch !== archivedSessionsLoadEpoch) return;
        syncArchivedSessionStateFromStore();
        renderSessionListIfChanged(!!opts.forceRender);
        clearSessionListError();
    } catch (err) {
        console.error('加载归档目录失败:', err);
        if (!opts.background) throw err;
    }
}
\r
async function loadSessions(opts) {\r
    opts = opts || {};\r
    if (sessionListLoadPromise && !opts.force) return sessionListLoadPromise;\r
    sessionListLoadPromise = loadSessionsInner(opts);\r
    try {\r
        return await sessionListLoadPromise;\r
    } finally {\r
        sessionListLoadPromise = null;\r
    }\r
}\r
\r
async function loadSessionsInner(opts) {\r
    const loadEpoch = ++sessionListLoadEpoch;\r
    sessionStore.ui.loadingSessions = true;\r
    try {\r
        let allSessions;\r
        let snapshot = null;\r
        \r
        try {\r
            snapshot = await fetchSessionsStateSnapshot();\r
            if (loadEpoch !== sessionListLoadEpoch) return;\r
            allSessions = Array.isArray(snapshot.sessions) ? snapshot.sessions : [];\r
        } catch (stateErr) {\r
            console.error('加载会话状态快照失败，回退至旧接口', stateErr);\r
            const response = await fetchWithTimeout('/sessions', {}, 12000);\r
            const archivedCountHeader = response.headers.get('X-Archived-Count');\r
            if (archivedCountHeader != null && archivedCountHeader !== '') {\r
                const parsedArchivedCount = Number(archivedCountHeader);\r
                if (Number.isFinite(parsedArchivedCount) && parsedArchivedCount >= 0) {\r
                    sessionStore.setArchivedCount(parsedArchivedCount);\r
                    syncArchivedSessionStateFromStore();\r
                }\r
            }\r
            const sessions = await response.json();\r
            if (loadEpoch !== sessionListLoadEpoch) return;\r
            allSessions = Array.isArray(sessions) ? sessions : [];\r
            snapshot = {\r
                sessions: allSessions,\r
                archived_count: archivedSessionsCount,\r
            };\r
        }\r
        applySessionSnapshot(snapshot || { sessions: allSessions, archived_count: archivedSessionsCount });\r
        syncArchivedSessionStateFromStore();\r
        allSessions = sessionStore.list();\r
        \r
        const idSet = new Set();\r
        for (let si = 0; si < allSessions.length; si += 1) {\r
            if (allSessions[si] && allSessions[si].id) idSet.add(allSessions[si].id);\r
        }\r
        [...sessionUnreadComplete].forEach(function (uid) {\r
            if (!idSet.has(uid)) sessionUnreadComplete.delete(uid);\r
        });\r
        persistSessionUnread();\r
\r
        renderSessionListIfChanged(!!opts.forceRender);\r
        clearSessionListError();\r
        sessionStore.ui.loadingSessions = false;\r
        if (opts.refreshArchived && !opts.skipArchivedRefresh && sessionStore.archivedLoaded) {\r
            void loadArchivedSessions({ background: true });\r
        }\r
        return true;\r
    } catch (error) {\r
        sessionStore.ui.loadingSessions = false;\r
        console.error('加载会话列表失败:', error);\r
        if (sessionStore.list().length > 0) {\r
            renderSessionListIfChanged(true);\r
            clearSessionListError();\r
        } else {\r
            renderSessionListError('加载会话列表失败');\r
        }\r
        return false;\r
    }\r
}\r
\r
async function reconcileRunStateFromServer(opts) {\r
    opts = opts || {};\r
    const suppressedBeforeFetch = new Set();\r
    if (opts.respectStopSuppress) {\r
        sessionStore.sessionOrder.forEach(function (sid) {\r
            if (isSessionStreamStopSuppressed(sid)) suppressedBeforeFetch.add(String(sid));\r
        });\r
        if (currentSessionId && isSessionStreamStopSuppressed(currentSessionId)) {\r
            suppressedBeforeFetch.add(String(currentSessionId));\r
        }\r
    }\r
    let snapshot = null;\r
    try {\r
        const cur = currentSessionId ? sessionStore.get(currentSessionId) : null;\r
        snapshot = await fetchSessionsStateSnapshot({\r
            includeArchived: !!(sessionStore.archivedLoaded || (cur && cur.archived)),\r
        });\r
    } catch (e) {\r
        if (!opts.silent) console.error('reconcile run state failed:', e);\r
        return;\r
    }\r
    applySessionSnapshot(snapshot);\r
    if (opts.respectStopSuppress) {\r
        suppressedBeforeFetch.forEach(function (sid) {\r
            if (isSessionStreamStopSuppressed(sid)) {\r
                sessionStore.setStreamActive(sid, false);\r
                const sess = sessionStore.get(sid);\r
                if (sess) {\r
                    sess.stream_active = false;\r
                    sess.run_active = false;\r
                    sess.run_started_at = null;\r
                }\r
                sessionStore.activeRunInfoBySession.delete(sid);\r
            }\r
        });\r
    }\r
    const active = new Set();\r
    sessionStore.activeRunInfoBySession.forEach(function (info, sid) {\r
        if (info && info.run_active === true) active.add(String(sid));\r
    });\r
    const localIds = [];\r
    sessionStore.runsBySession.forEach(function (_run, sid) {\r
        localIds.push(String(sid));\r
    });\r
    localIds.forEach(function (sid) {\r
        if (!active.has(sid)) {\r
            var run = getSessionRunState(sid);\r
            if (run && run.reattached) {\r
                abortSessionRun(sid, 'reconcile-finished');\r
            }\r
        }\r
    });\r
    if (currentSessionId && active.has(currentSessionId)) {\r
        const info = sessionStore.getActiveRunInfo(currentSessionId) || {};\r
        const run = getSessionRunState(currentSessionId);\r
        const ctx = run && run.ctx;\r
        const agg = ctx && ctx.currentProcessGroup && ctx.currentProcessGroup.isConnected\r
            ? ctx.currentProcessGroup\r
            : (getVisibleChatStream() && getVisibleChatStream().querySelector('.process-aggregate:last-of-type'));\r
        if (agg && info.started_at) applyRunStartedAtToProcessGroup(agg, info.started_at);\r
    }\r
    syncSessionListIndicatorClasses();\r
    setSendButtonState();\r
    renderSessionListIfChanged(false);\r
}\r
\r
function showSessionLoadRetry(sessionId) {\r
    var sid = String(sessionId || '');\r
    var stream = getVisibleChatStream();\r
    if (!sid || !stream) return;\r
    if (stream.querySelector('.session-load-retry')) return;\r
    var row = document.createElement('div');\r
    row.className = 'feed-item feed--err session-load-retry';\r
    var btn = document.createElement('button');\r
    btn.type = 'button';\r
    btn.className = 'history-load-older-btn';\r
    btn.textContent = '重新加载';\r
    btn.addEventListener('click', function (e) {\r
        e.preventDefault();\r
        if (typeof discardCachedSessionStream === 'function') discardCachedSessionStream(sid);\r
        void switchSession(sid, { forceReload: true });\r
    });\r
    row.appendChild(btn);\r
    stream.appendChild(row);\r
}\r
\r
async function loadSessionMessages(sessionId, scrollBehavior, opts) {
    const openSessionStartedAt = (typeof performance !== 'undefined' && performance.now)
        ? performance.now()
        : Date.now();
    scrollBehavior = scrollBehavior || 'saved-or-bottom';
    opts = opts || {};
    const loadToken = ++messageLoadEpoch;
    let historyHydrationStream = null;
    const finishHistoryHydration = function () {
        if (historyHydrationStream) {
            historyHydrationStream.hidden = false;
            historyHydrationStream = null;
        }
        if (loadToken === messageLoadEpoch) hideLoading();
        if (typeof attachAllHumanInteractionCards === 'function') {
            attachAllHumanInteractionCards(getVisibleChatStream());
        }
    };
    sessionStore.ui.loadingMessages = true;
    suppressTocDuringSessionLoad = true;
    replayingMessages = true;
    resetSessionHistoryPaging();
    try {
        let raw;
        let snapshotTocTurns = null;
        let snapshotTodoPlan = null;
        let historySource = 'messages';
        let snapshotTiming = null;
        const canUseSnapshot = !opts.full && opts.useSnapshot !== false && beforeSessionMessageSnapshotAvailable();
        if (canUseSnapshot) {
            try {
                const snapshotUrl = '/sessions/' + encodeURIComponent(sessionId)
                    + '/history_snapshot?turns=' + encodeURIComponent(String(HISTORY_DIALOGUES_PER_PAGE))
                    + '&event_budget=' + encodeURIComponent(String(HISTORY_EVENT_BUDGET))
                    + '&include_aux=false';
                for (let migrationAttempt = 0; migrationAttempt < 120; migrationAttempt += 1) {
                    const snapshotResp = await fetchWithTimeout(snapshotUrl, {}, 15000);
                    const snapshot = await snapshotResp.json().catch(function () { return null; });
                    if (snapshot && snapshot.migration_pending) {
                        if (loadToken !== messageLoadEpoch || sessionId !== currentSessionId) return;
                        const retryMs = Math.max(100, Math.min(Number(snapshot.retry_after_ms) || 250, 1000));
                        await new Promise(function (resolve) { setTimeout(resolve, retryMs); });
                        continue;
                    }
                    if (snapshotResp.ok) {
                    if (snapshot && snapshot.ok && snapshot.messages) {
                        raw = snapshot.messages;
                        historySource = 'history_snapshot';
                        snapshotTiming = snapshot.timing && typeof snapshot.timing === 'object'
                            ? snapshot.timing
                            : null;
                        if (typeof uiEventCountCache !== 'undefined' && typeof snapshot.count === 'number') {
                            uiEventCountCache.updateFromServer(sessionId, snapshot.count);
                        }
                        if (Array.isArray(snapshot.user_turns)) {
                            snapshotTocTurns = snapshot.user_turns;
                            if (typeof setTocTurnsForSession === 'function') setTocTurnsForSession(sessionId, snapshot.user_turns);
                        }
                        if (snapshot.todo_plan && typeof snapshot.todo_plan === 'object') {
                            snapshotTodoPlan = snapshot.todo_plan;
                            if (typeof setTodoPlanForSession === 'function') setTodoPlanForSession(sessionId, snapshot.todo_plan);
                        }
                        if (snapshot.context_tokens && snapshot.context_tokens.estimated != null) {
                            recordContextTokens(sessionId, snapshot.context_tokens.estimated, snapshot.context_tokens.threshold);
                        }
                    }
                    }
                    break;
                }
            } catch (snapshotErr) {
                console.warn('history snapshot unavailable, falling back to messages:', snapshotErr);
            }
        }
        if (!raw) {
            let url = '/sessions/' + encodeURIComponent(sessionId) + '/messages';
            if (!opts.full) {
                url += '?turns=' + HISTORY_DIALOGUES_PER_PAGE
                    + '&event_budget=' + encodeURIComponent(String(HISTORY_EVENT_BUDGET));
            }
            const response = await fetchWithTimeout(url, {}, 15000);
            if (!response.ok) throw new Error('messages failed: ' + response.status);
            raw = await response.json();
        }
        if (loadToken !== messageLoadEpoch || sessionId !== currentSessionId) return;
        if (getSessionRunState(sessionId) && !opts.allowDuringRun) return;\r
        if (!getVisibleChatStream()) ensureVisibleChatStreamSlot();
        const vis = getVisibleChatStream();
        if (vis) {
            const loader = document.getElementById('chat-loading');
            if (loader && loader.parentNode === vis && chatContainer) {
                chatContainer.insertBefore(loader, vis);
            }
            vis.hidden = true;
            historyHydrationStream = vis;
            emptyChatStreamKeepingStrip(vis);
        }
        else {
            chatContainer.innerHTML = '';
            ensureVisibleChatStreamSlot();
        }\r
        markVisibleSessionStreamLoadState(sessionId, 'loading');\r
        let events;\r
        let pageMeta = null;\r
        if (Array.isArray(raw)) {\r
            events = raw;\r
        } else if (raw && typeof raw === 'object' && Array.isArray(raw.events)) {
            events = raw.events;
            const pageTotal = Number(raw.total) || 0;
            const pageRangeEnd = Number(raw.range_end) || 0;
            pageMeta = {
                total: pageTotal,
                range_start: Number(raw.range_start) || 0,
                range_end: pageRangeEnd,
                has_older: !!raw.has_older,
                has_newer: raw.has_newer == null ? pageRangeEnd < pageTotal : !!raw.has_newer,
            };
            uiEventCountCache.updateFromServer(sessionId, pageMeta.total);\r
        } else {\r
            events = [];\r
        }\r
        beginMessageReplay(sessionId, pageMeta || {\r
            total: events.length,\r
            range_start: 0,\r
            range_end: events.length,\r
        });\r
        if (!opts.full && pageMeta) {\r
            setSessionHistoryPaging({\r
                sessionId: sessionId,\r
                total: pageMeta.total,\r
                range_start: pageMeta.range_start,
                range_end: pageMeta.range_end,
                has_older: !!pageMeta.has_older,
                has_newer: !!pageMeta.has_newer,
            });
            ensureHistorySentinel(getVisibleChatStream());\r
        }\r
        if (events.length === 0) {
            suppressTocDuringSessionLoad = false;
            setWelcome();
            finishHistoryHydration();
            updateSessionTitle();
            scheduleContextTokensAfterPaint(sessionId);\r
            applyChatScrollAfterHistoryLoad(sessionId, scrollBehavior);\r
            markVisibleSessionStreamLoadState(sessionId, 'ok');
            if (typeof renderLoadedTodoPlanForSession === 'function') {
                renderLoadedTodoPlanForSession(sessionId, snapshotTodoPlan, opts.todoAlreadyStarted);
            } else {
                renderTodoPlanForCurrentSession();
            }
            logOpenSessionTiming(sessionId, {
                source: historySource,
                events: 0,
                snapshotTiming: snapshotTiming,
                totalMs: elapsedSince(openSessionStartedAt),
            });
            return true;
        }
        const loadCtx = newDomContext(getVisibleChatStream());\r
        loadCtx.lastUserEventIndex = -1;\r
        const indexBase = pageMeta ? pageMeta.range_start : 0;\r
        const batchSize = opts.full ? 64 : 512;\r
        for (let evi = 0; evi < events.length; evi += 1) {
            const ev = events[evi];
            if (ev && typeof ev === 'object' && ev.type) {\r
                reduceAndRenderMessageEvent(loadCtx, ev, {\r
                    sessionId: sessionId,\r
                    eventIndex: indexBase + evi,\r
                    source: 'history',\r
                });\r
            }\r
            if (evi > 0 && evi % batchSize === 0) {\r
                await new Promise(function (resolve) { setTimeout(resolve, 0); });\r
                if (loadToken !== messageLoadEpoch || sessionId !== currentSessionId) return;
            }
        }
        finishHistoryHydration();
        if (!chatStreamHasConversationContent()) {
            suppressTocDuringSessionLoad = false;
            setWelcome();
            updateSessionTitle();
            scheduleContextTokensAfterPaint(sessionId);
            applyChatScrollAfterHistoryLoad(sessionId, scrollBehavior);
            markVisibleSessionStreamLoadState(sessionId, 'ok');
            if (typeof renderLoadedTodoPlanForSession === 'function') {
                renderLoadedTodoPlanForSession(sessionId, snapshotTodoPlan, opts.todoAlreadyStarted);
            } else {
                renderTodoPlanForCurrentSession();
            }
            logOpenSessionTiming(sessionId, {
                source: historySource,
                events: events.length,
                snapshotTiming: snapshotTiming,
                totalMs: elapsedSince(openSessionStartedAt),
            });
            return true;
        }
        if (!opts.full && opts.preloadOlderIfShort && pageMeta && pageMeta.has_older && events.length <= 2) {
            await loadOlderHistoryChunk({ keepTocStable: true });\r
            if (loadToken !== messageLoadEpoch || sessionId !== currentSessionId) return;\r
        }\r
        if (historyLoadScrollsToBottom(sessionId, scrollBehavior)) {\r
            tocScrollBottomOnNextBuild = true;\r
        }
        suppressTocDuringSessionLoad = false;
        if (snapshotTocTurns) rebuildToc({ turns: snapshotTocTurns });
        else if (!opts.tocAlreadyStarted) rebuildToc();
        updateSessionTitle();
        updateHistorySentinelVisibility();
        bindExistingLogInteractions();
        applyChatScrollAfterHistoryLoad(sessionId, scrollBehavior);
        var initialSmoothReachedBottom = await waitForChatScrollAfterHistoryLoad(sessionId, scrollBehavior);
        if (loadToken !== messageLoadEpoch || sessionId !== currentSessionId) return;
        finalizeExistingLogLayout();
        if (scrollBehavior === 'smooth-bottom' && initialSmoothReachedBottom) {
            setScrollTopImmediate(chatContainer, chatContainer.scrollHeight);
            requestAnimationFrame(function () {
                requestAnimationFrame(function () {
                    if (loadToken !== messageLoadEpoch || sessionId !== currentSessionId) return;
                    setScrollTopImmediate(chatContainer, chatContainer.scrollHeight);
                });
            });
        }
        scheduleTocActiveUpdate();
        scheduleContextTokensAfterPaint(sessionId);
        if (typeof renderLoadedTodoPlanForSession === 'function') {
            renderLoadedTodoPlanForSession(sessionId, snapshotTodoPlan, opts.todoAlreadyStarted);
        } else {
            renderTodoPlanForCurrentSession();
        }
        markVisibleSessionStreamLoadState(sessionId, 'ok');
        logOpenSessionTiming(sessionId, {
            source: historySource,
            events: events.length,
            snapshotTiming: snapshotTiming,
            totalMs: elapsedSince(openSessionStartedAt),
        });
        return true;
    } catch (error) {
        if (loadToken !== messageLoadEpoch || sessionId !== currentSessionId) return false;
        console.error('加载会话消息失败:', error);
        document.getElementById('chat-loading')?.remove();\r
        appendLogVisible('加载历史消息失败', 'error-log');\r
        markVisibleSessionStreamLoadState(sessionId, 'failed');\r
        showSessionLoadRetry(sessionId);\r
        return false;\r
    } finally {
        finishHistoryHydration();
        if (loadToken === messageLoadEpoch) sessionStore.ui.loadingMessages = false;
        if (loadToken === messageLoadEpoch) suppressTocDuringSessionLoad = false;\r
        if (loadToken === messageLoadEpoch) replayingMessages = false;\r
    }
}

function chatStreamHasConversationContent() {
    var stream = getVisibleChatStream();
    if (!stream) return false;
    return !!stream.querySelector('.msg-wrap, .process-aggregate, .human-interaction-card, .human-interaction-banner');
}

function elapsedSince(startedAt) {
    var now = (typeof performance !== 'undefined' && performance.now)
        ? performance.now()
        : Date.now();
    return Math.max(0, Math.round(now - Number(startedAt || now)));
}

function logOpenSessionTiming(sessionId, data) {
    data = data || {};
    var timing = data.snapshotTiming && typeof data.snapshotTiming === 'object' ? data.snapshotTiming : {};
    var backendTotal = Number(timing.total || 0);
    var frontendTotal = Number(data.totalMs || 0);
    if (frontendTotal < 500 && backendTotal < 500) return;
    console.info(
        'open_session_timing session=%s source=%s total=%sms events=%s backend_total=%sms read_page=%sms count=%sms user_turns=%sms context_tokens=%sms',
        sessionId,
        data.source || 'unknown',
        frontendTotal,
        Number(data.events || 0),
        backendTotal,
        Number(timing.read_page || 0),
        Number(timing.count || 0),
        Number(timing.user_turns || 0),
        Number(timing.context_tokens || 0)
    );
}

function beforeSessionMessageSnapshotAvailable() {
    return true;
}

async function switchSession(sessionId, opts) {
    opts = opts || {};
    if (typeof endHistorySmoothScroll === 'function') endHistorySmoothScroll();
    if (currentSessionId === sessionId && !opts.forceReload) return;
    if (opts.forceReload && typeof discardCachedSessionStream === 'function') discardCachedSessionStream(sessionId);\r
    const switchToken = ++switchSessionEpoch;\r
    suppressTocDuringSessionLoad = true;\r
    clearTocForSessionLoad();\r
    clearTodoForSessionLoad();\r
    pendingRewriteTruncate = null;\r
    hideRewriteUndoToast();\r
    // A green-dot session represents an unread completed result. Opening it
    // must land at the newest result, never at a stale reading anchor.
    var sessionHadUnreadResult = !!(
        (sessionStore.get(sessionId) && sessionStore.get(sessionId).unread_result)
        || sessionUnreadComplete.has(sessionId)
    );
    clearSessionUnreadState(sessionId);
    const leaving = currentSessionId;
    saveChatScrollForSession(leaving);
    stashInputDraft(leaving);
    if (typeof stashSkillPickerDraft === 'function') stashSkillPickerDraft(leaving);
    prepareStashLeaving(leaving);
    hideSubagentContinueBanner();
    resetSubagentPanelForSession();
    if (typeof closeGoalEditModal === 'function') closeGoalEditModal(false);
    setCurrentSessionState(sessionId);
    if (typeof renderGoalForCurrentSession === 'function') renderGoalForCurrentSession();
    if (typeof refreshGoalCard === 'function') void refreshGoalCard();
    if (typeof updateHumanInteractionBanner === 'function') updateHumanInteractionBanner(sessionId);
    localStorage.setItem('lastSessionId', sessionId);
    if (typeof applyContextTokenLabelForCurrentSession === 'function') applyContextTokenLabelForCurrentSession();
    restoreInputDraft(sessionId);
    if (typeof restoreSkillPickerDraft === 'function') restoreSkillPickerDraft(sessionId);
    if (typeof renderFollowupQueue === 'function') renderFollowupQueue(sessionId);
    if (typeof syncFollowupQueueFromServer === 'function') syncFollowupQueueFromServer(sessionId);
    if (typeof refreshModelProfileSelector === 'function') refreshModelProfileSelector(sessionId);\r
    syncSessionListIndicatorClasses();\r
    setSendButtonState();\r
    var restoredFromCache = false;
    var restoredRunningStream = false;
    if (!opts.forceReload && ((restoredRunningStream = restoreStreamForRunningSession(sessionId)) || (restoredFromCache = restoreCachedSessionStream(sessionId)))) {
        suppressTocDuringSessionLoad = false;\r
        hideLoading();\r
        rebuildToc({ localOnly: true });
        updateSessionTitle();
        scheduleContextTokensAfterPaint(sessionId);
        // Only a complete, idle stream restored from the in-memory cache may
        // return to its prior reading position. A live run and a green-dot
        // completion always open on their newest content.
        var sessionIsRunningNow = !!(
            restoredRunningStream
            || isSessionRunning(sessionId)
            || (typeof isServerStreamActive === 'function' && isServerStreamActive(sessionId))
        );
        if (restoredFromCache && !sessionHadUnreadResult && !sessionIsRunningNow) {
            restoreCachedSessionScrollPosition(sessionId);
        } else {
            streamChatNearBottom = true;
            streamProcNearBottom = true;
            liveAutoFollow = true;
            scrollToBottom();
            if (sessionIsRunningNow && typeof scrollCurrentRunningProcessToBottom === 'function') {
                scrollCurrentRunningProcessToBottom(sessionId);
            }
        }
        if (typeof refreshTodoPlanPanel === 'function') void refreshTodoPlanPanel();
        else renderTodoPlanForCurrentSession();
        if (typeof refreshHumanInteractions === 'function') void refreshHumanInteractions(sessionId);
        if (switchToken !== switchSessionEpoch || sessionId !== currentSessionId) return;
        /* 让 rebuildToc 的 /user_turns fetch 先发出，subagent 面板（含 N 个 /messages）顺序后置，\r
           避免抢占带宽与主线程，让目录最后才稳态。*/\r
        setTimeout(function () {
            if (switchToken === switchSessionEpoch && sessionId === currentSessionId) {
                refreshSubagentTreePanel(sessionId);
            }
        }, 0);
        void refreshSingleSessionRow(sessionId);\r
        setSendButtonState();\r
        maybeStartStreamPollForSession(sessionId, { skipInitialLoad: true });\r
        return;\r
    }\r
    const vs = getVisibleChatStream();\r
    resetSessionHistoryPaging();\r
    if (vs) emptyChatStreamKeepingStrip(vs);\r
    else {\r
        chatContainer.innerHTML = '';\r
        ensureVisibleChatStreamSlot();\r
    }
    showLoading();
    const tocAlreadyStarted = opts.useSnapshot === false && typeof startTocForSessionLoad === 'function';
    if (tocAlreadyStarted) startTocForSessionLoad(sessionId);
    if (tocAlreadyStarted && typeof startTodoForSessionLoad === 'function') startTodoForSessionLoad(sessionId);
    return new Promise(function (resolve) {
        setTimeout(async function () {\r
        if (switchToken !== switchSessionEpoch || sessionId !== currentSessionId) { resolve(false); return; }\r
        try {\r
            // A freshly loaded or force-reloaded stream does not restore a
            // persisted reading position. Once its history is rendered, ease
            // the viewport down to the newest message.
            var loadedOk = await loadSessionMessages(sessionId, 'smooth-bottom', {
                preloadOlderIfShort: isServerStreamActive(sessionId),
                allowDuringRun: isServerStreamActive(sessionId),
                tocAlreadyStarted: tocAlreadyStarted,
                todoAlreadyStarted: tocAlreadyStarted,
            });
            if (!loadedOk) { resolve(false); return; }\r
        } catch (error) {\r
            console.error('切换会话加载失败:', error);\r
            resolve(false);\r
            return;\r
        } finally {\r
            if (switchToken === switchSessionEpoch && sessionId === currentSessionId) {\r
                hideLoading();\r
                sessionStore.ui.loadingMessages = false;\r
                suppressTocDuringSessionLoad = false;\r
                replayingMessages = false;\r
            }\r
        }\r
        if (switchToken !== switchSessionEpoch || sessionId !== currentSessionId) { resolve(false); return; }\r
        /* loadSessionMessages 内部已发起 rebuildToc()；这里再延后一步调用 subagent panel\r
           重建，保证「目录 → 消息 → 副 agent 按钮」的稳定顺序（无 subagent 的会话表现一致）。*/\r
        setTimeout(function () {
            if (switchToken === switchSessionEpoch && sessionId === currentSessionId) {
                refreshSubagentTreePanel(sessionId);
            }
        }, 0);
        void refreshSingleSessionRow(sessionId);\r
        setSendButtonState();\r
        maybeStartStreamPollForSession(sessionId, { skipInitialLoad: true });
        if (typeof refreshHumanInteractions === 'function') void refreshHumanInteractions(sessionId);
        resolve(true);
        }, 20);\r
    });\r
}\r
\r
async function createNewSession() {\r
    createNewSessionQueue = createNewSessionQueue.then(\r
        function () { return createNewSessionInner(); },\r
        function () { return createNewSessionInner(); }\r
    );\r
    return createNewSessionQueue;\r
}\r
\r
async function createNewSessionInner() {\r
    try {\r
        saveChatScrollForSession(currentSessionId);
        stashInputDraft(currentSessionId);
        if (typeof stashSkillPickerDraft === 'function') stashSkillPickerDraft(currentSessionId);
        prepareStashLeaving(currentSessionId);
        const response = await fetch('/sessions', { method: 'POST' });\r
        const data = await response.json();\r
        if (data && data.session) sessionStore.upsert(data.session);\r
        resetSubagentPanelForSession();\r
        switchSessionEpoch += 1;\r
        messageLoadEpoch += 1;\r
        setCurrentSessionState(data.session_id);
        if (typeof updateHumanInteractionBanner === 'function') updateHumanInteractionBanner(currentSessionId);
        localStorage.setItem('lastSessionId', currentSessionId);
        restoreInputDraft(currentSessionId);
        if (typeof restoreSkillPickerDraft === 'function') restoreSkillPickerDraft(currentSessionId);
        if (typeof renderFollowupQueue === 'function') renderFollowupQueue(currentSessionId);
        if (typeof syncFollowupQueueFromServer === 'function') syncFollowupQueueFromServer(currentSessionId);
        if (typeof refreshModelProfileSelector === 'function') refreshModelProfileSelector(currentSessionId);
        if (typeof refreshPermissionModeSelector === 'function') refreshPermissionModeSelector(currentSessionId);
        if (!getVisibleChatStream()) ensureVisibleChatStreamSlot();\r
        setWelcome();\r
        replayingMessages = false;\r
        if (data && data.session) {\r
            syncArchivedSessionStateFromStore();\r
            renderSessionListIfChanged(true);\r
            void refreshSingleSessionRow(data.session_id);\r
        } else {\r
            await loadSessions();\r
        }\r
        setSendButtonState();\r
        maybeStartStreamPollForSession(currentSessionId);\r
        scheduleContextTokensAfterPaint(currentSessionId);\r
    } catch (error) {\r
        console.error('创建新会话失败', error);\r
        appendLogVisible('创建新会话失败', 'error-log');\r
    }\r
}\r
`,Qt=`const SSE_IDLE_TIMEOUT_MS = 120000;
const STREAM_RECONNECT_MAX_ATTEMPTS = 10;
const STREAM_RECONNECT_BASE_DELAY_MS = 500;
const STREAM_RECONNECT_MAX_DELAY_MS = 15000;
const streamReconnectStateBySession = Object.create(null);

function resetStreamReconnectState(sessionId) {
    var sid = String(sessionId || '');
    var state = streamReconnectStateBySession[sid];
    if (!state) return;
    if (state.timer) clearTimeout(state.timer);
    delete streamReconnectStateBySession[sid];
}

function streamReconnectState(sessionId) {
    var sid = String(sessionId || '');
    if (!streamReconnectStateBySession[sid]) {
        streamReconnectStateBySession[sid] = { attempts: 0, timer: null, exhausted: false };
    }
    return streamReconnectStateBySession[sid];
}

function isStreamConsuming(sessionId) {
    var sid = String(sessionId || '');
    var run = typeof getSessionRunState === 'function' ? getSessionRunState(sid) : null;
    return !!(run && run.ctx && run.ctx.streamConsuming);
}

function reportStreamReconnectExhausted(sessionId) {
    var sid = String(sessionId || '');
    var run = typeof getSessionRunState === 'function' ? getSessionRunState(sid) : null;
    var ctx = run && run.ctx;
    if (ctx && sid === String(currentSessionId || '')) {
        appendLog(ctx, '实时流恢复已停止重试（' + STREAM_RECONNECT_MAX_ATTEMPTS + ' 次）。请检查网络或服务状态后刷新页面。', 'error-log', sid);
    }
}

function sendPipelineKey(sessionId) {
    return String(sessionId || '__new_session__');
}

function isSendPipelineLocked(sessionId) {
    return !!sendPipelineLocksBySession[sendPipelineKey(sessionId)];
}

function acquireSendPipelineLock(sessionId) {
    const key = sendPipelineKey(sessionId);
    if (sendPipelineLocksBySession[key]) return null;
    const token = 'send-lock-' + Date.now() + '-' + Math.random().toString(16).slice(2);
    sendPipelineLocksBySession[key] = token;
    return { key: key, token: token };
}

function transferSendPipelineLock(lock, sessionId) {
    if (!lock || sendPipelineLocksBySession[lock.key] !== lock.token) return false;
    const nextKey = sendPipelineKey(sessionId);
    if (nextKey === lock.key) return true;
    if (sendPipelineLocksBySession[nextKey]) return false;
    delete sendPipelineLocksBySession[lock.key];
    sendPipelineLocksBySession[nextKey] = lock.token;
    lock.key = nextKey;
    return true;
}

function releaseSendPipelineLock(lock) {
    if (!lock) return;
    if (sendPipelineLocksBySession[lock.key] === lock.token) {
        delete sendPipelineLocksBySession[lock.key];
    }
}

/* ---------------------------------------------------------------------------
 * 会话级追问 dispatcher：所有显式“立即发送”共用同一 per-session 互斥链，
 * 保证同一会话同一时刻只处理一条追问，避免并发 steer 竞争。
 * ------------------------------------------------------------------------- */
function withFollowupDispatch(sessionId, fn) {
    var sid = String(sessionId || '');
    if (!sid) return Promise.resolve();
    var prev = followupDispatchChain[sid] || Promise.resolve();
    var run = function () { return Promise.resolve().then(fn); };
    // 前一条无论成功/失败都继续执行本条，避免一次失败永久堵塞后续追问。
    var next = prev.then(run, run);
    var settled = next.then(function () { return null; }, function () { return null; });
    followupDispatchChain[sid] = settled;
    settled.finally(function () {
        if (followupDispatchChain[sid] === settled) delete followupDispatchChain[sid];
    });
    return next;
}

function isFollowupDispatchBusy(sessionId) {
    return !!followupDispatchChain[String(sessionId || '')];
}

async function waitForSendPipelineIdle(sessionId, timeoutMs) {
    var sid = String(sessionId || '');
    var deadline = Date.now() + Math.max(0, Number(timeoutMs) || 0);
    while (isSendPipelineLocked(sid)) {
        if (Date.now() >= deadline) return false;
        await sleepMs(40);
    }
    return true;
}

function refreshPendingFollowupQueue(sessionId) {
    var sid = String(sessionId || '');
    if (!sid) return;
    renderFollowupQueue(sid);
}

function shouldApplySseSeqFilter(parsed) {
    if (!parsed || parsed.protocol === 'runtime_v2') return false;
    if (parsed.runtime_seq != null || parsed.runtimeSeq != null) return false;
    const type = String(parsed.type || '');
    if (type === 'context_trim_progress'
        || type === 'context_summary_progress'
        || type === 'key_context_progress'
        || type === 'context_trim_delta'
        || type === 'context_summary_delta'
        || type === 'key_context_delta'
        || type === 'context_trim_body'
        || type === 'context_summary_body'
        || type === 'key_context_body') return false;
    return true;
}

function endRunForClient(sessionId, ctx, opts) {
    opts = opts || {};
    var sid = String(sessionId || '');
    if (!sid) return;
    var allowFollowupDrain = opts.drainFollowup !== false
        && getRunAbortReason(sid, ctx) !== 'user';
    var preserveInterruptedPartial = !!(
        ctx && ctx.preserveInterruptedPartial && opts.discardPartialStreams
    );
    removeTemporaryStatus(ctx);
    if (!preserveInterruptedPartial) removeAbortedToolDraftRows(ctx, {});
    if (opts.discardPartialStreams && !preserveInterruptedPartial) {
        discardLlmStreamChunks(ctx, {});
        discardProgressStreamChunks(ctx);
    } else {
        finalizeLlmStreamChunks(ctx);
        finalizeProgressStreamChunks(ctx);
    }
    if (ctx) delete ctx.preserveInterruptedPartial;
    if (opts.reconcileFinal !== false) {
        scheduleFinalVisibleAfterRunIfEnabled(sid, ctx, { delayMs: opts.finalDelayMs != null ? opts.finalDelayMs : 80 });
    }
    sealProcessGroup(ctx);
    markSessionRunInactive(sid);
    resetStreamReconnectState(sid);
    if (getSessionRunState(sid)) {
        clearSessionRunStateIfMatch(sid, opts.runId || (ctx && ctx.runId));
    }
    syncSessionListIndicatorClasses();
    setSendButtonState();
    if (sid === currentSessionId) renderTodoPlanForCurrentSession();
    if (opts.syncFollowup !== false && typeof syncFollowupQueueFromServer === 'function') {
        // 终止边界必须先与服务端对账，再决定是否自动续发队首 pending。
        // 入队和普通同步本身都不具备发送权限。
        var followupSync = syncFollowupQueueFromServer(sid);
        if (allowFollowupDrain) {
            void Promise.resolve(followupSync).then(function () {
                scheduleFollowupQueueDrain(sid, opts.followupDelayMs || 0);
            }).catch(function (error) {
                // 未完成服务端对账时不能把“未知状态”当作发送许可。
                console.warn('follow-up reconciliation failed; auto-drain skipped', error);
            });
        }
    } else if (allowFollowupDrain) {
        scheduleFollowupQueueDrain(sid, opts.followupDelayMs || 0);
    }
    if (liveAutoFollow && opts.scroll !== false) {
        scrollProcessBodyToBottom(ctx, sid);
        scrollChatToBottomIfFollow(sid, {});
    }
}

async function readSseChunkWithIdleTimeout(reader, timeoutMs) {
    var timer = null;
    try {
        return await Promise.race([
            reader.read(),
            new Promise(function (_resolve, reject) {
                var armedAt = performance.now();
                var arm = function () {
                    timer = setTimeout(function () {
                        var elapsed = performance.now() - armedAt;
                        /* A heavily delayed timer means the browser/system was suspended.
                           Give the live stream another full idle window after resume. */
                        if (elapsed > timeoutMs + 15000) {
                            armedAt = performance.now();
                            arm();
                            return;
                        }
                        var err = new Error('SSE idle timeout after ' + String(timeoutMs) + 'ms');
                        err.name = 'SseIdleTimeout';
                        try { reader.cancel(err).catch(function () { /* ignore */ }); } catch (e) { /* ignore */ }
                        reject(err);
                    }, timeoutMs);
                };
                arm();
            }),
        ]);
    } finally {
        if (timer) clearTimeout(timer);
    }
}

async function consumeAgentSseResponse(response, runCtx, runSessionId, streamEventIdx) {
    if (!response || !response.body) throw new Error('stream response missing body');
    var ct0 = (response.headers && response.headers.get ? (response.headers.get('content-type') || '') : '').toLowerCase();
    if (!response.ok || ct0.indexOf('text/event-stream') < 0) {
        throw new Error('stream response failed: ' + (response.status || 'no status'));
    }
    if (runCtx) runCtx.streamConsuming = true;
    try {
        return await consumeAgentSseResponseInner(response, runCtx, runSessionId, streamEventIdx);
    } finally {
        if (runCtx) runCtx.streamConsuming = false;
    }
}

async function consumeAgentSseResponseInner(response, runCtx, runSessionId, streamEventIdx) {
    if (!response || !response.body) throw new Error('stream response missing body');
    var ct0 = (response.headers && response.headers.get ? (response.headers.get('content-type') || '') : '').toLowerCase();
    if (!response.ok || ct0.indexOf('text/event-stream') < 0) {
        throw new Error('stream response failed: ' + (response.status || 'no status'));
    }
    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = '';
    while (true) {
        const { done, value } = await readSseChunkWithIdleTimeout(reader, SSE_IDLE_TIMEOUT_MS);
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\\n');
        buffer = lines.pop();
        for (const line of lines) {
            if (line.startsWith(':')) continue;
            if (!line.startsWith('data: ')) continue;
            const data = line.slice(6);
            if (data === '[DONE]') {
                if (runCtx && runCtx.streamCompletedSuccessfully !== false) {
                    runCtx.streamCompletedSuccessfully = true;
                }
                endRunForClient(runSessionId, runCtx, { finalDelayMs: 80, followupDelayMs: 0 });
                return streamEventIdx;
            }
            try {
                let parsed = JSON.parse(data);
                if (parsed && (parsed.type === 'sse_keepalive' || parsed.keepalive === true)) continue;
                if (parsed && parsed.protocol === 'runtime_v2') {
                    const envelopeSessionId = parsed.session_id || parsed.sessionId || runSessionId;
                    if (!sessionStore.shouldAcceptSseEvent(envelopeSessionId, parsed.seq, 'runtime_v2')) continue;
                    if (parsed.skip_ui) {
                        applySkippedRuntimeV2EventMetadata(parsed, runCtx, envelopeSessionId);
                        continue;
                    }
                    const uiEvent = parsed.ui_event && typeof parsed.ui_event === 'object' ? parsed.ui_event : null;
                    if (!uiEvent) continue;
                    const runtimeSeq = parsed.runtime_seq || parsed.seq;
                    parsed = Object.assign({}, uiEvent, {
                        protocol: 'runtime_v2',
                        runtime_seq: runtimeSeq,
                        seq: parsed.seq,
                        session_id: uiEvent.session_id || envelopeSessionId,
                    });
                }
                const eventSessionId = parsed.session_id || parsed.sessionId || runSessionId;
                if (shouldApplySseSeqFilter(parsed)
                    && !sessionStore.shouldAcceptSseEvent(eventSessionId, parsed.seq, parsed.seq_scope || 'legacy')) continue;
                if (parsed.type === 'goal_state') {
                    const goal = parsed.goal && typeof parsed.goal === 'object' ? parsed.goal : parsed;
                    setGoalStateForSession(eventSessionId, goal);
                    continue;
                }
                if (parsed.type === 'user_steer' && parsed.steer) {
                    var steerOpId = String(parsed.client_id || parsed.steer_id || '');
                    var optimisticSteerRow = steerOpId ? findSteerProcessRow(runCtx, steerOpId) : null;
                    var reservedSteerIndex = !!(optimisticSteerRow && optimisticSteerRow.dataset.steerEventReserved === '1');
                    var steerEventIndex = reservedSteerIndex && Number.isFinite(Number(runCtx && runCtx.lastUserEventIndex))
                        ? Number(runCtx.lastUserEventIndex)
                        : (parsed.ephemeral && Number.isFinite(Number(parsed.seq)) ? Number(parsed.seq) : streamEventIdx);
                    try {
                        applyMessageEvent(eventSessionId, parsed, steerEventIndex, 'sse');
                    } catch (eStoreSteer) {
                        console.error('store user steer event failed:', eStoreSteer);
                    }
                    removeConsumedFollowupSteer(eventSessionId, parsed);
                    // 通过 operation-id（steer_id/client_id）提交已存在的乐观 pending 行，
                    // 而非再 appendLog 一条新行，避免 append 追问出现「一条灰色 pending + 一条 committed」。
                    // Optimistic append rows are keyed by client_id before the
                    // server steer id exists, so live commit must use the same
                    // priority to update that row instead of creating a second.
                    prepareSteerProcessBoundary(runCtx, parsed.steer_mode || 'interrupt', steerOpId);
                    markSteerEventPosition(runCtx, steerEventIndex, parsed.runtime_seq || parsed.runtimeSeq);
                    if (steerOpId && typeof appendSteerProcessMessage === 'function') {
                        var committedSteerRow = appendSteerProcessMessage(
                            eventSessionId, runCtx, parsed.content || '', steerOpId,
                            String(parsed.steer_mode || 'interrupt'), false
                        );
                        if (committedSteerRow) {
                            if (parsed.client_id) committedSteerRow.dataset.steerClientId = String(parsed.client_id);
                            if (parsed.steer_id) committedSteerRow.dataset.steerId = String(parsed.steer_id);
                            committedSteerRow.removeAttribute('data-steer-event-reserved');
                        }
                    } else {
                        appendLog(runCtx, parsed.content || '', 'user-steer', runSessionId);
                    }
                    if (!reservedSteerIndex) streamEventIdx += 1;
                    continue;
                }
                const reduced = applySessionEvent(parsed, {
                    sessionId: eventSessionId,
                    eventIndex: parsed.ephemeral && Number.isFinite(Number(parsed.seq)) ? Number(parsed.seq) : streamEventIdx,
                    source: 'sse',
                });
                if (reduced.runStateChanged) {
                    if (parsed.type === 'run_finished' || parsed.type === 'run_interrupted' || parsed.type === 'run_failed') {
                        if (runCtx) runCtx.streamCompletedSuccessfully = parsed.type === 'run_finished';
                        if (
                            runCtx
                            && (parsed.cleanup_scope === 'none' || parsed.checkpoint_ok === false)
                        ) {
                            runCtx.preserveInterruptedPartial = true;
                        }
                        endRunForClient(eventSessionId, runCtx, {
                            finalDelayMs: 80,
                            followupDelayMs: 0,
                            runId: parsed.run_id || parsed.runId || (runCtx && runCtx.runId),
                            reconcileFinal: parsed.type === 'run_finished',
                            discardPartialStreams: parsed.type !== 'run_finished',
                        });
                        streamEventIdx += 1;
                        continue;
                    }
                    syncSessionListIndicatorClasses();
                    continue;
                }
                if (reduced.contextStateChanged && eventSessionId === currentSessionId) {
                    if (parsed.type === 'context_tokens') applyContextTokenLabelForCurrentSession();
                    else if (parsed.type === 'todo_plan') renderTodoPlanForCurrentSession();
                    if (parsed.type === 'context_tokens' || parsed.type === 'todo_plan') continue;
                }
                if (parsed.ephemeral) {
                    /* 任何携带 agent_id 的 ephemeral 都属于子 agent；无论投递成功与否都不能 fall-through
                       到父 ctx 的 appendLlmStreamDelta，否则会污染主对话区。 */
                    if (parsed.agent_id) { handleSubagentStreamEvent(parsed, streamEventIdx, runSessionId); continue; }
                    if (parsed.type === 'llm_stream_aborted') {
                        removeTemporaryStatus(runCtx);
                        var preserveInterruptedPartial = parsed.cleanup_scope === 'none'
                            || parsed.checkpoint_ok === false;
                        if (runCtx) runCtx.preserveInterruptedPartial = preserveInterruptedPartial;
                        discardLlmStreamChunks(runCtx, parsed);
                        if (!preserveInterruptedPartial) {
                            removeAbortedToolDraftRows(runCtx, parsed);
                            discardProgressStreamChunks(runCtx);
                        } else {
                            finalizeProgressStreamChunks(runCtx);
                        }
                        continue;
                    }
                    if (parsed.type === 'tool_approval_required') {
                        finalizeLlmStreamChunks(runCtx);
                        var aidApr = parsed.approval_id != null ? String(parsed.approval_id) : '';
                        var ttlApr = parsed.title != null ? String(parsed.title) : '需要确认';
                        var msgApr = parsed.message != null ? String(parsed.message) : '';
                        var subApr = parsed.subtitle != null ? String(parsed.subtitle) : '';
                        var allowApr = false;
                        try {
                            allowApr = await openUiModal({
                                title: ttlApr,
                                subtitle: subApr,
                                message: msgApr,
                                danger: true,
                                confirmText: '允许执行',
                                cancelText: '拒绝',
                            });
                        } catch (eApr) {
                            allowApr = false;
                        }
                        try {
                            await fetch('/sessions/' + encodeURIComponent(runSessionId) + '/tool-approval', {
                                method: 'POST',
                                headers: { 'Content-Type': 'application/json' },
                                body: JSON.stringify({ approval_id: aidApr, approve: allowApr }),
                            });
                        } catch (errApr) {
                            console.error('tool-approval POST failed:', errApr);
                        }
                        continue;
                    }
                    if (parsed.type === 'tool_pending') {
                        appendToolPendingRow(runCtx, parsed, runSessionId);
                        continue;
                    }
                    if (parsed.type === 'tool_call_delta') {
                        appendToolCallDelta(runCtx, parsed, runSessionId);
                        continue;
                    }
                    if (parsed.type === 'tool_command_delta') {
                        appendToolCommandDelta(runCtx, parsed, runSessionId);
                        continue;
                    }
                    if (parsed.type === 'llm_reasoning_delta' || parsed.type === 'llm_response_delta') appendLlmStreamDelta(runCtx, parsed, runSessionId);
                    else if (parsed.type === 'context_summary_delta') appendProgressStreamDelta(runCtx, parsed.delta, 'context-summary', runSessionId);
                    else if (parsed.type === 'key_context_delta') appendKeyContextStreamDelta(runCtx, parsed.delta, runSessionId);
                    else if (parsed.type === 'context_tokens' && eventSessionId === currentSessionId) applyContextTokenLabelForCurrentSession();
                    else if (parsed.type === 'cache_stats' && eventSessionId === currentSessionId) applyCacheStatsFromEvent(runCtx, parsed, runSessionId);
                    else if (parsed.type === 'todo_plan' && runSessionId === currentSessionId) renderTodoPlanForCurrentSession();
                    else if (parsed.type === 'runtime_resumed') {
                        removeTemporaryStatus(runCtx);
                        var resumeSeconds = Math.max(0, Number(parsed.suspended_seconds || 0));
                        appendLog(
                            runCtx,
                            parsed.content || (
                                parsed.cause === 'system_sleep'
                                    ? ('检测到系统睡眠约 ' + Math.round(resumeSeconds) + ' 秒，任务已恢复')
                                    : ('检测到 Agent 进程暂停约 ' + Math.round(resumeSeconds) + ' 秒，任务已恢复')
                            ),
                            'status',
                            runSessionId
                        );
                    }
                    else if (parsed.type === 'status') {
                        var statusContent = String(parsed.content || '');
                        if (parsed.model_switch) {
                            appendModelSwitchStatus(runCtx, parsed, runSessionId);
                            continue;
                        }
                        var isTemporaryStatus = statusContent.indexOf('正在思考中...') >= 0;
                        isTemporaryStatus = isTemporaryStatus || !!parsed.ephemeral || statusContent.indexOf('正在重连') >= 0;
                        if (isTemporaryStatus) removeTemporaryStatus(runCtx);
                        var statusRow = appendLog(runCtx, statusContent, 'status', runSessionId);
                        if (isTemporaryStatus && statusRow) {
                            statusRow.dataset.temporaryStatus = '1';
                        }
                    }
                    continue;
                }
                if (parsed.agent_id) {
                    /* 非 ephemeral 子 agent 事件：必须走子 agent 通道，绝不能落到 renderEvent(runCtx,...) */
                    handleSubagentStreamEvent(parsed, streamEventIdx, runSessionId);
                    streamEventIdx += 1;
                    continue;
                }
                finalizeLlmStreamChunks(runCtx);
                if (parsed.type === 'tool_call') {
                    upsertToolCallResult(runCtx, parsed, runSessionId);
                    const completedTool = String(parsed.tool || parsed.tool_name || '');
                    if ((completedTool === 'create_goal' || completedTool === 'update_goal')
                        && eventSessionId === currentSessionId) {
                        void refreshGoalCard();
                    }
                    streamEventIdx += 1;
                    continue;
                }
                if (parsed.type === 'final') {
                    if (eventSessionId === runSessionId) markRunFinalSeen(runCtx);
                    var finalStream = runCtx && runCtx.stream && runCtx.stream.isConnected ? runCtx.stream : getVisibleChatStream();
                    var finalLastUserIdx = latestVisibleUserEventIndex(finalStream);
                    if (hasDuplicateVisibleFinal(finalStream, finalLastUserIdx, parsed.content)) {
                        streamEventIdx += 1;
                        continue;
                    }
                }
                renderMessageRecord(runCtx, reduced.messageRecord || {
                    index: streamEventIdx,
                    event: parsed,
                    source: 'sse',
                }, runSessionId);
                if (parsed.type === 'final' && eventSessionId === runSessionId) {
                    endRunForClient(runSessionId, runCtx, {
                        reconcileFinal: false,
                        followupDelayMs: 250,
                    });
                }
                streamEventIdx += 1;
            } catch (e) { console.error('解析事件失败:', e); }
        }
    }
    scheduleFinalVisibleAfterRunIfEnabled(runSessionId, runCtx, { delayMs: 120 });
    return streamEventIdx;
}

function latestVisibleUserEventIndex(stream) {
    var maxIdx = -1;
    if (!stream || !stream.querySelectorAll) return maxIdx;
    stream.querySelectorAll('.msg-wrap--user[data-event-index]').forEach(function (wrap) {
        var n = Number(wrap.getAttribute('data-event-index'));
        if (Number.isFinite(n)) maxIdx = Math.max(maxIdx, Math.floor(n));
    });
    return maxIdx;
}

function hasVisibleFinalAfterUser(stream, userEventIndex) {
    if (!stream || !stream.querySelectorAll) return false;
    var found = false;
    stream.querySelectorAll('.msg-wrap--assistant[data-event-index]').forEach(function (wrap) {
        if (found) return;
        var n = Number(wrap.getAttribute('data-event-index'));
        if (Number.isFinite(n) && Math.floor(n) > userEventIndex) found = true;
    });
    return found;
}

function hasDuplicateVisibleFinal(stream, userEventIndex, content) {
    if (!stream || !stream.querySelectorAll) return false;
    var expected = String(content || '').replace(/\\s+/g, ' ').trim();
    if (!expected) return false;
    var found = false;
    stream.querySelectorAll('.msg-wrap--assistant[data-event-index]').forEach(function (wrap) {
        if (found) return;
        var n = Number(wrap.getAttribute('data-event-index'));
        if (!Number.isFinite(n) || Math.floor(n) <= userEventIndex) return;
        var raw = messageRawMarkdown.get(wrap);
        var actual = String(raw != null ? raw : (wrap.textContent || '')).replace(/\\s+/g, ' ').trim();
        if (actual === expected) found = true;
    });
    return found;
}

function findStoredFinalAfterUser(sessionId, userEventIndex) {
    var events = [];
    try { events = selectMessageEvents(sessionId) || []; } catch (e) { events = []; }
    for (var i = events.length - 1; i >= 0; i -= 1) {
        var rec = events[i];
        if (!rec || rec.type !== 'final') continue;
        if (Number.isFinite(Number(rec.index)) && Number(rec.index) > userEventIndex) return rec;
    }
    return null;
}

function renderFinalRecordIfMissing(sessionId, ctx, stream, finalRecord, userEventIndex) {
    if (!finalRecord || !finalRecord.event || finalRecord.type !== 'final') return false;
    var content = finalRecord.event.content || '';
    if (hasVisibleFinalAfterUser(stream, userEventIndex)) return true;
    if (hasDuplicateVisibleFinal(stream, userEventIndex, content)) return true;
    var renderCtx = ctx || newDomContext(stream);
    renderCtx.stream = stream;
    renderCtx.lastUserEventIndex = Math.max(renderCtx.lastUserEventIndex || -1, userEventIndex);
    renderMessageRecord(renderCtx, finalRecord, sessionId);
    return hasVisibleFinalAfterUser(stream, userEventIndex);
}

async function ensureFinalVisibleAfterRunIfEnabled(sessionId, ctx, opts) {
    if (!isMyAgentFeatureEnabled('finalReconcile', true)) return false;
    return ensureFinalVisibleAfterRun(sessionId, ctx, opts);
}

function markRunFinalSeen(ctx) {
    if (ctx) ctx.seenFinal = true;
}

function initRunFinalTracking(ctx) {
    if (ctx) ctx.seenFinal = false;
}

function scheduleFinalVisibleAfterRunIfEnabled(sessionId, ctx, opts) {
    if (!isMyAgentFeatureEnabled('finalReconcile', true)) return;
    if (ctx && ctx.seenFinal === true) return;
    setTimeout(function () {
        if (ctx && ctx.seenFinal === true) return;
        ensureFinalVisibleAfterRun(sessionId, ctx, opts).catch(function (e) {
            console.error('final reconcile failed:', e);
        });
    }, 0);
}

async function ensureFinalVisibleAfterRun(sessionId, ctx, opts) {
    opts = opts || {};
    var sid = String(sessionId || '');
    if (!sid || sid !== currentSessionId) return false;
    var stream = (ctx && ctx.stream && ctx.stream.isConnected) ? ctx.stream : getVisibleChatStream();
    if (!stream) return false;
    var lastUserIdx = latestVisibleUserEventIndex(stream);
    if (hasVisibleFinalAfterUser(stream, lastUserIdx)) return true;
    var storedFinal = findStoredFinalAfterUser(sid, lastUserIdx);
    if (storedFinal) {
        if (renderFinalRecordIfMissing(sid, ctx, stream, storedFinal, lastUserIdx)) return true;
    }
    var delayMs = Math.max(0, Number(opts.delayMs) || 0);
    if (delayMs) await new Promise(function (resolve) { setTimeout(resolve, delayMs); });
    if (sid !== currentSessionId) return false;
    stream = getVisibleChatStream();
    if (!stream || hasVisibleFinalAfterUser(stream, lastUserIdx)) return true;
    return false;
}

async function startContinueAfterSubagents(sessionId, forcedMode) {
    if (!sessionId || sessionId !== currentSessionId) return;
    delete subagentContinueDismissedForSession[sessionId];
    if (isSessionRunning(sessionId) || subagentContinueInFlight) {
        updateSubagentContinueBanner(sessionId);
        return;
    }
    if (isSendPipelineLocked(sessionId)) {
        updateSubagentContinueBanner(sessionId);
        return;
    }
    hideSubagentContinueBanner();
    subagentContinueSessionId = sessionId;
    subagentContinueInFlight = true;
    var runCtx = null;
    var runSessionId = sessionId;
    var continuationFailed = false;
    try {
    if (typeof ensureLatestHistoryTailForLiveAppend === 'function') {
        var continuationTailReady = await ensureLatestHistoryTailForLiveAppend(sessionId);
        if (!continuationTailReady) {
            showUiAlert({
                title: '无法继续任务',
                message: '当前页面正在查看较早历史，且未能恢复最新历史尾部。请重试。',
                variant: 'error'
            });
            return;
        }
    }
    var banner = document.getElementById('subagent-continue-banner');
    var continueMode = forcedMode === 'react'
        ? 'react'
        : (banner && banner.dataset && banner.dataset.continueMode === 'react' ? 'react' : 'subagents');
    var continueUrl = continueMode === 'react'
        ? '/sessions/' + encodeURIComponent(sessionId) + '/continue' + (forcedMode === 'react' ? '?recovery=true' : '')
        : '/sessions/' + encodeURIComponent(sessionId) + '/continue-subagents';
        const response = await fetch(continueUrl, { method: 'POST' });
        if (response.status === 204) {
            hideSubagentContinueBanner();
            return;
        }
        if (response.status === 409) {
            updateSubagentContinueBanner(sessionId);
            return;
        }
        var ct = (response.headers.get('content-type') || '').toLowerCase();
        if (!response.ok || !response.body || ct.indexOf('text/event-stream') < 0) return;
        const preCount = await getUiEventCount(runSessionId, { preferCache: true });
        if (!getVisibleChatStream()) ensureVisibleChatStreamSlot();
        runCtx = newDomContext(getVisibleChatStream());
        if (sessionStore && typeof sessionStore.resetSseSeq === 'function') {
            sessionStore.resetSseSeq(runSessionId);
        }
        initRunFinalTracking(runCtx);
        runCtx.runStartedAt = new Date().toISOString();
        if (getSessionRunState(runSessionId) && getSessionRunState(runSessionId).ctx) {
            runCtx = getSessionRunState(runSessionId).ctx;
            initRunFinalTracking(runCtx);
            if (!runCtx.runStartedAt) runCtx.runStartedAt = new Date().toISOString();
        } else {
            runCtx.lastUserEventIndex = Math.max(0, preCount - 1);
            resetLlmState(runCtx);
            finalizeLlmStreamChunks(runCtx);
        }
        const ac = new AbortController();
        setSessionRunState(runSessionId, { controller: ac, ctx: runCtx });
        if (sessionStore && typeof sessionStore.resetSseSeq === 'function') {
            sessionStore.resetSseSeq(runSessionId);
        }
        setSendButtonState();
        syncSessionListIndicatorClasses();
        liveAutoFollow = true;
        streamProcNearBottom = true;
        scheduleContextTokensAfterPaint(runSessionId);
        let streamEventIdx = preCount;
        try {
            await consumeAgentSseResponse(response, runCtx, runSessionId, streamEventIdx);
        } catch (error) {
            if (error.name === 'AbortError') {
                if (getRunAbortReason(runSessionId, runCtx) === 'user') appendLog(runCtx, '任务已中断', 'status', runSessionId);
            }
            else {
                continuationFailed = true;
                console.error('续接 subagent 失败:', error);
                const msg = (error && error.message) ? String(error.message) : String(error);
                appendLog(runCtx, '续接失败: ' + msg, 'error-log', runSessionId);
            }
        } finally {
            finalizeLlmStreamChunks(runCtx);
            finalizeProgressStreamChunks(runCtx);
            if (runSessionId === currentSessionId
                && getRunAbortReason(runSessionId, runCtx) !== 'user'
                && !isServerStreamActive(runSessionId)) {
                scheduleFinalVisibleAfterRunIfEnabled(runSessionId, runCtx, { delayMs: 120 });
            }
            if (runSessionId === currentSessionId) renderTodoPlanForCurrentSession();
            if (liveAutoFollow) {
                scrollProcessBodyToBottom(runCtx, runSessionId);
                scrollChatToBottomIfFollow(runSessionId, {});
            }
            if (getSessionRunState(runSessionId)) clearSessionRunState(runSessionId);
            setSendButtonState();
            syncSessionListIndicatorClasses();
            void refreshSingleSessionRow(runSessionId);
            applyContextTokenLabelForCurrentSession();
            if (continuationFailed || isServerStreamActive(runSessionId)) {
                scheduleActiveSessionReconnect(runSessionId, { delayMs: 120, failure: continuationFailed });
            } else {
                resetStreamReconnectState(runSessionId);
            }
        }
        hideSubagentContinueBanner();
        if (!subagentContinueDismissedForSession[sessionId]) updateSubagentContinueBanner(sessionId);
    } finally {
        if (subagentContinueSessionId === runSessionId) subagentContinueSessionId = null;
        subagentContinueInFlight = false;
        var continuationStoppedByUser = !!runCtx && getRunAbortReason(runSessionId, runCtx) === 'user';
        if (!continuationStoppedByUser
            && getFollowupQueue(runSessionId).some(function (entry) { return entry && !entry.status; })) {
            var followupSync = syncFollowupQueueFromServer(runSessionId);
            void Promise.resolve(followupSync).then(function () {
                scheduleFollowupQueueDrain(runSessionId, 0);
            }).catch(function (error) {
                console.warn('follow-up reconciliation failed; auto-drain skipped', error);
            });
        }
    }
}

var autoResumeReactAttemptAt = Object.create(null);

function maybeAutoResumeInterruptedReact(sessionId, sessionDetail) {
    var sid = String(sessionId || '');
    var detail = sessionDetail || {};
    if (!sid || sid !== currentSessionId) return;
    if (typeof navigator !== 'undefined' && navigator.onLine === false) return;
    if (!detail.react_auto_resume || !detail.react_can_continue || detail.run_active || detail.stream_active) return;
    if (isSessionRunning(sid) || subagentContinueInFlight) return;
    var now = Date.now();
    if (now - Number(autoResumeReactAttemptAt[sid] || 0) < 30000) return;
    autoResumeReactAttemptAt[sid] = now;
    if (getVisibleChatStream()) {
        var ctx = newDomContext(getVisibleChatStream());
        appendLog(ctx, '检测到上次运行未完成，正在自动恢复任务…', 'status', sid);
    }
    void startContinueAfterSubagents(sid, 'react');
}

window.addEventListener('online', function () {
    var sid = String(currentSessionId || '');
    if (!sid) return;
    scheduleActiveSessionReconnect(sid, { delayMs: 100, reset: true });
    setTimeout(function () { void refreshSingleSessionRow(sid); }, 250);
});

function nowPipelineMs() {
    return (typeof performance !== 'undefined' && performance.now) ? performance.now() : Date.now();
}

function isClientPipelineTerminalStep(label, step) {
    var s = String(step || '');
    var l = String(label || '');
    if (l.indexOf('client_send_pipeline') >= 0) {
        return s === 'release_send_lock';
    }
    if (l.indexOf('client_followup') >= 0) {
        return s === 'followup_cancel_after_steer'
            || s === 'followup_restart_takeover'
            || s === 'followup_accepted_by_running_agent'
            || s === 'followup_steer_error'
            || s === 'followup_fallback_to_chat';
    }
    return /(?:final|finish|done|error|failed|cancel|release)$/i.test(s);
}

function flushClientPipelineTiming(ctx, finalStep) {
    if (!ctx || ctx._timingFlushed) return;
    var steps = ctx._timingSteps || {};
    var names = Object.keys(steps);
    if (!names.length) return;
    var now = nowPipelineMs();
    var label = String(ctx.label || 'client_pipeline_step_timing').replace(/_step_timing$/, '_timing');
    var payload = {
        label: label,
        session_id: ctx.sessionId || '',
        run_id: ctx.runId || '',
        mode: ctx.mode || '',
        total_ms: Math.max(0, Math.round(now - Number(ctx.startedAt || now))),
        final_step: finalStep || '',
        steps: steps
    };
    ctx._timingFlushed = true;
    try {
        var stepText = names.map(function (name) {
            return name + '=' + Math.max(0, Math.round(Number(steps[name] && steps[name].ms || 0))) + 'ms';
        }).join(' ');
        console.info(
            payload.label,
            'session=' + payload.session_id,
            'total=' + payload.total_ms + 'ms',
            'run_id=' + payload.run_id,
            'mode=' + payload.mode,
            stepText
        );
    } catch (e) { /* ignore */ }
    try {
        const body = JSON.stringify(payload);
        if (navigator && typeof navigator.sendBeacon === 'function') {
            const blob = new Blob([body], { type: 'application/json' });
            if (navigator.sendBeacon('/api/client_timing', blob)) return;
        }
        fetch('/api/client_timing', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: body,
            keepalive: true
        }).catch(function () { /* ignore */ });
    } catch (e) { /* ignore */ }
}

function reportClientPipelineStep(ctx, step, startedAt, extra) {
    if (!ctx || !step) return;
    const now = nowPipelineMs();
    var stepName = String(step || '');
    if (!ctx._timingSteps) ctx._timingSteps = {};
    ctx._timingSteps[stepName] = {
        ms: Math.max(0, Math.round(now - Number(startedAt || now))),
        since_start_ms: Math.max(0, Math.round(now - Number(ctx.startedAt || now))),
        extra: extra || {}
    };
    if (isClientPipelineTerminalStep(ctx.label, stepName)) flushClientPipelineTiming(ctx, stepName);
}

function applySkippedRuntimeV2EventMetadata(event, runCtx, sessionId) {
    if (!event || !event.skip_ui) return;
    const runtimeEvent = event.runtime_event && typeof event.runtime_event === 'object' ? event.runtime_event : null;
    if (!runtimeEvent || (runtimeEvent.type !== 'message_user' && runtimeEvent.type !== 'user_turn_committed')) return;
    const runtimeSeq = Number(event.runtime_seq || event.seq);
    if (!Number.isFinite(runtimeSeq) || runtimeSeq <= 0) return;
    if (runCtx) runCtx.lastUserRuntimeSeq = Math.floor(runtimeSeq);
    if (sessionId && sessionId !== currentSessionId) return;
    const eventIndex = runCtx && Number.isFinite(Number(runCtx.lastUserEventIndex))
        ? Math.floor(Number(runCtx.lastUserEventIndex))
        : NaN;
    let wrap = null;
    const stream = (runCtx && runCtx.stream) || getVisibleChatStream();
    if (stream && Number.isFinite(eventIndex)) {
        try {
            wrap = stream.querySelector('.msg-wrap--user[data-event-index="' + String(eventIndex) + '"]');
        } catch (e) { wrap = null; }
    }
    if (!wrap && stream) {
        const users = stream.querySelectorAll('.msg-wrap--user');
        wrap = users.length ? users[users.length - 1] : null;
    }
    if (wrap) {
        wrap.setAttribute('data-runtime-seq', String(Math.floor(runtimeSeq)));
    }
}

async function attachSessionEventStream(sessionId, opts) {
    opts = opts || {};
    if (!sessionId || getSessionRunState(sessionId)) return;
    if (!isServerStreamActive(sessionId)) return;
    var runSessionId = sessionId;
    var runCtx = null;
    var reattachFailed = false;
    try {
        if (runSessionId !== currentSessionId) return;
        if (!opts.skipInitialLoad) {
            await loadSessionMessages(runSessionId, 'saved-or-bottom', { preloadOlderIfShort: true });
            if (runSessionId !== currentSessionId) return;
        } else if (typeof ensureLatestHistoryTailForLiveAppend === 'function') {
            var attachTailReady = await ensureLatestHistoryTailForLiveAppend(runSessionId);
            if (!attachTailReady || runSessionId !== currentSessionId) return;
        }
        if (!getVisibleChatStream()) ensureVisibleChatStreamSlot();
        runCtx = newDomContext(getVisibleChatStream());
        var activeInfoForAttach = sessionStore.getActiveRunInfo(runSessionId) || {};
        runCtx.runStartedAt = activeInfoForAttach.started_at || new Date().toISOString();
        var existingProcessGroup = runCtx.stream.querySelector('.process-aggregate:last-of-type');
        if (existingProcessGroup) {
            runCtx.currentProcessGroup = existingProcessGroup;
            existingProcessGroup.classList.add('is-running');
            bindProcessAggregate(existingProcessGroup);
            var activeInfo = sessionStore.getActiveRunInfo(runSessionId) || {};
            if (activeInfo.started_at) {
                applyRunStartedAtToProcessGroup(existingProcessGroup, activeInfo.started_at);
            } else if (!existingProcessGroup.dataset.procStartedAt && !existingProcessGroup.dataset.procDurationMs) {
                existingProcessGroup.dataset.procStartedAt = String(procNow());
                refreshProcessAggregateStats(existingProcessGroup);
            }
            existingProcessGroup.classList.remove('is-collapsed');
            var top = existingProcessGroup.querySelector('.process-aggregate-top');
            if (top) top.setAttribute('aria-expanded', 'true');
        }
        resetLlmState(runCtx);
        initRunFinalTracking(runCtx);
        finalizeLlmStreamChunks(runCtx);
        const ac = new AbortController();
        setSessionRunState(runSessionId, { controller: ac, ctx: runCtx, reattached: true });
        setSendButtonState();
        syncSessionListIndicatorClasses();
        liveAutoFollow = true;
        streamProcNearBottom = true;
        const preCount = await getUiEventCount(runSessionId, { preferCache: true });
        const streamUrl = '/sessions/' + encodeURIComponent(runSessionId)
            + '/stream?after_index=' + encodeURIComponent(String(preCount - 1));
        const response = await fetch(streamUrl, { signal: ac.signal });
        await consumeAgentSseResponse(response, runCtx, runSessionId, preCount);
    } catch (error) {
        if (error && error.name === 'AbortError') return;
        reattachFailed = true;
        console.error('reattach stream failed:', error);
        const msg = (error && error.message) ? String(error.message) : String(error);
        if (runCtx && runSessionId === currentSessionId) appendLog(runCtx, '恢复实时流失败: ' + msg, 'error-log', runSessionId);
    } finally {
        if (runCtx) {
            finalizeLlmStreamChunks(runCtx);
            finalizeProgressStreamChunks(runCtx);
        }
        if (runSessionId === currentSessionId
            && getRunAbortReason(runSessionId, runCtx) !== 'user'
            && !isServerStreamActive(runSessionId)) {
            scheduleFinalVisibleAfterRunIfEnabled(runSessionId, runCtx, { delayMs: 120 });
        }
        if (getSessionRunState(runSessionId) && getSessionRunState(runSessionId).reattached) {
            clearSessionRunState(runSessionId);
        }
        setSendButtonState();
        syncSessionListIndicatorClasses();
        void refreshSingleSessionRow(runSessionId);
        setTimeout(function () { reconcileRunStateFromServer({ silent: true }); }, 800);
        if (reattachFailed) {
            scheduleActiveSessionReconnect(runSessionId, { delayMs: 120, failure: true });
        } else if (isServerStreamActive(runSessionId)) {
            scheduleActiveSessionReconnect(runSessionId, { delayMs: 1200 });
        } else {
            resetStreamReconnectState(runSessionId);
        }
        applyContextTokenLabelForCurrentSession();
        if (runSessionId === currentSessionId) {
            clearSessionUnreadState(runSessionId);
            updateSubagentContinueBanner(runSessionId);
        }
    }
}

function scheduleActiveSessionReconnect(sessionId, opts) {
    if (!isMyAgentFeatureEnabled('streamReconnect', true)) return;
    opts = opts || {};
    var sid = String(sessionId || '');
    if (!sid) return;
    if (opts.reset) resetStreamReconnectState(sid);
    if (isStreamConsuming(sid)) {
        resetStreamReconnectState(sid);
        return;
    }
    var state = streamReconnectState(sid);
    if (state.timer) return;
    if (state.exhausted || state.attempts >= STREAM_RECONNECT_MAX_ATTEMPTS) {
        if (!state.exhausted) {
            state.exhausted = true;
            reportStreamReconnectExhausted(sid);
        }
        return;
    }
    var countFailure = !!opts.failure;
    var baseDelay = Math.max(0, Number(opts.delayMs) || 0);
    var delayMs = Math.max(
        baseDelay,
        Math.min(STREAM_RECONNECT_MAX_DELAY_MS, STREAM_RECONNECT_BASE_DELAY_MS * Math.pow(2, state.attempts))
    );
    state.timer = setTimeout(async function () {
        state.timer = null;
        if (sid !== currentSessionId) return;
        if (countFailure) state.attempts += 1;
        try {
            if (typeof reconcileRunStateFromServer === 'function') {
                await reconcileRunStateFromServer({ silent: true });
            }
            if (sid !== currentSessionId) return;
            if (isStreamConsuming(sid)) {
                resetStreamReconnectState(sid);
                return;
            }
            if ((isServerStreamActive(sid) || isSessionRunning(sid)) && typeof maybeStartStreamPollForSession === 'function') {
                maybeStartStreamPollForSession(sid, { skipInitialLoad: true });
            } else {
                resetStreamReconnectState(sid);
            }
        } catch (e) {
            scheduleActiveSessionReconnect(sid, { failure: countFailure });
        }
    }, delayMs);
}

async function processRewriteTruncateAsync(pr) {
    try {
        const anchor = document.querySelector('.msg-wrap--user[data-truncate-from="' + String(pr.before) + '"]');
        const res = await truncateSessionOnServer(pr.before, {
            sessionId: pr.sessionId,
            beforeSeq: pr.beforeSeq,
            backup: false
        });
        if (!res || !res.ok) {
            showUiAlert({
                title: '截断失败',
                message: describeServerSyncFailure(res, '无法同步服务器，改写未生效。'),
                variant: 'error'
            });
            return false;
        }
        if (currentSessionId === pr.sessionId) {
            if (anchor) {
                if (activeInlineRewriteWrap === anchor) activeInlineRewriteWrap = null;
            }
        }
        applyClientHistoryTruncate(pr.sessionId, pr.before, anchor);
        return true;
    } catch (error) {
        console.error('异步截断失败:', error);
        showUiAlert({
            title: '截断失败',
            message: describeServerSyncFailure({ error: (error && error.message) || String(error) }, '无法同步服务器，改写未生效。'),
            variant: 'error'
        });
        return false;
    }
}

function getFollowupQueue(sessionId) {
    const sid = String(sessionId || '');
    if (!sid) return [];
    if (!followupQueueLoadedBySession[sid]) {
        followupQueueBySession[sid] = readStoredFollowupQueue(sid);
        followupQueueLoadedBySession[sid] = true;
    }
    if (!followupQueueBySession[sid]) followupQueueBySession[sid] = [];
    return followupQueueBySession[sid];
}

function followupQueueStorageKey(sessionId) {
    return LS_FOLLOWUP_QUEUE_PREFIX + String(sessionId || '');
}

function defaultSteerMode() {
    return String(window.__MYAGENT_STEER_MODE__ || 'append').toLowerCase() === 'interrupt'
        ? 'interrupt'
        : 'append';
}

function normalizeStoredFollowupItem(item) {
    if (!item || typeof item !== 'object') return null;
    var text = String(item.text || '').trim();
    if (!text) return null;
    var display = String(item.display || item.text || '').trim();
    var skills = Array.isArray(item.skills)
        ? item.skills.map(function (skill) { return String(skill || '').trim(); }).filter(Boolean)
        : [];
    var restoredStatus = String(item.status || '');
    if (restoredStatus === 'submitting' || restoredStatus === 'sending') restoredStatus = '';
    // A browser reload cannot resume the in-flight DELETE request. If the
    // durable steer id is known, reconcile it as accepted; otherwise restore a
    // normal pending row so the user never gets a permanently disabled item.
    if (restoredStatus === 'withdrawing') {
        restoredStatus = String(item.steerId || '') ? 'accepted' : '';
    }
    return {
        id: item.id || ('stored-followup-' + (followupQueueSeq++)),
        text: text,
        display: display || text,
        skills: skills,
        createdAt: Number(item.createdAt) || Date.now(),
        order: Number.isFinite(Number(item.order)) ? Number(item.order) : undefined,
        steerMode: String(item.steerMode || item.mode || defaultSteerMode()) === 'interrupt' ? 'interrupt' : 'append',
        // 恢复提交期间的 in-flight 状态：刷新/崩溃后可继续恢复，不再静默丢失。
        clientId: String(item.clientId || ''),
        steerId: String(item.steerId || ''),
        status: restoredStatus,
        replacementRunId: String(item.replacementRunId || ''),
        awaitingRunEnd: item.awaitingRunEnd !== false,
    };
}

function readStoredFollowupQueue(sessionId) {
    try {
        var raw = localStorage.getItem(followupQueueStorageKey(sessionId));
        if (!raw) return [];
        var arr = JSON.parse(raw);
        if (!Array.isArray(arr)) return [];
        var out = arr.map(normalizeStoredFollowupItem).filter(Boolean);
        out.forEach(function (item) {
            var n = Number(item.id);
            if (Number.isFinite(n)) followupQueueSeq = Math.max(followupQueueSeq, Math.floor(n) + 1);
        });
        return out;
    } catch (e) {
        return [];
    }
}

function persistFollowupQueue(sessionId) {
    const sid = String(sessionId || '');
    if (!sid) return;
    var q = followupQueueBySession[sid] || [];
    // 持久化所有非终态条目：包括 submitting/sending/accepted/restarting，
    // 这样刷新/崩溃/请求未达服务端时仍可恢复。只有 'sent'（/chat 已成功开跑）
    // 视为本地终态不再持久化；consumed/cancelled 由 takeFollowupItem 直接移除。
    var pending = q.filter(function (item) {
        var status = item && item.status ? String(item.status) : '';
        return item && item.text && status !== 'sent';
    }).map(function (item) {
        return {
            id: item.id,
            text: item.text,
            display: item.display || item.text,
            skills: Array.isArray(item.skills) ? item.skills : [],
            createdAt: item.createdAt || Date.now(),
            order: item.order,
            steerMode: item.steerMode === 'append' ? 'append' : 'interrupt',
            clientId: item.clientId || '',
            steerId: item.steerId || '',
            status: item.status || '',
            replacementRunId: item.replacementRunId || '',
            awaitingRunEnd: item.awaitingRunEnd !== false,
        };
    });
    try {
        var key = followupQueueStorageKey(sid);
        if (pending.length) localStorage.setItem(key, JSON.stringify(pending));
        else localStorage.removeItem(key);
    } catch (e) { /* ignore */ }
}

function removeStoredFollowupQueue(sessionId) {
    const sid = String(sessionId || '');
    if (!sid) return;
    delete followupQueueBySession[sid];
    delete followupQueueLoadedBySession[sid];
    delete followupManualDispatchEpochBySession[sid];
    try { localStorage.removeItem(followupQueueStorageKey(sid)); } catch (e) { /* ignore */ }
}

function inputHasSendableText() {
    if (!messageInput) return false;
    return String(messageInput.value || '').replace(/[\\u200B-\\u200D\\uFEFF]/g, '').trim().length > 0;
}

var followupDragState = null;
var FOLLOWUP_DRAG_TOUCH_THRESHOLD = 8;

function startFollowupDrag(sessionId, item, row, ev) {
    if (!item || item.status) return;
    if (followupDragState && followupDragState.mode === 'touch') {
        if (ev && ev.preventDefault) ev.preventDefault();
        return;
    }
    followupDragState = {
        sid: String(sessionId || ''),
        itemId: String(item.id),
        row: row,
        mode: 'html5',
    };
    if (row && row.classList) row.classList.add('is-dragging');
    if (ev && ev.dataTransfer) {
        ev.dataTransfer.effectAllowed = 'move';
        try { ev.dataTransfer.setData('text/plain', String(item.id)); } catch (e) { /* ignore */ }
    }
}

function clearFollowupDragIndicators(panel) {
    if (!panel) return;
    var rows = panel.querySelectorAll('.followup-queue-row');
    for (var i = 0; i < rows.length; i += 1) {
        rows[i].classList.remove('is-drag-over-before');
        rows[i].classList.remove('is-drag-over-after');
    }
}

function endFollowupDrag() {
    if (!followupDragState) return;
    if (followupDragState.row && followupDragState.row.classList) {
        followupDragState.row.classList.remove('is-dragging');
    }
    followupDragState = null;
    clearFollowupDragIndicators(document.getElementById('followup-queue-panel'));
}

function startFollowupTouchDrag(sessionId, item, row, ev) {
    if (!item || item.status) return;
    if (followupDragState) endFollowupDrag();
    followupDragState = {
        sid: String(sessionId || ''),
        itemId: String(item.id),
        row: row,
        mode: 'touch',
        pointerId: ev.pointerId,
        active: false,
        startX: ev.clientX,
        startY: ev.clientY,
        targetRow: null,
        after: false,
    };
    try {
        if (ev.currentTarget && ev.currentTarget.setPointerCapture) {
            ev.currentTarget.setPointerCapture(ev.pointerId);
        }
    } catch (e) { /* ignore */ }
    if (ev.preventDefault) ev.preventDefault();
}

function autoScrollFollowupQueuePanel(panel, clientY) {
    if (!panel || panel.scrollHeight <= panel.clientHeight) return;
    var rect = panel.getBoundingClientRect();
    var zone = 28;
    if (clientY < rect.top + zone) panel.scrollTop -= 10;
    else if (clientY > rect.bottom - zone) panel.scrollTop += 10;
}

function onFollowupTouchDragMove(ev) {
    var state = followupDragState;
    if (!state || state.mode !== 'touch' || state.pointerId !== ev.pointerId) return;
    if (!state.active) {
        var dx = ev.clientX - state.startX;
        var dy = ev.clientY - state.startY;
        if (Math.abs(dx) < FOLLOWUP_DRAG_TOUCH_THRESHOLD && Math.abs(dy) < FOLLOWUP_DRAG_TOUCH_THRESHOLD) return;
        state.active = true;
        if (state.row && state.row.classList) state.row.classList.add('is-dragging');
    }
    if (ev.preventDefault) ev.preventDefault();
    var panel = document.getElementById('followup-queue-panel');
    if (!panel) return;
    autoScrollFollowupQueuePanel(panel, ev.clientY);
    var el = document.elementFromPoint ? document.elementFromPoint(ev.clientX, ev.clientY) : null;
    var target = el && el.closest ? el.closest('.followup-queue-row') : null;
    if (!target || !target.dataset || !target.dataset.id
        || target.dataset.reorderable !== 'true' || target === state.row) {
        clearFollowupDragIndicators(panel);
        state.targetRow = null;
        return;
    }
    var rect = target.getBoundingClientRect();
    var after = ev.clientY > rect.top + rect.height / 2;
    clearFollowupDragIndicators(panel);
    target.classList.add(after ? 'is-drag-over-after' : 'is-drag-over-before');
    state.targetRow = target;
    state.after = after;
}

function onFollowupTouchDragEnd(ev) {
    var state = followupDragState;
    if (!state || state.mode !== 'touch' || state.pointerId !== ev.pointerId) return;
    var target = state.targetRow;
    var after = state.after;
    var sid = state.sid;
    var itemId = state.itemId;
    var active = state.active;
    endFollowupDrag();
    if (active && target && target.dataset && target.dataset.id) {
        moveFollowupQueueItem(sid, itemId, target.dataset.id, after ? 'after' : 'before');
    }
}

function ensureFollowupQueueHost() {
    var existing = document.getElementById('followup-queue-panel');
    if (existing) return existing;
    var panel = document.createElement('div');
    panel.id = 'followup-queue-panel';
    panel.className = 'followup-queue-panel';
    panel.setAttribute('aria-live', 'polite');
    if (!panel.dataset.dragReady) {
        panel.dataset.dragReady = '1';
        panel.addEventListener('dragover', function (e) {
            if (!followupDragState) return;
            var target = e.target && e.target.closest ? e.target.closest('.followup-queue-row') : null;
            if (!target || !target.dataset || !target.dataset.id
                || target.dataset.reorderable !== 'true' || target === followupDragState.row) {
                clearFollowupDragIndicators(panel);
                if (e.dataTransfer) e.dataTransfer.dropEffect = 'none';
                return;
            }
            e.preventDefault();
            if (e.dataTransfer) e.dataTransfer.dropEffect = 'move';
            var rect = target.getBoundingClientRect();
            var after = e.clientY > rect.top + rect.height / 2;
            clearFollowupDragIndicators(panel);
            target.classList.add(after ? 'is-drag-over-after' : 'is-drag-over-before');
        });
        panel.addEventListener('drop', function (e) {
            if (!followupDragState) return;
            e.preventDefault();
            var target = e.target && e.target.closest ? e.target.closest('.followup-queue-row') : null;
            if (!target || !target.dataset || !target.dataset.id
                || target.dataset.reorderable !== 'true' || target === followupDragState.row) return;
            var after = target.classList.contains('is-drag-over-after');
            var sid = followupDragState.sid;
            var itemId = followupDragState.itemId;
            endFollowupDrag();
            moveFollowupQueueItem(sid, itemId, target.dataset.id, after ? 'after' : 'before');
        });
    }
    var anchor = messageInput && messageInput.closest ? messageInput.closest('.composer-row') : null;
    var host = anchor && anchor.parentNode ? anchor.parentNode : null;
    if (host && anchor) host.insertBefore(panel, anchor);
    else document.body.appendChild(panel);
    return panel;
}

function positionFollowupQueuePanel() {
    var panel = document.getElementById('followup-queue-panel');
    if (!panel) return;
    panel.style.left = '';
    panel.style.top = '';
    panel.style.width = '';
}

function renderFollowupQueue(sessionId) {
    var sid = String(sessionId != null ? sessionId : (currentSessionId || ''));
    var panel = ensureFollowupQueueHost();
    if (!panel) return;
    if (!sid || sid !== currentSessionId) {
        if (!currentSessionId) {
            panel.innerHTML = '';
            panel.classList.remove('is-visible');
            panel.removeAttribute('data-session-id');
        }
        return;
    }
    var q = getFollowupQueue(sid);
    syncMessageInputPlaceholder();
    panel.innerHTML = '';
    panel.dataset.sessionId = sid;
    panel.classList.toggle('is-visible', !!q.length);
    if (!q.length) {
        positionFollowupQueuePanel();
        return;
    }
    q.forEach(function (item, idx) {
        if (item && ['submitting', 'sending', 'accepted', 'restarting'].includes(String(item.status || ''))) {
            scheduleAcceptedFollowupWatch(sid, item.id);
        }
        var row = document.createElement('div');
        row.className = 'followup-queue-row';
        row.classList.toggle('is-sending', item.status === 'sending' || item.status === 'submitting');
        row.classList.toggle('is-accepted', item.status === 'accepted');
        row.classList.toggle('is-sent', item.status === 'sent');
        row.dataset.id = String(item.id);
        row.dataset.reorderable = item.status ? 'false' : 'true';
        var dragHandle = document.createElement('div');
        dragHandle.className = 'followup-queue-drag';
        dragHandle.textContent = '⠿';
        dragHandle.setAttribute('title', '拖拽调整顺序');
        dragHandle.draggable = !item.status;
        dragHandle.classList.toggle('is-disabled', !!item.status);
        dragHandle.addEventListener('dragstart', function (ev) {
            startFollowupDrag(sid, item, row, ev);
        });
        dragHandle.addEventListener('dragend', endFollowupDrag);
        dragHandle.addEventListener('pointerdown', function (ev) {
            if (ev.pointerType === 'touch' || ev.pointerType === 'pen') {
                startFollowupTouchDrag(sid, item, row, ev);
            }
        });
        dragHandle.addEventListener('pointermove', onFollowupTouchDragMove);
        dragHandle.addEventListener('pointerup', onFollowupTouchDragEnd);
        dragHandle.addEventListener('pointercancel', endFollowupDrag);
        var order = document.createElement('div');
        order.className = 'followup-queue-order';
        order.textContent = String(idx + 1);
        var text = document.createElement('div');
        text.className = 'followup-queue-text';
        var itemSkills = Array.isArray(item.skills) ? item.skills : [];
        var itemDisplay = String(item.display || item.text || '');
        var itemDetail = itemDisplay + (itemSkills.length ? ('\\n\\nSkill: ' + itemSkills.join('、')) : '');
        text.textContent = itemDisplay + (itemSkills.length ? ('  · Skill: ' + itemSkills.join('、')) : '');
        text.setAttribute('data-ui-tip', itemDetail);
        var status = document.createElement('div');
        status.className = 'followup-queue-status';
        status.textContent = getFollowupStatusText(item);
        var sendNow = document.createElement('button');
        sendNow.type = 'button';
        sendNow.className = 'followup-queue-action followup-queue-send';
        sendNow.textContent = '立即发送';
        sendNow.disabled = !!item.status;
        var modeSelect = document.createElement('select');
        modeSelect.className = 'followup-queue-mode';
        modeSelect.setAttribute('aria-label', '追问发送模式');
        var interruptOption = document.createElement('option');
        interruptOption.value = 'interrupt';
        interruptOption.textContent = '打断';
        var appendOption = document.createElement('option');
        appendOption.value = 'append';
        appendOption.textContent = '追加';
        modeSelect.appendChild(interruptOption);
        modeSelect.appendChild(appendOption);
        modeSelect.value = item.steerMode === 'append' ? 'append' : 'interrupt';
        modeSelect.disabled = !!item.status;
        var undo = document.createElement('button');
        undo.type = 'button';
        undo.className = 'followup-queue-action followup-queue-undo';
        undo.textContent = '撤回';
        undo.disabled = item.status === 'sent' || item.status === 'withdrawing';
        sendNow.addEventListener('click', function (ev) {
            ev.preventDefault();
            void sendFollowupNow(String(item.id), sid, { manual: true });
        });
        modeSelect.addEventListener('change', function () {
            item.steerMode = modeSelect.value === 'append' ? 'append' : 'interrupt';
            persistFollowupQueue(sid);
        });
        undo.addEventListener('click', function (ev) {
            ev.preventDefault();
            withdrawFollowup(String(item.id));
        });
        row.appendChild(dragHandle);
        row.appendChild(order);
        row.appendChild(text);
        row.appendChild(status);
        row.appendChild(modeSelect);
        row.appendChild(sendNow);
        row.appendChild(undo);
        panel.appendChild(row);
        if (typeof initUiHoverTips === 'function') initUiHoverTips(row);
    });
    positionFollowupQueuePanel();
    if (typeof scrollChatToBottomIfFollow === 'function') {
        scrollChatToBottomIfFollow(sid, {});
    }
}

function getFollowupStatusText(item) {
    var status = item && item.status ? String(item.status) : '';
    if (status === 'withdrawing') return '撤回中';
    if (status === 'submitting') return '提交中';
    if (status === 'accepted') return item && item.steerMode === 'append' ? '已追加，等待下一轮' : '已接收，等待插入';
    if (status === 'restarting') return '正在接管当前任务';
    if (status === 'sending') return '发送中';
    if (status === 'sent') return '已发送';
    return '待发送';
}

function appendFollowupQueueItem(sessionId, text, display, selectedSkills) {
    const sid = String(sessionId || '');
    if (!sid || !String(text || '').trim()) return null;
    const item = {
        id: followupQueueSeq++,
        text: String(text),
        display: String(display || text),
        skills: Array.isArray(selectedSkills) ? selectedSkills.slice() : [],
        createdAt: Date.now(),
        steerMode: defaultSteerMode(),
        awaitingRunEnd: isSessionRunning(sid) || isServerStreamActive(sid),
    };
    getFollowupQueue(sid).push(item);
    persistFollowupQueue(sid);
    renderFollowupQueue(sid);
    setSendButtonState();
    return item;
}

function buildSelectedSkillsDisplayMessage(rawMessage, selectedSkills) {
    var message = String(rawMessage || '');
    var names = Array.isArray(selectedSkills)
        ? selectedSkills.map(function (skill) { return String(skill || '').trim(); }).filter(Boolean)
        : [];
    if (!names.length) return message;
    var suffix = '\\n\\nActivated Skill: ' + names.join(', ');
    return message.endsWith(suffix) ? message : message + suffix;
}

function enqueueCurrentInputAsFollowup() {
    if (!isMyAgentFeatureEnabled('followupRestart', false)) return false;
    if (isChatFileUploadBusy()) return false;
    const sid = currentSessionId;
    if (!sid) return false;
    rewriteInputWorkspacePaths();
    const visibleMessage = messageInput.value;
    const rawMessage = expandInputPathTokens(visibleMessage);
    if (!String(rawMessage).trim()) return false;
    var selectedSkills = [];
    if (typeof window.consumeSelectedSkillsForSend === 'function') {
        selectedSkills = window.consumeSelectedSkillsForSend();
    }
    appendFollowupQueueItem(sid, rawMessage, visibleMessage, selectedSkills);
    messageInput.value = '';
    persistInputDraft(sid, '');
    clearInputPathTokens();
    autoResizeTextarea();
    // appendFollowupQueueItem() refreshed the button while the composer still
    // contained the follow-up. Refresh again after clearing it so the active
    // run exposes "Stop", rather than leaving a stale "Follow up" label.
    setSendButtonState();
    return true;
}

function rollbackOptimisticUserEvent(sessionId, eventIndex) {
    const sid = String(sessionId || '');
    const before = Math.max(0, Number(eventIndex) || 0);
    if (!sid) return;
    if (typeof truncateMessageStateForSession === 'function') {
        truncateMessageStateForSession(sid, before);
    }
    if (typeof uiEventCountCache !== 'undefined') {
        uiEventCountCache.updateFromServer(sid, before);
    }
    if (typeof truncateTocTurnsForSession === 'function') {
        truncateTocTurnsForSession(sid, before);
    }
    if (sid !== currentSessionId) return;
    const anchor = document.querySelector('.msg-wrap--user[data-event-index="' + String(before) + '"]');
    if (anchor) removeMessagesFromNode(anchor);
    rebuildToc({ localOnly: true });
}

function takeFollowupItem(sessionId, itemId) {
    var q = getFollowupQueue(sessionId);
    var idx = q.findIndex(function (item) { return String(item.id) === String(itemId); });
    if (idx < 0) return null;
    var item = q.splice(idx, 1)[0] || null;
    persistFollowupQueue(sessionId);
    return item;
}

function moveFollowupQueueItem(sessionId, itemId, targetId, placement) {
    var sid = String(sessionId || '');
    var q = getFollowupQueue(sid);
    var from = q.findIndex(function (item) { return item && String(item.id) === String(itemId); });
    var to = q.findIndex(function (item) { return item && String(item.id) === String(targetId); });
    if (from < 0 || to < 0 || from === to) return false;
    if (q[from].status || q[to].status) return false;

    // Reorder only the pending slots.  In-flight rows remain at their exact
    // array indexes while pending rows move around them.
    var pendingIndexes = [];
    var pendingItems = [];
    q.forEach(function (entry, idx) {
        if (entry && !entry.status) {
            pendingIndexes.push(idx);
            pendingItems.push(entry);
        }
    });
    var pendingFrom = pendingItems.findIndex(function (entry) { return String(entry.id) === String(itemId); });
    var pendingTo = pendingItems.findIndex(function (entry) { return String(entry.id) === String(targetId); });
    if (pendingFrom < 0 || pendingTo < 0 || pendingFrom === pendingTo) return false;
    var item = pendingItems.splice(pendingFrom, 1)[0];
    var insertAt = pendingTo;
    if (pendingFrom < pendingTo) {
        insertAt = pendingTo - 1;
        if (placement === 'after') insertAt = pendingTo;
    } else if (placement === 'after') {
        insertAt = pendingTo + 1;
    }
    pendingItems.splice(insertAt, 0, item);
    pendingIndexes.forEach(function (queueIndex, idx) {
        q[queueIndex] = pendingItems[idx];
    });
    q.forEach(function (entry, idx) {
        if (entry) entry.order = idx;
    });
    persistFollowupQueue(sid);
    renderFollowupQueue(sid);
    return true;
}

function withdrawFollowup(itemId) {
    const sid = currentSessionId;
    var q = getFollowupQueue(sid);
    var pendingItem = q.find(function (entry) { return String(entry.id) === String(itemId); });
    if (pendingItem && (pendingItem.status === 'sending' || pendingItem.status === 'submitting' || pendingItem.status === 'accepted' || pendingItem.status === 'restarting')) {
        pendingItem.cancelRequested = true;
        pendingItem.status = 'withdrawing';
        persistFollowupQueue(sid);
        renderFollowupQueue(sid);
        if (pendingItem.steerInFlight && !pendingItem.steerId) return;
        cancelSteerMessage(sid, pendingItem).then(function () {
            var item = takeFollowupItem(sid, itemId);
            if (item) returnFollowupToInput(sid, item);
        }).catch(function (e) {
            var item = q.find(function (entry) { return String(entry.id) === String(itemId); });
            if (item) item.status = 'sending';
            persistFollowupQueue(sid);
            renderFollowupQueue(sid);
            appendLogVisible('追问已被接收，无法撤回: ' + ((e && e.message) || String(e)), 'error-log');
        });
        return;
    }
    const item = takeFollowupItem(sid, itemId);
    if (!item) return;
    returnFollowupToInput(sid, item);
}

function returnFollowupToInput(sid, item) {
    removePendingSteerFromProcess(sid, item);
    const returned = String(item.display || item.text || '');
    if (sid !== currentSessionId) {
        const backgroundDraft = Object.prototype.hasOwnProperty.call(draftBySession, sid)
            ? String(draftBySession[sid] || '')
            : String(readStoredInputDraft(sid) || '');
        const nextDraft = backgroundDraft.trim() ? (returned + '\\n' + backgroundDraft) : returned;
        persistInputDraft(sid, nextDraft);
        if (typeof window.setSelectedSkillsForSession === 'function') {
            window.setSelectedSkillsForSession(sid, item.skills || []);
        }
        renderFollowupQueue(sid);
        return;
    }
    const existing = String(messageInput.value || '');
    messageInput.value = existing.trim() ? (returned + '\\n' + existing) : returned;
    if (typeof window.setSelectedSkillsForCurrentSession === 'function') {
        window.setSelectedSkillsForCurrentSession(item.skills || []);
    }
    rewriteInputWorkspacePaths();
    persistInputDraft(sid, messageInput.value);
    autoResizeTextarea();
    renderFollowupQueue(sid);
    setSendButtonState();
    messageInput.focus();
}

function findSteerProcessRow(ctx, operationId) {
    var key = String(operationId || '');
    if (!ctx || !key || typeof getProcessBody !== 'function') return null;
    var body = getProcessBody(ctx);
    if (!body || !body.querySelectorAll) return null;
    var rows = body.querySelectorAll('.feed-item[data-steer-operation-id]');
    for (var i = 0; i < rows.length; i += 1) {
        if (String(rows[i].dataset.steerOperationId || '') === key
            || String(rows[i].dataset.steerClientId || '') === key
            || String(rows[i].dataset.steerId || '') === key) return rows[i];
    }
    return null;
}

function commitPendingSteerProcessRow(sessionId, item, serverItem) {
    var sid = String(sessionId || '');
    if (!sid || !item) return null;
    var run = getSessionRunState(sid);
    var ctx = run && run.ctx;
    var row = item.pendingProcessRow && item.pendingProcessRow.isConnected
        ? item.pendingProcessRow
        : findSteerProcessRow(ctx, item.clientId || item.steerId || '');
    var content = String((serverItem && (serverItem.ui_content || serverItem.content)) || item.display || item.text || '');
    if (!row && ctx) {
        row = appendSteerProcessMessage(
            sid, ctx, content, item.clientId || item.steerId || '',
            item.steerMode || (serverItem && serverItem.mode) || 'interrupt', false
        );
    }
    if (!row) return null;
    var scroller = row.querySelector('.feed-chunk-scroller');
    if (scroller && content.trim()) scroller.textContent = truncateLogTextForUi(content);
    row.dataset.steerCommitted = '1';
    row.removeAttribute('data-steer-pending');
    if (item.clientId) row.dataset.steerClientId = String(item.clientId);
    if (item.steerId) row.dataset.steerId = String(item.steerId);
    item.pendingProcessRow = row;
    return row;
}

function appendSteerProcessMessage(sessionId, ctx, content, operationId, steerMode, pending) {
    var sid = String(sessionId || '');
    var key = String(operationId || '');
    if (!sid || !ctx || !key) return null;
    var existing = findSteerProcessRow(ctx, key);
    if (existing) {
        if (!pending) {
            var existingScroller = existing.querySelector('.feed-chunk-scroller');
            if (existingScroller && String(content || '').trim()) {
                existingScroller.textContent = truncateLogTextForUi(String(content || ''));
            }
            existing.dataset.steerCommitted = '1';
            existing.removeAttribute('data-steer-pending');
        }
        return existing;
    }
    var scroller = appendLog(ctx, String(content || ''), 'user-steer', sid);
    var row = scroller && scroller.closest ? scroller.closest('.feed-item') : null;
    if (!row) return null;
    row.dataset.steerOperationId = key;
    row.dataset.steerMode = steerMode === 'append' ? 'append' : 'interrupt';
    if (pending) row.dataset.steerPending = '1';
    else row.dataset.steerCommitted = '1';
    return row;
}

function appendPendingSteerToProcess(sessionId, item) {
    var sid = String(sessionId || '');
    if (!sid || !item || item.steerMode !== 'append') return null;
    var run = getSessionRunState(sid);
    var ctx = run && run.ctx;
    if (!ctx) return null;
    var row = appendSteerProcessMessage(
        sid,
        ctx,
        buildSelectedSkillsDisplayMessage(item.display || item.text || '', item.skills || []),
        item.clientId || item.steerId || '',
        'append',
        true
    );
    if (row) {
        if (item.clientId) row.dataset.steerClientId = String(item.clientId);
        if (item.steerId) row.dataset.steerId = String(item.steerId);
        item.pendingProcessRow = row;
    }
    return row;
}

function prepareSteerProcessBoundary(ctx, steerMode, operationId) {
    if (!ctx || String(steerMode || 'interrupt') !== 'interrupt') return;
    var key = String(operationId || '');
    if (key && String(ctx.lastInterruptSteerOperationId || '') === key) return;
    // An interrupt starts a new logical ReAct generation, but remains in the
    // same execution-process aggregate.  Generation-aware row keys preserve
    // ordering when react_iter restarts at 1.
    finalizeLlmStreamChunks(ctx);
    finalizeProgressStreamChunks(ctx);
    resetLlmState(ctx);
    ctx.reactGeneration = Math.max(0, Number(ctx.reactGeneration) || 0) + 1;
    if (key) ctx.lastInterruptSteerOperationId = key;
}

function markSteerEventPosition(ctx, eventIndex, runtimeSeq) {
    if (!ctx) return;
    if (Number.isFinite(Number(eventIndex))) {
        ctx.lastUserEventIndex = Math.max(
            Number.isFinite(Number(ctx.lastUserEventIndex)) ? Number(ctx.lastUserEventIndex) : -1,
            Math.floor(Number(eventIndex))
        );
    }
    if (Number.isFinite(Number(runtimeSeq)) && Number(runtimeSeq) > 0) {
        ctx.lastUserRuntimeSeq = Math.floor(Number(runtimeSeq));
    }
}

function removePendingSteerFromProcess(sessionId, item) {
    var sid = String(sessionId || '');
    if (!sid || !item || item.steerMode !== 'append') return;
    var run = getSessionRunState(sid);
    var row = item.pendingProcessRow && item.pendingProcessRow.isConnected
        ? item.pendingProcessRow
        : findSteerProcessRow(run && run.ctx, item.clientId || item.steerId || '');
    if (row && row.dataset.steerPending === '1' && row.dataset.steerCommitted !== '1') row.remove();
}

async function sendSteerMessage(sessionId, text, clientId, selectedSkills, uiContent, steerMode) {
    var activeRun = getSessionRunState(sessionId);
    var sourceRunId = activeRun && activeRun.runId ? String(activeRun.runId) : '';
    var r = await fetch('/sessions/' + encodeURIComponent(sessionId) + '/steer', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            message: text,
            client_id: clientId || '',
            selected_skills: selectedSkills || [],
            ui_content: uiContent || text,
            source_run_id: sourceRunId,
            mode: steerMode === 'append' ? 'append' : 'interrupt',
        }),
    });
    var j = await r.json().catch(function () {
        return { ok: false, error: 'steer failed' };
    });
    if (!r.ok || !j.ok) throw new Error((j && j.error) || 'steer failed');
    return j;
}

function sleepMs(ms) {
    return new Promise(function (resolve) {
        setTimeout(resolve, Math.max(0, Number(ms) || 0));
    });
}

async function refreshFollowupRunState(sessionId) {
    const sid = String(sessionId || '');
    if (!sid) return;
    try {
        if (typeof reconcileRunStateFromServer === 'function') {
            await reconcileRunStateFromServer({ silent: true });
        }
    } catch (e) { /* ignore */ }
    try {
        scheduleActiveSessionReconnect(sid, { delayMs: 0 });
    } catch (e2) { /* ignore */ }
}

async function cancelSteerMessage(sessionId, item) {
    var r = await fetch('/sessions/' + encodeURIComponent(sessionId) + '/steer', {
        method: 'DELETE',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            steer_id: (item && item.steerId) || '',
            client_id: (item && item.clientId) || '',
        }),
    });
    var j = await r.json().catch(function () {
        return { ok: false, error: 'cancel steer failed' };
    });
    if (!r.ok || !j.ok) throw new Error((j && j.error) || 'cancel steer failed');
    return j;
}

async function fetchSteerStatus(sessionId, item) {
    var steerId = String(item && item.steerId || '');
    if (!sessionId || !steerId) return null;
    var r = await fetch('/sessions/' + encodeURIComponent(sessionId) + '/steer/' + encodeURIComponent(steerId));
    var j = await r.json().catch(function () { return null; });
    if (!r.ok || !j || !j.ok) return null;
    return j.item || null;
}

async function recoverSteerForRestart(sessionId, item) {
    var steerId = String(item && item.steerId || '');
    if (!sessionId || !steerId) return null;
    var r = await fetch('/sessions/' + encodeURIComponent(sessionId) + '/steer/' + encodeURIComponent(steerId) + '/recover', {
        method: 'POST',
    });
    var j = await r.json().catch(function () { return null; });
    return r.ok && j && j.ok ? (j.item || null) : null;
}

async function syncFollowupQueueFromServer(sessionId) {
    var sid = String(sessionId || '');
    if (!sid || followupServerSyncInFlight[sid]) return followupServerSyncInFlight[sid] || null;
    followupServerSyncInFlight[sid] = fetch('/sessions/' + encodeURIComponent(sid) + '/steer?include_terminal=true')
        .then(function (r) { return r.ok ? r.json() : null; })
        .then(function (payload) {
            if (!payload || !payload.ok || !Array.isArray(payload.items)) return;
            var q = getFollowupQueue(sid);
            var pendingIds = new Set();
            payload.items.forEach(function (serverItem) {
                var steerId = String(serverItem.id || '');
                var clientId = String(serverItem.client_id || '');
                var state = String(serverItem.state || 'queued');
                var isTerminal = state === 'consumed' || state === 'cancelled' || state === 'failed';
                if (steerId && !isTerminal) pendingIds.add(steerId);
                var local = q.find(function (entry) {
                    return (steerId && String(entry.steerId || '') === steerId)
                        || (clientId && String(entry.clientId || '') === clientId);
                });
                if (!local && !isTerminal) {
                    local = {
                        id: 'server-' + (steerId || clientId || Date.now()),
                        text: String(serverItem.content || ''),
                        display: String(serverItem.ui_content || serverItem.content || ''),
                        clientId: clientId,
                        steerId: steerId,
                        createdAt: Math.round(Number(serverItem.created_at || 0) * 1000) || Date.now(),
                        steerMode: String(serverItem.mode || '') === 'append' ? 'append' : 'interrupt',
                    };
                    q.push(local);
                }
                if (!local) return;
                if (state === 'failed' || state === 'cancelled') {
                    var failedIndex = q.indexOf(local);
                    if (failedIndex >= 0) q.splice(failedIndex, 1);
                    returnFollowupToInput(sid, local);
                    return;
                }
                if (state === 'consumed') {
                    commitPendingSteerProcessRow(sid, local, serverItem);
                    var terminalIndex = q.indexOf(local);
                    if (terminalIndex >= 0) q.splice(terminalIndex, 1);
                    return;
                }
                local.steerId = steerId || local.steerId;
                local.clientId = clientId || local.clientId;
                local.replacementRunId = String(serverItem.replacement_run_id || local.replacementRunId || '');
                local.steerMode = String(serverItem.mode || local.steerMode || '') === 'append' ? 'append' : 'interrupt';
                local.status = state === 'restarting' ? 'restarting' : 'accepted';
                if (local.steerMode === 'append' && (state === 'queued' || state === 'claimed')) {
                    // Rebuild the transient tail anchor after refresh/reattach.
                    // The durable user_steer event will commit this same row.
                    appendPendingSteerToProcess(sid, local);
                }
            });
            for (var i = q.length - 1; i >= 0; i -= 1) {
                var entry = q[i];
                if (entry.steerId && (entry.status === 'accepted' || entry.status === 'restarting') && !pendingIds.has(String(entry.steerId))) {
                    q.splice(i, 1);
                }
            }
            q.sort(function (a, b) {
                var aOrder = Number(a.order);
                var bOrder = Number(b.order);
                var aHas = Number.isFinite(aOrder);
                var bHas = Number.isFinite(bOrder);
                if (aHas && bHas) return aOrder - bOrder;
                if (aHas) return -1;
                if (bHas) return 1;
                return Number(a.createdAt || 0) - Number(b.createdAt || 0);
            });
            persistFollowupQueue(sid);
            renderFollowupQueue(sid);
        })
        .finally(function () { delete followupServerSyncInFlight[sid]; });
    return followupServerSyncInFlight[sid];
}

function removeConsumedFollowupSteer(sessionId, ev) {
    const sid = String(sessionId || '');
    if (!sid || !ev || !ev.steer) return false;
    var steerId = String(ev.steer_id || '');
    var clientId = String(ev.client_id || '');
    if (!steerId && !clientId) return false;
    var q = getFollowupQueue(sid);
    var item = q.find(function (entry) {
        return (clientId && String(entry.clientId || '') === clientId)
            || (steerId && String(entry.steerId || '') === steerId);
    });
    if (!item) return false;
    takeFollowupItem(sid, item.id);
    renderFollowupQueue(sid);
    // 只发起一次门禁检查：活跃 run 会直接拦截；若终止事件先到、consumed 后到，
    // 则允许已经结束的这一轮继续 FIFO 队首。
    scheduleFollowupQueueDrain(sid, 0);
    return true;
}

function isFollowupAutoDrainReady(sessionId) {
    var sid = String(sessionId || '');
    return !!sid
        && !(typeof isSessionStreamStopSuppressed === 'function' && isSessionStreamStopSuppressed(sid))
        && !isSessionRunning(sid)
        && !isServerStreamActive(sid)
        && !isSendPipelineLocked(sid)
        && !isFollowupDispatchBusy(sid);
}

function cancelFollowupQueueDrain(sessionId) {
    var sid = String(sessionId || '');
    var existing = sid && followupDrainTimers[sid];
    if (!existing) return;
    clearTimeout(existing.timer);
    delete followupDrainTimers[sid];
}

function scheduleFollowupQueueDrain(sessionId, delayMs) {
    var sid = String(sessionId || '');
    if (!sid) return;
    var delay = Math.max(0, Number(delayMs) || 0);
    var dueAt = Date.now() + delay;
    var existing = followupDrainTimers[sid];
    if (existing && existing.dueAt <= dueAt) return;
    if (existing) clearTimeout(existing.timer);
    var timer = setTimeout(function () {
        var current = followupDrainTimers[sid];
        if (!current || current.timer !== timer) return;
        delete followupDrainTimers[sid];
        drainFollowupQueue(sid);
    }, delay);
    followupDrainTimers[sid] = { timer: timer, dueAt: dueAt };
}

function drainFollowupQueue(sessionId) {
    var sid = String(sessionId || '');
    if (!sid) return;
    if (!isFollowupAutoDrainReady(sid)) {
        // 活跃 run 会在自己的终止边界重新启动 drain；这里只重试瞬时的锁/dispatcher 竞争。
        if (isSessionRunning(sid)
            || isServerStreamActive(sid)
            || (typeof isSessionStreamStopSuppressed === 'function' && isSessionStreamStopSuppressed(sid))) return;
        scheduleFollowupQueueDrain(sid, 120);
        return;
    }
    var q = getFollowupQueue(sid);
    if (!q.length) { renderFollowupQueue(sid); return; }
    var item = q[0];
    if (!item || item.status) { renderFollowupQueue(sid); return; }
    // 一个终止边界最多尝试一条。失败后 sendFollowupNow 会恢复 pending；
    // 不在这里循环重试，避免网络错误造成请求风暴或重复执行。
    void Promise.resolve(sendFollowupNow(item.id, sid, { autoAfterRun: true }))
        .catch(function (error) {
            console.error('follow-up auto-drain failed:', error);
        });
}

function markFollowupQueueManualOnly(sessionId) {
    var sid = String(sessionId || '');
    if (!sid) return;
    cancelFollowupQueueDrain(sid);
    var q = getFollowupQueue(sid);
    q.forEach(function (item) {
        if (item) item.awaitingRunEnd = false;
    });
    persistFollowupQueue(sid);
    renderFollowupQueue(sid);
}

function recoverFollowupQueueDrainsFromSessionSnapshot(previousActiveIds, currentActiveIds) {
    var previous = previousActiveIds instanceof Set ? previousActiveIds : new Set(previousActiveIds || []);
    var current = currentActiveIds instanceof Set ? currentActiveIds : new Set(currentActiveIds || []);
    var candidates = new Set();
    previous.forEach(function (sid) {
        sid = String(sid || '');
        if (sid && !current.has(sid)) candidates.add(sid);
    });
    if (!followupSnapshotRecoveryInitialized) {
        followupSnapshotRecoveryInitialized = true;
        try {
            for (var i = 0; i < localStorage.length; i += 1) {
                var key = String(localStorage.key(i) || '');
                if (key.indexOf(LS_FOLLOWUP_QUEUE_PREFIX) !== 0) continue;
                var sid = key.slice(LS_FOLLOWUP_QUEUE_PREFIX.length);
                if (sid && !current.has(sid)) candidates.add(sid);
            }
        } catch (e) { /* localStorage may be unavailable */ }
    }
    candidates.forEach(function (sid) {
        if (current.has(sid)
            || (typeof isSessionStreamStopSuppressed === 'function' && isSessionStreamStopSuppressed(sid))) return;
        var q = getFollowupQueue(sid);
        var waiting = q.some(function (item) {
            return item && !item.status && item.awaitingRunEnd !== false;
        });
        if (!waiting) return;
        void Promise.resolve(syncFollowupQueueFromServer(sid)).then(function () {
            if (!isSessionRunning(sid) && !isServerStreamActive(sid)) {
                scheduleFollowupQueueDrain(sid, 0);
            }
        }).catch(function (error) {
            console.warn('background follow-up reconciliation failed', error);
        });
    });
}

function scheduleAcceptedFollowupWatch(sid, itemId) {
    var watchKey = String(sid || '') + ':' + String(itemId || '');
    if (followupWatchTimers[watchKey]) return;
    followupWatchTimers[watchKey] = setTimeout(function () {
        delete followupWatchTimers[watchKey];
        var queued = getFollowupQueue(sid).find(function (entry) {
            return String(entry.id) === String(itemId);
        });
        if (!queued || !['submitting', 'sending', 'accepted', 'restarting'].includes(String(queued.status || ''))) return;
        // Recovery can start a replacement /chat, so it participates in the
        // same per-session dispatcher as manual and automatic sends.
        void withFollowupDispatch(sid, async function () {
            await refreshFollowupRunState(sid);
            var latest = getFollowupQueue(sid).find(function (entry) {
                return String(entry.id) === String(itemId);
            });
            if (!latest) return;
            var serverItem = latest.steerId ? await fetchSteerStatus(sid, latest) : null;
            // A request may have reached the server immediately before refresh,
            // leaving only client_id locally. Reconcile first, then resolve the
            // authoritative steer state without creating another operation.
            if (!serverItem && latest.clientId) {
                await syncFollowupQueueFromServer(sid);
                latest = getFollowupQueue(sid).find(function (entry) {
                    return String(entry.id) === String(itemId);
                });
                if (!latest) return;
                if (latest.steerId) serverItem = await fetchSteerStatus(sid, latest);
            }
            var serverState = String(serverItem && serverItem.state || '');
            if (latest.steerMode === 'append'
                && (serverState === 'queued' || serverState === 'claimed')) {
                appendPendingSteerToProcess(sid, latest);
            }
            if (serverState === 'consumed') {
                commitPendingSteerProcessRow(sid, latest, serverItem);
                takeFollowupItem(sid, itemId);
                renderFollowupQueue(sid);
                refreshPendingFollowupQueue(sid);
                scheduleFollowupQueueDrain(sid, 0);
                return;
            }
            if (serverState === 'cancelled' || serverState === 'failed') {
                var failed = takeFollowupItem(sid, itemId);
                if (failed) returnFollowupToInput(sid, failed);
                return;
            }
            if (!serverItem && (latest.status === 'submitting' || latest.status === 'sending')) {
                if (latest.steerInFlight || isSessionRunning(sid) || isServerStreamActive(sid) || isSendPipelineLocked(sid)) {
                    scheduleAcceptedFollowupWatch(sid, itemId);
                    return;
                }
                // No local activity and no authoritative server operation: the
                // previous attempt was orphaned. Restore a durable pending row.
                latest.status = '';
                persistFollowupQueue(sid);
                renderFollowupQueue(sid);
                refreshPendingFollowupQueue(sid);
                return;
            }
            if ((serverState === 'queued' || serverState === 'interrupting' || serverState === 'claimed') && !isSessionRunning(sid) && !isServerStreamActive(sid)) {
                var recovered = await recoverSteerForRestart(sid, latest);
                if (recovered) {
                    latest.status = 'restarting';
                    latest.replacementRunId = String(recovered.replacement_run_id || '');
                    persistFollowupQueue(sid);
                    renderFollowupQueue(sid);
                }
                scheduleAcceptedFollowupWatch(sid, itemId);
                return;
            }
            if (serverState === 'restarting' && !isSessionRunning(sid) && !isServerStreamActive(sid) && !latest.restartRecoveryAttempted) {
                latest.restartRecoveryAttempted = true;
                latest.replacementRunId = String(serverItem && serverItem.replacement_run_id || latest.replacementRunId || '');
                persistFollowupQueue(sid);
                var restarted = await startFollowupChat({
                    message: latest.text,
                    displayMessage: latest.display || latest.text,
                    selectedSkills: latest.skills || [],
                    fromQueue: true,
                    sessionId: sid,
                    forceStart: true,
                    preserveInput: true,
                    asSteer: true,
                    steerId: latest.steerId,
                    steerClientId: latest.clientId,
                    steerMode: latest.steerMode,
                    clientRunId: latest.replacementRunId,
                });
                if (restarted) {
                    takeFollowupItem(sid, itemId);
                    renderFollowupQueue(sid);
                } else {
                    latest.restartRecoveryAttempted = false;
                    persistFollowupQueue(sid);
                    scheduleAcceptedFollowupWatch(sid, itemId);
                }
                return;
            }
            if (isSessionRunning(sid) || isServerStreamActive(sid)) {
                scheduleActiveSessionReconnect(sid, { delayMs: 0 });
                scheduleActiveSessionReconnect(sid, { delayMs: 1200 });
            }
            scheduleAcceptedFollowupWatch(sid, itemId);
        }).catch(function () {
            scheduleAcceptedFollowupWatch(sid, itemId);
        });
    }, 1200);
}

// Resolve as soon as /chat has been accepted and its SSE stream is ready. The
// long-running sendMessage promise continues consuming the stream in the
// background, while the dispatcher is released for genuine in-run steers.
function startFollowupChat(options) {
    return new Promise(function (resolve) {
        var settled = false;
        var finish = function (started) {
            if (settled) return;
            settled = true;
            resolve(!!started);
        };
        var opts = Object.assign({}, options || {});
        var priorStarted = opts.onRunStarted;
        opts.onRunStarted = function (info) {
            if (typeof priorStarted === 'function') {
                try { priorStarted(info); } catch (e) { /* callback is observational */ }
            }
            finish(true);
        };
        var completion;
        try {
            completion = Promise.resolve(sendMessage(opts));
        } catch (e) {
            finish(false);
            return;
        }
        completion.then(function (result) {
            finish(result === true);
        }, function () {
            finish(false);
        });
    });
}

function isFollowupAutoDispatchSuperseded(sessionId, dispatchEpoch) {
    var sid = String(sessionId || '');
    if (!sid || dispatchEpoch == null) return false;
    return Number(followupManualDispatchEpochBySession[sid] || 0) !== Number(dispatchEpoch);
}

async function isSessionAutoResumePending(sessionId) {
    var sid = String(sessionId || '');
    // Auto-resume only applies to the currently open session. Background
    // sessions keep their previous pending auto-drain behavior.
    if (!sid || sid !== String(currentSessionId || '')) return false;
    if (typeof subagentContinueSessionId !== 'undefined' && subagentContinueSessionId === sid) return true;
    // During an initial session load the normal switch/refresh path will wake
    // auto-resume; do not start /continue while history is still hydrating.
    if (typeof suppressTocDuringSessionLoad !== 'undefined' && suppressTocDuringSessionLoad) return true;
    try {
        var response = await fetch('/sessions/' + encodeURIComponent(sid), { cache: 'no-store' });
        if (!response.ok) return false;
        var detail = await response.json();
        if (!detail
            || !detail.react_auto_resume
            || detail.run_active
            || detail.stream_active) return false;
        if (typeof maybeAutoResumeInterruptedReact === 'function') {
            maybeAutoResumeInterruptedReact(sid, detail);
        }
        return true;
    } catch (e) {
        return false;
    }
}

async function sendQueuedFollowupAsChat(sessionId, item, itemId, dispatchEpoch) {
    var sid = String(sessionId || '');
    if (!sid || !item) return false;
    if (isFollowupAutoDispatchSuperseded(sid, dispatchEpoch)) return false;
    if (isSessionRunning(sid) || isServerStreamActive(sid)) {
        item.awaitingRunEnd = true;
        persistFollowupQueue(sid);
        renderFollowupQueue(sid);
        return false;
    }
    if (await isSessionAutoResumePending(sid)) {
        // A process-restarted session must resume its previous run before any
        // queued follow-up may start a new ordinary /chat turn.
        item.awaitingRunEnd = true;
        persistFollowupQueue(sid);
        renderFollowupQueue(sid);
        scheduleFollowupQueueDrain(sid, 1000);
        return false;
    }
    var previousAwaitingRunEnd = item.awaitingRunEnd;
    item.awaitingRunEnd = false;
    item.status = 'sending';
    persistFollowupQueue(sid);
    renderFollowupQueue(sid);
    var lockReady = await waitForSendPipelineIdle(sid, 4000);
    if (isFollowupAutoDispatchSuperseded(sid, dispatchEpoch)) {
        item.status = '';
        item.awaitingRunEnd = previousAwaitingRunEnd;
        persistFollowupQueue(sid);
        renderFollowupQueue(sid);
        return false;
    }
    if (!lockReady || isSendPipelineLocked(sid)) {
        item.status = '';
        item.awaitingRunEnd = true;
        persistFollowupQueue(sid);
        renderFollowupQueue(sid);
        scheduleFollowupQueueDrain(sid, 120);
        return false;
    }
    var started = await startFollowupChat({
        message: item.text,
        displayMessage: item.display || item.text,
        selectedSkills: item.skills || [],
        fromQueue: true,
        sessionId: sid,
        forceStart: true,
    });
    if (started) {
        takeFollowupItem(sid, itemId);
        renderFollowupQueue(sid);
        return true;
    }
    item.status = '';
    persistFollowupQueue(sid);
    renderFollowupQueue(sid);
    return false;
}

async function sendFollowupNowImpl(itemId, sessionId, options) {
    options = options || {};
    const followupTimingStartedAt = nowPipelineMs();
    const followupTimingCtx = {
        label: 'client_followup_step_timing',
        sessionId: sessionId || currentSessionId || '',
        runId: '',
        mode: 'followup',
        startedAt: followupTimingStartedAt
    };
    let _followupStepStart = followupTimingStartedAt;
    const sid = String(sessionId || currentSessionId || '');
    if (!sid) return;
    followupTimingCtx.sessionId = sid;
    var q = getFollowupQueue(sid);
    var idx = q.findIndex(function (item) { return String(item.id) === String(itemId); });
    if (idx < 0) return;
    const item = q[idx];
    if (!item) return;
    item.steerMode = item.steerMode === 'append' ? 'append' : 'interrupt';
    followupTimingCtx.mode = 'followup_' + item.steerMode;
    if (idx !== 0) {
        var moved = q.splice(idx, 1)[0];
        q.unshift(moved);
        persistFollowupQueue(sid);
        renderFollowupQueue(sid);
        idx = 0;
    }
    if (['submitting', 'sending', 'accepted', 'restarting', 'sent', 'withdrawing'].includes(String(item.status || ''))) {
        return;
    }
    if (options.autoAfterRun) {
        return sendQueuedFollowupAsChat(sid, item, itemId, options.autoDispatchEpoch);
    }
    item.awaitingRunEnd = false;
    item.clientId = item.clientId || ('followup-' + item.id + '-' + Date.now());
    item.status = 'submitting';
    persistFollowupQueue(sid);
    renderFollowupQueue(sid);
    reportClientPipelineStep(followupTimingCtx, 'followup_prepare_item', _followupStepStart, {
        itemId: itemId,
        running: isSessionRunning(sid)
    });
    try {
        _followupStepStart = nowPipelineMs();
        item.steerInFlight = true;
        var steerResult = await sendSteerMessage(
            sid,
            item.text,
            item.clientId,
            item.skills || [],
            item.display || item.text,
            item.steerMode
        );
        item.steerInFlight = false;
        item.steerId = steerResult && steerResult.item && steerResult.item.id ? String(steerResult.item.id) : '';
        if (steerResult && steerResult.item && steerResult.item.mode) {
            item.steerMode = String(steerResult.item.mode) === 'append' ? 'append' : 'interrupt';
        }
        reportClientPipelineStep(followupTimingCtx, 'followup_send_steer', _followupStepStart, {
            restart: !!(steerResult && steerResult.restart),
            steerId: item.steerId || ''
        });
        if (item.cancelRequested) {
            _followupStepStart = nowPipelineMs();
            await cancelSteerMessage(sid, item);
            reportClientPipelineStep(followupTimingCtx, 'followup_cancel_after_steer', _followupStepStart);
            var withdrawn = takeFollowupItem(sid, item.id);
            if (withdrawn) returnFollowupToInput(sid, withdrawn);
            return;
        }
        if (steerResult && steerResult.restart && isMyAgentFeatureEnabled('followupRestart', false)) {
            _followupStepStart = nowPipelineMs();
            var previousRun = getSessionRunState(sid);
            if (previousRun) abortSessionRun(sid, 'followup-restart');
            markSessionRunInactive(sid);
            // The server has created a durable replacement operation, but the
            // replacement /chat has not started yet. Keep it persisted and
            // watcher-visible until the new stream is actually accepted.
            item.status = 'restarting';
            item.replacementRunId = String(steerResult.replacement_run_id || '');
            persistFollowupQueue(sid);
            renderFollowupQueue(sid);
            setSendButtonState();
            syncSessionListIndicatorClasses();
            reportClientPipelineStep(followupTimingCtx, 'followup_restart_takeover', _followupStepStart, {
                hadPreviousRun: !!previousRun
            });
            var restartLockReady = await waitForSendPipelineIdle(sid, 4000);
            if (!restartLockReady || isSendPipelineLocked(sid)) {
                appendLogVisible('追问接管已保留，等待发送通道释放。', 'error-log');
                scheduleAcceptedFollowupWatch(sid, itemId);
                return;
            }
            var restartStarted = await startFollowupChat({
                message: item.text,
                displayMessage: item.display || item.text,
                selectedSkills: item.skills || [],
                fromQueue: true,
                sessionId: sid,
                forceStart: true,
                preserveInput: true,
                asSteer: true,
                steerId: item.steerId,
                steerClientId: item.clientId,
                steerMode: item.steerMode,
                clientRunId: String(steerResult.replacement_run_id || ''),
            });
            if (restartStarted) {
                takeFollowupItem(sid, itemId);
                renderFollowupQueue(sid);
            } else {
                item.restartRecoveryAttempted = false;
                persistFollowupQueue(sid);
                renderFollowupQueue(sid);
                scheduleAcceptedFollowupWatch(sid, itemId);
            }
            return;
        }
        item.status = 'accepted';
        persistFollowupQueue(sid);
        renderFollowupQueue(sid);
        if (item.steerMode === 'append') {
            appendPendingSteerToProcess(sid, item);
        }
        reportClientPipelineStep(followupTimingCtx, 'followup_accepted_by_running_agent', followupTimingStartedAt, {
            steerId: item.steerId || ''
        });
        scheduleAcceptedFollowupWatch(sid, itemId);
        return;
    } catch (e) {
        reportClientPipelineStep(followupTimingCtx, 'followup_steer_error', _followupStepStart, {
            error: (e && e.message) ? String(e.message) : String(e)
        });
        item.steerInFlight = false;
        var msg = (e && e.message) ? String(e.message) : String(e);
        var canFallbackToChat = /session is not running/i.test(msg);
        if (canFallbackToChat && !item.steerRetryAfterSync) {
            item.steerRetryAfterSync = true;
            item.status = 'submitting';
            persistFollowupQueue(sid);
            renderFollowupQueue(sid);
            await refreshFollowupRunState(sid);
            await sleepMs(250);
            if (isSessionRunning(sid) || isServerStreamActive(sid)) {
                try {
                    item.steerInFlight = true;
                    var retrySteerResult = await sendSteerMessage(
                        sid,
                        item.text,
                        item.clientId,
                        item.skills || [],
                        item.display || item.text,
                        item.steerMode
                    );
                    item.steerInFlight = false;
                    item.steerId = retrySteerResult && retrySteerResult.item && retrySteerResult.item.id ? String(retrySteerResult.item.id) : '';
                    if (retrySteerResult && retrySteerResult.item && retrySteerResult.item.mode) {
                        item.steerMode = String(retrySteerResult.item.mode) === 'append' ? 'append' : 'interrupt';
                    }
                    item.status = 'accepted';
                    persistFollowupQueue(sid);
                    renderFollowupQueue(sid);
                    if (item.steerMode === 'append') {
                        appendPendingSteerToProcess(sid, item);
                    }
                    reportClientPipelineStep(followupTimingCtx, 'followup_steer_retry_after_sync', _followupStepStart, {
                        steerId: item.steerId || ''
                    });
                    scheduleAcceptedFollowupWatch(sid, itemId);
                    return;
                } catch (retryError) {
                    item.steerInFlight = false;
                    msg = (retryError && retryError.message) ? String(retryError.message) : String(retryError);
                    canFallbackToChat = /session is not running/i.test(msg);
                }
            }
        }
        if (!canFallbackToChat) {
            await syncFollowupQueueFromServer(sid);
            var reconciled = getFollowupQueue(sid).find(function (entry) {
                return String(entry.id) === String(item.id);
            });
            if (reconciled && reconciled.steerId && (reconciled.status === 'accepted' || reconciled.status === 'restarting')) {
                scheduleAcceptedFollowupWatch(sid, itemId);
                return;
            }
            if (item.cancelRequested) {
                item.status = 'sending';
                item.cancelRequested = false;
                persistFollowupQueue(sid);
                renderFollowupQueue(sid);
                appendLogVisible('追问已被接收，无法撤回: ' + msg, 'error-log');
                return;
            }
            item.status = '';
            persistFollowupQueue(sid);
            renderFollowupQueue(sid);
            appendLogVisible('追问插入失败: ' + msg, 'error-log');
            return;
        }
    }
    markSessionRunInactive(sid);
    if (typeof sessionStore !== 'undefined') sessionStore.setStreamActive(sid, false);
    // 降级 /chat 前必须等待发送锁释放，否则 sendMessage 会因锁未释放而静默返回，
    // 随后定时器无条件删除条目 → 表现为「点了立即发送却没反应」「发送后内容被删」。
    var lockAcquired = await waitForSendPipelineIdle(sid, 4000);
    if (!lockAcquired || isSendPipelineLocked(sid)) {
        // 锁迟迟未释放：恢复为 pending，交由后续 drain 或手动重试，绝不删除。
        item.status = '';
        item.steerInFlight = false;
        persistFollowupQueue(sid);
        renderFollowupQueue(sid);
        appendLogVisible('追问暂未发出（发送通道繁忙），已保留待重试: ' + msg, 'error-log');
        refreshPendingFollowupQueue(sid);
        return;
    }
    if (await isSessionAutoResumePending(sid)) {
        item.status = '';
        item.steerInFlight = false;
        item.awaitingRunEnd = true;
        persistFollowupQueue(sid);
        renderFollowupQueue(sid);
        scheduleFollowupQueueDrain(sid, 1000);
        return;
    }
    item.status = 'sending';
    persistFollowupQueue(sid);
    renderFollowupQueue(sid);
    reportClientPipelineStep(followupTimingCtx, 'followup_fallback_to_chat', followupTimingStartedAt);
    var chatStarted = await startFollowupChat({
        message: item.text,
        displayMessage: item.display || item.text,
        selectedSkills: item.skills || [],
        fromQueue: true,
        sessionId: sid,
        forceStart: true,
    });
    if (chatStarted) {
        // /chat 已成功开跑，追问作为普通用户轮次发出，删除队列项。
        takeFollowupItem(sid, itemId);
        renderFollowupQueue(sid);
    } else {
        // /chat 未真正开跑：恢复为 pending，保留条目，交由 drain 重试。
        item.status = '';
        item.steerInFlight = false;
        persistFollowupQueue(sid);
        renderFollowupQueue(sid);
        appendLogVisible('追问降级发送未成功，已保留待重试: ' + msg, 'error-log');
        refreshPendingFollowupQueue(sid);
    }
    return;
}

/* 会话级互斥：所有显式立即发送共用同一 dispatcher 链，防止并发 steer 竞争。 */
async function sendFollowupNow(itemId, sessionId, options) {
    options = options || {};
    const sid = String(sessionId || currentSessionId || '');
    if (!sid) return;
    var dispatchOptions = Object.assign({}, options);
    var observedManualEpoch = Number(followupManualDispatchEpochBySession[sid] || 0);
    if (options.manual) {
        observedManualEpoch += 1;
        followupManualDispatchEpochBySession[sid] = observedManualEpoch;
        cancelFollowupQueueDrain(sid);
        var q = getFollowupQueue(sid);
        var idx = q.findIndex(function (item) { return String(item.id) === String(itemId); });
        if (idx < 0) return;
        if (idx > 0) q.unshift(q.splice(idx, 1)[0]);
        q[0].awaitingRunEnd = false;
        persistFollowupQueue(sid);
        renderFollowupQueue(sid);
    }
    dispatchOptions.autoDispatchEpoch = observedManualEpoch;
    return withFollowupDispatch(sid, function () {
        if (dispatchOptions.autoAfterRun
            && isFollowupAutoDispatchSuperseded(sid, dispatchOptions.autoDispatchEpoch)) return false;
        return sendFollowupNowImpl(itemId, sid, dispatchOptions);
    });
}

async function sendMessage(options) {
    options = options || {};
    if (!options.fromQueue && !options.fromInlineRewrite && isChatFileUploadBusy()) return;
    const clientPipelineStartedAt = nowPipelineMs();
    let clientTimingCtx = {
        label: 'client_send_pipeline_step_timing',
        sessionId: options.sessionId || currentSessionId || '',
        runId: '',
        mode: options.asSteer ? 'followup_steer' : (options.fromQueue ? 'followup_queue' : (options.fromInlineRewrite ? 'inline_rewrite' : 'chat')),
        startedAt: clientPipelineStartedAt
    };
    let _clientStepStart = clientPipelineStartedAt;
    messageLoadEpoch += 1;
    /* 立即快照「提交会话」：之后所有 await 都不能改变它，避免用户在 await 空隙切走后消息发到新会话。
       关键不变式：runSessionId === submitSessionId 全程恒等。 */
    const submitSessionIdInitial = options.sessionId || currentSessionId;
    if (!options.fromQueue && !options.fromInlineRewrite) rewriteInputWorkspacePaths();
    const visibleMessage = options.message != null ? String(options.message) : messageInput.value;
    const rawMessage = (options.fromQueue || options.fromInlineRewrite) ? visibleMessage : expandInputPathTokens(visibleMessage);
    if (!String(rawMessage).trim()) return;
    if (isSessionRunning(submitSessionIdInitial) && !options.forceStart) return;
    if (isSendPipelineLocked(submitSessionIdInitial)) return;
    if (options.forceStart && submitSessionIdInitial) {
        var previousRun = getSessionRunState(submitSessionIdInitial);
        if (previousRun) abortSessionRun(submitSessionIdInitial, 'followup-restart');
    }
    if (submitSessionIdInitial && typeof ensureLatestHistoryTailForLiveAppend === 'function') {
        var sendTailReady = await ensureLatestHistoryTailForLiveAppend(submitSessionIdInitial);
        if (!sendTailReady) {
            showUiAlert({
                title: '无法发送',
                message: '当前页面正在查看较早历史，且未能恢复最新历史尾部。请重试。',
                variant: 'error'
            });
            return;
        }
    }
    var selectedSkillsForRun = [];
    if (Array.isArray(options.selectedSkills)) {
        selectedSkillsForRun = options.selectedSkills.map(function (skill) { return String(skill || '').trim(); }).filter(Boolean);
    } else if (!options.fromQueue && !options.fromInlineRewrite && typeof window.consumeSelectedSkillsForSend === 'function') {
        selectedSkillsForRun = window.consumeSelectedSkillsForSend();
    }
    var uiBaseMessage = options.displayMessage != null ? String(options.displayMessage) : rawMessage;
    var displayMessage = buildSelectedSkillsDisplayMessage(uiBaseMessage, selectedSkillsForRun);
    reportClientPipelineStep(clientTimingCtx, 'preflight_checks', _clientStepStart, {
        forceStart: !!options.forceStart,
        fromQueue: !!options.fromQueue,
        fromInlineRewrite: !!options.fromInlineRewrite,
        asSteer: !!options.asSteer
    });

    /* 立即上锁：阻止后续连击；锁的 key 是提交时的会话，而非当前会话。 */
    _clientStepStart = nowPipelineMs();
    const sendPipelineLock = acquireSendPipelineLock(submitSessionIdInitial);
    if (!sendPipelineLock) return;
    let submittedRunCtx = null;
    let submittedRunSessionId = submitSessionIdInitial;
    _clientStepStart = nowPipelineMs();
    const clientRunId = options.clientRunId || ((window.crypto && window.crypto.randomUUID)
        ? window.crypto.randomUUID()
        : ('run-' + Date.now() + '-' + Math.random().toString(16).slice(2)));
    clientTimingCtx.runId = clientRunId;
    const ac = new AbortController();
    var optimisticRunState = {
        controller: ac,
        ctx: null,
        runId: clientRunId,
        optimistic: true,
        submitted: false,
        suppressFollowupButton: true
    };
    // Publish before rewrite truncation, session creation, event-count reads,
    // or any other network await so every send path flips in the same frame.
    if (submitSessionIdInitial) {
        if (typeof clearSessionStreamStopSuppress === 'function') clearSessionStreamStopSuppress(submitSessionIdInitial);
        setSessionRunState(submitSessionIdInitial, optimisticRunState);
    } else {
        optimisticNewSessionRun = optimisticRunState;
    }
    setSendButtonState();
    syncSessionListIndicatorClasses();
    reportClientPipelineStep(clientTimingCtx, 'publish_optimistic_run_state', _clientStepStart);
    try {
    reportClientPipelineStep(clientTimingCtx, 'acquire_send_lock', _clientStepStart);

    if (pendingRewriteTruncate && pendingRewriteTruncate.sessionId === submitSessionIdInitial) {
        _clientStepStart = nowPipelineMs();
        const pendingRewrite = pendingRewriteTruncate;
        const truncated = await processRewriteTruncateAsync(pendingRewrite);
        reportClientPipelineStep(clientTimingCtx, 'pending_rewrite_truncate', _clientStepStart, { ok: !!truncated });
        if (!truncated) {
            pendingRewriteTruncate = null;
            return;
        }
        pendingRewriteTruncate = null;
        uiEventCountCache.updateFromServer(submitSessionIdInitial, pendingRewrite.before);
        if (ac.signal.aborted) return;
    }
    hideRewriteUndoToast();

    hideSubagentContinueBanner();
    const userSentAt = new Date().toISOString();

    let submitSessionId = submitSessionIdInitial;
    if (!submitSessionId) {
        _clientStepStart = nowPipelineMs();
        await createNewSession();
        submitSessionId = currentSessionId;
        clientTimingCtx.sessionId = submitSessionId || clientTimingCtx.sessionId;
        reportClientPipelineStep(clientTimingCtx, 'create_new_session', _clientStepStart, { ok: !!submitSessionId });
        if (!submitSessionId) return;
        if (!transferSendPipelineLock(sendPipelineLock, submitSessionId)) return;
        if (ac.signal.aborted) return;
        if (optimisticNewSessionRun === optimisticRunState) optimisticNewSessionRun = null;
        setSessionRunState(submitSessionId, optimisticRunState);
        setSendButtonState();
        syncSessionListIndicatorClasses();
    }
    clientTimingCtx.sessionId = submitSessionId || clientTimingCtx.sessionId;
    const runSessionId = submitSessionId;
    submittedRunSessionId = runSessionId;
    if (typeof clearSessionStreamStopSuppress === 'function') clearSessionStreamStopSuppress(runSessionId);
    reportClientPipelineStep(clientTimingCtx, 'prepare_client_run_id', _clientStepStart);
    _clientStepStart = nowPipelineMs();
    let preCount = await getUiEventCount(submitSessionId, {
        preferCache: true,
        maxAgeMs: 10000,
        signal: ac.signal,
        timeoutMs: 5000
    });
    if (ac.signal.aborted) return;
    const existingStreamForIndex = (submitSessionId === currentSessionId) ? getVisibleChatStream() : null;
    if (existingStreamForIndex) {
        existingStreamForIndex.querySelectorAll('.msg-wrap--user[data-event-index]').forEach(function (wrap) {
            const n = Number(wrap.getAttribute('data-event-index'));
            if (Number.isFinite(n)) preCount = Math.max(preCount, Math.floor(n) + 1);
        });
    }
    reportClientPipelineStep(clientTimingCtx, 'resolve_ui_event_count', _clientStepStart, { preCount: preCount });
    _clientStepStart = nowPipelineMs();
    if (sessionStore && typeof sessionStore.resetSseSeq === 'function') {
        sessionStore.resetSseSeq(runSessionId);
    }
    reportClientPipelineStep(clientTimingCtx, 'prepare_sse_sequence_state', _clientStepStart);

    /* 用户在 createNewSession / getUiEventCount 期间切走：
       后台仍然发起 /chat（消息已属于 runSessionId），但不要往当前可见 stream 画用户气泡。 */
    const switchedAway = currentSessionId !== runSessionId;
    let runCtx;
    if (switchedAway) {
        const offscreen = document.createElement('div');
        offscreen.className = 'chat-stream is-offscreen';
        offscreen.dataset.partialBackgroundRun = '1';
        if (typeof offscreenRoot !== 'undefined' && offscreenRoot) offscreenRoot.appendChild(offscreen);
        runCtx = newDomContext(offscreen);
    } else {
        if (!getVisibleChatStream()) ensureVisibleChatStreamSlot();
        runCtx = newDomContext(getVisibleChatStream());
    }
    _clientStepStart = nowPipelineMs();
    submittedRunCtx = runCtx;
    runCtx.runId = clientRunId;
    initRunFinalTracking(runCtx);
    runCtx.runStartedAt = userSentAt;
    runCtx.lastUserEventIndex = preCount;
    resetLlmState(runCtx);
    finalizeLlmStreamChunks(runCtx);
    sealProcessGroup(runCtx);
    optimisticRunState.ctx = runCtx;
    optimisticRunState.optimistic = false;
    setSessionRunState(runSessionId, optimisticRunState);
    setSendButtonState();
    syncSessionListIndicatorClasses();
    reportClientPipelineStep(clientTimingCtx, 'prepare_run_context', _clientStepStart, { switchedAway: !!switchedAway });
    _clientStepStart = nowPipelineMs();
    const renderAsSteer = !!options.asSteer;
    if (!renderAsSteer) {
        applySessionEvent({ type: 'user', content: displayMessage, created_at: userSentAt }, {
            sessionId: runSessionId,
            eventIndex: preCount,
            source: 'local-send',
        });
    }
    uiEventCountCache.updateFromServer(runSessionId, preCount + 1);
    if (!switchedAway) {
        liveAutoFollow = true;
        streamChatNearBottom = true;
        streamProcNearBottom = true;
        if (renderAsSteer) {
            var optimisticSteerClientId = String(options.steerClientId || '');
            var optimisticSteerId = String(options.steerId || '');
            var optimisticSteerOpId = optimisticSteerClientId || optimisticSteerId || clientRunId;
            var optimisticSteerMode = String(options.steerMode || 'interrupt') === 'append' ? 'append' : 'interrupt';
            prepareSteerProcessBoundary(runCtx, optimisticSteerMode, optimisticSteerOpId);
            var optimisticSteerRow = appendSteerProcessMessage(
                runSessionId, runCtx, displayMessage, optimisticSteerOpId,
                optimisticSteerMode, true
            );
            if (optimisticSteerRow) {
                optimisticSteerRow.dataset.steerEventReserved = '1';
                if (optimisticSteerClientId) optimisticSteerRow.dataset.steerClientId = optimisticSteerClientId;
                if (optimisticSteerId) optimisticSteerRow.dataset.steerId = optimisticSteerId;
            }
        } else {
            appendMessage(runCtx, 'user', displayMessage, { eventIndex: preCount, turnTruncateIdx: preCount, createdAt: userSentAt }, runSessionId);
        }
        if (!options.fromQueue && !options.preserveInput) {
            messageInput.value = '';
            persistInputDraft(runSessionId, '');
            clearInputPathTokens();
            autoResizeTextarea();
            setSendButtonState();
        }
    }
    optimisticRunState.suppressFollowupButton = false;
    setSendButtonState();
    updateSidebarLastUserPreviewImmediate(runSessionId, displayMessage);
    lastUserMessageBySession[runSessionId] = displayMessage;
    reportClientPipelineStep(clientTimingCtx, 'local_user_render', _clientStepStart, { renderAsSteer: !!renderAsSteer, switchedAway: !!switchedAway });
    _clientStepStart = nowPipelineMs();
    const formData = new FormData();
    formData.append('message', rawMessage);
    const rememberedAttachments = window.MyAgentPathPicker
        && typeof window.MyAgentPathPicker.chatAttachments === 'function'
        ? window.MyAgentPathPicker.chatAttachments(messageInput)
        : [];
    const attachmentsForRun = rememberedAttachments.filter(function (item) {
        return item && item.path && rawMessage.indexOf(String(item.path)) >= 0;
    });
    if (attachmentsForRun.length) {
        formData.append('attachments', JSON.stringify(attachmentsForRun));
    }
    if (window.MyAgentPathPicker
            && typeof window.MyAgentPathPicker.clearChatAttachments === 'function') {
        window.MyAgentPathPicker.clearChatAttachments(messageInput);
    }
    // The backend owns durable UI-message decoration. Sending the undecorated
    // value keeps the optimistic row and the reloaded history identical.
    formData.append('ui_message', uiBaseMessage);
    formData.append('session_id', runSessionId);
    formData.append('client_run_id', clientRunId);
    formData.append('stream_protocol', 'runtime_v2');
    formData.append(
        'ui_language',
        (document.documentElement && document.documentElement.getAttribute('data-language'))
            || localStorage.getItem('myagent-language')
            || 'zh-CN'
    );
    if (selectedSkillsForRun && selectedSkillsForRun.length) {
        formData.append('selected_skills', JSON.stringify(selectedSkillsForRun));
    }
    if (renderAsSteer) formData.append('followup_steer', 'true');
    if (renderAsSteer && options.steerId) formData.append('steer_id', String(options.steerId));
    /* 发送后优先使用本轮 API usage/cache_stats 刷新 token；缺少 usage 时仍保留上一快照。 */
    if (!switchedAway) applyContextTokenLabelForCurrentSession();
    let streamEventIdx = preCount + 1;
    let streamDisconnectedUnexpectedly = false;
    try {
        reportClientPipelineStep(clientTimingCtx, 'build_form_data', _clientStepStart, { followupSteer: !!renderAsSteer });
        _clientStepStart = nowPipelineMs();
        optimisticRunState.submitted = true;
        let response = null;
        for (let migrationAttempt = 0; migrationAttempt < 120; migrationAttempt += 1) {
            response = await fetch('/chat', { method: 'POST', body: formData, signal: ac.signal });
            if (response.status !== 425) break;
            const pending = await response.json().catch(function () { return null; });
            if (!pending || pending.reason !== 'runtime_migration_pending') break;
            if (migrationAttempt >= 119) {
                rollbackOptimisticUserEvent(runSessionId, preCount);
                throw new Error('Runtime V2 migration timed out');
            }
            const retryMs = Math.max(100, Math.min(Number(pending.retry_after_ms) || 250, 1000));
            await new Promise(function (resolve) { setTimeout(resolve, retryMs); });
        }
        reportClientPipelineStep(clientTimingCtx, 'fetch_chat_response_headers', _clientStepStart, { status: response && response.status });
        _clientStepStart = nowPipelineMs();
        if (response.status === 409) {
            streamDisconnectedUnexpectedly = true;
            rollbackOptimisticUserEvent(runSessionId, preCount);
            if (!options.fromQueue && isMyAgentFeatureEnabled('followupRestart', false)) {
                appendFollowupQueueItem(
                    runSessionId,
                    rawMessage,
                    displayMessage,
                    selectedSkillsForRun
                );
            } else if (!options.fromQueue && runSessionId === currentSessionId) {
                messageInput.value = visibleMessage;
                persistInputDraft(runSessionId, visibleMessage);
                if (typeof window.setSelectedSkillsForCurrentSession === 'function') {
                    window.setSelectedSkillsForCurrentSession(selectedSkillsForRun);
                }
                autoResizeTextarea();
            }
            scheduleActiveSessionReconnect(runSessionId, { delayMs: 0, failure: true });
            return false;
        }
        var responseContentType = String(response.headers && response.headers.get
            ? (response.headers.get('content-type') || '')
            : '').toLowerCase();
        if (response.ok && responseContentType.indexOf('text/event-stream') >= 0
            && typeof options.onRunStarted === 'function') {
            try {
                options.onRunStarted({ sessionId: runSessionId, runId: clientRunId });
            } catch (onStartedError) {
                console.error('run start callback failed:', onStartedError);
            }
        }
        streamEventIdx = await consumeAgentSseResponse(response, runCtx, runSessionId, streamEventIdx);
        reportClientPipelineStep(clientTimingCtx, 'consume_sse_until_done', _clientStepStart, { streamEventIdx: streamEventIdx });
        return true;
    } catch (error) {
        reportClientPipelineStep(clientTimingCtx, 'chat_fetch_or_sse_error', _clientStepStart, { error: (error && error.message) ? String(error.message) : String(error) });
        if (error.name === 'AbortError') {
            if (getRunAbortReason(runSessionId, runCtx) === 'user') appendLog(runCtx, '任务已中断', 'status', runSessionId);
        }
        else {
            console.error('请求失败:', error);
            streamDisconnectedUnexpectedly = true;
            const msg = (error && error.message) ? String(error.message) : String(error);
            appendLog(runCtx, '请求失败: ' + msg, 'error-log', runSessionId);
        }
        return false;
    } finally {
        _clientStepStart = nowPipelineMs();
        finalizeLlmStreamChunks(runCtx);
        finalizeProgressStreamChunks(runCtx);
        if (!switchedAway && runSessionId === currentSessionId && getRunAbortReason(runSessionId, runCtx) !== 'user') {
            scheduleFinalVisibleAfterRunIfEnabled(runSessionId, runCtx, { delayMs: 120 });
        }
        if (runSessionId === currentSessionId) renderTodoPlanForCurrentSession();
        if (liveAutoFollow && !switchedAway) {
            scrollProcessBodyToBottom(runCtx, runSessionId);
            scrollChatToBottomIfFollow(runSessionId, {});
        }
        if (runSessionId !== currentSessionId) {
            void tryMarkSessionUnreadComplete(runSessionId);
        } else {
            clearSessionUnreadState(runSessionId);
            updateSubagentContinueBanner(runSessionId);
        }
        if (getSessionRunState(runSessionId)) {
            clearSessionRunStateIfMatch(runSessionId, clientRunId);
        }
        if (streamDisconnectedUnexpectedly && runSessionId === currentSessionId && getRunAbortReason(runSessionId, runCtx) !== 'user') {
            scheduleActiveSessionReconnect(runSessionId, { delayMs: 500, failure: true });
            scheduleActiveSessionReconnect(runSessionId, { delayMs: 2500, failure: true });
        } else {
            resetStreamReconnectState(runSessionId);
        }
        if (runSessionId !== currentSessionId) {
            const el = runCtx.stream;
            const reusableCompletedCache = !!(
                el && el.parentNode
                && !switchedAway
                && !streamDisconnectedUnexpectedly
                && getRunAbortReason(runSessionId, runCtx) !== 'user'
                && runCtx.streamCompletedSuccessfully === true
                && runCtx.seenFinal === true
                && el.dataset.partialBackgroundRun !== '1'
                && el.dataset.cacheSessionId === String(runSessionId)
                && el.dataset.sessionLoadFailed !== '1'
            );
            if (reusableCompletedCache) {
                el.dataset.sessionLoadOk = '1';
                delete el.dataset.sessionLoading;
                delete el.dataset.sessionLoadFailed;
                if (typeof cacheOrderTouch === 'function') cacheOrderTouch(runSessionId);
                if (typeof trimCachedSessionStreams === 'function') trimCachedSessionStreams();
            } else {
                // A partial background projection may coexist with an older
                // cached stream for this session. Both are stale after this
                // run, so invalidate the registered cache as well as runCtx.
                if (typeof discardCachedSessionStream === 'function') {
                    discardCachedSessionStream(runSessionId);
                }
                if (el && el.parentNode) el.remove();
            }
        }
        setSendButtonState();
        syncSessionListIndicatorClasses();
        void refreshSingleSessionRow(runSessionId);
        applyContextTokenLabelForCurrentSession();
        if (runSessionId === currentSessionId && countRunningSubagentCards() > 0) {
            scheduleSubagentIncrementalSync();
        }
        reportClientPipelineStep(clientTimingCtx, 'finalize_visible_state', _clientStepStart, {
            disconnected: !!streamDisconnectedUnexpectedly,
            currentSession: runSessionId === currentSessionId
        });
    }
    } finally {
        _clientStepStart = nowPipelineMs();
        if (optimisticNewSessionRun === optimisticRunState) optimisticNewSessionRun = null;
        if (optimisticRunState && optimisticRunState.submitted === false && submittedRunSessionId) {
            clearSessionRunStateIfMatch(submittedRunSessionId, optimisticRunState.runId);
        }
        releaseSendPipelineLock(sendPipelineLock);
        var stoppedByUser = getRunAbortReason(submittedRunSessionId, submittedRunCtx) === 'user'
            || (optimisticRunState && optimisticRunState.abortReason === 'user');
        reportClientPipelineStep(clientTimingCtx, 'release_send_lock', _clientStepStart, {
            stoppedByUser: !!stoppedByUser,
            fromQueue: !!options.fromQueue
        });
        setSendButtonState();
        syncSessionListIndicatorClasses();
        if (!stoppedByUser && getFollowupQueue(submittedRunSessionId).length) {
            renderFollowupQueue(submittedRunSessionId);
        }
    }
}

async function submitComposerWithPendingQuestionGuard() {
    if (typeof pendingHumanQuestions !== 'function' || !pendingHumanQuestions(currentSessionId).length) return false;
    if (!inputHasSendableText() || isChatFileUploadBusy()) return false;
    var shouldSend = await confirmAndCancelPendingHumanQuestionsForMessage(currentSessionId);
    if (shouldSend) {
        await sendMessage({ forceStart: isSessionRunning(currentSessionId) });
    }
    // A visible confirmation was shown, so the originating key/click event is
    // handled even when the user chooses to return to the question.
    return true;
}

messageInput.addEventListener('keydown', async function onFollowupInputKeydown(e) {
    if (!isMyAgentFeatureEnabled('followupRestart', false)) return;
    if (e.key !== 'Enter') return;
    e.stopImmediatePropagation();
    if (e.ctrlKey && !e.shiftKey && !e.metaKey) {
        const start = this.selectionStart;
        const end = this.selectionEnd;
        this.value = this.value.substring(0, start) + '\\n' + this.value.substring(end);
        this.selectionStart = this.selectionEnd = start + 1;
        e.preventDefault();
        autoResizeTextarea();
        return;
    }
    if (e.shiftKey) return;
    if (isChatFileUploadBusy()) {
        e.preventDefault();
        return;
    }
    e.preventDefault();
    if (await submitComposerWithPendingQuestionGuard()) return;
    if (isSessionRunning(currentSessionId)) {
        enqueueCurrentInputAsFollowup();
        return;
    }
    sendMessage();
}, true);

messageInput.addEventListener('keydown', async function onInputKeydown(e) {
    if (e.key !== 'Enter') return;
    // Ctrl+Enter → 插入换行（跨浏览器兼容）
    if (e.ctrlKey && !e.shiftKey && !e.metaKey) {
        const start = this.selectionStart;
        const end = this.selectionEnd;
        this.value = this.value.substring(0, start) + '\\n' + this.value.substring(end);
        this.selectionStart = this.selectionEnd = start + 1;
        e.preventDefault();
        autoResizeTextarea();
        return;
    }
    // Shift+Enter → 浏览器默认插入换行
    if (e.shiftKey) return;
    if (isChatFileUploadBusy()) {
        e.preventDefault();
        return;
    }
    // 纯 Enter → 发送；pending Ask 即使仍处于运行状态，也先进入
    // “取消问题并发送”确认流程。
    e.preventDefault();
    if (await submitComposerWithPendingQuestionGuard()) return;
    if (isSessionRunning(currentSessionId)) return;
    sendMessage();
});
chatContainer.addEventListener('scroll', function () {
    refreshLiveAutoFollowPins();
    scheduleTocActiveUpdate();
    maybeAutoLoadOlderHistory();
}, { passive: true });
sendBtn.addEventListener('click', async function (e) {
    e.stopImmediatePropagation();
    if (!currentSessionId && optimisticNewSessionRun) {
        pauseCurrentRun();
        return;
    }
    if (await submitComposerWithPendingQuestionGuard()) return;
    if (isSessionRunning(currentSessionId)) {
        const activeRun = getSessionRunState(currentSessionId);
        const canQueueFollowup = isMyAgentFeatureEnabled('followupRestart', false)
            && inputHasSendableText()
            && !isChatFileUploadBusy()
            && !(activeRun && activeRun.suppressFollowupButton);
        if (canQueueFollowup) enqueueCurrentInputAsFollowup();
        else pauseCurrentRun();
        return;
    }
    sendMessage();
}, true);
sendBtn.addEventListener('click', function () {
    if ((!currentSessionId && optimisticNewSessionRun) || isSessionRunning(currentSessionId)) pauseCurrentRun();
    else sendMessage();
});
window.addEventListener('resize', positionFollowupQueuePanel);
window.addEventListener('scroll', positionFollowupQueuePanel, true);
(function bindRewriteUndo() {
    const toast = document.getElementById('rewrite-undo-toast');
    const btn = toast && toast.querySelector('.rewrite-undo-btn');
    if (!btn) return;
    btn.addEventListener('click', async function (e) {
        e.preventDefault();
        if (!rewriteUndoState) { hideRewriteUndoToast(); return; }
        const s = rewriteUndoState;
        if (s.type === 'rewrite_pending') {
            const prevIn = (s.data && s.data.prevInput != null) ? s.data.prevInput : '';
            messageInput.value = prevIn;
            rewriteInputWorkspacePaths();
            autoResizeTextarea();
            messageInput.focus();
            pendingRewriteTruncate = null;
            hideRewriteUndoToast();
            return;
        }
        if (s.type === 'input' && s.data) {
            messageInput.value = s.data.prev;
            rewriteInputWorkspacePaths();
            autoResizeTextarea();
            messageInput.focus();
            hideRewriteUndoToast();
            return;
        }
        if (s.type === 'tail' && s.data && s.data.sessionId && s.data.tail && s.data.tail.length) {
            try {
                const r = await historyOperationJson(
                    '/sessions/' + encodeURIComponent(s.data.sessionId) + '/append_ui_events',
                    { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ events: s.data.tail }) },
                    45000
                );
                if (!r || !r.ok) { alert('撤销失败，请重试。'); return; }
                if (s.data.sessionId === currentSessionId) {
                    showLoading();
                    try {
                        await loadSessionMessages(s.data.sessionId, 'bottom', { full: true });
                    } finally {
                        hideLoading();
                    }
                }
            } catch (err) { console.error(err); alert('撤销失败，请重试。'); return; }
        }
        hideRewriteUndoToast();
    });
})();
(function bindSubagentContinueBannerOnce() {
    if (window.__myAgentSubagentContinueBound) return;
    window.__myAgentSubagentContinueBound = true;
    var btn = document.getElementById('subagent-continue-btn');
    var dismissBtn = document.getElementById('subagent-continue-dismiss');
    if (btn) btn.addEventListener('click', function (e) {
        e.preventDefault();
        if (!currentSessionId || subagentContinueInFlight) return;
        void startContinueAfterSubagents(currentSessionId);
    });
    if (dismissBtn) dismissBtn.addEventListener('click', function (e) {
        e.preventDefault();
        e.stopPropagation();
        dismissSubagentContinueBanner(currentSessionId);
    });
})();
initUiHoverTips(document);
`,Kt=`newSessionBtn.addEventListener('click', async () => { await createNewSession(); });

function initSidebarSash() {
    const side = document.getElementById('sidebar');
    const sash = document.getElementById('sash');
    if (!side || !sash) return;
    const KEY = 'sidebar-width-px';
    function clampW(n) {
        const max = Math.min(480, Math.floor(window.innerWidth * 0.5));
        return Math.max(120, Math.min(max, n));
    }
    const saved = localStorage.getItem(KEY);
    if (saved) { const w = parseInt(saved, 10); if (!isNaN(w)) side.style.width = clampW(w) + 'px'; }
    let startX = 0, startW = 0;
    function onMouseMove(e) { side.style.width = clampW(startW + e.clientX - startX) + 'px'; }
    function onMouseUp() {
        sash.classList.remove('is-dragging');
        document.body.style.cursor = '';
        document.body.style.userSelect = '';
        document.removeEventListener('mousemove', onMouseMove);
        document.removeEventListener('mouseup', onMouseUp);
        localStorage.setItem(KEY, String(Math.round(side.getBoundingClientRect().width)));
    }
    sash.addEventListener('mousedown', function (e) {
        e.preventDefault();
        startX = e.clientX;
        startW = side.getBoundingClientRect().width;
        sash.classList.add('is-dragging');
        document.body.style.cursor = 'col-resize';
        document.body.style.userSelect = 'none';
        document.addEventListener('mousemove', onMouseMove);
        document.addEventListener('mouseup', onMouseUp);
    });
}

async function init() {
    loadUnreadFromStorage();
    initSidebarSash();
    showLoading();
    const sessionsLoaded = await loadSessions();
    const sessions = sessionStore.list();
    let lastSessionId = localStorage.getItem('lastSessionId');
    let targetSession = null;
    if (lastSessionId && sessions.some(s => s.id === lastSessionId)) targetSession = lastSessionId;
    else if (!sessionsLoaded && lastSessionId) targetSession = lastSessionId;
    else if (sessions.length > 0) targetSession = sessions[0].id;
    // Restore durable approvals/questions before switchSession decides whether
    // the global pending banner should be hidden for the selected session.
    if (targetSession && typeof refreshHumanInteractions === 'function') {
        void refreshHumanInteractions(targetSession, { render: false });
    }
    if (targetSession) await switchSession(targetSession);
    else await createNewSession();
    bindExistingLogs();
}
init();
function toggleTocPanel() {
    panelWasAutoCollapsed = false;
    const toc = document.getElementById('chat-toc');
    if (!toc) return;
    toc.classList.toggle('is-open');
    syncEdgeTabArrows();
    schedulePanelEdgeTabsLayout();
}

function toggleTodoPlanPanel() {
    panelWasAutoCollapsed = false;
    const root = document.getElementById('chat-todo-plan');
    if (!root) return;
    root.classList.toggle('is-open');
    syncEdgeTabArrows();
    schedulePanelEdgeTabsLayout();
}

function syncEdgeTabArrows() {
    const toc = document.getElementById('chat-toc');
    const todo = document.getElementById('chat-todo-plan');
    const tocTab = document.getElementById('toc-edge-tab');
    const todoTab = document.getElementById('todo-edge-tab');
    if (tocTab && toc) {
        tocTab.textContent = toc.classList.contains('is-open') ? '▶' : '◀';
    }
    if (todoTab && todo) {
        todoTab.textContent = todo.classList.contains('is-open') ? '◀' : '▶';
    }
}

function updatePanelToggles() {
    const tocList = document.getElementById('chat-toc-list');
    const todoList = document.getElementById('chat-todo-plan-list');
    const tocTab = document.getElementById('toc-edge-tab');
    const todoTab = document.getElementById('todo-edge-tab');
    if (tocTab) tocTab.classList.toggle('visible', !!(tocList && tocList.children.length));
    if (todoTab) todoTab.classList.toggle('visible', !!(todoList && todoList.children.length));
    syncEdgeTabArrows();
    schedulePanelEdgeTabsLayout();
}

function notifyPanelContentChanged() {
    if (typeof updatePanelToggles !== 'function') return;
    updatePanelToggles();
    if (typeof runPanelAutoCollapseCheck === 'function') {
        requestAnimationFrame(function () {
            runPanelAutoCollapseCheck();
            schedulePanelEdgeTabsLayout();
        });
    }
}

/* 折叠三角挂在 stage 外层面，对齐面板边缘（收起后只剩按钮，不被 aside 裁切） */
var panelEdgeTabsObserver = null;
var panelEdgeTabsRaf = null;
function layoutPanelEdgeTabs() {
    var stage = document.querySelector('.chat-stage');
    var todo = document.getElementById('chat-todo-plan');
    var toc = document.getElementById('chat-toc');
    var todoTab = document.getElementById('todo-edge-tab');
    var tocTab = document.getElementById('toc-edge-tab');
    if (!stage || !todoTab || !tocTab) return;
    var sr = stage.getBoundingClientRect();
    todoTab.style.top = '50%';
    tocTab.style.top = '50%';
    /* Todo：仅用 left，与 CSS 一致（贴在面板右缘） */
    todoTab.style.right = 'auto';
    if (todo) {
        var tr = todo.getBoundingClientRect();
        todoTab.style.left = (tr.right - sr.left) + 'px';
    }
    /* TOC：仅用 right，勿写 left（否则与样式表里 right 并存导致错位 / hover 异常） */
    tocTab.style.left = 'auto';
    if (toc) {
        var cr = toc.getBoundingClientRect();
        tocTab.style.right = (sr.right - cr.left) + 'px';
    }
}

function schedulePanelEdgeTabsLayout() {
    if (panelEdgeTabsRaf != null) return;
    panelEdgeTabsRaf = requestAnimationFrame(function () {
        panelEdgeTabsRaf = null;
        layoutPanelEdgeTabs();
    });
}

function initPanelEdgeTabsLayout() {
    var stage = document.querySelector('.chat-stage');
    var todo = document.getElementById('chat-todo-plan');
    var toc = document.getElementById('chat-toc');
    if (!stage || panelEdgeTabsObserver) return;
    panelEdgeTabsObserver = new ResizeObserver(schedulePanelEdgeTabsLayout);
    panelEdgeTabsObserver.observe(stage);
    if (todo) panelEdgeTabsObserver.observe(todo);
    if (toc) panelEdgeTabsObserver.observe(toc);
    schedulePanelEdgeTabsLayout();
}

/* 自动折叠：约在 750–805px 档就要收起；正文占比不足也收起；显著变宽后再展开（滞回 + 冷却） */
var panelAutoCollapseObserver = null;
var panelCollapseRaf = null;
var panelAutoCollapseCooldownUntil = 0;
var panelWasAutoCollapsed = false;

function runPanelAutoCollapseCheck() {
    var mainEl = document.querySelector('.main');
    var stage = document.querySelector('.chat-stage');
    if (!mainEl || !stage) return;
    var mainW = mainEl.clientWidth;
    var stageW = stage.clientWidth;
    var layoutW = Math.min(mainW, stageW);
    var todo = document.getElementById('chat-todo-plan');
    var toc = document.getElementById('chat-toc');
    var tocList = document.getElementById('chat-toc-list');
    var todoList = document.getElementById('chat-todo-plan-list');
    var now = (typeof performance !== 'undefined' && performance.now) ? performance.now() : Date.now();

    var LAYOUT_COLLAPSE_AT = 805;
    var LAYOUT_EXPAND_AT = 940;

    if (panelWasAutoCollapsed && now >= panelAutoCollapseCooldownUntil && layoutW >= LAYOUT_EXPAND_AT) {
        panelWasAutoCollapsed = false;
        if (toc && tocList && tocList.children.length && !toc.classList.contains('is-open')) toc.classList.add('is-open');
        if (todo && todoList && todoList.children.length && !todo.classList.contains('is-open')) todo.classList.add('is-open');
        syncEdgeTabArrows();
        return;
    }

    var todoOpen = todo && todo.classList.contains('is-open');
    var tocOpen = toc && toc.classList.contains('is-open');
    if (!todoOpen && !tocOpen) return;

    var todoW = todoOpen ? todo.offsetWidth : 0;
    var tocW = tocOpen ? toc.offsetWidth : 0;
    var centerW = layoutW - todoW - tocW;
    var minCenterByRatio = Math.max(400, Math.floor(layoutW * 0.52));
    var layoutTooNarrow = layoutW <= LAYOUT_COLLAPSE_AT;
    var centerTooTight = centerW < minCenterByRatio;

    if (layoutTooNarrow || centerTooTight) {
        var did = false;
        if (tocOpen) { toc.classList.remove('is-open'); did = true; }
        if (todoOpen) { todo.classList.remove('is-open'); did = true; }
        if (did) {
            panelWasAutoCollapsed = true;
            panelAutoCollapseCooldownUntil = now + 420;
            syncEdgeTabArrows();
        }
    }
}

function initPanelAutoCollapse() {
    var mainEl = document.querySelector('.main');
    var stage = document.querySelector('.chat-stage');
    if (!mainEl || !stage || panelAutoCollapseObserver) return;
    function schedule() {
        if (panelCollapseRaf != null) return;
        panelCollapseRaf = requestAnimationFrame(function () {
            panelCollapseRaf = null;
            runPanelAutoCollapseCheck();
        });
    }
    panelAutoCollapseObserver = new ResizeObserver(schedule);
    panelAutoCollapseObserver.observe(mainEl);
    panelAutoCollapseObserver.observe(stage);
}

initPanelAutoCollapse();
initPanelEdgeTabsLayout();

// Inline HTML (onclick) still expects these on globalThis.
if (typeof globalThis !== 'undefined') {
    globalThis.clearTodoPlan = clearTodoPlan;
    globalThis.toggleTodoPlanPanel = toggleTodoPlanPanel;
    globalThis.toggleTocPanel = toggleTocPanel;
}
`;globalThis.marked=R;let xe=null;globalThis.loadMyAgentMermaid=function(){return globalThis.mermaid?Promise.resolve(globalThis.mermaid):(xe||(xe=nn(()=>import("./mermaid.core-CNjlwD5x.js").then(e=>e.aJ),[]).then(function(e){const n=e.default||e.mermaid||e;return globalThis.mermaid=n,n})),xe)};let ke=null;globalThis.loadMyAgentHtml2Canvas=function(){return ke||(ke=nn(()=>import("./html2canvas.esm-QH1iLAAe.js"),[]).then(function(e){return e.default||e})),ke};const Yt=[vt,St,bt,yt,wt,It,xt,kt,Ct,Tt,Et,At,_t,Rt,Pt,Lt,Mt,Ft,Bt,Nt,Ot,qt,Dt,Ut,Ht,jt,Gt,$t,zt,Wt,Vt,Qt,Kt];Function(`"use strict";
`+Yt.join(`

`)+`
//# sourceURL=myagent-ui.js`)();typeof initUiHoverTips=="function"&&initUiHoverTips(document);export{nn as _};
