(function(){const w=document.createElement("link").relList;if(w&&w.supports&&w.supports("modulepreload"))return;for(const S of document.querySelectorAll('link[rel="modulepreload"]'))E(S);new MutationObserver(S=>{for(const h of S)if(h.type==="childList")for(const _ of h.addedNodes)_.tagName==="LINK"&&_.rel==="modulepreload"&&E(_)}).observe(document,{childList:!0,subtree:!0});function P(S){const h={};return S.integrity&&(h.integrity=S.integrity),S.referrerPolicy&&(h.referrerPolicy=S.referrerPolicy),S.crossOrigin==="use-credentials"?h.credentials="include":S.crossOrigin==="anonymous"?h.credentials="omit":h.credentials="same-origin",h}function E(S){if(S.ep)return;S.ep=!0;const h=P(S);fetch(S.href,h)}})();(function(y){var w='<svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M3 7a2 2 0 0 1 2-2h4l2 2h8a2 2 0 0 1 2 2v9a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V7z"></path></svg>';function P(){if(!document.getElementById("myagent-path-picker-styles")){var t=document.createElement("style");t.id="myagent-path-picker-styles",t.textContent='.path-input-row{display:flex;align-items:stretch;gap:.35rem;width:100%;}.path-input-row>.ip,.path-input-row>.tx,.path-input-row>input[type="text"],.path-input-row>input:not([type]){flex:1;min-width:0;}.path-browse-btn{flex-shrink:0;width:2.35rem;padding:0;border:1px solid var(--border-glass,rgba(255,255,255,.08));border-radius:var(--radius-sm,8px);background:var(--surface-glass2,rgba(40,40,60,.94));color:var(--text-secondary,#a6adc8);cursor:pointer;display:inline-flex;align-items:center;justify-content:center;transition:color .18s,border-color .18s,background .18s;}.path-browse-btn:hover{color:var(--text-primary,#cdd6f4);border-color:var(--border-brand-accent,rgba(124,111,247,.35));background:rgba(108,92,231,.12);}.path-browse-btn:disabled{opacity:.45;cursor:not-allowed;}.path-browse-btn--ghost{background:transparent;border-color:transparent;box-shadow:none;width:2.1rem;}.path-browse-btn--ghost:hover{background:rgba(108,92,231,.1);border-color:transparent;color:var(--accent-2,#d4b8fc);}.input-wrapper .path-browse-btn--ghost{align-self:center;margin-right:-.15rem;}.input-wrapper.is-drag-over{border-color:rgba(203,166,247,.62);box-shadow:0 0 0 3px rgba(203,166,247,.12),0 0 28px rgba(139,92,246,.18);}.workspace-file-popover{position:fixed;display:none;z-index:260;width:min(46rem,calc(100vw - 1.2rem));height:min(32rem,calc(100vh - 1.2rem));border:1px solid rgba(203,166,247,.24);border-radius:14px;background:linear-gradient(145deg,rgba(31,31,49,.88),rgba(19,20,31,.78));box-shadow:0 24px 70px rgba(0,0,0,.38),0 0 0 1px rgba(255,255,255,.045) inset,0 0 34px rgba(139,92,246,.16);overflow:hidden;backdrop-filter:blur(22px);-webkit-backdrop-filter:blur(22px);}.workspace-file-popover:before{content:"";position:absolute;inset:0;pointer-events:none;background:radial-gradient(circle at 18% 0%,rgba(203,166,247,.18),transparent 30%),radial-gradient(circle at 92% 18%,rgba(99,102,241,.16),transparent 28%);}.workspace-file-popover.is-open{display:flex;flex-direction:column;}.workspace-file-search{position:relative;width:100%;box-sizing:border-box;border:0;border-bottom:1px solid rgba(255,255,255,.08);background:rgba(255,255,255,.055);color:var(--text-primary,#cdd6f4);padding:.56rem .72rem;font:inherit;font-size:.78rem;outline:none;}.workspace-file-search::placeholder{color:var(--text-muted,#6c7086);}.workspace-file-list{position:relative;flex:1;min-height:0;overflow:auto;padding:.36rem .38rem .2rem;}.workspace-file-item{width:100%;display:grid;grid-template-columns:1.05rem minmax(0,1fr) auto;gap:.2rem .38rem;align-items:center;text-align:left;border:0;border-radius:8px;background:transparent;color:var(--text-secondary,#a6adc8);padding:.22rem .36rem;cursor:pointer;font:inherit;font-size:.74rem;}.workspace-file-item:hover,.workspace-file-item.is-active{background:rgba(139,92,246,.13);color:var(--text-primary,#cdd6f4);}.workspace-file-item.is-selected{background:rgba(99,102,241,.18);color:var(--text-primary,#cdd6f4);}.workspace-file-check{width:.82rem;height:.82rem;border:1px solid rgba(203,166,247,.38);border-radius:4px;display:inline-flex;align-items:center;justify-content:center;color:#fff;font-size:.62rem;line-height:1;background:transparent;}.workspace-file-item.is-selected .workspace-file-check{background:linear-gradient(135deg,#6366f1,#a78bfa);border-color:transparent;color:#fff;}.workspace-file-dir-row{grid-template-columns:1.05rem minmax(0,1fr) auto;color:var(--text-primary,#cdd6f4);font-weight:650;}.workspace-file-dir-row .workspace-file-tree{grid-column:2/3;}.workspace-file-file-row{grid-template-columns:1.05rem minmax(0,1fr) auto;}.workspace-file-tree{min-width:0;display:flex;align-items:center;gap:.24rem;}.workspace-file-indent{flex:0 0 auto;width:var(--indent,0);}.workspace-file-chevron{width:.8rem;min-width:.8rem;color:var(--text-muted,#6c7086);font-size:.72rem;text-align:center;border:0;background:transparent;padding:0;cursor:pointer;}.workspace-file-icon{position:relative;width:.98rem;min-width:.98rem;height:.74rem;margin-top:.04rem;border-radius:3px;border:1px solid rgba(203,166,247,.28);background:linear-gradient(135deg,rgba(203,166,247,.18),rgba(99,102,241,.1));box-shadow:inset 0 .12rem .26rem rgba(255,255,255,.08);}.workspace-file-icon:before{content:"";position:absolute;left:.06rem;right:.06rem;top:.12rem;height:.16rem;border-radius:999px;background:rgba(203,166,247,.34);}.workspace-file-icon:after{content:"";position:absolute;left:.06rem;right:.06rem;bottom:.11rem;height:.24rem;border-radius:2px;background:rgba(99,102,241,.16);}.workspace-file-icon.is-file{width:.82rem;min-width:.82rem;height:1rem;margin-top:0;border-radius:3px;background:transparent;border:1.5px solid rgba(166,173,200,.58);box-shadow:none;color:var(--text-muted,#6c7086);}.workspace-file-icon.is-file:before{left:auto;right:-1.5px;top:-1.5px;width:.3rem;height:.3rem;border:0;border-left:1.5px solid rgba(166,173,200,.58);border-bottom:1.5px solid rgba(166,173,200,.58);border-radius:0 3px 0 3px;background:var(--surface-glass2,rgba(40,40,60,.94));}.workspace-file-icon.is-file:after{display:none;}.workspace-file-icon.is-folder-svg{width:1rem;min-width:1rem;height:1rem;margin-top:0;border:0;background:transparent;box-shadow:none;color:var(--text-muted,#6c7086);display:inline-flex;align-items:center;justify-content:center;}.workspace-file-icon.is-folder-svg:before,.workspace-file-icon.is-folder-svg:after{display:none;}.workspace-file-icon.is-folder-svg svg{width:1rem;height:1rem;display:block;}.workspace-file-icon.is-image{border-color:rgba(45,212,191,.72);}.workspace-file-icon.is-image:after{display:block;left:.12rem;right:.12rem;bottom:.15rem;height:.24rem;clip-path:polygon(0 100%,38% 38%,56% 66%,76% 24%,100% 100%);background:rgba(45,212,191,.72);}.workspace-file-icon.is-audio{border-color:rgba(251,191,36,.76);}.workspace-file-icon.is-audio:after{display:block;left:.17rem;right:auto;bottom:.18rem;width:.36rem;height:.4rem;border-radius:0;background:rgba(251,191,36,.76);clip-path:polygon(0 32%,45% 32%,100% 0,100% 100%,45% 68%,0 68%);}.workspace-file-name{min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;font-size:.74rem;}.workspace-file-dir{grid-column:2/-1;color:var(--text-muted,#6c7086);font-size:.68rem;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;}.workspace-file-meta{color:var(--text-muted,#6c7086);font-size:.68rem;white-space:nowrap;}.workspace-file-footer{position:relative;display:flex;align-items:center;justify-content:space-between;gap:.5rem;padding:.42rem .52rem;border-top:1px solid rgba(255,255,255,.08);background:rgba(255,255,255,.035);font-size:.72rem;color:var(--text-muted,#6c7086);}.workspace-file-outside{flex-shrink:0;border:1px solid rgba(203,166,247,.24);border-radius:8px;padding:.28rem .58rem;background:rgba(203,166,247,.1);color:var(--text-primary,#cdd6f4);font:inherit;font-size:.7rem;font-weight:700;cursor:pointer;transition:background .16s,border-color .16s,color .16s;}.workspace-file-outside:hover{background:rgba(203,166,247,.18);border-color:rgba(203,166,247,.42);color:#fff;}.workspace-file-insert{border:0;border-radius:8px;padding:.34rem .62rem;background:linear-gradient(135deg,#6366f1,#8b5cf6);color:#fff;font-size:.72rem;font-weight:700;cursor:pointer;}.workspace-file-insert:disabled{opacity:.45;cursor:not-allowed;}.workspace-file-empty{padding:1rem;text-align:center;color:var(--text-muted,#6c7086);font-size:.78rem;}.theme-light .workspace-file-popover{background:linear-gradient(145deg,rgba(255,255,255,.93),rgba(244,247,252,.86));box-shadow:0 24px 64px rgba(31,35,52,.16),0 0 28px rgba(99,102,241,.12);}.theme-light .workspace-file-search,.theme-light .workspace-file-footer{background:rgba(34,40,58,.035);}',document.head.appendChild(t)}}async function E(t,l,o){var c=typeof AbortController<"u"?new AbortController:null,u=c?setTimeout(function(){c.abort()},5e4):null,f;try{f=await fetch("/api/pick-path",{method:"POST",headers:{"Content-Type":"application/json"},credentials:"same-origin",body:JSON.stringify({kind:t||"directory",initial:l||"",multiple:!!o}),signal:c?c.signal:void 0})}finally{u&&clearTimeout(u)}var p=await f.json().catch(function(){return{ok:!1,error:"请求失败"}});if(!f.ok||!p.ok){if(p&&p.cancelled)return null;var r=p&&p.error||"无法打开选择对话框";if(/取消|cancelled|800704c7|2147023673/i.test(r))return null;throw new Error(r)}return o?Array.isArray(p.paths)?p.paths:p.path?[p.path]:[]:p.path||null}async function S(t,l,o,c,u){t.disabled=!0;try{var f=await E(l,o||"",!!u);c&&c(f)}catch{return}finally{t.disabled=!1}}function h(t){var l=String(t||"").trim();return l?((l.charAt(0)==='"'&&l.charAt(l.length-1)==='"'||l.charAt(0)==="'"&&l.charAt(l.length-1)==="'")&&(l=l.slice(1,-1)),'"'+l.replace(/"/g,'\\"')+'"'):""}function _(t){var l=String(t||"").toLowerCase().split(".").pop()||"";return/^(png|jpe?g|gif|webp|bmp|svg|tiff?|ico|avif)$/.test(l)?"is-image":/^(mp3|wav|flac|aac|m4a|ogg|oga|opus|wma|aiff?)$/.test(l)?"is-audio":""}function B(t,l){var o=t.selectionStart,c=t.selectionEnd,u=t.value.slice(0,o),f=t.value.slice(c),p=String(l||"");u.length&&!/\s$/.test(u)&&(p=" "+p),f.length&&!/^\s/.test(f)&&(p=p+" "),t.value=u+p+f;var r=u.length+p.length;t.selectionStart=t.selectionEnd=r,t.dispatchEvent(new Event("input",{bubbles:!0})),t.focus()}async function J(t){var l=Array.prototype.slice.call(t||[]).filter(Boolean);if(!l.length)return[];var o=new FormData;l.forEach(function(f){o.append("files",f,f.name||"upload.bin")});var c=await fetch("/api/upload-chat-files",{method:"POST",credentials:"same-origin",body:o}),u=await c.json().catch(function(){return{ok:!1,error:"上传失败"}});if(!c.ok||!u.ok)throw new Error(u&&u.error||"上传失败");return Array.isArray(u.files)?u.files:[]}function ee(t){return t=Number(t||0),!isFinite(t)||t<=0?"":t<1024?t+" B":t<1024*1024?Math.round(t/102.4)/10+" KB":t<1024*1024*1024?Math.round(t/104857.6)/10+" MB":Math.round(t/1073741824e-1)/10+" GB"}async function U(t,l,o){var c=[];t?c.push("q="+encodeURIComponent(t)):l&&c.push("dir="+encodeURIComponent(l));var u="/api/workspace-files"+(c.length?"?"+c.join("&"):""),f=await fetch(u,{credentials:"same-origin",signal:o}),p=await f.json().catch(function(){return{ok:!1,error:"读取工作区文件失败"}});if(!f.ok||!p.ok)throw new Error(p&&p.error||"读取工作区文件失败");return Array.isArray(p.files)?p.files:[]}function H(t,l){return J(l).then(function(o){var c=o.map(function(u){return h(u.path||u.rel||u.name)}).join(" ");c&&B(t,c)})}function ne(t,l){var o=document.createElement("div");o.className="workspace-file-popover",o.setAttribute("aria-hidden","true"),o.innerHTML='<input class="workspace-file-search" type="text" autocomplete="off" spellcheck="false" placeholder="搜索工作区文件"><div class="workspace-file-list" role="listbox"></div><div class="workspace-file-footer"><span class="workspace-file-count">未选择文件</span><button type="button" class="workspace-file-outside">选择工作目录外文件</button></div>',document.body.appendChild(o);var c=o.querySelector(".workspace-file-search"),u=o.querySelector(".workspace-file-list"),f=o.querySelector(".workspace-file-count"),p=o.querySelector(".workspace-file-outside"),r={items:[],visible:[],active:0,open:!1,debounce:null,controller:null,selected:Object.create(null),expanded:Object.create(null),loadedDirs:Object.create(null),itemMap:Object.create(null)};function b(){var e=t.closest?t.closest(".input-wrapper"):t,n=e.getBoundingClientRect(),s=8,d=Math.min(Math.max(n.width,520),window.innerWidth-16),a=Math.max(8,Math.min(n.left,window.innerWidth-d-8)),g=o.offsetHeight||384,i=n.top-g-s;i<8&&(i=Math.min(window.innerHeight-g-8,n.bottom+s)),o.style.left=a+"px",o.style.top=Math.max(8,i)+"px",o.style.width=d+"px"}function I(){var e=Object.keys(r.selected).length;f.textContent=e?"已选择 "+e+" 项":"未选择文件",u.querySelectorAll(".workspace-file-item").forEach(function(n){var s=n.getAttribute("data-path-key")||"",d=!!r.selected[s];n.classList.toggle("is-selected",d);var a=n.querySelector(".workspace-file-check");a&&(a.textContent=d?"✓":"")})}function C(e){var n=u.querySelectorAll(".workspace-file-item");if(!n.length){r.active=0;return}r.active=Math.max(0,Math.min(e,n.length-1));for(var s=0;s<n.length;s++)n[s].classList.toggle("is-active",s===r.active),n[s].setAttribute("aria-selected",s===r.active?"true":"false");var d=n[r.active];d&&typeof d.scrollIntoView=="function"&&d.scrollIntoView({block:"nearest"})}function R(){r.open=!1,o.classList.remove("is-open"),o.setAttribute("aria-hidden","true"),r.debounce&&clearTimeout(r.debounce),r.controller&&r.controller.abort()}function N(e){return e&&(e.path||e.rel||e.name)||""}function W(e){return h(N(e))}function se(e,n){var s=N(e);if(!s)return!1;var d=String(e&&e.rel||"");return n.indexOf(W(e))>=0||n.indexOf(s)>=0||d&&n.indexOf(h(d))>=0||d&&n.indexOf(d)>=0}function ae(e,n){e=String(e||""),n=String(n||"");for(var s=0;s<e.length&&s<n.length&&e.charAt(s)===n.charAt(s);)s++;for(var d=e.length-1,a=n.length-1;d>=s&&a>=s&&e.charAt(d)===n.charAt(a);)d--,a--;return n.slice(s,a+1).trim()}function oe(e,n){if(n){var s=String(t.value||"");if(!(s.indexOf(n)>=0)){var d=t.value;B(t,n);var a=ae(d,t.value);e&&a&&(e._inputToken=a)}}}function ie(e,n){if(!n&&!e)return;var s=String(t.value||""),d=[];function a(i){i=String(i||"").trim(),i&&d.indexOf(i)<0&&d.push(i)}a(e&&e._inputToken),a(n),a(e&&e.path),a(e&&e.rel),a(e&&e.path&&h(e.path)),a(e&&e.rel&&h(e.rel));var g=s;d.sort(function(i,m){return m.length-i.length}).forEach(function(i){var m=i.replace(/[.*+?^${}()|[\]\\]/g,"\\$&"),v=new RegExp("(?:^|\\s)"+m+"(?=\\s|$)","g");g=g.replace(v,function(x){return x.charAt(0)&&/\s/.test(x.charAt(0))?" ":""})}),g=g.replace(/[ \t]{2,}/g," ").trim(),g!==s&&(t.value=g,t.selectionStart=t.selectionEnd=t.value.length,t.dispatchEvent(new Event("input",{bubbles:!0})))}function F(e){if(e){var n=N(e);if(n){var s=W(e);if(r.selected[n]){var d=r.selected[n];delete r.selected[n],ie(d,s)}else r.selected[n]=e,oe(e,s);I()}}}function z(){var e=String(t.value||"");Object.keys(r.selected).forEach(function(n){var s=r.selected[n];se(s,e)||delete r.selected[n]})}function le(){z(),I()}t.addEventListener("input",le),p&&p.addEventListener("click",function(e){e.preventDefault(),e.stopPropagation(),typeof l=="function"&&l()});function G(){var e=String(y.__WORK_DIR__||"workspace"),n=e.split(/[\\/]+/).filter(Boolean);return n[n.length-1]||"workspace"}function K(e,n,s){return{type:"dir",name:e,rel:n,root:!!s,path:"",dirs:Object.create(null),files:[],children:[],loaded:!1}}function de(e,n){var s=String(e&&e.path||""),d=String(n||"").replace(/\//g,"\\");return s&&d&&s.toLowerCase().slice(-d.length)===d.toLowerCase()?s.slice(0,Math.max(0,s.length-d.length)).replace(/[\\/]+$/,""):String(y.__WORK_DIR__||"").replace(/[\\/]+$/,"")}function V(e,n){var s=String(e||"").replace(/[\\/]+$/,""),d=String(n||"").replace(/[\\/]+/g,"/");if(!d)return s;var a=s.indexOf("\\")>=0?"\\":"/";return s?s+a+d.replace(/\//g,a):d}function L(e){return{kind:"directory",name:e.name||e.rel||G(),rel:e.rel||"",path:e.path||V(String(y.__WORK_DIR__||""),e.rel||"")}}function ce(e){var n=K(G(),"",!0);n.path=String(y.__WORK_DIR__||"").replace(/[\\/]+$/,""),n.loaded=!!r.loadedDirs.__root__;function s(a,g){for(var i=n,m=[],v=0;v<a.length;v++)m.push(a[v]),i.dirs[a[v]]||(i.dirs[a[v]]=K(a[v],m.join("/"),!1),i.dirs[a[v]].path=V(g||n.path,m.join("/"))),i=i.dirs[a[v]],i.loaded=!!r.loadedDirs[i.rel||"__root__"];return i}(e||[]).forEach(function(a){var g=String(a.rel||a.path||a.name||"").replace(/\\/g,"/"),i=g.split("/").filter(Boolean);if(i.length){var m=de(a,g);if(!n.path&&m&&(n.path=m),a.kind==="directory"){var v=s(i,m||n.path);v.name=a.name||v.name,v.path=a.path||v.path;return}var x=s(i.slice(0,-1),m||n.path);x.files.push({type:"file",name:a.name||i[i.length-1]||g,rel:g,item:a})}});function d(a){var g=Object.keys(a.dirs).map(function(i){return a.dirs[i]}).sort(function(i,m){return i.name.localeCompare(m.name,void 0,{sensitivity:"base"})});g.forEach(d),a.files.sort(function(i,m){return i.name.localeCompare(m.name,void 0,{sensitivity:"base"})}),a.children=g.concat(a.files)}return d(n),n}function Q(e,n,s){if(!(!e||e.type!=="dir")){s=Number(s||0);var d=e.rel||"__root__";n?r.expanded[d]=!0:typeof r.expanded[d]>"u"&&(r.expanded[d]=s===0),n&&e.children.forEach(function(a){a.type==="dir"&&Q(a,n,s+1)})}}function ue(e){var n=[];function s(d,a){n.push({type:"dir",node:d,depth:a}),r.expanded[d.rel||"__root__"]&&d.children.forEach(function(g){g.type==="dir"?s(g,a+1):n.push({type:"file",node:g,depth:a+1})})}return s(e,0),n}function pe(e){return String(e&&(e.kind||"file")||"file")+":"+String(e&&(e.rel||e.path||e.name)||"")}function $(e){(e||[]).forEach(function(n){var s=pe(n);s!==":"&&(r.itemMap[s]=n)}),r.items=Object.keys(r.itemMap).map(function(n){return r.itemMap[n]}),r.items.sort(function(n,s){return String(n.rel||"").localeCompare(String(s.rel||""),void 0,{sensitivity:"base"})})}function fe(e){if(e){var n=e.rel||"__root__";r.expanded[n]=!r.expanded[n],k(r.items,!1),r.expanded[n]&&!c.value&&!r.loadedDirs[n]&&ge(e.rel||"")}}function k(e,n,s){if(z(),r.items=(e||[]).slice().sort(function(a,g){return String(a.rel||"").localeCompare(String(g.rel||""),void 0,{sensitivity:"base"})}),u.innerHTML="",r.visible=[],n){u.innerHTML='<div class="workspace-file-empty">加载中</div>';return}if(s){u.innerHTML='<div class="workspace-file-empty">'+String(s)+"</div>";return}if(!r.items.length){u.innerHTML='<div class="workspace-file-empty">没有匹配文件</div>';return}var d=ce(r.items);Q(d,!!c.value),r.visible=ue(d),r.visible.forEach(function(a,g){var i=a.node,m=document.createElement("button");m.type="button",m.className="workspace-file-item "+(a.type==="dir"?"workspace-file-dir-row":"workspace-file-file-row"),m.setAttribute("role","option"),m.setAttribute("data-row-index",String(g)),m.setAttribute("data-path-key",a.type==="dir"?L(i).path||L(i).rel||L(i).name||"":i.item.path||i.item.rel||i.item.name||"");var v=document.createElement("div");v.className="workspace-file-tree";var x=document.createElement("span");x.className="workspace-file-indent",x.style.setProperty("--indent",Math.min(a.depth,10)*.86+"rem");var T=document.createElement("span");T.className="workspace-file-chevron",T.textContent=a.type==="dir"?r.expanded[i.rel||"__root__"]?"▾":"▸":"",a.type==="dir"?(T.setAttribute("aria-label",r.expanded[i.rel||"__root__"]?"折叠文件夹":"展开文件夹"),T.setAttribute("role","button"),T.addEventListener("click",function(A){A.preventDefault(),A.stopPropagation(),fe(i)})):T.setAttribute("tabindex","-1");var O=document.createElement("span");O.className="workspace-file-icon"+(a.type==="file"?" is-file "+_(i.item&&i.item.name):" is-folder-svg"),a.type==="dir"&&(O.innerHTML=w);var D=document.createElement("div");D.className="workspace-file-name",D.textContent=i.name||i.rel||"";var q=document.createElement("div");q.className="workspace-file-meta",q.textContent=a.type==="dir"?"":ee(i.item.size),v.appendChild(x),v.appendChild(T),v.appendChild(O),v.appendChild(D);var Z=document.createElement("span");Z.className="workspace-file-check",m.appendChild(Z),m.appendChild(v),m.appendChild(q),m.addEventListener("mouseenter",function(){C(g)}),m.addEventListener("click",function(A){A.preventDefault(),A.stopPropagation(),a.type==="dir"?F(L(i)):F(i.item)}),u.appendChild(m)}),C(0),I()}function X(){var e=c.value||"";r.controller&&r.controller.abort(),r.controller=typeof AbortController<"u"?new AbortController:null,k(r.items,!0),U(e,"",r.controller?r.controller.signal:void 0).then(function(n){r.open&&(e?k(n,!1):(r.loadedDirs.__root__=!0,$(n),k(r.items,!1)))}).catch(function(n){n&&n.name==="AbortError"||r.open&&k([],!1,n&&n.message||"读取失败")})}function ge(e){var n=e||"__root__";r.loadedDirs[n]||(r.loadedDirs[n]=!0,U("",e||"",void 0).then(function(s){!r.open||c.value||($(s),k(r.items,!1))}).catch(function(){delete r.loadedDirs[n]}))}function me(){r.debounce&&clearTimeout(r.debounce),r.debounce=setTimeout(X,120)}function Y(){if(r.open){b();try{c.focus(),c.select()}catch{}return}r.open=!0,o.classList.add("is-open"),o.setAttribute("aria-hidden","false"),c.value="",r.expanded=Object.create(null),r.loadedDirs=Object.create(null),r.itemMap=Object.create(null),r.items=[],k([],!0),b(),X(),setTimeout(function(){b();try{c.focus()}catch{}},0)}function ve(){r.open?R():Y()}return c.addEventListener("input",me),c.addEventListener("keydown",function(e){if(e.key==="ArrowDown")e.preventDefault(),C(r.active+1);else if(e.key==="ArrowUp")e.preventDefault(),C(r.active-1);else if(e.key==="Enter"){e.preventDefault();var n=r.visible[r.active];n&&n.type==="dir"?F(L(n.node)):n&&n.type==="file"&&F(n.node.item)}else e.key==="Escape"&&(e.preventDefault(),R(),t.focus())}),document.addEventListener("click",function(e){r.open&&(o.contains(e.target)||R())}),window.addEventListener("resize",function(){r.open&&b()}),window.addEventListener("scroll",function(){r.open&&b()},!0),{panel:o,open:Y,close:R,toggle:ve}}function j(t,l,o){if(!t||t.dataset.pathBrowseWrapped==="1")return t;P();var c=document.createElement("div");c.className="path-input-row";var u=t.parentNode;if(!u)return t;u.insertBefore(c,t),c.appendChild(t);var f=document.createElement("button");f.type="button",f.className="path-browse-btn",f.innerHTML=w;var p=o||"浏览路径";return f.setAttribute("aria-label",p),typeof bindUiHoverTip=="function"?(f.setAttribute("data-ui-tip",p),f.removeAttribute("title"),bindUiHoverTip(f)):f.title=p,f.addEventListener("click",function(r){r.stopPropagation();var b=t.getAttribute("data-path-kind")||l;b!=="file"&&b!=="directory"&&(b="directory"),S(f,b,t.value||"",function(I){if(I){var C=Array.isArray(I)?I[0]||"":String(I);C&&(t.value=C,t.dispatchEvent(new Event("input",{bubbles:!0})),t.dispatchEvent(new Event("change",{bubbles:!0})))}})}),c.appendChild(f),t.dataset.pathBrowseWrapped="1",t}function te(t){var l=t.closest?t.closest(".input-wrapper"):t;!l||l.dataset.fileDropBound==="1"||(l.dataset.fileDropBound="1",["dragenter","dragover"].forEach(function(o){l.addEventListener(o,function(c){!c.dataTransfer||!c.dataTransfer.files||!c.dataTransfer.files.length||(c.preventDefault(),l.classList.add("is-drag-over"))})}),["dragleave","drop"].forEach(function(o){l.addEventListener(o,function(){l.classList.remove("is-drag-over")})}),l.addEventListener("drop",function(o){!o.dataTransfer||!o.dataTransfer.files||!o.dataTransfer.files.length||(o.preventDefault(),H(t,o.dataTransfer.files).catch(function(){}))}))}function re(t,l){if(!(!t||!l)){P(),te(l),t.classList.add("path-browse-btn","path-browse-btn--ghost"),t.innerHTML=w,t.setAttribute("aria-label","工作区文件"),t.setAttribute("data-ui-tip","工作区文件"),t.dataset.silentPickerUnavailable="1",t.removeAttribute("title");var o=document.createElement("input");o.type="file",o.multiple=!0,o.style.display="none",o.setAttribute("aria-hidden","true"),document.body.appendChild(o),o.addEventListener("change",function(){var u=o.files;!u||!u.length||(t.disabled=!0,H(l,u).finally(function(){o.value="",t.disabled=!1}))});var c=ne(l,function(){o.click()});t.addEventListener("click",function(u){if(u.stopPropagation(),u.preventDefault(),u.altKey){o.click();return}if(!u.shiftKey){c.toggle();return}var f=y&&typeof y.__WORK_DIR__=="string"?y.__WORK_DIR__:"";S(t,"file",f,function(p){var r=Array.isArray(p)?p:p?[p]:[];r.length&&B(l,r.map(function(b){return h(b)}).join(" "))},!1)})}}function M(t){t=t||document;for(var l=t.querySelectorAll("[data-path-kind]"),o=0;o<l.length;o++){var c=l[o],u=c.getAttribute("data-path-kind");(u==="file"||u==="directory")&&j(c,u)}}y.MyAgentPathPicker={pickPath:E,wrapInputWithBrowse:j,attachChatPicker:re,scan:M},document.readyState==="loading"?document.addEventListener("DOMContentLoaded",function(){M(document)}):M(document)})(typeof window<"u"?window:globalThis);const Se=`// ═══════════════════════════════════════════════════════════
// General Agent · 智能会话 — 完整逻辑
// ═══════════════════════════════════════════════════════════

const chatContainer = document.getElementById('chat-container');
const messageInput = document.getElementById('message-input');
const sendBtn = document.getElementById('send-btn');
const pickPathBtn = document.getElementById('pick-path-btn');
if (window.MyAgentPathPicker && pickPathBtn && messageInput) {
    MyAgentPathPicker.attachChatPicker(pickPathBtn, messageInput);
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
    var envAdv = document.getElementById('settings-env-advanced');
    if (envAdv) {
        envAdv.addEventListener('click', function () {
            closeSettingsModal();
            var w = window.open('/setup/env', 'myagent-env');
            if (w) {
                try { w.focus(); } catch (e) {}
            } else {
                window.location.href = '/setup/env';
            }
        });
    }
}
initUiSettingsControls();
`,he=`let currentSessionId = null;
/** Blocks repeat sends while the async send pipeline is claiming a sessionStore run slot. */
let sendPipelineLock = false;
let sendPipelineLockSessionId = null;
const followupQueueBySession = Object.create(null);
const followupQueueLoadedBySession = Object.create(null);
let followupQueueSeq = 1;
const followupQueueDraining = Object.create(null);
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

function renderUserMessageContent(wrap, div, rawStr, linkifier) {
    var applyLinks = typeof linkifier === 'function' ? linkifier : null;

    function setPlain() {
        div.textContent = rawStr;
        if (applyLinks) applyLinks(div);
    }

    function setCollapsed() {
        if (div.classList.contains('is-collapsible')) return;
        wrap.classList.add('has-turn-process');
        div.classList.add('is-collapsible');
        div.textContent = '';
        var sum = document.createElement('div');
        sum.className = 'user-msg-summary';
        sum.textContent = buildUserMessageSummary(rawStr);
        if (applyLinks) applyLinks(sum);
        var ful = document.createElement('div');
        ful.className = 'user-msg-full';
        ful.textContent = rawStr;
        if (applyLinks) applyLinks(ful);
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
`,be=`const sessionStore = {
    seq: 0,
    sessionsById: new Map(),
    sessionOrder: [],
    currentSessionId: null,
    runsBySession: new Map(),
    terminalRunIdsBySession: new Map(),
    activeRunInfoBySession: new Map(),
    archivedCount: 0,
    archivedLoaded: false,
    archivedSessions: null,
    unreadComplete: new Set(),
    sseSeqBySession: new Map(),
    deletedSessionTombstones: new Map(),
    ui: {
        loadingSessions: false,
        loadingMessages: false,
    },
    streamActiveById: Object.create(null),

    applySnapshot(sessions, archivedCount) {
        this.pruneDeletedSessionTombstones();
        const nextById = new Map();
        const nextOrder = [];
        const nextStreamActive = Object.create(null);
        const list = Array.isArray(sessions) ? sessions : [];
        let unreadChanged = false;
        for (let i = 0; i < list.length; i += 1) {
            const s = list[i];
            if (!s || !s.id) continue;
            const sid = String(s.id);
            if (this.isDeletedSessionTombstoned(sid)) continue;
            const nextSession = Object.assign({}, s);
            if (typeof isSessionStreamStopSuppressed === 'function' && isSessionStreamStopSuppressed(sid)) {
                nextSession.stream_active = false;
                nextSession.run_active = false;
                nextSession.run_started_at = null;
            }
            if (typeof sessionUnreadComplete !== 'undefined') {
                if (nextSession.unread_result) {
                    if (!sessionUnreadComplete.has(sid)) {
                        sessionUnreadComplete.add(sid);
                        unreadChanged = true;
                    }
                } else if (sessionUnreadComplete.delete(sid)) {
                    unreadChanged = true;
                }
            }
            nextById.set(sid, nextSession);
            nextOrder.push(sid);
            nextStreamActive[sid] = !!nextSession.stream_active;
        }
        this.sessionsById = nextById;
        this.sessionOrder = nextOrder;
        this.streamActiveById = nextStreamActive;
        if (Number.isFinite(Number(archivedCount)) && Number(archivedCount) >= 0) {
            this.archivedCount = Number(archivedCount);
        }
        if (unreadChanged && typeof persistSessionUnread === 'function') persistSessionUnread();
    },

    upsert(session) {
        if (!session || !session.id) return;
        const sid = String(session.id);
        if (this.isDeletedSessionTombstoned(sid)) return;
        this.sessionsById.set(sid, session);
        if (this.sessionOrder.indexOf(sid) < 0) this.sessionOrder.unshift(sid);
        if (Object.prototype.hasOwnProperty.call(session, 'stream_active')) {
            this.streamActiveById[sid] = !!session.stream_active;
        }
    },

    remove(sessionId) {
        const sid = String(sessionId || '');
        if (!sid) return;
        this.sessionsById.delete(sid);
        delete this.streamActiveById[sid];
        this.runsBySession.delete(sid);
        this.terminalRunIdsBySession.delete(sid);
        this.activeRunInfoBySession.delete(sid);
        this.unreadComplete.delete(sid);
        this.sessionOrder = this.sessionOrder.filter(function (id) { return id !== sid; });
    },

    markDeletedSession(sessionId) {
        const sid = String(sessionId || '');
        if (!sid) return;
        this.deletedSessionTombstones.set(sid, Date.now());
        this.remove(sid);
    },

    clearDeletedSessionTombstone(sessionId) {
        const sid = String(sessionId || '');
        if (!sid) return;
        this.deletedSessionTombstones.delete(sid);
    },

    pruneDeletedSessionTombstones() {
        const now = Date.now();
        const ttl = 120000;
        this.deletedSessionTombstones.forEach(function (createdAt, sid, map) {
            if (now - Number(createdAt || 0) > ttl) map.delete(sid);
        });
    },

    isDeletedSessionTombstoned(sessionId) {
        this.pruneDeletedSessionTombstones();
        return this.deletedSessionTombstones.has(String(sessionId || ''));
    },

    list() {
        const out = [];
        for (let i = 0; i < this.sessionOrder.length; i += 1) {
            const s = this.sessionsById.get(this.sessionOrder[i]);
            if (s) out.push(s);
        }
        return out;
    },

    get(sessionId) {
        return this.sessionsById.get(String(sessionId || '')) || null;
    },

    setCurrentSession(sessionId) {
        this.currentSessionId = sessionId ? String(sessionId) : null;
    },

    setArchivedCount(count) {
        if (Number.isFinite(Number(count)) && Number(count) >= 0) {
            this.archivedCount = Number(count);
        }
    },

    setArchivedLoaded(sessions) {
        const list = Array.isArray(sessions)
            ? sessions.filter(function (s) { return s && s.id && !!s.archived; })
            : [];
        this.archivedLoaded = true;
        this.archivedSessions = list;
        this.archivedCount = list.length;
    },

    clearArchivedLoaded() {
        this.archivedLoaded = false;
        this.archivedSessions = null;
    },

    archivedList() {
        return this.archivedLoaded && Array.isArray(this.archivedSessions) ? this.archivedSessions : [];
    },

    isStreamActive(sessionId) {
        const sid = String(sessionId || '');
        if (!sid) return false;
        if (Object.prototype.hasOwnProperty.call(this.streamActiveById, sid)) {
            return !!this.streamActiveById[sid];
        }
        const sess = this.get(sid);
        return !!(sess && sess.stream_active);
    },

    setStreamActive(sessionId, active) {
        const sid = String(sessionId || '');
        if (!sid) return;
        this.streamActiveById[sid] = !!active;
        const sess = this.sessionsById.get(sid);
        if (sess) sess.stream_active = !!active;
    },

    applyStreamActiveMap(activeMap) {
        const next = Object.create(null);
        const src = activeMap || {};
        Object.keys(src).forEach(function (sid) {
            next[String(sid)] = !!src[sid];
        });
        this.streamActiveById = next;
        this.sessionsById.forEach(function (sess, sid) {
            sess.stream_active = !!next[sid];
            sess.run_active = !!next[sid];
            if (!next[sid]) sess.run_started_at = null;
        });
    },

    setRun(sessionId, run) {
        const sid = String(sessionId || '');
        if (!sid) return;
        if (run) this.runsBySession.set(sid, run);
        else this.runsBySession.delete(sid);
    },

    getRun(sessionId) {
        return this.runsBySession.get(String(sessionId || '')) || null;
    },

    hasRun(sessionId) {
        return this.runsBySession.has(String(sessionId || ''));
    },

    markTerminalRun(sessionId, runId) {
        const sid = String(sessionId || '');
        const rid = String(runId || '').trim();
        if (!sid || !rid) return;
        let bucket = this.terminalRunIdsBySession.get(sid);
        if (!bucket) {
            bucket = new Set();
            this.terminalRunIdsBySession.set(sid, bucket);
        }
        bucket.add(rid);
    },

    isTerminalRun(sessionId, runId) {
        const sid = String(sessionId || '');
        const rid = String(runId || '').trim();
        if (!sid || !rid) return false;
        const bucket = this.terminalRunIdsBySession.get(sid);
        return !!(bucket && bucket.has(rid));
    },

    applyActiveRuns(activeRuns) {
        const next = new Map();
        const list = Array.isArray(activeRuns) ? activeRuns : [];
        list.forEach(function (run) {
            const sid = typeof run === 'string' ? run : (run && run.session_id);
            if (!sid) return;
            const runId = typeof run === 'string' ? '' : String((run && (run.run_id || run.runId)) || '').trim();
            if (runId && this.isTerminalRun(sid, runId)) return;
            if (typeof isSessionStreamStopSuppressed === 'function' && isSessionStreamStopSuppressed(sid)) return;
            next.set(String(sid), typeof run === 'string' ? { session_id: String(sid) } : Object.assign({}, run));
        }, this);
        this.activeRunInfoBySession = next;
    },

    activeRunIds() {
        return Array.from(this.activeRunInfoBySession.keys());
    },

    getActiveRunInfo(sessionId) {
        return this.activeRunInfoBySession.get(String(sessionId || '')) || null;
    },

    shouldAcceptSseEvent(sessionId, seq) {
        const sid = String(sessionId || '');
        const n = Number(seq);
        if (!sid || !Number.isFinite(n) || n <= 0) return true;
        const prev = Number(this.sseSeqBySession.get(sid) || 0);
        if (n <= prev) return false;
        this.sseSeqBySession.set(sid, n);
        if (Number.isFinite(Number(this.seq)) && n > Number(this.seq)) this.seq = n;
        return true;
    },

    resetSseSeq(sessionId) {
        const sid = String(sessionId || '');
        if (!sid) return;
        this.sseSeqBySession.delete(sid);
    },
};

const SESSION_STREAM_STOP_SUPPRESS_MS = 60000;
const sessionStreamStopSuppressUntil = Object.create(null);

function isSessionStreamStopSuppressed(sessionId) {
    const sid = String(sessionId || '');
    if (!sid) return false;
    const until = Number(sessionStreamStopSuppressUntil[sid] || 0);
    if (!until) return false;
    if (Date.now() <= until) return true;
    delete sessionStreamStopSuppressUntil[sid];
    return false;
}

function clearSessionStreamStopSuppress(sessionId) {
    const sid = String(sessionId || '');
    if (!sid) return;
    delete sessionStreamStopSuppressUntil[sid];
}

function suppressSessionServerStreamActive(sessionId, ms) {
    const sid = String(sessionId || '');
    if (!sid) return;
    sessionStreamStopSuppressUntil[sid] = Date.now() + (Number(ms) > 0 ? Number(ms) : SESSION_STREAM_STOP_SUPPRESS_MS);
    sessionStore.setStreamActive(sid, false);
    sessionStore.activeRunInfoBySession.delete(sid);
    const sess = sessionStore.get(sid);
    if (sess) {
        sess.stream_active = false;
        sess.run_active = false;
        sess.run_started_at = null;
    }
}

function setSessionServerStreamActive(sessionId, active) {
    const sid = String(sessionId || '');
    if (!sid) return;
    if (active && isSessionStreamStopSuppressed(sid)) active = false;
    sessionStore.setStreamActive(sid, !!active);
}

function isServerStreamActive(sessionId) {
    const sid = String(sessionId || '');
    if (!sid) return false;
    if (isSessionStreamStopSuppressed(sid)) return false;
    return sessionStore.isStreamActive(sid);
}

function applyServerStreamActiveMap(activeMap) {
    const src = activeMap || Object.create(null);
    const m = Object.create(null);
    Object.keys(src).forEach(function (sid) {
        var active = !!src[sid];
        if (active && isSessionStreamStopSuppressed(sid)) active = false;
        m[sid] = active;
    });
    sessionStore.applyStreamActiveMap(m);
}
`,ye=`function selectCurrentSession() {
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
    return sessionStore.archivedLoaded ? selectArchivedSessions().length : sessionStore.archivedCount;
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
`,Ie=`function applySessionSnapshot(snapshot) {
    snapshot = snapshot || {};
    const sessions = Array.isArray(snapshot.sessions) ? snapshot.sessions : [];
    const archivedCount = snapshot.archived_count != null ? snapshot.archived_count : snapshot.archivedCount;
    if (Number.isFinite(Number(snapshot.seq)) && Number(snapshot.seq) > sessionStore.seq) {
        sessionStore.seq = Number(snapshot.seq);
    }
    sessionStore.applySnapshot(sessions, archivedCount);
    if (sessionStore.archivedLoaded && (snapshot.include_archived || snapshot.includeArchived)) {
        sessionStore.setArchivedLoaded(sessions);
    }
    if (snapshot.current_session_id || snapshot.currentSessionId) {
        sessionStore.setCurrentSession(snapshot.current_session_id || snapshot.currentSessionId);
    }
    if (Array.isArray(snapshot.active_runs)) {
        sessionStore.applyActiveRuns(snapshot.active_runs);
        const active = Object.create(null);
        sessionStore.activeRunInfoBySession.forEach(function (_run, sid) {
            if (sid) active[String(sid)] = true;
        });
        applyServerStreamActiveMap(active);
    }
}

function applySessionPatch(patch) {
    patch = patch || {};
    if (Number.isFinite(Number(patch.seq)) && Number(patch.seq) <= sessionStore.seq) return;
    if (Number.isFinite(Number(patch.seq))) sessionStore.seq = Number(patch.seq);
    if (patch.session) sessionStore.upsert(patch.session);
    if (patch.remove_session_id || patch.removedSessionId) {
        sessionStore.remove(patch.remove_session_id || patch.removedSessionId);
    }
    if (patch.current_session_id || patch.currentSessionId) {
        sessionStore.setCurrentSession(patch.current_session_id || patch.currentSessionId);
    }
    if (patch.archived_count != null || patch.archivedCount != null) {
        sessionStore.setArchivedCount(patch.archived_count != null ? patch.archived_count : patch.archivedCount);
    }
    if (patch.stream_active != null && (patch.session_id || patch.sessionId)) {
        setSessionServerStreamActive(patch.session_id || patch.sessionId, !!patch.stream_active);
    }
}

function setCurrentSessionState(sessionId) {
    currentSessionId = sessionId || null;
    sessionStore.setCurrentSession(currentSessionId);
}

function setSessionRunState(sessionId, run) {
    const sid = String(sessionId || '');
    if (!sid) return;
    sessionStore.setRun(sid, run || null);
}

function getSessionRunState(sessionId) {
    const sid = String(sessionId || '');
    if (!sid) return null;
    return sessionStore.getRun(sid) || null;
}

function clearSessionRunState(sessionId) {
    setSessionRunState(sessionId, null);
}

function markSessionRunInactive(sessionId) {
    const sid = String(sessionId || '');
    if (!sid) return;
    setSessionServerStreamActive(sid, false);
    sessionStore.activeRunInfoBySession.delete(sid);
    const sess = sessionStore.get(sid);
    if (sess) {
        sess.run_active = false;
        sess.run_started_at = null;
        sess.stream_active = false;
    }
}

function markRunAbortReason(run, reason) {
    if (!run) return;
    var r = reason || 'cleanup';
    run.abortReason = r;
    if (run.ctx) run.ctx.abortReason = r;
}

function getRunAbortReason(sessionId, ctx) {
    const run = getSessionRunState(sessionId);
    return (run && run.abortReason) || (ctx && ctx.abortReason) || '';
}

function abortSessionRun(sessionId, reason, opts) {
    opts = opts || {};
    const run = getSessionRunState(sessionId);
    if (!run) return null;
    markRunAbortReason(run, reason || 'cleanup');
    try { if (run.controller) run.controller.abort(); } catch (e) { /* ignore */ }
    if (opts.clear !== false) clearSessionRunState(sessionId);
    return run;
}
`,xe=`function renderSessionListFromStore() {
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
        if (sectionKey === 'archived') appendArchiveLoadButton(body);
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
    loadBtn.textContent = sessionStore.archivedLoaded ? '刷新归档目录' : '加载归档目录';
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
            loadBtn.textContent = sessionStore.archivedLoaded ? '刷新归档目录' : '加载归档目录';
        }
    });
    body.appendChild(loadBtn);
}

function renderSessionTitleFromStore() {
    updateSessionTitle();
}
`,we=`const messageStore = {
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
`,Ce=`function renderMessageRecord(ctx, record, sessionId) {
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
`,ke=`const subagentStore = {
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
`,Te=`var subagentContinueInFlight = false;
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
    banner.classList.add('is-on');
}

async function fetchSubagentContinueState(sessionId) {
    if (!sessionId) return { pending: 0, running: 0, can_continue: false };
    try {
        var r = await fetch('/sessions/' + encodeURIComponent(sessionId) + '?include_subagents=true');
        if (!r.ok) return { pending: 0, running: 0, can_continue: false };
        var j = await r.json();
        return {
            pending: Number(j.subagent_pending_continue || 0),
            running: Number(j.subagent_running || 0),
            can_continue: !!j.subagent_can_continue,
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
`,Ee=`function setSubagentCardEventCount(agentId, count) {
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
`,_e=`function subagentMoreDotsHtml() {
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
        div.innerHTML = renderMarkdown(rawStr);
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
    if (existing) {
        var msgEl = existing.querySelector('.message.assistant');
        if (msgEl) {
            msgEl.innerHTML = renderMarkdown(txt);
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
`,Le=`var subagentBodyHtmlCache = Object.create(null);

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
`,Ae=`var subagentCardViewportObserver = null;
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

async function loadSubagentDetailInto(el, agentId, hostEl, sessionIdOpt) {
    if (!el || !agentId) return;
    if (el.dataset.loading === '1') return;
    var card = hostEl || (el.closest ? el.closest('.subagent-grid-card, .subagent-block') : null);
    el.dataset.loading = '1';
    delete el.dataset.loaded;
    el.innerHTML = '<div class="subagent-detail-empty">加载详情中…</div>';
    try {
        var isCollapsed = card && card.classList && !card.classList.contains('is-expanded') && card.classList.contains('subagent-grid-card');
        var turnsParam = isCollapsed ? '&turns=3' : '&turns=10';
        var resp = await fetch('/sessions/' + encodeURIComponent(agentId) + '/messages?' + turnsParam);
        if (!resp.ok) throw new Error('HTTP ' + resp.status);
        var data = await resp.json();

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
`,Pe=`var subagentCardSyncTimer = null;
var subagentContextFetchInFlight = Object.create(null);
var subagentTreeRefreshTimer = null;
var subagentTreeRefreshTarget = null;
var subagentTreeRefreshInflight = null;
var subagentTreeRefreshInflightSid = null;
var subagentTreeRefreshQueued = false;
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
    subagentTreeRefreshQueued = false;
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
        var countResp = await fetch('/sessions/' + encodeURIComponent(agentId) + '/messages/count');
        if (!countResp.ok) return;
        var countData = await countResp.json();
        var total = countData && countData.count != null ? Number(countData.count) : 0;
        if (!Number.isFinite(total) || total <= prevCount) return;
        if (parentRunning && body.dataset.loaded === '1') {
            setSubagentCardEventCount(agentId, total);
            return;
        }
        var msgResp = await fetch('/sessions/' + encodeURIComponent(agentId) + '/messages');
        if (!msgResp.ok) return;
        var events = normalizeSubagentMessagesPayload(await msgResp.json());
        if (!body.isConnected) return;
        if (events.length <= prevCount) {
            setSubagentCardEventCount(agentId, events.length);
            return;
        }
        var gotFinal = false;
        for (var fi = prevCount; fi < events.length; fi += 1) {
            if (events[fi] && events[fi].type === 'final') { gotFinal = true; break; }
        }
        if (body.dataset.loaded !== '1') {
            if (!shouldLoadSubagentCardBodies()) return;
            if (summaryOnly) {
                ensureSubagentCardStreamReady(card, agentId);
                var ctxNew = getSubagentCardStreamCtx(body, card, agentId);
                for (var si = prevCount; si < events.length; si += 1) {
                    var sev = events[si];
                    if (!sev || typeof sev !== 'object') continue;
                    if (sev.type !== 'user' && sev.type !== 'final') continue;
                    dispatchSubagentCardEvent(ctxNew, card, sev, si, agentId);
                }
                rebindSubagentCardBody(body, card, agentId);
            } else {
                renderSubagentProcessEvents(body, card, events, agentId);
            }
            setSubagentCardEventCount(agentId, events.length);
            if (gotFinal) markSubagentCardCompleted(card, true);
            return;
        }
        var ctx = getSubagentCardStreamCtx(body, card, agentId);
        for (var i = prevCount; i < events.length; i += 1) {
            if (events[i] && typeof events[i] === 'object') {
                if (summaryOnly && events[i].type !== 'user' && events[i].type !== 'final' && !events[i].ephemeral) continue;
                dispatchSubagentCardEvent(ctx, card, events[i], i, agentId);
            }
        }
        rebindSubagentCardBody(body, card, agentId);
        setSubagentCardEventCount(agentId, events.length);
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
    if (subagentTreeRefreshInflight && subagentTreeRefreshInflightSid === sessionId) {
        subagentTreeRefreshQueued = true;
        return subagentTreeRefreshInflight;
    }
    subagentTreeRefreshInflightSid = sessionId;
    subagentTreeRefreshInflight = refreshSubagentTreePanelInner(sessionId);
    try {
        return await subagentTreeRefreshInflight;
    } finally {
        subagentTreeRefreshInflight = null;
        subagentTreeRefreshInflightSid = null;
        if (subagentTreeRefreshQueued && sessionId === currentSessionId) {
            subagentTreeRefreshQueued = false;
            void refreshSubagentTreePanel(currentSessionId);
        }
    }
}

async function refreshSubagentTreePanelInner(sessionId) {
    bindSubagentPanelOnce();
    var seq = ++subagentPanelRefreshSeq;
    var grid = document.getElementById('subagent-grid');
    var toggleBtn = document.getElementById('subagent-toggle-btn');
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
        if (toggleBtn) toggleBtn.classList.add('hidden');
        closeSubagentPanel();
        stopSubagentIncrementalSync();
    }
}
`,Re=`async function toggleSubagentOutputPanel(card, sessionId) {
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
`,Fe=`function onSubagentDockWheel(e) {
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
`,Be=`const contextStore = {
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
`,Me=`function markUiEventStoreApplied(event) {
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
    if (sessionId) {
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
        if (type === 'run_finished' && typeof clearSessionStreamStopSuppress === 'function') clearSessionStreamStopSuppress(sessionId);
        markSessionRunInactive(sessionId);
        const sess = sessionStore.get(sessionId);
        if (sess) {
            const keepFailed = sess.unread_result_status === 'failed';
            sess.unread_result = true;
            sess.unread_result_status = (keepFailed || type === 'run_interrupted' || type === 'run_failed') ? 'failed' : 'success';
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
`,Ne=`let modelProfilesCache = null;
let modelProfilesRefreshPromise = null;
let modelProfileBusy = false;
let activeModelProfileId = '__env__';

function h(str) {
    return String(str == null ? '' : str)
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#39;');
}

function profileLabel(profile) {
    if (!profile) return '默认方案';
    return String(profile.name || profile.model || '未命名方案');
}

function profileMeta(profile) {
    if (!profile) return '';
    var model = profile.model || '';
    var ctx = profile.context_window ? profile.context_window + ' ctx' : '';
    var out = profile.max_output_tokens ? profile.max_output_tokens + ' out' : '';
    return [model, ctx, out].filter(Boolean).join(' · ');
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

function allProfiles() {
    if (!modelProfilesCache) return [];
    var defaultProfile = modelProfilesCache.default_profile || { id: '__env__', name: '', model: '' };
    var profiles = modelProfilesCache.profiles || [];
    return profiles.length ? profiles : [defaultProfile];
}

function activeProfile() {
    var list = allProfiles();
    for (var i = 0; i < list.length; i += 1) {
        if (String(list[i].id || '__env__') === String(activeModelProfileId || '__env__')) return list[i];
    }
    return list[0] || null;
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
    e.menu.classList.add('is-open');
    e.trigger.classList.add('is-open');
    e.trigger.setAttribute('aria-expanded', 'true');
}

function renderModelProfileControl() {
    var e = els();
    if (!e.trigger || !e.current || !e.menu) return;
    var active = activeProfile();
    e.current.textContent = active ? profileLabel(active) : '未加载模型配置';
    e.trigger.removeAttribute('title');
    e.trigger.removeAttribute('data-ui-tip');
    var profiles = allProfiles();
    if (!profiles.length) {
        e.menu.innerHTML = '<button type="button" class="composer-model-option" disabled><span class="composer-model-option-name">没有可用模型配置</span></button>';
        return;
    }
    var html = '';
    for (var i = 0; i < profiles.length; i += 1) {
        var p = profiles[i] || {};
        var id = String(p.id || '__env__');
        var activeCls = id === String(activeModelProfileId || '__env__') ? ' is-active' : '';
        html += '<button type="button" class="composer-model-option' + activeCls + '" role="option" data-profile-id="' + h(id) + '">'
            + '<span class="composer-model-option-name">' + h(profileLabel(p)) + '</span>'
            + '<span class="composer-model-option-meta">' + h(profileMeta(p) || (id === '__env__' ? (p.model || '') : '')) + '</span>'
            + '</button>';
    }
    if (!(modelProfilesCache.profiles || []).length) {
        html += '<button type="button" class="composer-model-option" disabled><span class="composer-model-option-meta">暂无已保存模型配置，可到高级设置中保存</span></button>';
    }
    e.menu.innerHTML = html;
    e.menu.querySelectorAll('[data-profile-id]').forEach((btn) => {
        btn.addEventListener('click', () => {
            setCurrentSessionModelProfile(btn.getAttribute('data-profile-id') || '__env__');
            closeModelMenu();
        });
    });
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
    var sid = sessionId || currentSessionId;
    var e = els();
    opts = opts || {};
    if (!e.control) return;
    if (!opts.silent && e.current) e.current.textContent = '正在加载模型配置';
    try {
        await loadModelProfilesForSwitcher();
        activeModelProfileId = modelProfilesCache.new_session_default_profile_id || '__env__';
        if (sid) {
            var r = await fetch('/sessions/' + encodeURIComponent(sid) + '/model_profile', { credentials: 'same-origin' });
            var j = await r.json();
            if (j && j.ok && j.profile_id) activeModelProfileId = j.profile_id;
        }
        renderModelProfileControl();
    } catch (err) {
        if (e.current) e.current.textContent = '模型配置加载失败';
        if (e.menu) e.menu.innerHTML = '<button type="button" class="composer-model-option" disabled><span class="composer-model-option-name">模型配置加载失败</span><span class="composer-model-option-meta">' + h(err.message || err) + '</span></button>';
    }
}

function refreshModelProfileSelectorInBackground(sessionId, opts) {
    if (modelProfilesRefreshPromise) return modelProfilesRefreshPromise;
    modelProfilesRefreshPromise = refreshModelProfileSelector(sessionId, opts)
        .catch(function (err) {
            console.error('refresh model profiles failed:', err);
        })
        .finally(function () {
            modelProfilesRefreshPromise = null;
        });
    return modelProfilesRefreshPromise;
}

async function setCurrentSessionModelProfile(profileId) {
    if (!currentSessionId || modelProfileBusy) return;
    modelProfileBusy = true;
    try {
        var response = await fetch('/sessions/' + encodeURIComponent(currentSessionId) + '/model_profile', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            credentials: 'same-origin',
            body: JSON.stringify({ profile_id: profileId || '__env__' }),
        });
        var data = await response.json();
        if (!data || !data.ok) throw new Error((data && data.error) || '切换失败');
        activeModelProfileId = profileId || '__env__';
        renderModelProfileControl();
        scheduleContextTokensAfterPaint(currentSessionId);
    } catch (err) {
        appendLogVisible('模型配置切换失败: ' + String(err.message || err), 'error-log');
        await refreshModelProfileSelector(currentSessionId);
    } finally {
        modelProfileBusy = false;
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
    refreshModelProfileSelectorInBackground(currentSessionId);
}

initModelProfileSwitcher();
window.refreshModelProfileSelector = refreshModelProfileSelector;
window.loadModelProfilesForSwitcher = loadModelProfilesForSwitcher;
`,Oe=`function formatTokenCompact(n) {
    if (n == null || !Number.isFinite(Number(n))) return '—';
    const x = Math.max(0, Math.round(Number(n)));
    if (x >= 1000000) return (x / 1000000).toFixed(1).replace(/\\.0$/, '') + 'M';
    if (x >= 10000) return (x / 1000).toFixed(x % 1000 === 0 ? 0 : 1).replace(/\\.0$/, '') + 'k';
    if (x >= 1000) return (x / 1000).toFixed(1).replace(/\\.0$/, '') + 'k';
    return String(x);
}

function setContextTokenLabel(estimated, threshold) {
    const el = document.getElementById('ctx-tokens');
    if (!el) return;
    const label = el.querySelector('.ctx-label');
    const fill = el.querySelector('.ctx-fill');
    const pctEl = el.querySelector('.ctx-pct');
    const t = (threshold != null && Number(threshold) > 0) ? Number(threshold) : defaultCtxThreshold;
    const n = (estimated != null && Number(estimated) >= 0) ? Math.round(Number(estimated)) : null;
    if (n == null) {
        if (label) label.textContent = '— / —';
        if (pctEl) pctEl.textContent = '';
        if (fill) fill.style.width = '0%';
        el.classList.remove('is-warn', 'is-bad');
        el.setAttribute('data-ui-tip', '预估上下文 token：选择会话并加载或发送消息后显示。分母为压缩摘要阈值。');
        bindUiHoverTip(el);
        return;
    }
    const pct = (n / t) * 100;
    const pctDisp = (Math.round(pct * 10) / 10);
    if (label) label.textContent = formatTokenCompact(n) + ' / ' + formatTokenCompact(t);
    if (pctEl) pctEl.textContent = pctDisp + '%';
    if (fill) fill.style.width = Math.min(100, pct) + '%';
    el.classList.remove('is-warn', 'is-bad');
    if (pct >= 100) el.classList.add('is-bad');
    else if (pct >= 80) el.classList.add('is-warn');
    var tipPct = pct >= 100
        ? ('约 ' + pctDisp + '%，超出门限 ' + (Math.round((pct - 100) * 10) / 10) + '%')
        : ('约 ' + pctDisp + '%');
    el.setAttribute(
        'data-ui-tip',
        formatTokenCompact(n) + ' / ' + formatTokenCompact(t) + ' tokens（' + tipPct
            + '）。预估进入模型的上下文规模，含历史与系统提示；分母为触发压缩摘要的门限，可在.env文件中 CONTEXT_WINDOW 修改。'
    );
    bindUiHoverTip(el);
}

let contextTokenRequestSeq = 0;
const contextTokenInFlightBySession = Object.create(null);
const CONTEXT_TOKEN_CACHE_TTL_MS = 3000;

async function refreshContextTokensFromServer(sid, seq) {
    if (!sid) return;
    const cached = selectContextTokens(sid);
    if (cached && cached.updatedAt && (Date.now() - cached.updatedAt) < CONTEXT_TOKEN_CACHE_TTL_MS) {
        if (sid === currentSessionId) setContextTokenLabel(cached.estimated, cached.threshold);
        return;
    }
    if (contextTokenInFlightBySession[sid]) return;
    contextTokenInFlightBySession[sid] = true;
    try {
        const r = await fetch('/sessions/' + encodeURIComponent(sid) + '/context_tokens');
        const j = await r.json();
        if (seq != null && seq !== contextTokenRequestSeq) return;
        if (sid !== currentSessionId) return;
        if (r.ok && j && j.ok && j.estimated != null && j.estimated >= 0) {
            recordContextTokens(sid, j.estimated, j.threshold);
            return;
        }
    } catch (e) { /* ignore */ }
    finally {
        delete contextTokenInFlightBySession[sid];
    }
    applyContextTokenLabelForCurrentSession();
}

/** 在浏览器完成首帧绘制后再请求 context_tokens，避免与切换会话/新建会话的 DOM 抢主线程。 */
function scheduleContextTokensAfterPaint(sid) {
    if (!sid) return;
    const seq = ++contextTokenRequestSeq;
    requestAnimationFrame(function () {
        requestAnimationFrame(function () {
            refreshContextTokensFromServer(sid, seq);
        });
    });
}

function recordContextTokens(sessionId, estimated, threshold) {
    if (!sessionId) return;
    setContextTokensForSession(sessionId, estimated, threshold);
    if (sessionId === currentSessionId) setContextTokenLabel(estimated, threshold);
}

function applyContextTokenLabelForCurrentSession() {
    if (!currentSessionId) { setContextTokenLabel(null, null); return; }
    const x = selectContextTokens(currentSessionId);
    if (x) setContextTokenLabel(x.estimated, x.threshold);
    else setContextTokenLabel(null, null);
}

/** 主对话区跟到底 */
function scrollChatToBottomIfFollow(runSessionId, opts) {
    opts = opts || {};
    if (shouldGateScrollByRunSession(null, runSessionId)) return;
    if (!opts.force && !liveAutoFollow) return;
    if (chatContainer) chatContainer.scrollTop = chatContainer.scrollHeight;
}

function setScrollTopImmediate(el, y) {
    if (!el) return;
    var prev = el.style.scrollBehavior;
    el.style.scrollBehavior = 'auto';
    el.scrollTop = y;
    requestAnimationFrame(function () {
        if (el) el.style.scrollBehavior = prev;
    });
}

/** 当前运行会话对应的执行过程框滚动容器（.process-aggregate-body） */
function getProcessBodyElForCurrentRun() {
    var sid = currentSessionId;
    var run = sid && getSessionRunState(sid);
    if (!run || !run.ctx) return null;
    var c = run.ctx;
    if (c.currentProcessGroup && c.currentProcessGroup.isConnected) {
        return c.currentProcessGroup.querySelector('.process-aggregate-body');
    }
    if (!c.stream) return null;
    var agg = c.stream.querySelector('.process-aggregate:last-of-type');
    return agg ? agg.querySelector('.process-aggregate-body') : null;
}

var STREAM_PROC_NEAR_BOTTOM_PX = 96;
var STREAM_CHAT_NEAR_BOTTOM_PX = 72;

/** 生成中时：对话区与当前执行过程区均在底部附近时才允许自动跟随流式滚动 */
function refreshLiveAutoFollowPins() {
    if (!chatContainer) return;
    if (isSessionRunning(currentSessionId)) {
        streamChatNearBottom = isNearBottom(chatContainer, STREAM_CHAT_NEAR_BOTTOM_PX);
        var pb = getProcessBodyElForCurrentRun();
        streamProcNearBottom = !pb || isNearBottom(pb, STREAM_PROC_NEAR_BOTTOM_PX);
        liveAutoFollow = streamChatNearBottom && streamProcNearBottom;
    } else {
        liveAutoFollow = isNearBottom(chatContainer, STREAM_CHAT_NEAR_BOTTOM_PX);
    }
}

function isSubagentStreamCtx(ctx) {
    if (!ctx) return false;
    if (ctx._subagentBody && ctx._subagentBody.isConnected) return true;
    if (ctx.currentProcessGroup && ctx.currentProcessGroup.isConnected
        && ctx.currentProcessGroup.classList.contains('subagent-grid-card')) return true;
    return false;
}

/** 子 agent 卡片流式更新用 agentId 作 runSessionId，不能按主会话 currentSessionId 拦截滚动 */
function shouldGateScrollByRunSession(ctx, runSessionId) {
    if (!runSessionId) return false;
    if (isSubagentStreamCtx(ctx)) return false;
    return runSessionId !== currentSessionId;
}

function collectFeedChunkRootsFromCtx(ctx) {
    var roots = [];
    var seen = new Set();
    function addRoot(root) {
        if (!root || !root.isConnected || seen.has(root)) return;
        seen.add(root);
        roots.push(root);
    }
    if (ctx && ctx.stream && ctx.stream.isConnected) addRoot(ctx.stream);
    if (ctx && ctx._subagentTurnProcess) addRoot(ctx._subagentTurnProcess);
    if (ctx && ctx._subagentBody) addRoot(ctx._subagentBody);
    return roots;
}

function queryFeedChunksInCtx(ctx, selector) {
    var sel = selector || '.feed-chunk';
    var out = [];
    var seen = new Set();
    collectFeedChunkRootsFromCtx(ctx).forEach(function (root) {
        root.querySelectorAll(sel).forEach(function (ch) {
            if (!seen.has(ch)) {
                seen.add(ch);
                out.push(ch);
            }
        });
    });
    return out;
}

function refreshFeedChunksInCtx(ctx, selector) {
    queryFeedChunksInCtx(ctx, selector).forEach(function (ch) {
        scheduleFeedChunkOverflowRefresh(ch);
    });
}

function ensureSubagentTurnProcessOpen(ctx) {
    /* 默认折叠执行过程，不在自动滚动时强制展开 */
}

function shouldDeferSubagentProcessDom(ctx) {
    if (!ctx || !ctx.currentTurn || !ctx.currentTurn.isConnected) return true;
    return !ctx.currentTurn.classList.contains('is-process-open');
}

function deferSubagentProcessEvent(turn, event, eventIndex) {
    if (!turn || !event) return;
    if (!turn._deferredProcessEvents) turn._deferredProcessEvents = [];
    turn._deferredProcessEvents.push({ event: event, eventIndex: eventIndex });
    turn.dataset.processDeferred = '1';
}

function pinSubagentCardScrollForManualExpand(body) {
    if (!body) return { savedScroll: 0, release: function () {} };
    var ctx = body._subagentStreamCtx;
    var savedScroll = body.scrollTop;
    if (ctx) ctx._suppressSubagentScrollFollow = true;
    return {
        savedScroll: savedScroll,
        release: function () {
            if (ctx) ctx._suppressSubagentScrollFollow = false;
        },
        restoreScroll: function () {
            if (body.isConnected) body.scrollTop = savedScroll;
        }
    };
}

function restoreSubagentCardScrollAfterLayout(body, savedScroll) {
    if (!body) return;
    requestAnimationFrame(function () {
        requestAnimationFrame(function () {
            if (body.isConnected) body.scrollTop = savedScroll;
        });
    });
}

var SUBAGENT_PROCESS_HYDRATE_BATCH = 24;
var SUBAGENT_PROCESS_REFRESH_CHUNK_LIMIT = 80;

function runSubagentProcessBatch(fn) {
    if (typeof requestIdleCallback === 'function') {
        requestIdleCallback(fn, { timeout: 120 });
    } else {
        requestAnimationFrame(fn);
    }
}

function refreshSubagentProcessChunksLightly(turn) {
    if (!turn || !turn.querySelectorAll) return;
    var chunks = turn.querySelectorAll('.feed-chunk');
    var limit = Math.min(chunks.length, SUBAGENT_PROCESS_REFRESH_CHUNK_LIMIT);
    for (var i = 0; i < limit; i += 1) {
        scheduleFeedChunkOverflowRefresh(chunks[i]);
    }
}

function hydrateSubagentTurnProcess(turn, ctx, agentId) {
    if (!turn || !ctx) return;
    var processEl = turn.querySelector('.subagent-turn-process');
    if (turn.dataset.processHydrated === '1' && processEl && processEl.children.length) return;
    var items = turn._deferredProcessEvents;
    if (!items || !items.length) {
        turn.dataset.processHydrated = '1';
        return;
    }
    var body = ctx._subagentBody;
    var pin = pinSubagentCardScrollForManualExpand(body);
    ctx.currentTurn = turn;
    ctx._subagentTurnProcess = processEl;
    ctx._subagentTurnFinalSlot = turn.querySelector('.subagent-turn-final-slot');
    resetLlmState(ctx);
    finalizeProgressStreamChunks(ctx);
    function replayDeferredProcessEvent(item) {
        var ev = item && item.event;
        if (!ev || typeof ev !== 'object') return;
        if (shouldSkipSubagentProcessEvent(ev)) return;
        if (ev.ephemeral) {
            if (ev.type === 'llm_reasoning_delta' || ev.type === 'llm_response_delta') {
                appendLlmStreamDelta(ctx, ev, agentId);
            } else if (ev.type === 'context_summary_delta') {
                appendProgressStreamDelta(ctx, ev.delta, 'context-summary', agentId);
            } else if (ev.type === 'key_context_delta') {
                appendKeyContextStreamDelta(ctx, ev.delta, agentId);
            } else if (ev.type === 'context_tokens' || ev.type === 'process_metrics' || ev.type === 'cache_stats') {
                /* metrics 类事件只更新卡片统计，不在展开过程里落一条“信息”。 */
            }
            return;
        }
        reduceAndRenderMessageEvent(ctx, ev, {
            sessionId: agentId,
            eventIndex: item.eventIndex,
            source: 'subagent-history',
        });
    }
    var index = 0;
    turn.dataset.processLoading = '1';
    function finishHydrate() {
        finalizeLlmStreamChunks(ctx);
        finalizeProgressStreamChunks(ctx);
        delete turn._deferredProcessEvents;
        delete turn.dataset.processDeferred;
        delete turn.dataset.processLoading;
        turn.dataset.processHydrated = '1';
        markSubagentTurnHasProcess(turn);
        refreshSubagentProcessChunksLightly(turn);
        pin.release();
        restoreSubagentCardScrollAfterLayout(body, pin.savedScroll);
    }
    function step() {
        if (!turn.isConnected || !body || !body.isConnected) {
            delete turn.dataset.processLoading;
            pin.release();
            return;
        }
        var end = Math.min(index + SUBAGENT_PROCESS_HYDRATE_BATCH, items.length);
        for (; index < end; index += 1) {
            replayDeferredProcessEvent(items[index]);
        }
        if (index < items.length) {
            runSubagentProcessBatch(step);
        } else {
            finishHydrate();
        }
    }
    step();
}

function repairMisplacedSubagentFeedItems(body, turn) {
    if (!body || !turn) return;
    var proc = turn.querySelector('.subagent-turn-process');
    if (!proc) return;
    Array.prototype.slice.call(body.children).forEach(function (node) {
        if (!node || !node.classList || !node.classList.contains('feed-item')) return;
        proc.appendChild(node);
    });
}

function collectSubagentTurnProcessSlice(events, userEventIndex) {
    var slice = [];
    if (!events || !events.length || !Number.isFinite(userEventIndex) || userEventIndex < 0) return slice;
    for (var i = userEventIndex + 1; i < events.length; i += 1) {
        var ev = events[i];
        if (!ev || typeof ev !== 'object') continue;
        var t = ev.type;
        if (t === 'user') break;
        if (t === 'final') break;
        if (t === 'subagent_start' || t === 'subagent_finish') continue;
        if (shouldSkipSubagentProcessEvent(ev)) continue;
        slice.push({ event: ev, eventIndex: i });
    }
    return slice;
}

async function fetchAndHydrateSubagentTurnProcess(turn, body) {
    if (!turn || !body || turn.dataset.processLoading === '1' || turn.dataset.processFetching === '1') return;
    var card = body.closest('.subagent-grid-card');
    var agentId = (card && card.getAttribute('data-agent-id')) || body.getAttribute('data-agent-id') || '';
    if (!agentId) return;
    var userWrap = turn.querySelector('.msg-wrap--user');
    var userIdx = userWrap ? parseInt(userWrap.getAttribute('data-event-index') || '-1', 10) : -1;
    if (!Number.isFinite(userIdx) || userIdx < 0) return;
    var pin = pinSubagentCardScrollForManualExpand(body);
    turn.dataset.processFetching = '1';
    try {
        var resp = await fetch('/sessions/' + encodeURIComponent(agentId) + '/messages');
        if (!resp.ok) return;
        var events = normalizeSubagentMessagesPayload(await resp.json());
        if (!turn.isConnected) return;
        turn._deferredProcessEvents = collectSubagentTurnProcessSlice(events, userIdx);
        delete turn.dataset.processHydrated;
        hydrateSubagentTurnProcessFromEl(turn, body);
    } catch (e) { /* ignore */ }
    finally {
        delete turn.dataset.processFetching;
        pin.release();
        restoreSubagentCardScrollAfterLayout(body, pin.savedScroll);
    }
}

function ensureSubagentTurnProcessContent(turn, body) {
    if (!turn || !body) return;
    repairMisplacedSubagentFeedItems(body, turn);
    var processEl = turn.querySelector('.subagent-turn-process');
    if (processEl && processEl.children.length) return;
    if (turn._deferredProcessEvents && turn._deferredProcessEvents.length) {
        hydrateSubagentTurnProcessFromEl(turn, body);
        return;
    }
    if (turn.dataset.processDeferred === '1' || turn.querySelector('.msg-wrap--user.has-turn-process')) {
        void fetchAndHydrateSubagentTurnProcess(turn, body);
    }
}

function toggleSubagentTurnProcess(turn, body, userWrap) {
    if (!turn || !body || !userWrap) return;
    var open = !turn.classList.contains('is-process-open');
    turn.classList.toggle('is-process-open', open);
    userWrap.classList.toggle('is-process-open', open);
    delete body.dataset.cacheClean;
    if (open) {
        ensureSubagentTurnProcessContent(turn, body);
        refreshSubagentProcessChunksLightly(turn);
        return;
    }
}

function hydrateSubagentTurnProcessFromEl(turn, body) {
    if (!turn || !body) return;
    var card = body.closest('.subagent-grid-card');
    var agentId = (card && card.getAttribute('data-agent-id')) || body.getAttribute('data-agent-id') || '';
    var ctx = body._subagentStreamCtx || (agentId && card ? getSubagentCardStreamCtx(body, card, agentId) : null);
    if (ctx && agentId) hydrateSubagentTurnProcess(turn, ctx, agentId);
}

function feedChunkCollapsedMax(chunk) {
    var styles = getComputedStyle(chunk);
    var line = parseFloat(styles.getPropertyValue('--line')) || 21.6;
    var pad = parseFloat(styles.getPropertyValue('--scroller-pad-y')) || 4;
    return line * 2.5 + pad * 2;
}

function feedChunkInHiddenSubagentProcess(chunk) {
    var process = chunk.closest('.subagent-turn-process');
    if (!process || !process.children.length) return false;
    var turn = process.closest('.subagent-turn');
    return !!(turn && !turn.classList.contains('is-process-open'));
}

function measureFeedChunkScrollerHeight(sc, chunk) {
    if (!sc) return 0;
    var h = sc.scrollHeight;
    if (h > 1) return h;
    var process = chunk && chunk.closest('.subagent-turn-process');
    var turn = process && process.closest('.subagent-turn');
    if (!process || !turn || turn.classList.contains('is-process-open')) return h;
    var prevDisplay = process.style.display;
    var prevVis = process.style.visibility;
    var prevPos = process.style.position;
    var prevLeft = process.style.left;
    var prevRight = process.style.right;
    var prevPointer = process.style.pointerEvents;
    process.style.display = 'block';
    process.style.visibility = 'hidden';
    process.style.position = 'absolute';
    process.style.left = '0';
    process.style.right = '0';
    process.style.pointerEvents = 'none';
    h = sc.scrollHeight;
    process.style.display = prevDisplay;
    process.style.visibility = prevVis;
    process.style.position = prevPos;
    process.style.left = prevLeft;
    process.style.right = prevRight;
    process.style.pointerEvents = prevPointer;
    return h;
}

function refreshAllFeedChunksUnder(root) {
    if (!root || !root.querySelectorAll) return;
    root.querySelectorAll('.feed-chunk').forEach(scheduleFeedChunkOverflowRefresh);
}

function shouldFollowSubagentCard(ctx) {
    if (!ctx || ctx._suppressSubagentScrollFollow) return false;
    if (!ctx._subagentBody || !ctx._subagentBody.isConnected) return false;
    var aid = ctx._subagentBody.getAttribute('data-agent-id') || '';
    if (aid && subagentCardNearBottom[aid] === false) return false;
    return liveAutoFollow || subagentCardNearBottom[aid] !== false;
}

function bindSubagentCardBodyScrollFollow(body) {
    if (!body || body.dataset.subagentScrollFollowBound) return;
    body.dataset.subagentScrollFollowBound = '1';
    var aid = body.getAttribute('data-agent-id') || ('body-' + Math.random());
    if (subagentCardNearBottom[aid] == null) subagentCardNearBottom[aid] = true;
    body.addEventListener('scroll', function () {
        subagentCardNearBottom[aid] = isNearBottom(body, SUBAGENT_CARD_NEAR_BOTTOM_PX);
    }, { passive: true });
}

function scrollSubagentCardBodyToBottom(ctx) {
    if (!ctx || !ctx._subagentBody || !ctx._subagentBody.isConnected) return;
    var body = ctx._subagentBody;
    var aid = body.getAttribute('data-agent-id') || '';
    if (aid) subagentCardNearBottom[aid] = true;
    requestAnimationFrame(function () {
        body.scrollTop = body.scrollHeight;
        requestAnimationFrame(function () {
            body.scrollTop = body.scrollHeight;
        });
    });
}

function scrollContentAreaIfFollow(ctx, runSessionId) {
    if (shouldGateScrollByRunSession(ctx, runSessionId)) return;
    if (isSubagentStreamCtx(ctx)) {
        if (!shouldFollowSubagentCard(ctx)) return;
        scrollSubagentCardBodyToBottom(ctx);
        return;
    }
    if (!liveAutoFollow) return;
    scrollProcessBodyToBottom(ctx, runSessionId);
    scrollChatToBottomIfFollow(runSessionId, {});
}

/** 将当前轮次的执行框滚到底（流式增量主要长在这里，必须滚 procBody 而不是只滚对话区） */
function scrollProcessBodyToBottom(ctx, runSessionId) {
    if (shouldGateScrollByRunSession(ctx, runSessionId)) return;
    if (isSubagentStreamCtx(ctx)) {
        scrollSubagentCardBodyToBottom(ctx);
        return;
    }
    if (!ctx || !ctx.stream) return;
    var agg = (ctx.currentProcessGroup && ctx.currentProcessGroup.isConnected)
        ? ctx.currentProcessGroup
        : ctx.stream.querySelector('.process-aggregate:last-of-type');
    if (agg) {
        var procBody = agg.querySelector('.process-aggregate-body');
        if (procBody) procBody.scrollTop = procBody.scrollHeight;
    }
}

function followStreamProcessScroll(ctx, runSessionId) {
    if (shouldGateScrollByRunSession(ctx, runSessionId)) return;
    if (isSubagentStreamCtx(ctx)) {
        if (!shouldFollowSubagentCard(ctx)) return;
        if (subagentScrollFollowRaf) return;
        subagentScrollFollowRaf = requestAnimationFrame(function () {
            subagentScrollFollowRaf = 0;
            scrollSubagentCardBodyToBottom(ctx);
            refreshFeedChunksInCtx(ctx, '.feed-chunk.is-streaming');
        });
        return;
    }
    if (!liveAutoFollow) return;
    if (streamScrollFollowRaf) return;
    streamScrollFollowRaf = requestAnimationFrame(function () {
        streamScrollFollowRaf = 0;
        if (!liveAutoFollow) return;
        if (ctx && ctx.currentProcessGroup && ctx.currentProcessGroup.isConnected) {
            if (ctx.currentProcessGroup.classList.contains('is-collapsed')) {
                ctx.currentProcessGroup.classList.remove('is-collapsed');
                const topN = ctx.currentProcessGroup.querySelector('.process-aggregate-top');
                if (topN) topN.setAttribute('aria-expanded', 'true');
            }
        }
        scrollProcessBodyToBottom(ctx, runSessionId);
        scrollChatToBottomIfFollow(runSessionId, {});
        refreshLiveAutoFollowPins();
    });
}

function getVisibleChatStream() { return document.getElementById('chat-stream'); }

function ensureVisibleChatStreamSlot() {
    if (getVisibleChatStream() || !chatContainer) return;
    const ns = document.createElement('div');
    ns.className = 'chat-stream';
    ns.id = 'chat-stream';
    ns.setAttribute('aria-label', '消息');
    chatContainer.appendChild(ns);
}

function emptyChatStreamKeepingStrip(streamEl) {
    if (!streamEl) return;
    const strip = streamEl.querySelector('#history-load-sentinel');
    Array.from(streamEl.children).forEach(function (ch) {
        if (strip && ch === strip) return;
        ch.remove();
    });
}

function persistHistoryPagingToStream(streamEl, paging) {
    if (!streamEl) return;
    if (!paging || paging.sessionId !== currentSessionId) {
        delete streamEl.dataset.historyPaging;
        return;
    }
    streamEl.dataset.historyPaging = JSON.stringify({
        sessionId: paging.sessionId,
        total: Number(paging.total) || 0,
        range_start: Number(paging.range_start) || 0,
        range_end: Number(paging.range_end) || 0,
        has_older: !!paging.has_older,
    });
}

function restoreHistoryPagingFromStream(streamEl) {
    if (!streamEl || !streamEl.dataset.historyPaging) return null;
    try {
        var raw = JSON.parse(streamEl.dataset.historyPaging);
        if (!raw || raw.sessionId !== currentSessionId) return null;
        return {
            sessionId: raw.sessionId,
            total: Number(raw.total) || 0,
            range_start: Number(raw.range_start) || 0,
            range_end: Number(raw.range_end) || 0,
            has_older: !!raw.has_older,
        };
    } catch (_e) {
        delete streamEl.dataset.historyPaging;
        return null;
    }
}

function setSessionHistoryPaging(paging) {
    sessionHistoryPaging = paging || null;
    persistHistoryPagingToStream(getVisibleChatStream(), sessionHistoryPaging);
    updateHistorySentinelVisibility();
}

function ensureHistorySentinel(streamEl) {
    if (!streamEl) return null;
    var el = streamEl.querySelector('#history-load-sentinel');
    if (el) return el;
    el = document.createElement('div');
    el.id = 'history-load-sentinel';
    el.className = 'history-load-sentinel';
    el.hidden = true;
    var btn = document.createElement('button');
    btn.type = 'button';
    btn.className = 'history-load-older-btn';
    btn.textContent = '更早 ' + HISTORY_DIALOGUES_PER_PAGE + ' 轮对话';
    btn.addEventListener('click', function () { loadOlderHistoryChunk(); });
    el.appendChild(btn);
    streamEl.insertBefore(el, streamEl.firstChild);
    return el;
}

function getHistoryScrollAnchor(container) {
    if (!container) return null;
    var cr = container.getBoundingClientRect();
    var nodes = container.querySelectorAll('.msg-wrap, .process-aggregate, .welcome');
    for (var i = 0; i < nodes.length; i += 1) {
        var n = nodes[i];
        if (!n || !n.isConnected || n.id === 'chat-loading') continue;
        var r = n.getBoundingClientRect();
        if (r.bottom >= cr.top + 4) return { el: n, top: r.top };
    }
    return null;
}

function updateHistorySentinelVisibility() {
    var strip = document.getElementById('history-load-sentinel');
    var btn = strip && strip.querySelector('.history-load-older-btn');
    var ph = sessionHistoryPaging;
    if (!strip || !btn) return;
    if (!ph || !ph.has_older || ph.sessionId !== currentSessionId) {
        strip.hidden = true;
        btn.disabled = false;
        btn.textContent = '更早 ' + HISTORY_DIALOGUES_PER_PAGE + ' 轮对话';
        return;
    }
    strip.hidden = false;
    btn.disabled = historyOlderLoading;
    btn.textContent = historyOlderLoading ? '加载中…' : ('更早 ' + HISTORY_DIALOGUES_PER_PAGE + ' 轮对话');
}

function resetSessionHistoryPaging() {
    setSessionHistoryPaging(null);
    historyOlderLoading = false;
    updateHistorySentinelVisibility();
}

async function loadOlderHistoryChunk(opts) {
    opts = opts || {};
    var sid = currentSessionId;
    var stream = getVisibleChatStream();
    var ph = sessionHistoryPaging;
    if ((!ph || ph.sessionId !== sid) && stream) {
        ph = restoreHistoryPagingFromStream(stream);
        if (ph) sessionHistoryPaging = ph;
    }
    if (!sid || !ph || ph.sessionId !== sid || !ph.has_older || historyOlderLoading) return;
    historyOlderLoading = true;
    var prevReplaying = replayingMessages;
    replayingMessages = true;
    updateHistorySentinelVisibility();
    var cc = chatContainer;
    var prevScrollTop = cc ? cc.scrollTop : 0;
    var anchor = getHistoryScrollAnchor(cc);
    var loadedOlder = false;
    try {
        var pageTurns = Math.max(1, Math.min(Number(opts.turns) || HISTORY_DIALOGUES_PER_PAGE, 50));
        var url = '/sessions/' + encodeURIComponent(sid) + '/messages?turns=' + encodeURIComponent(String(pageTurns)) + '&before_index=' + ph.range_start;
        var response = await fetch(url);
        var data = await response.json();
        if (!response.ok || !data || typeof data !== 'object') return;
        var events = data.events;
        if (!Array.isArray(events) || events.length === 0) {
            setSessionHistoryPaging(Object.assign({}, ph, { has_older: !!data.has_older }));
            return;
        }
        ensureHistorySentinel(stream);
        var frag = document.createDocumentFragment();
        var tmpCtx = newDomContext(frag);
        tmpCtx.lastUserEventIndex = -1;
        var rs = typeof data.range_start === 'number' ? data.range_start : 0;
        for (var i = 0; i < events.length; i += 1) {
            var ev = events[i];
            if (ev && typeof ev === 'object' && ev.type) {
                reduceAndRenderMessageEvent(tmpCtx, ev, {
                    sessionId: sid,
                    eventIndex: rs + i,
                    source: 'history-older',
                });
            }
        }
        var sen = stream && stream.querySelector('#history-load-sentinel');
        if (stream && frag.childNodes.length) {
            stream.insertBefore(frag, sen ? sen.nextSibling : stream.firstChild);
        }
        loadedOlder = true;
        setSessionHistoryPaging({
            sessionId: sid,
            total: typeof data.total === 'number' ? data.total : ph.total,
            range_start: typeof data.range_start === 'number' ? data.range_start : ph.range_start,
            range_end: ph.range_end,
            has_older: !!data.has_older,
        });
    } catch (e) {
        console.error('加载更早消息失败:', e);
    } finally {
        historyOlderLoading = false;
        updateHistorySentinelVisibility();
        if (cc && stream && stream.parentNode === cc) {
            if (anchor && anchor.el && anchor.el.isConnected) {
                var nextTop = anchor.el.getBoundingClientRect().top;
                setScrollTopImmediate(cc, cc.scrollTop + (nextTop - anchor.top));
            } else {
                setScrollTopImmediate(cc, prevScrollTop);
            }
        }
        if (loadedOlder) {
            bindExistingLogs(stream);
            if (!opts.keepTocStable) rebuildToc();
            scheduleTocActiveUpdate();
        }
        replayingMessages = prevReplaying;
    }
}

function insertNewEmptyChatStream() { ensureVisibleChatStreamSlot(); }

function prepareStashLeaving(leavingId) {
    if (!leavingId) return;
    if (isSessionRunning(leavingId)) {
        const el = getVisibleChatStream();
        if (el && el.parentNode) {
            el.remove();
            el.removeAttribute('id');
            el.removeAttribute('aria-label');
            if (offscreenRoot) offscreenRoot.appendChild(el);
        }
        insertNewEmptyChatStream();
    } else {
        const v = getVisibleChatStream();
        if (v) {
            resetSessionHistoryPaging();
            emptyChatStreamKeepingStrip(v);
        }
        else ensureVisibleChatStreamSlot();
    }
}

function restoreStreamForRunningSession(enteringId) {
    const run = getSessionRunState(enteringId);
    if (!run || !run.ctx || !run.ctx.stream) return false;
    const st = run.ctx.stream;
    if (!st.parentNode) return false;
    if (st.parentNode === chatContainer) return st.id === 'chat-stream';
    if (offscreenRoot && st.parentNode !== offscreenRoot) return false;
    const cur = getVisibleChatStream();
    if (cur && cur.parentNode === chatContainer) cur.remove();
    st.id = 'chat-stream';
    st.setAttribute('aria-label', '消息');
    chatContainer.appendChild(st);
    var restoredPaging = restoreHistoryPagingFromStream(st);
    if (restoredPaging) sessionHistoryPaging = restoredPaging;
    updateHistorySentinelVisibility();
    bindExistingLogs(st);
    return true;
}

function appendLogVisible(msg, type) {
    if (!getVisibleChatStream()) ensureVisibleChatStreamSlot();
    const c = newDomContext(getVisibleChatStream());
    appendLog(c, msg, type, currentSessionId);
}

function newLlmState() {
    return {
        llmStreamReasoningIter: null,
        llmStreamResponseIter: null,
        llmStreamReasoningScroller: null,
        llmStreamResponseScroller: null,
        llmDeltaLastSeq: null,
        llmPendingReasoningDelta: '',
        llmPendingResponseDelta: '',
        llmDeltaFlushRaf: 0,
    };
}

function newDomContext(streamEl) {
    return {
        stream: streamEl,
        currentProcessGroup: null,
        lastUserEventIndex: -1,
        progressScrollers: {},
        progressStream: {},
        keyContextStreamFilter: { phase: 'seek', carry: '' },
        runStartedAt: null,
        llm: newLlmState(),
    };
}

function resetKeyContextStreamFilter(ctx) {
    if (ctx) ctx.keyContextStreamFilter = { phase: 'seek', carry: '' };
}

/** 要点流式输出：隐藏 <analysis>…</analysis>，仅展示 <summary> 内正文 */
function extractKeyContextVisibleDelta(filter, delta) {
    if (!filter) return String(delta || '');
    filter.carry += String(delta || '');
    var out = '';
    var tagTail = 24;
    while (filter.carry.length > 0) {
        var lower = filter.carry.toLowerCase();
        if (filter.phase === 'seek') {
            var ai = lower.indexOf('<analysis');
            var si = lower.indexOf('<summary');
            if (ai >= 0 && (si < 0 || ai < si)) {
                if (ai > 0) out += filter.carry.slice(0, ai);
                filter.carry = filter.carry.slice(ai);
                filter.phase = 'in_analysis';
                continue;
            }
            if (si >= 0) {
                if (si > 0) out += filter.carry.slice(0, si);
                filter.carry = filter.carry.slice(si);
                filter.phase = 'in_summary';
                continue;
            }
            if (filter.carry.length > tagTail) {
                var safe = filter.carry.length - tagTail;
                out += filter.carry.slice(0, safe);
                filter.carry = filter.carry.slice(safe);
            }
            break;
        }
        if (filter.phase === 'in_analysis') {
            var ae = lower.indexOf('</analysis>');
            if (ae >= 0) {
                var aClose = filter.carry.slice(ae).match(/^<\\/analysis\\s*>/i);
                var aLen = aClose ? aClose[0].length : 11;
                filter.carry = filter.carry.slice(ae + aLen);
                filter.phase = 'seek';
                continue;
            }
            filter.carry = '';
            break;
        }
        if (filter.phase === 'in_summary') {
            var se = lower.indexOf('</summary>');
            var chunk = se >= 0 ? filter.carry.slice(0, se) : filter.carry;
            chunk = chunk.replace(/^<summary[^>]*>\\s*/i, '');
            out += chunk;
            if (se >= 0) {
                var sClose = filter.carry.slice(se).match(/^<\\/summary\\s*>/i);
                var sLen = sClose ? sClose[0].length : 10;
                filter.carry = filter.carry.slice(se + sLen);
                filter.phase = 'done';
            } else {
                filter.carry = '';
            }
            break;
        }
        if (filter.phase === 'done') {
            filter.carry = '';
            break;
        }
        break;
    }
    return out;
}

function appendKeyContextStreamDelta(ctx, delta, runSessionId) {
    if (!ctx || !delta) return;
    if (!ctx.keyContextStreamFilter) resetKeyContextStreamFilter(ctx);
    var vis = extractKeyContextVisibleDelta(ctx.keyContextStreamFilter, delta);
    if (vis) appendProgressStreamDelta(ctx, vis, 'key-context', runSessionId);
}

function isSessionRunning(sessionId) {
    return selectIsSessionRunning(sessionId);
}

function syncDisconnectedProcessGroups() {
    sessionStore.runsBySession.forEach(function (run, sid) {
        const c = run && run.ctx;
        if (c && c.currentProcessGroup && !c.currentProcessGroup.isConnected) c.currentProcessGroup = null;
    });
}

function finalizeLlmStreamChunks(ctx) {
    if (!ctx) return;
    flushLlmDeltaText(ctx);
    queryFeedChunksInCtx(ctx, '.feed-chunk.is-streaming').forEach(function (ch) {
        ch.classList.remove('is-streaming');
        scheduleFeedChunkOverflowRefresh(ch);
    });
    if (ctx.llm) {
        const l = ctx.llm;
        l.llmStreamReasoningIter = null;
        l.llmStreamResponseIter = null;
        l.llmStreamReasoningScroller = null;
        l.llmStreamResponseScroller = null;
        l.llmDeltaLastSeq = null;
    }
    var bodies = [];
    if (ctx.currentProcessGroup && !isSubagentStreamCtx(ctx)) {
        var mainBody = ctx.currentProcessGroup.querySelector('.process-aggregate-body');
        if (mainBody) bodies.push(mainBody);
    }
    if (ctx._subagentTurnProcess && ctx._subagentTurnProcess.isConnected) {
        bodies.push(ctx._subagentTurnProcess);
    }
    bodies.forEach(function (body) {
        body.querySelectorAll('.feed-item.feed--llm, .feed-item.feed--llm2').forEach(function (el) {
            var sc = el.querySelector('.feed-chunk-scroller');
            var ch = el.querySelector('.feed-chunk');
            if (sc) {
                var norm = trimSurroundingBlankLines(sc.textContent || '');
                sc.textContent = truncateLogTextForUi(norm);
                if (ch) {
                    refreshFeedChunkOverflow(ch);
                    requestAnimationFrame(function () { refreshFeedChunkOverflow(ch); });
                }
            }
            if (!getFeedItemText(el).trim()) el.remove();
        });
    });
}

function discardLlmStreamChunks(ctx, ev) {
    if (!ctx) return;
    if (ctx.llm) {
        const l = ctx.llm;
        if (l.llmDeltaFlushRaf) {
            cancelAnimationFrame(l.llmDeltaFlushRaf);
            l.llmDeltaFlushRaf = 0;
        }
        l.llmPendingReasoningDelta = '';
        l.llmPendingResponseDelta = '';
        l.llmStreamReasoningIter = null;
        l.llmStreamResponseIter = null;
        l.llmStreamReasoningScroller = null;
        l.llmStreamResponseScroller = null;
        l.llmDeltaLastSeq = null;
    }
    var bodies = [];
    if (ctx.currentProcessGroup && !isSubagentStreamCtx(ctx)) {
        var mainBody = ctx.currentProcessGroup.querySelector('.process-aggregate-body');
        if (mainBody) bodies.push(mainBody);
    }
    if (ctx._subagentTurnProcess && ctx._subagentTurnProcess.isConnected) {
        bodies.push(ctx._subagentTurnProcess);
    }
    var reactIter = ev && ev.react_iter != null && Number.isFinite(Number(ev.react_iter))
        ? String(Math.max(1, Math.floor(Number(ev.react_iter))))
        : '';
    bodies.forEach(function (body) {
        body.querySelectorAll('.feed-item.feed--llm, .feed-item.feed--llm2').forEach(function (el) {
            var ch = el.querySelector('.feed-chunk');
            if (ch && ch.classList.contains('is-streaming')) el.remove();
        });
        body.querySelectorAll('.feed-item.feed--tool[data-tool-pending="1"]').forEach(function (el) {
            el.remove();
        });
        if (reactIter) {
            var sel = '.feed-item[data-react-iter="' + reactIter + '"]';
            body.querySelectorAll(sel).forEach(function (el) {
                if (
                    el.classList.contains('feed--tool')
                    || el.classList.contains('feed--llm')
                    || el.classList.contains('feed--llm2')
                ) {
                    el.remove();
                }
            });
        }
    });
}

function flushLlmDeltaText(ctx) {
    if (!ctx || !ctx.llm) return;
    const l = ctx.llm;
    if (l.llmDeltaFlushRaf) {
        cancelAnimationFrame(l.llmDeltaFlushRaf);
        l.llmDeltaFlushRaf = 0;
    }
    if (l.llmPendingReasoningDelta && l.llmStreamReasoningScroller) {
        var rs = trimSurroundingBlankLines((l.llmStreamReasoningScroller.textContent || '') + l.llmPendingReasoningDelta);
        l.llmStreamReasoningScroller.textContent = truncateLogTextForUi(rs);
    }
    l.llmPendingReasoningDelta = '';
    if (l.llmPendingResponseDelta && l.llmStreamResponseScroller) {
        var rsp = trimSurroundingBlankLines((l.llmStreamResponseScroller.textContent || '') + l.llmPendingResponseDelta);
        l.llmStreamResponseScroller.textContent = truncateLogTextForUi(rsp);
    }
    l.llmPendingResponseDelta = '';
}

function scheduleLlmDeltaFlush(ctx, runSessionId) {
    const l = ctx.llm;
    if (!l || l.llmDeltaFlushRaf) return;
    l.llmDeltaFlushRaf = requestAnimationFrame(function () {
        l.llmDeltaFlushRaf = 0;
        flushLlmDeltaText(ctx);
        followStreamProcessScroll(ctx, runSessionId);
    });
}

function resetLlmState(ctx) {
    if (!ctx || !ctx.llm) return;
    flushLlmDeltaText(ctx);
    const l = ctx.llm;
    l.llmStreamReasoningIter = null;
    l.llmStreamResponseIter = null;
    l.llmStreamReasoningScroller = null;
    l.llmStreamResponseScroller = null;
    l.llmDeltaLastSeq = null;
}

function showCopyFeedback() {
    const t = document.getElementById('copy-toast');
    if (!t) return;
    t.classList.add('is-on');
    if (t._copyTm) clearTimeout(t._copyTm);
    t._copyTm = setTimeout(function () { t.classList.remove('is-on'); }, 1500);
}

function showOpenFileFeedback(msg) {
    var t = document.getElementById('copy-toast');
    if (!t) return;
    var prev = t.getAttribute('data-default-msg') || t.textContent || '已复制';
    if (!t.getAttribute('data-default-msg')) t.setAttribute('data-default-msg', prev);
    t.textContent = msg || '已请求打开';
    t.classList.add('is-on');
    if (t._openFileTm) clearTimeout(t._openFileTm);
    t._openFileTm = setTimeout(function () {
        t.classList.remove('is-on');
        t.textContent = t.getAttribute('data-default-msg') || '已复制';
    }, 2200);
}

(function initWorkspaceFileOpenDelegation() {
    if (document.body.dataset.workspaceFileOpenBound) return;
    document.body.dataset.workspaceFileOpenBound = '1';
    document.body.addEventListener('click', function (ev) {
        var el = ev.target;
        if (!el || !el.closest) return;
        var a = el.closest('a.msg-link-workspace-open');
        if (!a) return;
        ev.preventDefault();
        var rel = a.getAttribute('data-workspace-open') || '';
        fetch('/api/open-workspace-file?rel=' + encodeURIComponent(rel))
            .then(function (r) {
                return r.json().catch(function () { return { ok: false, error: '响应异常' }; });
            })
            .then(function (j) {
                if (j && j.ok) showOpenFileFeedback('已调用系统打开文件');
                else showOpenFileFeedback((j && j.error) ? ('无法打开：' + j.error) : '无法打开文件');
            })
            .catch(function () { showOpenFileFeedback('无法连接服务'); });
    });
})();

let rewriteUndoState = null;
/** 改写待发送：仅在点击发送时调用截断；取消则丢弃 */
let pendingRewriteTruncate = null;
function hideRewriteUndoToast() {
    const t = document.getElementById('rewrite-undo-toast');
    if (t) {
        t.classList.remove('is-on');
        const btn = t.querySelector('.rewrite-undo-btn');
        if (btn) btn.textContent = '撤销';
    }
    rewriteUndoState = null;
}
function showRewriteUndoToast(type, data) {
    const t = document.getElementById('rewrite-undo-toast');
    const msgEl = t && t.querySelector('.rewrite-undo-msg');
    const btn = t && t.querySelector('.rewrite-undo-btn');
    if (!t || !msgEl) return;
    rewriteUndoState = { type: type, data: data };
    if (type === 'rewrite_pending') {
        msgEl.textContent = '改写待生效：发送消息后才会截断历史并发送；点此取消改写。';
        if (btn) btn.textContent = '取消改写';
    } else if (type === 'tail') {
        msgEl.textContent = '已截断历史，可撤销恢复';
        if (btn) btn.textContent = '撤销';
    } else {
        msgEl.textContent = '已填入输入框，可撤销';
        if (btn) btn.textContent = '撤销';
    }
    t.classList.add('is-on');
}

function smoothScrollBy(el, dy) {
    if (!el || !dy) return;
    const bMax = Math.max(0, el.scrollHeight - el.clientHeight);
    const start = el.scrollTop;
    const target = Math.max(0, Math.min(bMax, start + dy));
    const dist = target - start;
    if (Math.abs(dist) < 0.5) return;
    const frames = 3;
    let f = 0;
    function step() {
        f += 1;
        const t = f / frames;
        const ease = 1 - Math.pow(1 - t, 2);
        el.scrollTop = start + dist * ease;
        if (f < frames) requestAnimationFrame(step);
    }
    requestAnimationFrame(step);
}

function isNearBottom(el, thresholdPx) {
    if (!el) return true;
    const th = (thresholdPx == null) ? 56 : thresholdPx;
    return (el.scrollHeight - el.clientHeight - el.scrollTop) <= th;
}

async function getUiEventCount(sessionId) {
    const sid = sessionId != null ? sessionId : currentSessionId;
    if (!sid) return 0;
    try {
        const r = await fetch('/sessions/' + encodeURIComponent(sid) + '/messages/count');
        if (!r.ok) return 0;
        const j = await r.json();
        return (j && typeof j.count === 'number') ? j.count : 0;
    } catch (e) { return 0; }
}

function loadUnreadFromStorage() {
    try {
        const raw = localStorage.getItem(LS_SESSION_UNREAD);
        if (!raw) return;
        const arr = JSON.parse(raw);
        if (!Array.isArray(arr)) return;
        arr.forEach(function (id) { sessionUnreadComplete.add(String(id)); });
    } catch (e) { /* ignore */ }
}

function persistSessionUnread() {
    try {
        localStorage.setItem(LS_SESSION_UNREAD, JSON.stringify([...sessionUnreadComplete]));
    } catch (e) { /* ignore */ }
}

function stashInputDraft(sessionId) {
    if (!messageInput || !sessionId) return;
    draftBySession[sessionId] = messageInput.value;
    persistInputDraft(sessionId, messageInput.value);
}

function restoreInputDraft(sessionId) {
    if (!messageInput) return;
    const v = (sessionId && Object.prototype.hasOwnProperty.call(draftBySession, sessionId))
        ? draftBySession[sessionId]
        : readStoredInputDraft(sessionId);
    messageInput.value = v != null ? String(v) : '';
    rewriteInputWorkspacePaths();
    autoResizeTextarea();
}

function inputDraftStorageKey(sessionId) {
    return LS_INPUT_DRAFT_PREFIX + String(sessionId || '');
}

function persistInputDraft(sessionId, value) {
    if (!sessionId) return;
    const text = String(value || '');
    draftBySession[sessionId] = text;
    try {
        const key = inputDraftStorageKey(sessionId);
        if (text) localStorage.setItem(key, text);
        else localStorage.removeItem(key);
    } catch (e) { /* ignore */ }
}

function readStoredInputDraft(sessionId) {
    if (!sessionId) return '';
    try {
        return localStorage.getItem(inputDraftStorageKey(sessionId)) || '';
    } catch (e) {
        return '';
    }
}

function removeStoredInputDraft(sessionId) {
    if (!sessionId) return;
    delete draftBySession[sessionId];
    try { localStorage.removeItem(inputDraftStorageKey(sessionId)); } catch (e) { /* ignore */ }
}

function clearStreamPoll() {
    if (streamPollTimer) {
        clearInterval(streamPollTimer);
        streamPollTimer = null;
    }
}

async function fetchSessionStreamActiveMap() {
    try {
        const response = await fetch('/sessions');
        const sessions = await response.json();
        if (!Array.isArray(sessions)) return Object.create(null);
        const m = Object.create(null);
        for (let i = 0; i < sessions.length; i += 1) {
            const s = sessions[i];
            if (s && s.id) m[s.id] = !!s.stream_active;
        }
        return m;
    } catch (e) {
        return Object.create(null);
    }
}

function maybeStartStreamPollForSession(sid, opts) {
    opts = opts || {};
    clearStreamPoll();
    if (!sid) return;
    if (!isSessionRunning(sid)) return;
    if (!getSessionRunState(sid) && typeof attachSessionEventStream === 'function') {
        void attachSessionEventStream(sid, { skipInitialLoad: !!opts.skipInitialLoad });
    }
    let pollCount = 0;
    let MAX_POLL_COUNT = 20;
    streamPollTimer = setInterval(function () {
        (async function () {
            if (currentSessionId !== sid) {
                clearStreamPoll();
                return;
            }
            pollCount += 1;
            const m = await fetchSessionStreamActiveMap();
            applyServerStreamActiveMap(m);
            const still = !!m[sid];
            if (!still || pollCount >= MAX_POLL_COUNT) {
                clearStreamPoll();
                await loadSessions();
                syncSessionListIndicatorClasses();
                setSendButtonState();
                return;
            }
            if (currentSessionId === sid && document.visibilityState === 'visible') {
                syncSessionListIndicatorClasses();
                setSendButtonState();
            }
        })();
    }, 15000);
}

async function scrollToUserTurnOrLoadOlder(eventIndex) {
    var ei = Number(eventIndex);
    if (!Number.isFinite(ei)) return;
    function setTocJumpLoading(active) {
        var list = document.getElementById('chat-toc-list');
        var link = list && list.querySelector('a[data-event-index="' + ei + '"]');
        if (!link) return;
        link.classList.toggle('is-loading', !!active);
        if (active) link.setAttribute('aria-busy', 'true');
        else link.removeAttribute('aria-busy');
    }
    function findWrap() {
        var stream = getVisibleChatStream();
        if (!stream) return null;
        return stream.querySelector('.msg-wrap--user[data-event-index="' + ei + '"]')
            || stream.querySelector('#user-msg-' + ei);
    }
    async function loadFullHistoryForTarget(sid) {
        if (sid !== currentSessionId || typeof loadSessionMessages !== 'function') return;
        try {
            await loadSessionMessages(sid, 'saved-or-bottom', {
                full: true,
                allowDuringRun: typeof isServerStreamActive === 'function' && isServerStreamActive(sid),
            });
        } catch (e) {
            console.error('reload full history for toc target failed:', e);
        }
    }
    setTocJumpLoading(true);
    try {
        var wrap = findWrap();
        if (wrap) {
            wrap.scrollIntoView({ behavior: 'smooth', block: 'start' });
            return;
        }
        var sid = currentSessionId;
        var safety = 0;
        var pagingCoveredTarget = false;
        while (sid === currentSessionId && safety < 120) {
            safety += 1;
            wrap = findWrap();
            if (wrap) {
                wrap.scrollIntoView({ behavior: 'smooth', block: 'start' });
                return;
            }
            var ph = sessionHistoryPaging;
            if ((!ph || ph.sessionId !== sid) && getVisibleChatStream()) {
                ph = restoreHistoryPagingFromStream(getVisibleChatStream());
                if (ph) sessionHistoryPaging = ph;
            }
            if (!ph || ph.sessionId !== sid) {
                await loadFullHistoryForTarget(sid);
                break;
            }
            if (ei >= ph.range_start) {
                pagingCoveredTarget = true;
                break;
            }
            if (!ph.has_older) break;
            while (historyOlderLoading && currentSessionId === sid) {
                await new Promise(function (r) { setTimeout(r, 40); });
            }
            await loadOlderHistoryChunk({ keepTocStable: true, turns: 50 });
        }
        wrap = findWrap();
        if (wrap) {
            wrap.scrollIntoView({ behavior: 'smooth', block: 'start' });
            return;
        }
        if (sid === currentSessionId && pagingCoveredTarget) {
            await loadFullHistoryForTarget(sid);
            if (sid !== currentSessionId) return;
            wrap = findWrap();
            if (wrap) {
                wrap.scrollIntoView({ behavior: 'smooth', block: 'start' });
                return;
            }
            rebuildToc();
        }
        if (wrap) wrap.scrollIntoView({ behavior: 'smooth', block: 'start' });
        else {
            showUiAlert({
                title: '无法定位该条',
                message: '未能加载到对应的用户提问（可能索引不一致）。可刷新页面或使用「更早 ' + HISTORY_DIALOGUES_PER_PAGE + ' 轮对话」手动分页。',
                showCancel: false,
                confirmText: '知道了',
            });
        }
    } finally {
        setTocJumpLoading(false);
    }
}
`,De=`function ensureUiHoverTooltipEl() {
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

function rebuildToc(options) {
    options = options || {};
    const toc = document.getElementById('chat-toc');
    const list = document.getElementById('chat-toc-list');
    if (!toc || !list) return;
    if (suppressTocDuringSessionLoad) {
        clearTocForSessionLoad();
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
            if (options.localOnly) {
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

function hideTodoPlanPanel() {
    const root = document.getElementById('chat-todo-plan');
    if (!root) return;
    root.classList.remove('is-open');
    notifyPanelContentChanged();
}

async function clearTodoPlan() {
    const sid = currentSessionId;
    if (!sid) return;
    try {
        await fetch('/sessions/' + encodeURIComponent(sid) + '/todo_plan', { method: 'DELETE' });
    } catch (e) { /* ignore */ }
    clearTodoPlanState(sid);
    hideTodoPlanPanel();
    const statsEl = document.getElementById('chat-todo-plan-stats');
    const listEl = document.getElementById('chat-todo-plan-list');
    if (statsEl) statsEl.textContent = '';
    if (listEl) listEl.textContent = '';
    notifyPanelContentChanged();
}

function renderTodoPlanSnapshot(snapshot) {
    const root = document.getElementById('chat-todo-plan');
    const listEl = document.getElementById('chat-todo-plan-list');
    const statsEl = document.getElementById('chat-todo-plan-stats');
    if (!root || !listEl || !statsEl) return;
    const data = snapshot || { items: [], done: 0, total: 0, has_plan: false };
    const items = Array.isArray(data.items) ? data.items : [];
    const has = !!(data.has_plan && items.length > 0);
    if (!has) {
        listEl.textContent = '';
        statsEl.textContent = '';
        hideTodoPlanPanel();
        notifyPanelContentChanged();
        return;
    }
    const done = data.done;
    const total = data.total;
    statsEl.textContent = String(done) + ' / ' + String(total) + ' 已完成';
    listEl.textContent = '';
    items.forEach(function (it) {
        const li = document.createElement('li');
        const st = (it && it.status) || 'pending';
        li.className = 'todo-plan-item todo-plan--' + String(st);
        const tag = document.createElement('span');
        tag.className = 'todo-plan-status-tag';
        tag.textContent = todoPlanStatusLabel(st);
        li.appendChild(tag);
        const text = document.createElement('span');
        text.textContent = (it && it.text != null) ? String(it.text) : '';
        li.appendChild(text);
        listEl.appendChild(li);
    });
    root.classList.add('is-open');
    notifyPanelContentChanged();
}

function applyTodoPlanFromPayload(data) {
    renderTodoPlanSnapshot(applyTodoPlanToStore(currentSessionId, data));
}

function renderTodoPlanForCurrentSession() {
    renderTodoPlanSnapshot(selectTodoPlan(currentSessionId));
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
`,qe=`function removeMessagesFromNode(startWrap) {
    const stream = getVisibleChatStream() || chatContainer;\r
    if (!stream) return;\r
    const kids = Array.from(stream.children);\r
    const i = kids.indexOf(startWrap);\r
    if (i < 0) return;\r
    for (let j = kids.length - 1; j >= i; j--) kids[j].remove();\r
    syncDisconnectedProcessGroups();\r
}\r
\r
async function truncateSessionOnServer(beforeIndex, options) {\r
    options = options || {};\r
    const sid = options.sessionId || currentSessionId;\r
    if (!sid) return { ok: false, error: 'no_session' };\r
    if (!Number.isFinite(Number(beforeIndex)) || Number(beforeIndex) < 0) {\r
        return { ok: false, error: 'invalid_before_index' };\r
    }\r
    const url = '/sessions/' + encodeURIComponent(sid) + '/truncate'\r
        + '?before_index=' + encodeURIComponent(String(beforeIndex))\r
        + '&backup=' + (options.backup ? '1' : '0');\r
    try {\r
        const r = await fetch(url, { method: 'POST' });\r
        const j = await r.json().catch(function () { return {}; });\r
        return { ok: r.ok, error: (j && j.error) ? String(j.error) : '' };\r
    } catch (e) {\r
        return { ok: false, error: (e && e.message) || String(e) };\r
    }\r
}\r
\r
function describeServerSyncFailure(res, fallback) {\r
    var base = fallback || '无法同步服务器。';\r
    var err = res && res.error ? String(res.error).trim() : '';\r
    if (!err) return base;\r
    var friendly = err;\r
    if (err === 'no_session') friendly = '当前没有选中的会话。';\r
    else if (err === 'invalid_before_index' || err === 'invalid before_index') friendly = '消息定位索引无效，可能需要刷新当前会话。';\r
    else if (err === 'refuse empty truncation') friendly = '服务端拒绝清空整个会话。';\r
    else if (err === 'truncation failed') friendly = '服务端裁剪历史失败，可能是历史索引已变化或会话文件暂时不一致。';\r
    return base + '\\n原因：' + friendly;\r
}\r
\r
function hasPreviousUserMessageBefore(wrap) {\r
    var node = wrap ? wrap.previousElementSibling : null;\r
    while (node) {\r
        if (node.classList && node.classList.contains('msg-wrap--user')) return true;\r
        node = node.previousElementSibling;\r
    }\r
    return false;\r
}\r
\r
let activeInlineRewriteWrap = null;\r
\r
function restoreUserMessageBubble(wrap, rawText) {\r
    if (!wrap) return;\r
    const div = wrap.querySelector('.message.user');\r
    if (!div) return;\r
    wrap.classList.remove('is-inline-rewriting', 'user-msg-expanded', 'has-turn-process');\r
    div.className = 'message user';\r
    div.textContent = '';\r
    messageRawMarkdown.set(wrap, String(rawText || ''));\r
    renderUserMessageContent(wrap, div, String(rawText || ''), linkifyAssistantTextNodes);\r
}\r
\r
function closeInlineRewriteEditor(wrap, rawText) {\r
    restoreUserMessageBubble(wrap, rawText);\r
    if (activeInlineRewriteWrap === wrap) activeInlineRewriteWrap = null;\r
}\r
\r
function autoResizeInlineRewriteTextarea(textarea) {\r
    if (!textarea) return;\r
    textarea.style.height = 'auto';\r
    textarea.style.height = Math.min(Math.max(textarea.scrollHeight, 84), 260) + 'px';\r
}\r
\r
function openInlineRewriteEditor(wrap, rawText, beforeIndex) {\r
    if (!wrap) return;\r
    if (activeInlineRewriteWrap && activeInlineRewriteWrap !== wrap) {\r
        const prevRaw = messageRawMarkdown.get(activeInlineRewriteWrap) || '';\r
        closeInlineRewriteEditor(activeInlineRewriteWrap, prevRaw);\r
    }\r
    const div = wrap.querySelector('.message.user');\r
    if (!div) return;\r
    activeInlineRewriteWrap = wrap;\r
    wrap.classList.add('is-inline-rewriting');\r
    wrap.classList.remove('user-msg-expanded', 'has-turn-process');\r
    div.className = 'message user user-inline-rewrite';\r
    div.textContent = '';\r
\r
    const editor = document.createElement('div');\r
    editor.className = 'user-inline-rewrite-box';\r
    const textarea = document.createElement('textarea');\r
    textarea.className = 'user-inline-rewrite-input';\r
    textarea.value = String(rawText || '');\r
    textarea.rows = 3;\r
    const actions = document.createElement('div');\r
    actions.className = 'user-inline-rewrite-actions';\r
    const cancelBtn = document.createElement('button');\r
    cancelBtn.type = 'button';\r
    cancelBtn.className = 'user-inline-rewrite-btn user-inline-rewrite-btn--ghost';\r
    cancelBtn.textContent = '取消';\r
    const confirmBtn = document.createElement('button');\r
    confirmBtn.type = 'button';\r
    confirmBtn.className = 'user-inline-rewrite-btn user-inline-rewrite-btn--primary';\r
    confirmBtn.textContent = '确认';\r
    actions.appendChild(cancelBtn);\r
    actions.appendChild(confirmBtn);\r
    editor.appendChild(textarea);\r
    editor.appendChild(actions);\r
    div.appendChild(editor);\r
\r
    function cancel() {\r
        closeInlineRewriteEditor(wrap, rawText);\r
    }\r
\r
    async function confirm() {\r
        const nextText = String(textarea.value || '');\r
        if (!nextText.trim()) {\r
            showUiAlert({\r
                title: '无法改写',\r
                message: '改写内容不能为空。',\r
                variant: 'warning',\r
            });\r
            return;\r
        }\r
        if (!currentSessionId || !Number.isFinite(Number(beforeIndex))) return;\r
        confirmBtn.disabled = true;\r
        cancelBtn.disabled = true;\r
        pendingRewriteTruncate = {\r
            sessionId: currentSessionId,\r
            before: Number(beforeIndex),\r
            prevInput: ''\r
        };\r
        try {\r
            await sendMessage({\r
                message: nextText,\r
                sessionId: currentSessionId,\r
                preserveInput: true,\r
                fromInlineRewrite: true,\r
            });\r
        } finally {\r
            if (wrap.isConnected) {\r
                confirmBtn.disabled = false;\r
                cancelBtn.disabled = false;\r
            }\r
        }\r
    }\r
\r
    textarea.addEventListener('input', function () {\r
        autoResizeInlineRewriteTextarea(textarea);\r
    });\r
    textarea.addEventListener('keydown', function (e) {\r
        if (e.key === 'Escape') {\r
            e.preventDefault();\r
            cancel();\r
            return;\r
        }\r
        if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) {\r
            e.preventDefault();\r
            void confirm();\r
        }\r
    });\r
    cancelBtn.addEventListener('click', function (e) {\r
        e.preventDefault();\r
        cancel();\r
    });\r
    confirmBtn.addEventListener('click', function (e) {\r
        e.preventDefault();\r
        void confirm();\r
    });\r
    autoResizeInlineRewriteTextarea(textarea);\r
    textarea.focus();\r
    try {\r
        textarea.setSelectionRange(textarea.value.length, textarea.value.length);\r
    } catch (e) { /* ignore */ }\r
}\r
\r
async function branchSessionOnServer(beforeIndex, sessionId) {
    const sid = sessionId || currentSessionId;
    if (!sid) return { ok: false, error: 'no_session' };
    const url = '/sessions/' + encodeURIComponent(sid) + '/branch'
        + '?before_index=' + encodeURIComponent(String(beforeIndex));
    try {\r
        const r = await fetch(url, { method: 'POST' });\r
        const j = await r.json().catch(function () { return {}; });\r
        return {\r
            ok: r.ok,
            session_id: j && j.session_id,
            name: j && j.name,
            session: j && j.session,
            error: (j && j.error) ? String(j.error) : '',
        };
    } catch (e) {\r
        return { ok: false, error: (e && e.message) || String(e) };\r
    }\r
}\r
\r
function normalizeBranchFinalText(text) {\r
    return String(text || '').replace(/\\s+/g, ' ').trim();\r
}\r
\r
function branchFinalTextMatches(eventContent, expectedText) {\r
    var a = normalizeBranchFinalText(eventContent);\r
    var b = normalizeBranchFinalText(expectedText);\r
    if (!a || !b) return false;\r
    if (a === b) return true;\r
    if (a.length > 80 && b.length > 80) {\r
        return a.indexOf(b.slice(0, 80)) >= 0 || b.indexOf(a.slice(0, 80)) >= 0;\r
    }\r
    return false;\r
}\r
\r
async function waitForBranchFinalPersisted(sessionId, beforeIndex, expectedText) {\r
    if (!sessionId || !Number.isFinite(beforeIndex) || beforeIndex <= 0) {\r
        return { ready: true, beforeIndex: beforeIndex };\r
    }\r
    var deadline = Date.now() + 2600;\r
    while (Date.now() < deadline) {\r
        try {\r
            var url = '/sessions/' + encodeURIComponent(sessionId)\r
                + '/messages?limit=1&before_index=' + encodeURIComponent(String(beforeIndex));\r
            var r = await fetch(url);\r
            var j = await r.json().catch(function () { return null; });\r
            var events = Array.isArray(j) ? j : (j && Array.isArray(j.events) ? j.events : []);\r
            if (events.length && events[events.length - 1] && events[events.length - 1].type === 'final') {\r
                return { ready: true, beforeIndex: beforeIndex };\r
            }\r
            var recentUrl = '/sessions/' + encodeURIComponent(sessionId) + '/messages?limit=80';\r
            var rr = await fetch(recentUrl);\r
            var jj = await rr.json().catch(function () { return null; });\r
            var recent = Array.isArray(jj) ? jj : (jj && Array.isArray(jj.events) ? jj.events : []);\r
            var base = jj && typeof jj.range_start === 'number' ? jj.range_start : 0;\r
            for (var i = recent.length - 1; i >= 0; i -= 1) {\r
                var ev = recent[i];\r
                if (!ev || ev.type !== 'final') continue;\r
                if (branchFinalTextMatches(ev.content, expectedText)) {\r
                    return { ready: true, beforeIndex: base + i + 1 };\r
                }\r
            }\r
        } catch (e) { /* retry */ }\r
        await new Promise(function (resolve) { setTimeout(resolve, 180); });\r
    }\r
    return { ready: false, beforeIndex: beforeIndex };\r
}\r
\r
function onMessageToolbarClick(wrap, role, act) {\r
    const msg = wrap.querySelector('.message');\r
    const plain = msg ? (msg.innerText || '') : '';\r
    const tf = wrap.dataset.truncateFrom;\r
    const eiRaw = wrap.dataset.eventIndex;\r
    const eventIndex = eiRaw !== undefined && eiRaw !== '' ? parseInt(eiRaw, 10) : NaN;\r
    const truncateFrom = tf !== undefined && tf !== '' ? parseInt(tf, 10) : NaN;\r
    const before = role === 'user' ? eventIndex : truncateFrom;\r
    if ((act === 'delete' || act === 'rewrite') && isSessionRunning(currentSessionId)) {\r
        showUiAlert({\r
            title: '生成中不可操作',\r
            message: '当前会话仍在生成。请等待完成或停止后再修改历史。',\r
            variant: 'warning',\r
        });\r
        return;\r
    }\r
    if (act === 'copy') {\r
        const raw = messageRawMarkdown.get(wrap);\r
        const toCopy = raw !== undefined ? String(raw) : plain;\r
        const done = function () { showCopyFeedback(); };\r
        if (navigator.clipboard && navigator.clipboard.writeText) {\r
            navigator.clipboard.writeText(toCopy).then(done).catch(function () {\r
                try {\r
                    const ta = document.createElement('textarea');\r
                    ta.value = toCopy;\r
                    ta.setAttribute('readonly', 'readonly');\r
                    document.body.appendChild(ta);\r
                    ta.select();\r
                    document.execCommand('copy');\r
                    document.body.removeChild(ta);\r
                    done();\r
                } catch (e) { /* ignore */ }\r
            });\r
        }\r
        return;\r
    }\r
    if (act === 'delete') {\r
        if (!Number.isFinite(before) || before < 0 || (before === 0 && hasPreviousUserMessageBefore(wrap))) {\r
            if (Number.isFinite(before) && (before < 0 || (before === 0 && hasPreviousUserMessageBefore(wrap)))) {\r
                showUiAlert({\r
                    title: '无法删除该条',\r
                    message: '消息索引异常，已阻止清空整个会话。请刷新后再试。',\r
                    variant: 'error'\r
                });\r
                return;\r
            }\r
            removeMessagesFromNode(wrap);\r
            syncDisconnectedProcessGroups();\r
            rebuildToc();\r
            return;\r
        }\r
        openUiModal({\r
            title: '删除消息',\r
            subtitle: '将同步到服务器',\r
            message: '确定删除本条及之后的所有对话内容吗？',\r
            danger: true,\r
            confirmText: '删除',\r
            cancelText: '取消',\r
        }).then(function (ok) {\r
            if (!ok) return;\r
            truncateSessionOnServer(before).then(function (res) {\r
                if (!res || !res.ok) {\r
                    showUiAlert({\r
                        title: '同步失败',\r
                        message: describeServerSyncFailure(res, '删除未生效。'),\r
                        variant: 'error'\r
                    });\r
                    return;\r
                }\r
                removeMessagesFromNode(wrap);\r
                syncDisconnectedProcessGroups();\r
                rebuildToc();\r
                scheduleContextTokensAfterPaint(currentSessionId);\r
            });\r
        });\r
        return;\r
    }\r
    if (act === 'rewrite' && role === 'user') {\r
        const raw = messageRawMarkdown.get(wrap);\r
        const toFill = raw !== undefined ? String(raw) : plain;\r
        if (Number.isFinite(before) && before === 0 && hasPreviousUserMessageBefore(wrap)) {\r
            showUiAlert({\r
                title: '无法改写该条',\r
                message: '消息索引异常，已阻止从错误位置清空会话。请刷新后再试。',\r
                variant: 'error'\r
            });\r
            return;\r
        }\r
        if (!Number.isFinite(before)) {\r
            showUiAlert({\r
                title: '无法改写该条',\r
                message: '该消息尚未与服务器索引对齐，请刷新当前会话后再试。',\r
                variant: 'warning',\r
            });\r
            return;\r
        }\r
        openInlineRewriteEditor(wrap, toFill, before);\r
        return;\r
    }\r
    if (act === 'branch' && role === 'assistant') {
        const sourceSessionId = currentSessionId;
        const eiRaw = wrap.dataset.eventIndex;
        const eventIdx = eiRaw !== undefined && eiRaw !== '' ? parseInt(eiRaw, 10) : NaN;
        if (!Number.isFinite(eventIdx) || eventIdx < 0) {\r
            showUiAlert({\r
                title: '无法分支',\r
                message: '该回答尚未与服务器同步，请刷新页面后重试。',\r
                variant: 'error',\r
            });\r
            return;\r
        }\r
        const branchBefore = eventIdx + 1;\r
        openUiModal({\r
            title: '创建分支会话',\r
            subtitle: '原会话不会被修改',\r
            message: '将在当前回答之后创建独立分支会话。分支点之前的内容与原会话相同，可在分支中继续提问且不影响原会话。',\r
            confirmText: '创建分支',\r
            cancelText: '取消',\r
        }).then(function (ok) {\r
            if (!ok) return;
            (async function () {
                var res = await branchSessionOnServer(branchBefore, sourceSessionId);
                if (!res || !res.ok || !res.session_id) {
                    showUiAlert({\r
                        title: '创建失败',\r
                        message: describeServerSyncFailure(res, '创建分支未生效。'),\r
                        variant: 'error',\r
                    });\r
                    return;\r
                }\r
                if (res.session && typeof sessionStore !== 'undefined') {
                    sessionStore.upsert(res.session);
                    renderSessionListIfChanged(true);
                }
                await switchSession(res.session_id);
                setTimeout(function () { void loadSessions({ forceRender: true }); }, 0);
            })();\r
        });\r
        return;\r
    }\r
}\r
\r
function attachMessageToolbar(wrap, role) {\r
    const bar = document.createElement('div');\r
    bar.className = 'msg-toolbar';\r
    if (role === 'user') {\r
        var createdAt = wrap && wrap.dataset ? (wrap.dataset.createdAt || '') : '';\r
        if (createdAt) {\r
            var timeEl = document.createElement('span');\r
            timeEl.className = 'user-message-time';\r
            timeEl.setAttribute('data-created-at', createdAt);\r
            timeEl.title = createdAt;\r
            timeEl.textContent = formatUserMessageTimestamp(createdAt);\r
            bar.appendChild(timeEl);\r
        }\r
    }\r
    var html = '<button type="button" class="msg-tb" data-act="copy" data-ui-tip="复制">复制</button>'\r
        + '<button type="button" class="msg-tb" data-act="delete" data-ui-tip="删除">删除</button>';\r
    if (role === 'assistant') {\r
        html += '<button type="button" class="msg-tb" data-act="branch" data-ui-tip="分支">分支</button>';\r
    }\r
    if (role === 'user') html += '<button type="button" class="msg-tb" data-act="rewrite" data-ui-tip="改写">改写</button>';\r
    bar.insertAdjacentHTML('beforeend', html);\r
    bar.querySelectorAll('.msg-tb').forEach(bindUiHoverTip);\r
    bar.addEventListener('click', function (e) {\r
        var t = e.target;\r
        if (!t || t.tagName !== 'BUTTON' || !t.getAttribute) return;\r
        e.preventDefault();\r
        var a = t.getAttribute('data-act');\r
        if (a) onMessageToolbarClick(wrap, role, a);\r
    });\r
    wrap.appendChild(bar);\r
}\r
\r
function getFeedItemText(row) {\r
    const sc = row.querySelector('.feed-chunk-scroller');\r
    if (sc) return sc.textContent.trim();\r
    const ch = row.querySelector('.feed-chunk');\r
    return ch ? ch.textContent.trim() : '';\r
}\r
\r
function extractToolNameFromLog(text) {\r
    if (!text) return '工具';\r
    const line = (text.split(/\\n/)[0] || text).trim();\r
    var m = line.match(/^([A-Za-z_][\\w-]*)\\s*\\(/);\r
    if (m) return m[1];\r
    m = line.match(/^([^\\s(]+)\\s*\\(/);\r
    if (m) return m[1];\r
    m = line.match(/^(\\S+?)(?:\\(|：)/);\r
    if (m) return m[1];\r
    return '工具';\r
}\r
\r
function pushBriefLine(lines, line) {\r
    if (!line || !String(line).trim()) return;\r
    var t = String(line);\r
    if (lines.length && lines[lines.length - 1] === t) return;\r
    lines.push(t);\r
}\r
\r
function refreshFeedChunkOverflow(chunk) {\r
    if (!chunk || !chunk.isConnected) return;\r
    const sc = chunk.querySelector('.feed-chunk-scroller');\r
    if (!sc) return;\r
    if (feedChunkInHiddenSubagentProcess(chunk)) return;\r
    if (chunk.classList.contains('expanded')) {\r
        chunk.classList.remove('is-overflowing');\r
        return;\r
    }\r
    function measure() {\r
        if (!chunk.isConnected || chunk.classList.contains('expanded')) return;\r
        var collapsedMax = feedChunkCollapsedMax(chunk);\r
        var contentH = sc.scrollHeight;\r
        if (contentH < 2) contentH = measureFeedChunkScrollerHeight(sc, chunk);\r
        if (chunk.classList.contains('is-streaming') || sc.clientHeight < 2) {\r
            chunk.classList.toggle('is-overflowing', contentH > collapsedMax + 1);\r
            return;\r
        }\r
        chunk.classList.toggle('is-overflowing', sc.scrollHeight > sc.clientHeight + 1);\r
    }\r
    requestAnimationFrame(function () { requestAnimationFrame(measure); });\r
}\r
\r
function scheduleFeedChunkOverflowRefresh(chunk) {\r
    if (!chunk) return;\r
    var card = chunk.closest && chunk.closest('.subagent-grid-card');\r
    if (card && subagentPanelOpen && !card.classList.contains('is-expanded') && card.dataset.viewportVisible !== '1') return;\r
    /* streaming 中的块每个 delta 都会触发本函数；measure 是 layout 重操作，\r
       3 次 RAF × 每个 delta = 主线程灾难。streaming 时只 set class、不 measure。 */\r
    if (chunk.classList && chunk.classList.contains('is-streaming')) {\r
        refreshFeedChunkOverflow(chunk);\r
        return;\r
    }\r
    refreshFeedChunkOverflow(chunk);\r
    requestAnimationFrame(function () { refreshFeedChunkOverflow(chunk); });\r
}\r
\r
function bindFeedChunkScrollChain(sc) {\r
    if (!sc || sc._wheelScrollChainBound) return;\r
    sc._wheelScrollChainBound = true;\r
    sc.addEventListener('wheel', onFeedChunkScrollerWheel, { passive: false });\r
}\r
\r
function onFeedChunkScrollerWheel(e) {\r
    const sc = e.currentTarget;\r
    const chunk = sc.closest && sc.closest('.feed-chunk');\r
    if (!chunk || !chunk.classList.contains('expanded')) return;\r
    const dy = e.deltaY;\r
    const eps = 2;\r
    const st = sc.scrollTop;\r
    const ch = sc.clientHeight;\r
    const sh = sc.scrollHeight;\r
    const canScrollY = sh > ch + eps;\r
    if (canScrollY) {\r
        if (dy < 0 && st > eps) return;\r
        if (dy > 0 && st < sh - ch - eps) return;\r
    }\r
    e.preventDefault();\r
    e.stopPropagation();\r
    const body = sc.closest('.process-aggregate-body');\r
    const chat = document.getElementById('chat-container');\r
    if (body) {\r
        const bPrev = body.scrollTop;\r
        const bMax = Math.max(0, body.scrollHeight - body.clientHeight);\r
        var bt = bPrev + dy;\r
        if (bt < 0) bt = 0;\r
        if (bt > bMax) bt = bMax;\r
        if (bt !== bPrev) { smoothScrollBy(body, dy); return; }\r
    }\r
    if (chat) smoothScrollBy(chat, dy);\r
}\r
\r
function bindProcessBriefScrollChain(brief) {\r
    if (!brief || brief._briefWheelBound) return;\r
    brief._briefWheelBound = true;\r
    brief.addEventListener('wheel', onProcessBriefWheel, { passive: false });\r
}\r
\r
function onProcessBriefWheel(e) {\r
    const brief = e.currentTarget;\r
    const agg = brief.closest && brief.closest('.process-aggregate');\r
    if (!agg || !agg.classList.contains('is-collapsed')) return;\r
    const dy = e.deltaY;\r
    const eps = 2;\r
    const st = brief.scrollTop;\r
    const ch = brief.clientHeight;\r
    const sh = brief.scrollHeight;\r
    const canScrollY = sh > ch + eps;\r
    if (canScrollY) {\r
        if (dy < 0 && st > eps) return;\r
        if (dy > 0 && st < sh - ch - eps) return;\r
    }\r
    e.preventDefault();\r
    e.stopPropagation();\r
    const chat = document.getElementById('chat-container');\r
    if (chat) smoothScrollBy(chat, dy);\r
}\r
\r
function setBriefRows(brief, texts) {\r
    brief.textContent = '';\r
    texts.forEach(function (t) {\r
        if (!t || !String(t).trim()) return;\r
        const row = document.createElement('div');\r
        row.className = 'process-brief-item';\r
        row.textContent = t;\r
        brief.appendChild(row);\r
    });\r
}\r
\r
function updateProcessBrief(agg) {\r
    if (!agg || !agg.isConnected) return;\r
    const body = agg.querySelector('.process-aggregate-body');\r
    const brief = agg.querySelector('.process-aggregate-brief');\r
    if (!body || !brief) return;\r
    const items = Array.from(body.querySelectorAll('.feed-item'));\r
    const lines = [];\r
    var i = 0;\r
    while (i < items.length) {\r
        var el = items[i];\r
        var raw = getFeedItemText(el);\r
        if (el.classList.contains('feed--llm')) {\r
            if (raw) pushBriefLine(lines, '思·' + raw);\r
            i += 1;\r
        } else if (el.classList.contains('feed--llm2')) {\r
            if (raw) pushBriefLine(lines, '答·' + raw);\r
            i += 1;\r
        } else if (el.classList.contains('feed--tool')) {\r
            var countMap = {};\r
            var order = [];\r
            while (i < items.length && items[i].classList.contains('feed--tool')) {\r
                var tname = extractToolNameFromLog(getFeedItemText(items[i]));\r
                if (countMap[tname] === undefined) { countMap[tname] = 0; order.push(tname); }\r
                countMap[tname] += 1;\r
                i += 1;\r
            }\r
            for (var oi = 0; oi < order.length; oi += 1) {\r
                var nm = order[oi];\r
                var n = countMap[nm] || 0;\r
                if (n > 0) pushBriefLine(lines, '调用工具 ' + nm + ' ' + n + '次');\r
            }\r
        } else { i += 1; }\r
    }\r
    if (lines.length) setBriefRows(brief, lines);\r
    else {\r
        var st = body.querySelector('.feed-item.feed--st .feed-chunk-scroller, .feed-item.feed--st .feed-chunk');\r
        var tSt = st ? st.textContent.trim() : '';\r
        if (tSt) setBriefRows(brief, [tSt]);\r
        else {\r
            var any = body.querySelector('.feed-chunk-scroller, .feed-chunk');\r
            var tAny = any ? any.textContent.trim() : '';\r
            setBriefRows(brief, [tAny || '本段过程已折叠']);\r
        }\r
    }\r
}\r
\r
function bindProcessAggregate(agg) {\r
    const procBody = agg.querySelector('.process-aggregate-body, .subagent-card-body');\r
    if (procBody && !procBody._streamFollowScrollBound) {\r
        procBody._streamFollowScrollBound = true;\r
        procBody.addEventListener('scroll', function () {\r
            if (!isSessionRunning(currentSessionId)) return;\r
            var active = getProcessBodyElForCurrentRun();\r
            if (active !== procBody) return;\r
            refreshLiveAutoFollowPins();\r
        }, { passive: true });\r
    }\r
    if (agg.classList.contains('subagent-grid-card')) return;\r
    const top = agg.querySelector('.process-aggregate-top');\r
    if (top && !top.dataset.bound) {\r
        top.dataset.bound = '1';\r
        top.addEventListener('click', function () {\r
            agg.classList.toggle('is-collapsed');\r
            const expanded = !agg.classList.contains('is-collapsed');\r
            top.setAttribute('aria-expanded', expanded ? 'true' : 'false');\r
            if (agg.classList.contains('is-collapsed')) {\r
                updateProcessBrief(agg);\r
            } else {\r
                requestAnimationFrame(function () {\r
                    requestAnimationFrame(function () {\r
                        agg.querySelectorAll('.process-aggregate-body .feed-chunk').forEach(refreshFeedChunkOverflow);\r
                        registerMermaidLazy(agg);\r
                    });\r
                });\r
            }\r
        });\r
        top.addEventListener('keydown', function (e) {\r
            if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); top.click(); }\r
        });\r
    }\r
    const briefEl = agg.querySelector('.process-aggregate-brief');\r
    if (briefEl) bindProcessBriefScrollChain(briefEl);\r
}\r
\r
function procNow() {\r
    return (typeof performance !== 'undefined' && typeof performance.now === 'function') ? performance.now() : Date.now();\r
}\r
\r
var processAggregateStatsTimer = null;\r
\r
function processAggregateNeedsLiveStats(agg) {\r
    if (!agg || !agg.isConnected || !agg.dataset) return false;\r
    if (!agg.dataset.procStartedAt || agg.dataset.procEndedAt) return false;\r
    return !(agg.dataset.procDurationMs != null && agg.dataset.procDurationMs !== '');\r
}\r
\r
function refreshLiveProcessAggregateStats() {\r
    if (typeof document === 'undefined') return false;\r
    var live = Array.from(document.querySelectorAll('.process-aggregate[data-proc-started-at]'))\r
        .filter(processAggregateNeedsLiveStats);\r
    live.forEach(refreshAggregateStatsSmart);\r
    return live.length > 0;\r
}\r
\r
function stopLiveProcessAggregateStats() {\r
    if (!processAggregateStatsTimer) return;\r
    clearInterval(processAggregateStatsTimer);\r
    processAggregateStatsTimer = null;\r
}\r
\r
function scheduleLiveProcessAggregateStats() {\r
    if (processAggregateStatsTimer) return;\r
    if (!refreshLiveProcessAggregateStats()) return;\r
    processAggregateStatsTimer = setInterval(function () {\r
        if (!refreshLiveProcessAggregateStats()) stopLiveProcessAggregateStats();\r
    }, 250);\r
}\r
\r
function formatProcDurationMs(ms) {\r
    if (ms == null || !Number.isFinite(ms) || ms < 0) return null;\r
    if (ms < 800) return Math.max(0, Math.round(ms)) + 'ms';\r
    if (ms < 60000) {\r
        var s = ms / 1000;\r
        return (s < 10 ? s.toFixed(1) : Math.round(s)) + 's';\r
    }\r
    var mi = Math.floor(ms / 60000);\r
    var sec = Math.round((ms % 60000) / 1000);\r
    return mi + '分' + sec + '秒';\r
}\r
\r
function processStartedAtToProcNow(startedAt) {\r
    if (!startedAt) return null;\r
    var startedMs = Date.parse(String(startedAt));\r
    if (!Number.isFinite(startedMs)) return null;\r
    return procNow() - Math.max(0, Date.now() - startedMs);\r
}\r
\r
function applyRunStartedAtToProcessGroup(agg, startedAt) {\r
    if (!agg || !startedAt) return;\r
    var t0 = processStartedAtToProcNow(startedAt);\r
    if (!Number.isFinite(Number(t0))) return;\r
    agg.dataset.procStartedAt = String(t0);\r
    delete agg.dataset.procEndedAt;\r
    if (!agg.dataset.procDurationMs) refreshProcessAggregateStats(agg);\r
    scheduleLiveProcessAggregateStats();\r
}\r
\r
function bumpAggregateMaxReactIter(agg, reactIter) {\r
    if (!agg) return;\r
    var n = Number(reactIter);\r
    if (!Number.isFinite(n) || n < 1) return;\r
    var flo = Math.floor(n);\r
    var cur = parseInt(agg.dataset.maxReactIter || '0', 10);\r
    if (flo > cur) agg.dataset.maxReactIter = String(flo);\r
}\r
\r
function resolveSubagentAggFromCtx(ctx) {\r
    if (!ctx) return null;\r
    if (ctx.currentProcessGroup && ctx.currentProcessGroup.isConnected\r
        && ctx.currentProcessGroup.classList.contains('subagent-grid-card')) {\r
        return ctx.currentProcessGroup;\r
    }\r
    if (ctx._subagentBody && ctx._subagentBody.isConnected) {\r
        var card = ctx._subagentBody.closest('.subagent-grid-card');\r
        if (card) return card;\r
    }\r
    return null;\r
}\r
\r
function applySubagentSessionMetricsToCard(card, metrics) {\r
    if (!card || !metrics || typeof metrics !== 'object') return;\r
    if (metrics.duration_ms != null && Number.isFinite(Number(metrics.duration_ms))) {\r
        card.dataset.procDurationMs = String(Math.max(0, Math.floor(Number(metrics.duration_ms))));\r
    }\r
    if (metrics.react_loops != null && Number.isFinite(Number(metrics.react_loops))) {\r
        card.dataset.procReactLoops = String(Math.max(0, Math.floor(Number(metrics.react_loops))));\r
    }\r
    if (metrics.tool_calls != null && Number.isFinite(Number(metrics.tool_calls))) {\r
        card.dataset.procToolCalls = String(Math.max(0, Math.floor(Number(metrics.tool_calls))));\r
    }\r
    if (metrics.tool_failures != null && Number.isFinite(Number(metrics.tool_failures))) {\r
        card.dataset.procToolFails = String(Math.max(0, Math.floor(Number(metrics.tool_failures))));\r
    }\r
}\r
\r
function applySubagentProcessMetricsToCard(card, event) {\r
    if (!card || !event) return;\r
    var isRunEnd = event.duration_ms != null && Number.isFinite(Number(event.duration_ms));\r
    if (isRunEnd) {\r
        var runDur = Math.max(0, Math.round(Number(event.duration_ms)));\r
        var runLoops = event.react_loops != null && Number.isFinite(Number(event.react_loops))\r
            ? Math.max(0, Math.floor(Number(event.react_loops))) : 0;\r
        var runTools = event.tool_calls != null && Number.isFinite(Number(event.tool_calls))\r
            ? Math.max(0, Math.floor(Number(event.tool_calls))) : 0;\r
        var runFails = event.tool_failures != null && Number.isFinite(Number(event.tool_failures))\r
            ? Math.max(0, Math.floor(Number(event.tool_failures))) : 0;\r
        card.dataset.procDurationMs = String((parseInt(card.dataset.procDurationMs || '0', 10) || 0) + runDur);\r
        card.dataset.procReactLoops = String((parseInt(card.dataset.procReactLoops || '0', 10) || 0) + runLoops);\r
        card.dataset.procToolCalls = String((parseInt(card.dataset.procToolCalls || '0', 10) || 0) + runTools);\r
        card.dataset.procToolFails = String((parseInt(card.dataset.procToolFails || '0', 10) || 0) + runFails);\r
        delete card.dataset.procLiveToolCalls;\r
        delete card.dataset.procLiveToolFails;\r
    } else {\r
        if (event.tool_calls != null && Number.isFinite(Number(event.tool_calls))) {\r
            var liveTools = Math.max(0, Math.floor(Number(event.tool_calls)));\r
            var prevTools = parseInt(card.dataset.procLiveToolCalls || '0', 10) || 0;\r
            card.dataset.procLiveToolCalls = String(Math.max(prevTools, liveTools));\r
        }\r
        if (event.tool_failures != null && Number.isFinite(Number(event.tool_failures))) {\r
            var liveFails = Math.max(0, Math.floor(Number(event.tool_failures)));\r
            var prevFails = parseInt(card.dataset.procLiveToolFails || '0', 10) || 0;\r
            card.dataset.procLiveToolFails = String(Math.max(prevFails, liveFails));\r
        }\r
    }\r
}\r
\r
function uiEventReactIter(ev) {\r
    if (!ev || ev.react_iter == null) return null;\r
    var n = Number(ev.react_iter);\r
    if (!Number.isFinite(n) || n < 1) return null;\r
    return n;\r
}\r
\r
function applyCacheStatsFromEvent(ctx, event) {\r
    if (!event || typeof event !== 'object') return;\r
    var agg = resolveSubagentAggFromCtx(ctx);\r
    if (!agg || !agg.isConnected) {\r
        agg = ctx && ctx.currentProcessGroup;\r
        if (!agg || !agg.isConnected) {\r
            var st = (ctx && ctx.stream) ? ctx.stream : getVisibleChatStream();\r
            if (st) agg = st.querySelector('.process-aggregate:last-of-type');\r
        }\r
    }\r
    if (!agg) return;\r
    if (event.cache_hit != null) agg.dataset.procCacheHit = String(Math.max(0, Math.floor(Number(event.cache_hit))));\r
    if (event.cache_miss != null) agg.dataset.procCacheMiss = String(Math.max(0, Math.floor(Number(event.cache_miss))));\r
    if (event.hit_rate != null) agg.dataset.procCacheRate = String(Math.max(0, Number(event.hit_rate)));\r
    if (event.model != null) agg.dataset.procCacheModel = String(event.model);\r
    if (event.input_tokens != null) agg.dataset.procCacheInput = String(Math.max(0, Math.floor(Number(event.input_tokens))));\r
    if (event.output_tokens != null) agg.dataset.procCacheOutput = String(Math.max(0, Math.floor(Number(event.output_tokens))));\r
    if (event.tokens_per_sec != null) agg.dataset.procCacheTps = String(Math.max(0, Number(event.tokens_per_sec)));\r
    refreshAggregateStatsSmart(agg);\r
}\r
\r
function applyProcessMetricsFromEvent(ctx, event) {\r
    if (!event || typeof event !== 'object') return;\r
    var subCard = resolveSubagentAggFromCtx(ctx);\r
    if (subCard && subCard.isConnected) {\r
        applySubagentProcessMetricsToCard(subCard, event);\r
        scheduleSubagentCardStats(subCard);\r
        return;\r
    }\r
    var agg = ctx && ctx.currentProcessGroup;\r
    if (!agg || !agg.isConnected) {\r
        var st = (ctx && ctx.stream) ? ctx.stream : getVisibleChatStream();\r
        if (st) agg = st.querySelector('.process-aggregate:last-of-type');\r
    }\r
    if (!agg) return;\r
    if (event.duration_ms != null && Number.isFinite(Number(event.duration_ms))) {\r
        if (!replayingMessages && agg.dataset.procStartedAt) {\r
            agg.dataset.procEndedAt = String(procNow());\r
            delete agg.dataset.procDurationMs;\r
        } else {\r
            agg.dataset.procDurationMs = String(Math.max(0, Math.round(Number(event.duration_ms))));\r
        }\r
    }\r
    if (event.react_loops != null && Number.isFinite(Number(event.react_loops))) {\r
        agg.dataset.procReactLoops = String(Math.max(0, Math.floor(Number(event.react_loops))));\r
    }\r
    if (event.tool_calls != null && Number.isFinite(Number(event.tool_calls))) {\r
        agg.dataset.procToolCalls = String(Math.max(0, Math.floor(Number(event.tool_calls))));\r
    }\r
    if (event.tool_failures != null && Number.isFinite(Number(event.tool_failures))) {\r
        agg.dataset.procToolFails = String(Math.max(0, Math.floor(Number(event.tool_failures))));\r
    }\r
    refreshAggregateStatsSmart(agg);\r
    if (processAggregateNeedsLiveStats(agg)) scheduleLiveProcessAggregateStats();\r
    else if (!refreshLiveProcessAggregateStats()) stopLiveProcessAggregateStats();\r
}\r
\r
function refreshAggregateStatsSmart(agg) {\r
    if (agg && agg.classList && agg.classList.contains('subagent-grid-card')) refreshSubagentCardStats(agg);\r
    else refreshProcessAggregateStats(agg);\r
}\r
\r
function refreshSubagentCardStats(card) {\r
    if (!card) return;\r
    var el = card.querySelector('.process-aggregate-stats');\r
    if (!el) return;\r
    var body = card.querySelector('.subagent-card-body');\r
    var pDur = card.dataset.procDurationMs != null && card.dataset.procDurationMs !== ''\r
        ? parseInt(card.dataset.procDurationMs, 10) : NaN;\r
    var pLoops = card.dataset.procReactLoops != null && card.dataset.procReactLoops !== ''\r
        ? parseInt(card.dataset.procReactLoops, 10) : NaN;\r
    var pTools = card.dataset.procToolCalls != null && card.dataset.procToolCalls !== ''\r
        ? parseInt(card.dataset.procToolCalls, 10) : NaN;\r
    var pFails = card.dataset.procToolFails != null && card.dataset.procToolFails !== ''\r
        ? parseInt(card.dataset.procToolFails, 10) : NaN;\r
    var maxFromRows = 0;\r
    var bodyLoaded = subagentBodyIsLoaded(body) && body.dataset.stashed !== '1';\r
    if (bodyLoaded) {\r
        body.querySelectorAll('.subagent-turn-process .feed-item[data-react-iter]').forEach(function (row) {\r
            var v = parseInt(row.getAttribute('data-react-iter'), 10);\r
            if (Number.isFinite(v) && v > maxFromRows) maxFromRows = v;\r
        });\r
    }\r
    var dsRi = card.dataset.maxReactIter ? parseInt(card.dataset.maxReactIter, 10) : 0;\r
    var reactLoops = Math.max(maxFromRows, dsRi);\r
    if (!reactLoops && bodyLoaded) {\r
        reactLoops = body.querySelectorAll('.subagent-turn-process .feed-item[data-log-type="llm-response"]').length;\r
    }\r
    if (Number.isFinite(pLoops) && pLoops > 0) reactLoops = pLoops;\r
    var sessionTools = Number.isFinite(pTools) && pTools >= 0 ? pTools : 0;\r
    var liveTools = parseInt(card.dataset.procLiveToolCalls || '0', 10) || 0;\r
    var toolN = sessionTools + liveTools;\r
    if (!toolN && bodyLoaded) {\r
        toolN = body.querySelectorAll('.subagent-turn-process .feed-item[data-log-type="tool-call"]').length;\r
    }\r
    var sessionFails = Number.isFinite(pFails) && pFails >= 0 ? pFails : 0;\r
    var liveFails = parseInt(card.dataset.procLiveToolFails || '0', 10) || 0;\r
    var failN = sessionFails + liveFails;\r
    if (!failN && bodyLoaded) {\r
        body.querySelectorAll('.subagent-turn-process .feed-item[data-log-type="tool-call"]').forEach(function (row) {\r
            var sc = row.querySelector('.feed-chunk-scroller');\r
            var txt = sc ? String(sc.textContent || '') : '';\r
            if (/Error:|失败|异常|error executing command:/i.test(txt)) failN += 1;\r
        });\r
    }\r
    var t0s = card.dataset.procStartedAt;\r
    var t0 = (t0s != null && t0s !== '') ? Number(t0s) : NaN;\r
    var parts = [];\r
    var durStr = null;\r
    if (Number.isFinite(pDur) && pDur >= 0) durStr = formatProcDurationMs(pDur);\r
    else if (Number.isFinite(t0)) {\r
        var t1s = card.dataset.procEndedAt;\r
        var t1 = (t1s != null && t1s !== '') ? Number(t1s) : procNow();\r
        durStr = formatProcDurationMs(t1 - t0);\r
    }\r
    if (durStr) parts.push(durStr);\r
    parts.push(String(reactLoops) + ' 轮');\r
    parts.push('工具 ' + String(toolN) + ' 次');\r
    parts.push('失败 ' + String(failN) + ' 次');\r
    var modelStr = card.dataset.procCacheModel || card.dataset.executorModel || '—';\r
    var est = card.dataset.procCtxEstimated;\r
    var thr = card.dataset.procCtxThreshold;\r
    var pctStr = '—';\r
    if (est != null && est !== '' && thr != null && thr !== '' && Number(thr) > 0) {\r
        pctStr = (Math.round(Number(est) / Number(thr) * 1000) / 10) + '%';\r
    }\r
    el.innerHTML = '<span>' + parts.join(' · ') + '</span><span>' + escapeHtml(modelStr) + ' · ' + escapeHtml(pctStr) + '</span>';\r
}\r
\r
function refreshProcessAggregateStats(agg) {\r
    if (!agg) return;\r
    var el = agg.querySelector('.process-aggregate-stats');\r
    if (!el) return;\r
    var body = agg.querySelector('.process-aggregate-body');\r
    if (!body) { el.textContent = ''; return; }\r
    var pDur = agg.dataset.procDurationMs != null && agg.dataset.procDurationMs !== ''\r
        ? parseInt(agg.dataset.procDurationMs, 10) : NaN;\r
    var pLoops = agg.dataset.procReactLoops != null && agg.dataset.procReactLoops !== ''\r
        ? parseInt(agg.dataset.procReactLoops, 10) : NaN;\r
    var pTools = agg.dataset.procToolCalls != null && agg.dataset.procToolCalls !== ''\r
        ? parseInt(agg.dataset.procToolCalls, 10) : NaN;\r
    var pFails = agg.dataset.procToolFails != null && agg.dataset.procToolFails !== ''\r
        ? parseInt(agg.dataset.procToolFails, 10) : NaN;\r
    var maxFromRows = 0;\r
    body.querySelectorAll('.feed-item[data-react-iter]').forEach(function (row) {\r
        var v = parseInt(row.getAttribute('data-react-iter'), 10);\r
        if (Number.isFinite(v) && v > maxFromRows) maxFromRows = v;\r
    });\r
    var dsRi = agg.dataset.maxReactIter ? parseInt(agg.dataset.maxReactIter, 10) : 0;\r
    var reactLoops = Math.max(maxFromRows, dsRi);\r
    if (!reactLoops) {\r
        reactLoops = body.querySelectorAll('.feed-item[data-log-type="llm-response"]').length;\r
    }\r
    if (Number.isFinite(pLoops) && pLoops >= 0) reactLoops = pLoops;\r
    var toolN = body.querySelectorAll('.feed-item[data-log-type="tool-call"]').length;\r
    if (Number.isFinite(pTools) && pTools >= 0) toolN = pTools;\r
    var failN = 0;\r
    if (Number.isFinite(pFails) && pFails >= 0) failN = pFails;\r
    var t0s = agg.dataset.procStartedAt;\r
    var t0 = (t0s != null && t0s !== '') ? Number(t0s) : NaN;\r
    var parts = [];\r
    var durStr = null;\r
    if (Number.isFinite(pDur) && pDur >= 0) durStr = formatProcDurationMs(pDur);\r
    else if (Number.isFinite(t0)) {\r
        var t1s = agg.dataset.procEndedAt;\r
        var t1 = (t1s != null && t1s !== '') ? Number(t1s) : procNow();\r
        durStr = formatProcDurationMs(t1 - t0);\r
    }\r
    if (durStr) parts.push(durStr);\r
    parts.push(String(reactLoops) + ' 轮');\r
    parts.push('工具 ' + String(toolN) + ' 次');\r
        parts.push('失败 ' + String(failN) + ' 次');\r
    var ch = agg.dataset.procCacheHit != null && agg.dataset.procCacheHit !== '' ? parseInt(agg.dataset.procCacheHit, 10) : 0;\r
    var cm = agg.dataset.procCacheMiss != null && agg.dataset.procCacheMiss !== '' ? parseInt(agg.dataset.procCacheMiss, 10) : 0;\r
    var cr = agg.dataset.procCacheRate != null && agg.dataset.procCacheRate !== '' ? parseFloat(agg.dataset.procCacheRate) : 0;\r
    var modelStr = agg.dataset.procCacheModel || '';\r
    var inputStr = agg.dataset.procCacheInput || '0';\r
    var outputStr = agg.dataset.procCacheOutput || '0';\r
    var tps = agg.dataset.procCacheTps;\r
    var cacheParts = [];\r
    if (modelStr) cacheParts.push(modelStr);\r
    cacheParts.push('input=' + inputStr);\r
    cacheParts.push('output=' + outputStr);\r
    if (tps && tps !== '0') cacheParts.push(tps + ' tok/s');\r
    var rateStr = (ch + cm > 0) ? (cr % 1 === 0 ? cr.toFixed(0) : cr.toFixed(1)) + '%' : '0%';\r
    cacheParts.push('hit_rate=' + rateStr);\r
    var cacheLine = cacheParts.join(' · ');\r
    el.innerHTML = '<span>' + parts.join(' · ') + '</span><span>' + cacheLine + '</span>';\r
}\r
\r
function ensureProcessGroup(ctx) {\r
    if (!ctx || !ctx.stream) return null;\r
    /* DocumentFragment 或未挂上 document 的节点 isConnected 为 false；回放或「加载更早消息」预挂载时需保留同一执行过程框 */\r
    if (ctx.currentProcessGroup && !ctx.currentProcessGroup.isConnected && !replayingMessages) ctx.currentProcessGroup = null;\r
    if (ctx.currentProcessGroup) return ctx.currentProcessGroup;\r
    stripWelcome(ctx);\r
    const wrap = document.createElement('div');\r
    wrap.className = 'process-aggregate';\r
    var replayCollapsed = !!replayingMessages;\r
    if (replayCollapsed) wrap.classList.add('is-collapsed');\r
    if (!replayingMessages) wrap.classList.add('is-running');\r
    wrap.innerHTML = '<div class="process-aggregate-top" role="button" tabindex="0" aria-expanded="' + (replayCollapsed ? 'false' : 'true') + '">'\r
        + '<div class="process-aggregate-top-line">'\r
        + '<span class="process-aggregate-title-wrap">'\r
        + '<span class="process-aggregate-title">执行过程</span>'\r
        + '<span class="process-aggregate-stats" aria-live="polite"></span>'\r
        + '</span>'\r
        + '<span class="process-chev" aria-hidden="true">▼</span></div>'\r
        + '<div class="process-aggregate-brief"></div></div>'\r
        + '<div class="process-aggregate-body"></div>';\r
    if (!replayingMessages) {\r
        if (ctx.runStartedAt) applyRunStartedAtToProcessGroup(wrap, ctx.runStartedAt);\r
        else {\r
            wrap.dataset.procStartedAt = String(procNow());\r
        }\r
    }\r
    delete wrap.dataset.maxReactIter;\r
    (ctx.stream || chatContainer).appendChild(wrap);\r
    bindProcessAggregate(wrap);\r
    ctx.currentProcessGroup = wrap;\r
    refreshProcessAggregateStats(wrap);\r
    if (processAggregateNeedsLiveStats(wrap)) scheduleLiveProcessAggregateStats();\r
    return wrap;\r
}\r
\r
function sealProcessGroup(ctx) {\r
    if (!ctx) return;\r
    if (!ctx.currentProcessGroup) return;\r
    const agg = ctx.currentProcessGroup;\r
    if (agg.isConnected) {\r
        agg.classList.remove('is-running');\r
        updateProcessBrief(agg);\r
        if (agg.dataset.procStartedAt) agg.dataset.procEndedAt = String(procNow());\r
        refreshProcessAggregateStats(agg);\r
        if (!refreshLiveProcessAggregateStats()) stopLiveProcessAggregateStats();\r
    }\r
    ctx.currentProcessGroup = null;\r
    ctx.progressScrollers = {};\r
    resetKeyContextStreamFilter(ctx);\r
    finalizeProgressStreamChunks(ctx);\r
}\r
\r
function getProcessBody(ctx) {\r
    if (ctx && ctx._subagentTurnProcess && ctx._subagentTurnProcess.isConnected) return ctx._subagentTurnProcess;\r
    if (ctx && ctx.currentTurn && ctx.currentTurn.isConnected) {\r
        var subProc = ctx.currentTurn.querySelector('.subagent-turn-process');\r
        if (subProc) {\r
            ctx._subagentTurnProcess = subProc;\r
            return subProc;\r
        }\r
    }\r
    if (ctx && ctx._subagentBody && ctx._subagentBody.isConnected) return null;\r
    const w = ensureProcessGroup(ctx);\r
    if (!w) return null;\r
    return w.querySelector('.process-aggregate-body');\r
}\r
\r
function autoResizeTextarea() {\r
    messageInput.style.height = 'auto';\r
    messageInput.style.height = Math.min(messageInput.scrollHeight, 120) + 'px';\r
}\r
messageInput.addEventListener('input', autoResizeTextarea);\r
messageInput.addEventListener('input', rewriteInputWorkspacePaths);\r
messageInput.addEventListener('input', function () {\r
    if (currentSessionId) persistInputDraft(currentSessionId, messageInput.value);\r
    if (typeof setSendButtonState === 'function') setSendButtonState();\r
});\r
autoResizeTextarea();\r
refreshInputPathChips();\r
\r
function escapeHtml(str) {
    if (!str) return '';
    return str.replace(/[&<>]/g, function(m) {
        if (m === '&') return '&amp;';
        if (m === '<') return '&lt;';
        if (m === '>') return '&gt;';\r
        return m;
    });
}

function escapeHtmlAttr(str) {
    return escapeHtml(String(str || '')).replace(/"/g, '&quot;').replace(/'/g, '&#39;');
}

function scrollToBottom() {
    requestAnimationFrame(function () {\r
        requestAnimationFrame(function () {\r
            if (chatContainer) chatContainer.scrollTop = chatContainer.scrollHeight;\r
            requestAnimationFrame(function () {\r
                if (chatContainer) chatContainer.scrollTop = chatContainer.scrollHeight;\r
            });\r
        });\r
    });\r
}\r
\r
// 滚动位置存储\r
const LS_SCROLL_POSITION_PREFIX = 'myagent-scroll-';\r
const LS_SCROLL_ANCHOR_PREFIX = 'myagent-scroll-anchor-';\r
\r
function getScrollPositionKey(sessionId) {\r
    return LS_SCROLL_POSITION_PREFIX + sessionId;\r
}\r
\r
function getScrollAnchorKey(sessionId) {\r
    return LS_SCROLL_ANCHOR_PREFIX + sessionId;\r
}\r
\r
function saveScrollPosition(sessionId, scrollTop) {\r
    if (!sessionId) return;\r
    try {\r
        localStorage.setItem(getScrollPositionKey(sessionId), String(Math.round(scrollTop)));\r
    } catch (e) { /* ignore */ }\r
}\r
\r
function saveScrollAnchorPosition(sessionId) {\r
    if (!chatContainer || !sessionId) return;\r
    try {\r
        if (isNearBottom(chatContainer, STREAM_CHAT_NEAR_BOTTOM_PX)) {\r
            localStorage.removeItem(getScrollAnchorKey(sessionId));\r
            return;\r
        }\r
        var rect = chatContainer.getBoundingClientRect();\r
        var wraps = chatContainer.querySelectorAll('.msg-wrap--user[data-event-index]');\r
        var best = null;\r
        for (var i = 0; i < wraps.length; i += 1) {\r
            var wr = wraps[i];\r
            var ei = Number(wr.getAttribute('data-event-index'));\r
            if (!Number.isFinite(ei)) continue;\r
            var top = wr.getBoundingClientRect().top;\r
            if (top <= rect.top + 8) best = ei;\r
            else if (best == null) {\r
                best = ei;\r
                break;\r
            }\r
        }\r
        if (best != null) localStorage.setItem(getScrollAnchorKey(sessionId), String(best));\r
    } catch (e) { /* ignore */ }\r
}\r
\r
function getSavedScrollAnchorPosition(sessionId) {\r
    if (!sessionId) return null;\r
    try {\r
        var saved = localStorage.getItem(getScrollAnchorKey(sessionId));\r
        if (saved == null || saved === '') return null;\r
        var n = Number(saved);\r
        return Number.isFinite(n) ? n : null;\r
    } catch (e) { return null; }\r
}\r
\r
function getSavedScrollPosition(sessionId) {\r
    if (!sessionId) return null;\r
    try {\r
        var saved = localStorage.getItem(getScrollPositionKey(sessionId));\r
        return saved ? parseInt(saved, 10) : null;\r
    } catch (e) { return null; }\r
}\r
\r
function saveChatScrollForSession(sid) {\r
    if (!chatContainer || !sid) return;\r
    saveScrollPosition(sid, chatContainer.scrollTop);\r
    saveScrollAnchorPosition(sid);\r
}\r
\r
function clampChatScrollTop(y) {\r
    if (!chatContainer) return 0;\r
    const max = Math.max(0, chatContainer.scrollHeight - chatContainer.clientHeight);\r
    return Math.min(Math.max(0, y), max);\r
}\r
\r
/**\r
 * @param {string} sessionId\r
 * @param {'saved-or-bottom'|'bottom'} mode — saved-or-bottom：有离开记录则恢复，否则置底；bottom：始终置底\r
 */\r
function applyChatScrollAfterHistoryLoad(sessionId, mode) {\r
    if (!chatContainer || !sessionId) return;\r
    \r
    // 如果会话正在运行，执行过程块默认置底\r
    if (isSessionRunning(sessionId)) {\r
        var run = getSessionRunState(sessionId);\r
        if (run && run.ctx && run.ctx.stream) {\r
            var agg = run.ctx.stream.querySelector('.process-aggregate:last-of-type');\r
            if (agg) {\r
                var procBody = agg.querySelector('.process-aggregate-body');\r
                if (procBody) {\r
                    // 延迟一帧确保DOM已渲染\r
                    requestAnimationFrame(function() {\r
                        procBody.scrollTop = procBody.scrollHeight;\r
                    });\r
                }\r
            }\r
        }\r
    }\r
    \r
    if (mode === 'saved-or-bottom') {\r
        var savedAnchor = getSavedScrollAnchorPosition(sessionId);\r
        if (savedAnchor != null && typeof scrollToUserTurnOrLoadOlder === 'function') {\r
            requestAnimationFrame(function () {\r
                if (sessionId === currentSessionId) void scrollToUserTurnOrLoadOlder(savedAnchor);\r
            });\r
            streamChatNearBottom = false;\r
            streamProcNearBottom = true;\r
            liveAutoFollow = false;\r
            return;\r
        }\r
        var savedPosition = getSavedScrollPosition(sessionId);\r
        if (savedPosition !== null && savedPosition > 0) {\r
            // 恢复保存的滚动位置\r
            chatContainer.scrollTop = savedPosition;\r
            streamChatNearBottom = isNearBottom(chatContainer, STREAM_CHAT_NEAR_BOTTOM_PX);\r
            streamProcNearBottom = true;\r
            liveAutoFollow = streamChatNearBottom;\r
            return;\r
        }\r
    }\r
    \r
    // 默认行为：滚动到底部\r
    streamChatNearBottom = true;\r
    streamProcNearBottom = true;\r
    liveAutoFollow = true;\r
    scrollToBottom();\r
}\r
\r
window.addEventListener('beforeunload', function () {\r
    saveChatScrollForSession(currentSessionId);\r
});\r
document.addEventListener('visibilitychange', function () {\r
    if (document.visibilityState === 'hidden') saveChatScrollForSession(currentSessionId);\r
    else if (typeof reconcileRunStateFromServer === 'function') {\r
        void reconcileRunStateFromServer({ silent: true });\r
    }\r
});\r
window.addEventListener('pageshow', function () {\r
    if (typeof reconcileRunStateFromServer === 'function') {\r
        void reconcileRunStateFromServer({ silent: true });\r
    }\r
});\r
window.addEventListener('focus', function () {\r
    if (typeof reconcileRunStateFromServer === 'function') {\r
        void reconcileRunStateFromServer({ silent: true });\r
    }\r
});\r
\r
const WELCOME_HTML = \`<div class="welcome" role="status"><div class="welcome-icon" aria-hidden="true"><img src="/assets/sugar-logo.png" alt="" draggable="false"></div><strong>开始一段新的对话</strong><p>在左侧侧栏新建或选择会话。Enter 发送，Ctrl+Enter / Shift+Enter 换行。</p></div>\`;\r
\r
function historyLoadScrollsToBottom(sessionId, mode) {\r
    return true;\r
}\r
\r
function waitForChatScrollAfterHistoryLoad(sessionId, mode) {\r
    if (!chatContainer || !sessionId) return Promise.resolve(false);\r
    var toBottom = true;\r
    var started = (window.performance && performance.now) ? performance.now() : Date.now();\r
    var lastTop = -1;\r
    var stableFrames = 0;\r
    return new Promise(function (resolve) {\r
        var done = false;\r
        var cleanup = null;\r
        function nowMs() {\r
            return (window.performance && performance.now) ? performance.now() : Date.now();\r
        }\r
        function targetReached() {\r
            if (!chatContainer) return true;\r
            return isNearBottom(chatContainer, 24);\r
        }\r
        function finish(ok) {\r
            if (done) return;\r
            done = true;\r
            if (cleanup) cleanup();\r
            resolve(ok);\r
        }\r
        if ('onscrollend' in chatContainer) {\r
            var onEnd = function () {\r
                if (sessionId !== currentSessionId) {\r
                    finish(false);\r
                    return;\r
                }\r
                if (targetReached()) finish(true);\r
            };\r
            chatContainer.addEventListener('scrollend', onEnd, { passive: true });\r
            cleanup = function () {\r
                chatContainer.removeEventListener('scrollend', onEnd);\r
            };\r
        }\r
        function step() {\r
            if (done) return;\r
            if (sessionId !== currentSessionId || !chatContainer) {\r
                finish(false);\r
                return;\r
            }\r
            var top = chatContainer.scrollTop;\r
            var reached = targetReached();\r
            if (Math.abs(top - lastTop) < 0.5) stableFrames += 1;\r
            else stableFrames = 0;\r
            lastTop = top;\r
            if ((reached && stableFrames >= 2) || nowMs() - started > 2400) {\r
                finish(reached);\r
                return;\r
            }\r
            requestAnimationFrame(step);\r
        }\r
        requestAnimationFrame(step);\r
    });\r
}\r
\r
function setWelcome() {\r
    resetSessionHistoryPaging();\r
    const vs = getVisibleChatStream();\r
    if (vs) {\r
        emptyChatStreamKeepingStrip(vs);\r
        vs.insertAdjacentHTML('beforeend', WELCOME_HTML);\r
    } else {\r
        chatContainer.innerHTML = '';\r
        ensureVisibleChatStreamSlot();\r
        const vs2 = getVisibleChatStream();\r
        if (vs2) vs2.insertAdjacentHTML('beforeend', WELCOME_HTML);\r
        else chatContainer.innerHTML = WELCOME_HTML;\r
    }\r
    rebuildToc();\r
    renderTodoPlanForCurrentSession();\r
}\r
\r
function stripWelcome(ctx) {\r
    if (ctx && ctx._subagentBody) return;\r
    const root = (ctx && ctx.stream) ? ctx.stream : (getVisibleChatStream() || chatContainer);\r
    if (root) root.querySelector('.welcome')?.remove();\r
}\r
\r
function clearChat() { setWelcome(); }\r
\r
function pathJoinBaseName(baseDir, name) {\r
    if (!baseDir) return name || '';\r
    if (!name) return baseDir;\r
    var d = String(baseDir).replace(/[\\\\/]+$/, '');\r
    var useBack = d.indexOf('\\\\') !== -1;\r
    return d + (useBack ? '\\\\' : '/') + name;\r
}\r
\r
/** 将「工作区绝对路径」转为 file:// URL（Windows / Unix）；分段编码以支持空格、中文等。 */\r
function fileUrlFromFsPath(fsPath) {\r
    var norm = String(fsPath || '').replace(/\\\\/g, '/');\r
    if (/^\\/\\//.test(norm)) return 'file:' + norm.replace(/\\//g, '/');\r
    var encRest = function (rel) {\r
        if (!rel) return '';\r
        return rel.split('/').map(function (seg) {\r
            return encodeURIComponent(seg);\r
        }).join('/');\r
    };\r
    if (/^[A-Za-z]:\\//.test(norm)) {\r
        return 'file:///' + norm.slice(0, 3) + encRest(norm.slice(3));\r
    }\r
    return 'file:///' + encRest(norm.replace(/^\\/+/, ''));\r
}\r
\r
/**\r
 * 助手常写「保存至：📄 /报告.md」——以 / 开头表示相对工作区根目录的路径（非 URL）。\r
 */\r
function joinWorkDirAndRelativeSlashPath(workDir, slashPath) {\r
    var rel = String(slashPath || '').replace(/^\\/+/, '');\r
    if (!rel || !workDir) return null;\r
    var d = String(workDir).replace(/[\\\\/]+$/, '');\r
    var useBack = d.indexOf('\\\\') !== -1;\r
    var segs = rel.split(/\\/+/).filter(Boolean);\r
    if (!segs.length) return null;\r
    var tail = segs.join(useBack ? '\\\\' : '/');\r
    return d + (useBack ? '\\\\' : '/') + tail;\r
}\r
\r
function trimTrailingPathPunct(s) {\r
    return String(s || '').replace(/[，。、；：）】』」\\]\\)\\.,;:!?'"」]+$/g, '').trim();\r
}\r
\r
function stripPathWrappingQuotes(s) {\r
    var t = String(s || '').trim();\r
    if (t.length >= 2) {\r
        var a = t.charAt(0);\r
        var b = t.charAt(t.length - 1);\r
        if ((a === '"' && b === '"') || (a === "'" && b === "'")) {\r
            return t.slice(1, -1).trim();\r
        }\r
    }\r
    return t;\r
}\r
\r
function decodePathPercentEscapes(s) {\r
    var t = String(s || '');\r
    if (t.indexOf('%') < 0) return t;\r
    return t.replace(/(?:%[0-9A-Fa-f]{2})+/g, function (part) {\r
        try {\r
            return decodeURIComponent(part);\r
        } catch (e) {\r
            return part;\r
        }\r
    });\r
}\r
\r
function cleanPathTokenForLink(s) {\r
    var t = linkifyNormalizePathToken(String(s || '').trim());\r
    if (!/^https?:\\/\\//i.test(t)) t = decodePathPercentEscapes(t);\r
    if (!t) return '';\r
    var a = t.charAt(0);\r
    var b = t.charAt(t.length - 1);\r
    if (t.length >= 2 && ((a === '"' && b === '"') || (a === "'" && b === "'"))) {\r
        return trimTrailingPathPunct(t.slice(1, -1).trim());\r
    }\r
    return stripPathWrappingQuotes(trimTrailingPathPunct(t));\r
}\r
\r
/** 统一全角标点/数字等，便于识别「．xlsx」「路径：／」等变体 */\r
function linkifyNormalizePathToken(s) {\r
    try {\r
        return String(s || '').normalize('NFKC');\r
    } catch (e) {\r
        return String(s || '');\r
    }\r
}\r
\r
/** 可链转「工作区下文件」的已知后缀（与 linkify / 虚拟路径规则共用） */\r
var LINKIFY_EXT_FRAGMENT = (\r
    'md|markdown|txt|py|jsx?|tsx?|mjs|cjs|json|ya?ml|toml|xml|html?|htm|css|s?css|less|sass|scss|' +\r
    'xlsx?|xlsm?|xlsb?|xlt|csv|tsv|ods|numbers|et|' +\r
    'pdf|docx?|docm?|dotx?|rtf|odt|pages|' +\r
    'pptx?|pptm?|potx?|odp|key|' +\r
    'png|jpe?g|gif|webp|svg|ico|bmp|tiff?|heic|avif|jfif|raw|' +\r
    'zip|7z|rar|gz|tgz|tar|bz2|xz|lz4|zst|' +\r
    'mp3|mp4|m4a|aac|flac|wav|ogg|webm|mov|avi|mkv|' +\r
    'log|ini|env|cfg|conf|properties|plist|' +\r
    'sh|bash|zsh|fish|bat|cmd|ps1|' +\r
    'rs|go|java|kt|kts|swift|scala|rb|php|pl|pm|' +\r
    '[ch]pp?|cc|hh|mm|hpp|cs|fs|fsx|vb|' +\r
    'vue|svelte|elm|dart|ex|exs|erl|hrl|' +\r
    'ipynb|rmd|qmd|tex|bib|cls|sty|rst|adoc|org|' +\r
    'sql|graphql|proto|thrift|cmake|gradle|mk|dockerfile|' +\r
    'wasm|wat|lock|patch|diff|rej|har|drawio|vsix|' +\r
    'sqlite3?|db|duckdb|mdb|accdb|parquet|feather|arrow|orc|ndjson|' +\r
    'ttf|otf|woff2?|eot|apk|ipa|exe|msi|dmg|iso|pkg|deb|rpm|bin|so|dylib|dll|lib|o|a|map|' +\r
    'epub|mobi|azw3|chm|cert|pem|crt|cer|pub|asc|p12|pfx|keystore'\r
);\r
\r
var _linkifyKnownExtRe = null;\r
function linkifyKnownExtRegex() {\r
    if (!_linkifyKnownExtRe) {\r
        _linkifyKnownExtRe = new RegExp('\\\\.(' + LINKIFY_EXT_FRAGMENT + ')\\\\b', 'i');\r
    }\r
    return _linkifyKnownExtRe;\r
}\r
\r
/**\r
 * 以 / 开头的「工作区相对路径」是否做成可点击链接。\r
 * 仅允许带常见文件后缀的路径，避免 ARPU/DOU/MOU、日期 2024/01 等内联斜杠被当成目录。\r
 * （仍排除明显的 POSIX/Git Bash 根路径，以免误链。）\r
 */\r
function workspaceRelativePathAutoLinkOk(slashPath) {\r
    var t = linkifyNormalizePathToken(String(slashPath || '').trim());\r
    if (!t || t.charAt(0) !== '/' || t.charAt(1) === '/') return false;\r
    var posixTop = /^\\/(mingw\\d*|usr|bin|etc|proc|dev|sys|opt|var|run|lib|lib64|snap|sbin|boot|srv|tmp|media|mnt)(\\/|$)/i;\r
    var msysDrive = /^\\/[a-z](\\/|$)/i;\r
    var webish = /^\\/(api|v\\d+|static|assets|node_modules)(\\/|$)/i;\r
    if (posixTop.test(t) || msysDrive.test(t) || webish.test(t)) return false;\r
    return linkifyKnownExtRegex().test(t);\r
}\r
\r
function workspaceRelativePathNoSlashAutoLinkOk(relPath) {\r
    var t = linkifyNormalizePathToken(String(relPath || '').trim());\r
    if (!t || t.charAt(0) === '/' || t.charAt(0) === '\\\\' || /^https?:\\/\\//i.test(t)) return false;\r
    if (/^([A-Za-z]):[\\\\/]/.test(t) || /^\\\\\\\\/.test(t)) return false;\r
    if (!/[\\\\/]/.test(t)) return false;\r
    if (/[<>:'"|\\r\\n]/.test(t)) return false;\r
    if (/(^|[\\\\/])\\.{1,2}([\\\\/]|$)/.test(t)) return false;\r
    return linkifyKnownExtRegex().test(t);\r
}\r
\r
function workspaceRelFromNormalizedAbs(absNorm, workDir) {
    if (!absNorm || !workDir) return null;
    var base = String(workDir).replace(/\\\\/g, '/').replace(/\\/+$/, '');
    var absLower = absNorm.toLowerCase();
    var baseLower = base.toLowerCase();
    if (absLower === baseLower) return '';\r
    if (absLower.indexOf(baseLower + '/') === 0) {\r
        return absNorm.slice(base.length).replace(/^\\/+/, '');\r
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
    var sdir = (typeof window.__SESSIONS_DIR__ === 'string') ? window.__SESSIONS_DIR__ : '';\r
    if (sdir && currentSessionId) return pathJoinBaseName(sdir, currentSessionId);\r
    var w = (typeof window.__WORK_DIR__ === 'string') ? window.__WORK_DIR__ : '';\r
    if (w && currentSessionId) return pathJoinBaseName(pathJoinBaseName(w, 'sessions'), currentSessionId);\r
    return '';\r
}\r
\r
/** 标题栏与侧栏：工作目录绝对路径与会话 ID（与服务端 window.__WORK_DIR__ 一致） */\r
function buildSessionWorkspaceSubtitle(sessionId) {\r
    var w = (typeof window.__WORK_DIR__ === 'string') ? window.__WORK_DIR__ : '';\r
    if (!sessionId) return w || '';\r
    if (w) {\r
        var workspaceLink = '<a href="#" data-workspace-open="' + w + '" class="msg-link-workspace-open" style="color:inherit;text-decoration:inherit;cursor:pointer;" data-ui-tip="打开工作目录">' + w + '</a>';\r
        var sessionPath = 'sessions/' + sessionId;\r
        var sessionLink = '<a href="#" data-workspace-open="' + sessionPath + '" class="msg-link-workspace-open" style="color:inherit;text-decoration:inherit;cursor:pointer;" data-ui-tip="打开会话目录">' + sessionId + '</a>';\r
        return workspaceLink + ' | ' + sessionLink;\r
    }\r
    return String(sessionId);\r
}\r
\r
/** 侧栏每条会话标题下方：最近一次用户提问（服务端字段 last_user_preview） */\r
function formatSessionListSubtitle(sess) {\r
    if (!sess) return '暂无提问';\r
    var t = sess.last_user_preview != null ? String(sess.last_user_preview).trim() : '';\r
    return t || '暂无提问';\r
}\r
\r
/** 与服务端 _normalize_sidebar_preview_text 对齐：折叠空白、180 字符、省略号 */\r
function normalizeSidebarPreviewText(text, maxLen) {\r
    maxLen = maxLen || 180;\r
    var s = String(text || '').trim();\r
    if (!s) return '';\r
    var oneLine = s.split(/\\s+/).join(' ');\r
    if (oneLine.length > maxLen) return oneLine.slice(0, maxLen - 1) + '\\u2026';\r
    return oneLine;\r
}\r
\r
/** 发送后立即更新侧栏「最近提问」（与服务器摘要规则一致）；稍后 refreshSingleSessionRow 仍会校正 */\r
function updateSidebarLastUserPreviewImmediate(sessionId, questionText) {\r
    if (!sessionId || !sessionsList) return;\r
    var nameEl = sessionsList.querySelector('.session-name[data-id="' + sessionId + '"]');\r
    var div = nameEl && nameEl.closest('.session-item');\r
    if (!div) return;\r
    var wsEl = div.querySelector('.session-last-query');\r
    if (!wsEl) return;\r
    var line = normalizeSidebarPreviewText(questionText, 180);\r
    if (!line) line = '暂无提问';\r
    wsEl.textContent = line;\r
    wsEl.setAttribute('data-ui-tip', line);\r
    bindUiHoverTip(wsEl);\r
}\r
\r
function updateSessionTitle() {\r
    const br = document.getElementById('breadcrumb-text');\r
    const sub = document.getElementById('breadcrumb-sub');\r
    if (!br || !sub) return;\r
    if (!currentSessionId) {\r
        br.textContent = '未选择会话';\r
        sub.textContent = '';\r
        setContextTokenLabel(null, null);\r
        return;\r
    }\r
    const sess = selectCurrentSession();\r
    const el = document.querySelector('.session-name[data-id="' + currentSessionId + '"]');\r
    const raw = sess && sess.name != null ? String(sess.name) : (el ? (el.getAttribute('data-original') || el.textContent || '') : '');\r
    const name = (raw && raw.trim()) ? raw.trim() : 'Session';\r
    br.textContent = name;\r
    sub.innerHTML = buildSessionWorkspaceSubtitle(currentSessionId);\r
    initUiHoverTips(sub);\r
}\r
\r
function ensureMermaidInitialized() {\r
    if (mermaidInitialized || !window.mermaid) return;\r
    try {\r
        var light = document.documentElement.classList.contains('theme-light');\r
        mermaid.initialize({\r
            startOnLoad: false,\r
            theme: light ? 'neutral' : 'dark',\r
            securityLevel: 'loose',\r
            themeVariables: {\r
                fontSize: '11px',\r
                fontFamily: 'Plus Jakarta Sans, system-ui, sans-serif',\r
            },\r
            flowchart: { htmlLabels: true, curve: 'basis' },\r
            sequence: { useMaxWidth: true },\r
        });\r
        mermaidInitialized = true;\r
    } catch (e) { /* ignore */ }\r
}\r
\r
/**\r
 * flowchart 节点 E[文本] 内若含 <br> 且又含裸引号 "，Mermaid 10.9 会报 got 'STR'。\r
 * 将此类标签整体包成 ["..."] 并转义内部 ASCII 引号。\r
 */\r
function fixFlowchartBracketLabelsWithLineBreak(text) {\r
    return text.replace(/\\[[^\\]\\n\\r]*<br\\s*\\/?[^\\]\\n\\r]*\\]/gi, function (match) {\r
        var inner = match.slice(1, -1);\r
        var s = inner.trim();\r
        if (!s) return match;\r
        if (s.charAt(0) === '"' && s.charAt(s.length - 1) === '"') return match;\r
        var escaped = s.replace(/\\\\/g, '\\\\\\\\').replace(/"/g, '\\\\"');\r
        return '["' + escaped + '"]';\r
    });\r
}\r
\r
/** 未用引号包裹的 [] 节点里出现裸 " 时同样会触发词法错误 */\r
function fixFlowchartBracketLabelsWithRawQuotes(text) {\r
    return text.replace(/\\[[^\\]\\n\\r]*"[^\\]\\n\\r]*\\]/g, function (match) {\r
        var inner = match.slice(1, -1);\r
        var s = inner.trim();\r
        if (!s) return match;\r
        if (s.charAt(0) === '"' && s.charAt(s.length - 1) === '"') return match;\r
        var escaped = s.replace(/\\\\/g, '\\\\\\\\').replace(/"/g, '\\\\"');\r
        return '["' + escaped + '"]';\r
    });\r
}\r
\r
/** 去除 LLM/粘贴带来的杂讯，减少 Mermaid 10.9+ 报 Syntax error in text */\r
function normalizeMermaidSource(raw) {\r
    var t = String(raw || '')\r
        .replace(/^\\uFEFF/, '')\r
        .replace(/\\u200b|\\u200c|\\u200d/g, '')\r
        .replace(/\\r\\n/g, '\\n')\r
        .replace(/\\r/g, '\\n');\r
    t = t.replace(/^\\s*\`\`\`(?:mermaid)?\\s*\\n/i, '');\r
    t = t.replace(/\\n\\s*\`\`\`\\s*$/i, '');\r
    t = t.replace(/[\\u201C\\u201D\\u201E\\u00AB\\u00BB]/g, '"');\r
    t = t.replace(/<br\\s*\\/?>/gi, '<br/>');\r
    t = fixFlowchartBracketLabelsWithLineBreak(t);\r
    t = fixFlowchartBracketLabelsWithRawQuotes(t);\r
    var lines = t.split('\\n');\r
    if (lines.length && lines[0]) {\r
        lines[0] = lines[0].replace(/\\s*[\\uFF1A：]\\s*$/, '');\r
    }\r
    t = lines.map(function (line) { return line.replace(/\\s+$/g, ''); }).join('\\n').trim();\r
    return t;\r
}\r
\r
function showMermaidRenderError(el, source, err) {\r
    el.classList.add('mermaid-error');\r
    el.removeAttribute('data-processed');\r
    var msg = 'Mermaid 无法解析此图';\r
    if (err) {\r
        if (typeof err === 'string') msg = err;\r
        else if (err.str) msg = String(err.str);\r
        else if (err.message) msg = String(err.message);\r
    }\r
    el.innerHTML = '<div class="mermaid-error-msg">' + escapeHtml(msg) + '</div>'\r
        + '<pre class="mermaid-raw">' + escapeHtml(source) + '</pre>';\r
}\r
\r
function upgradeMermaidBlocks(root) {\r
    if (!root) return;\r
    root.querySelectorAll('pre > code').forEach(function (codeEl) {\r
        var cls = codeEl.getAttribute('class') || '';\r
        if (!/\\bmermaid\\b/.test(cls)) return;\r
        var pre = codeEl.parentNode;\r
        if (!pre || pre.tagName !== 'PRE') return;\r
        var div = document.createElement('div');\r
        div.className = 'mermaid';\r
        div.textContent = normalizeMermaidSource(codeEl.textContent || '');\r
        pre.parentNode.replaceChild(div, pre);\r
    });\r
}\r
\r
/** 无盘符、无路径分隔符的「纯文件名 + 已知后缀」→ 相对工作区根解析 */\r
function isBareWorkspaceFilenameForLink(t) {\r
    var s = linkifyNormalizePathToken(String(t || '').trim());\r
    if (!s || /[/\\\\:]/.test(s)) return false;\r
    if (!/^[^\\s<>'"]+$/.test(s)) return false;\r
    if (/^\\.\\.?$/.test(s)) return false;\r
    return linkifyKnownExtRegex().test(s);\r
}\r
\r
function makeHrefFromAutoLinkToken(s) {\r
    var t = cleanPathTokenForLink(s);\r
    if (!t) return null;\r
    if (/^https?:\\/\\//i.test(t)) return t;\r
    var m = /^([A-Za-z]):[\\\\/](.*)$/.exec(t);\r
    if (m) {\r
        var rest = (m[2] || '').replace(/\\\\/g, '/');\r
        return fileUrlFromFsPath(m[1].toUpperCase() + ':/' + rest);\r
    }\r
    if (t.charAt(0) === '/' && t.charAt(1) !== '/') {\r
        if (!workspaceRelativePathAutoLinkOk(t)) return null;\r
        var w = (typeof window.__WORK_DIR__ === 'string') ? window.__WORK_DIR__ : '';\r
        var abs = joinWorkDirAndRelativeSlashPath(w, t);\r
        if (abs) return fileUrlFromFsPath(abs);\r
    }\r
    if (workspaceRelativePathNoSlashAutoLinkOk(t)) {\r
        var wr = (typeof window.__WORK_DIR__ === 'string') ? window.__WORK_DIR__ : '';\r
        if (!wr) return null;\r
        var absRel = pathJoinBaseName(wr, t.replace(/\\\\/g, '/'));\r
        if (absRel) return fileUrlFromFsPath(absRel);\r
    }\r
    if (isBareWorkspaceFilenameForLink(t)) {\r
        var wk = (typeof window.__WORK_DIR__ === 'string') ? window.__WORK_DIR__ : '';\r
        if (!wk) return null;\r
        var absBare = pathJoinBaseName(wk, t);\r
        if (absBare) return fileUrlFromFsPath(absBare);\r
    }\r
    return null;\r
}\r
\r
/**\r
 * 解析为可交给 /api/open-workspace-file 的路径：工作区相对、Windows/UNC 绝对路径（均由服务端校验须在 WORK_DIR 内）。\r
 */\r
function pathTokenToWorkspaceOpenRel(token) {\r
    var t = cleanPathTokenForLink(token);\r
    if (!t || /^https?:\\/\\//i.test(t)) return null;\r
    var w = (typeof window.__WORK_DIR__ === 'string') ? window.__WORK_DIR__ : '';\r
    var uncFlat = t.replace(/\\//g, '\\\\');\r
    if (/^\\\\\\\\([^\\\\]+)\\\\([^\\\\]+)/i.test(uncFlat)) {\r
        return uncFlat;\r
    }\r
    var win = /^([A-Za-z]):[\\\\/](.*)$/.exec(t);\r
    if (win) {\r
        var rest = (win[2] || '').replace(/\\\\/g, '/');\r
        var absNorm = (win[1].toUpperCase() + ':/' + rest).replace(/\\/+/g, '/');\r
        if (w) {
            var absRel = workspaceRelFromNormalizedAbs(absNorm, w);
            if (absRel != null) return absRel;
            var foreignRel = workspaceRelFromForeignWorkspaceAbs(absNorm, w);
            if (foreignRel != null) return foreignRel;
        }
        return absNorm;
    }\r
    if (!w) return null;\r
    var slashRooted = t.replace(/\\\\/g, '/');\r
    if (slashRooted.charAt(0) === '/' && slashRooted.charAt(1) !== '/') {\r
        var wDrive = /^([A-Za-z]):[\\\\/]/.exec(String(w || ''));\r
        if (wDrive) {\r
            var rootedAbs = (wDrive[1].toUpperCase() + ':' + slashRooted).replace(/\\/+/g, '/');\r
            var rootedRel = workspaceRelFromNormalizedAbs(rootedAbs, w);\r
            if (rootedRel != null) return rootedRel;\r
        }\r
        if (!workspaceRelativePathAutoLinkOk(slashRooted)) return null;\r
        return slashRooted.replace(/^\\/+/, '');\r
    }\r
    if (t === '.env' && typeof window.__APP_DOTENV_PATH__ === 'string' && window.__APP_DOTENV_PATH__) {\r
        return window.__APP_DOTENV_PATH__;\r
    }\r
    var relPath = stripWorkspaceRootPrefixFromRelPath(t);
    if (workspaceRelativePathNoSlashAutoLinkOk(relPath)) return relPath;
    if (isBareWorkspaceFilenameForLink(relPath)) return relPath;
    return null;
}
\r
function decodeMarkdownHrefPathTarget(href) {\r
    var raw = String(href || '').trim();\r
    if (!raw) return '';\r
    try { raw = decodeURI(raw); } catch (e) { /* keep raw */ }\r
    raw = decodePathPercentEscapes(raw);\r
    try { raw = decodeURIComponent(raw); } catch (e2) { /* keep partially decoded raw */ }\r
    return stripPathWrappingQuotes(trimTrailingPathPunct(raw));\r
}\r
\r
function markdownHrefToWorkspaceOpenRel(href) {\r
    var raw = decodeMarkdownHrefPathTarget(href);\r
    if (!raw || raw.charAt(0) === '#') return null;\r
    if (/^(https?|mailto|tel|javascript|data|blob):/i.test(raw)) return null;\r
    if (/^[A-Za-z][A-Za-z0-9+.-]*:/i.test(raw) && !/^[A-Za-z]:[\\\\/]/.test(raw) && !/^file:\\/\\//i.test(raw)) {\r
        return null;\r
    }\r
    var rel = pathTokenToWorkspaceOpenRel(raw);\r
    if (rel) return rel;\r
    if (/^file:\\/\\//i.test(raw)) {\r
        var fsPath = raw.replace(/^file:\\/\\/\\/?/i, '');\r
        fsPath = decodePathPercentEscapes(fsPath);\r
        if (/^[A-Za-z]:[\\\\/]/.test(fsPath)) return fsPath.replace(/\\\\/g, '/');\r
        return '/' + fsPath.replace(/^\\/+/, '').replace(/\\\\/g, '/');\r
    }\r
    if (/^[A-Za-z]:[\\\\/]/.test(raw) || /^\\\\\\\\/.test(raw)) return raw.replace(/\\\\/g, '/');
    if (/[\\\\/]/.test(raw)) return stripWorkspaceRootPrefixFromRelPath(raw);
    return stripWorkspaceRootPrefixFromRelPath(raw);
}
\r
function workspaceOpenDisplayLabel(original, wsRel) {\r
    var rel = String(wsRel || '').replace(/\\\\/g, '/').replace(/\\/+$/, '');\r
    var name = rel.split('/').filter(Boolean).pop();\r
    if (name) return '@' + name;\r
    var raw = stripPathWrappingQuotes(trimTrailingPathPunct(original || ''));\r
    name = raw.replace(/\\\\/g, '/').replace(/\\/+$/, '').split('/').filter(Boolean).pop();\r
    return name ? ('@' + name) : raw;\r
}\r
\r
function escapeRegExpLiteral(s) {\r
    return String(s || '').replace(/[.*+?^\${}()|[\\]\\\\]/g, '\\\\$&');\r
}\r
\r
function quotePromptPath(p) {\r
    var t = stripPathWrappingQuotes(String(p || '').trim());\r
    if (!t) return '';\r
    return '"' + t.replace(/"/g, '\\\\"') + '"';\r
}\r
\r
function inputQuotedWindowsPathRegex() {\r
    return /(["'])([A-Za-z]:[\\\\/][^"'\\r\\n]+)\\1/g;\r
}\r
\r
var _inputKnownExtWinPathRe = null;\r
function inputKnownExtWindowsPathRegex() {\r
    if (!_inputKnownExtWinPathRe) {\r
        _inputKnownExtWinPathRe = new RegExp('(^|[\\\\s(（\\\\[])([A-Za-z]:[\\\\\\\\/][^\\\\r\\\\n"\\\\\\'<>|]+?\\\\.(' + LINKIFY_EXT_FRAGMENT + '))(?=$|[\\\\s,，。;；:：)）\\\\]】])', 'gi');\r
    }\r
    _inputKnownExtWinPathRe.lastIndex = 0;\r
    return _inputKnownExtWinPathRe;\r
}\r
\r
function inputSimpleWindowsPathRegex() {\r
    return /(^|[\\s(（\\[])([A-Za-z]:(?:\\\\|\\/)(?:(?:[^\\\\/:*?"<>|\\s\\r\\n]+)(?:\\\\|\\/))*[^\\\\/:*?"<>|\\s\\r\\n]+)(?=$|[\\s,，。;；:：)）\\]】])/g;\r
}\r
\r
function ensureInputPathChipHost() {\r
    var host = document.getElementById('input-path-chips');\r
    if (host || !messageInput) return host;\r
    var wrapper = messageInput.closest ? messageInput.closest('.input-wrapper') : null;\r
    var panel = wrapper && wrapper.parentNode;\r
    if (!panel || !wrapper) return null;\r
    host = document.createElement('div');\r
    host.id = 'input-path-chips';\r
    host.className = 'input-path-chips';\r
    panel.insertBefore(host, wrapper);\r
    return host;\r
}\r
\r
function clearInputPathTokens() {\r
    Object.keys(inputPathTokenMap).forEach(function (k) { delete inputPathTokenMap[k]; });\r
    refreshInputPathChips();\r
}\r
\r
function removeInputPathToken(label) {\r
    if (!label || !messageInput) return;\r
    delete inputPathTokenMap[label];\r
    var text = String(messageInput.value || '');\r
    var re = new RegExp('(?:\\\\s*)' + escapeRegExpLiteral(label), 'g');\r
    messageInput.value = text.replace(re, '').replace(/[ \\t]{2,}/g, ' ').trimStart();\r
    refreshInputPathChips();\r
    autoResizeTextarea();\r
    try { messageInput.focus(); } catch (e) {}\r
}\r
\r
function refreshInputPathChips() {\r
    var host = ensureInputPathChipHost();\r
    if (!host || !messageInput) return;\r
    var text = String(messageInput.value || '');\r
    var labels = Object.keys(inputPathTokenMap).filter(function (label) {\r
        return label && text.indexOf(label) >= 0;\r
    });\r
    if (!labels.length) {\r
        host.innerHTML = '';\r
        host.classList.remove('is-visible');\r
        return;\r
    }\r
    host.innerHTML = '';\r
    labels.forEach(function (label) {\r
        var stored = inputPathTokenMap[label];\r
        var rel = pathTokenToWorkspaceOpenRel(stored);\r
        if (!rel) return;\r
        var chip = document.createElement('span');\r
        chip.className = 'input-path-chip';\r
        var a = document.createElement('a');\r
        a.href = '#';\r
        a.className = 'input-path-chip-link msg-link-workspace-open';\r
        a.dataset.workspaceOpen = rel;\r
        a.textContent = label;\r
        a.setAttribute('data-ui-tip', String(stored || rel));\r
        var rm = document.createElement('button');\r
        rm.type = 'button';\r
        rm.className = 'input-path-chip-remove';\r
        rm.setAttribute('aria-label', '移除 ' + label);\r
        rm.setAttribute('data-ui-tip', '移除文件路径');\r
        rm.textContent = '×';\r
        rm.addEventListener('click', function (ev) {\r
            ev.preventDefault();\r
            ev.stopPropagation();\r
            removeInputPathToken(label);\r
        });\r
        chip.appendChild(a);\r
        chip.appendChild(rm);\r
        host.appendChild(chip);\r
    });\r
    host.classList.toggle('is-visible', !!host.children.length);\r
}\r
\r
function rewriteInputWorkspacePaths() {\r
    if (!messageInput || inputPathRewriteGuard) return;\r
    var raw = String(messageInput.value || '');\r
    var changed = false;\r
    function replacePathToken(match, prefix, path) {\r
        var rel = pathTokenToWorkspaceOpenRel(path);\r
        if (!rel) return match;\r
        var label = workspaceOpenDisplayLabel(path, rel);\r
        if (!label) return match;\r
        inputPathTokenMap[label] = stripPathWrappingQuotes(path);\r
        changed = true;\r
        return (prefix || '') + label;\r
    }\r
    var next = raw.replace(inputQuotedWindowsPathRegex(), function (match, q, path) {\r
        return replacePathToken(match, '', path);\r
    });\r
    next = next.replace(inputKnownExtWindowsPathRegex(), function (match, prefix, path) {\r
        return replacePathToken(match, prefix, path);\r
    });\r
    next = next.replace(inputSimpleWindowsPathRegex(), function (match, prefix, path) {\r
        return replacePathToken(match, prefix, path);\r
    });\r
    if (changed && next !== raw) {\r
        var wasFocused = document.activeElement === messageInput;\r
        inputPathRewriteGuard = true;\r
        messageInput.value = next;\r
        if (wasFocused) {\r
            var pos = next.length;\r
            try { messageInput.setSelectionRange(pos, pos); } catch (e) {}\r
        }\r
        inputPathRewriteGuard = false;\r
    }\r
    refreshInputPathChips();\r
}\r
\r
function expandInputPathTokens(text) {\r
    var out = String(text || '');\r
    Object.keys(inputPathTokenMap)\r
        .sort(function (a, b) { return b.length - a.length; })\r
        .forEach(function (label) {\r
            var stored = inputPathTokenMap[label];\r
            if (!stored || out.indexOf(label) < 0) return;\r
            out = out.replace(new RegExp(escapeRegExpLiteral(label), 'g'), quotePromptPath(stored));\r
        });\r
    return out;\r
}\r
\r
/** 整段文本是否仅为可链转的 Windows 绝对路径（用于行内 code 内路径） */\r
function isEntireTextNodeWindowsPath(raw) {\r
    var t = trimTrailingPathPunct(linkifyNormalizePathToken(String(raw || '').trim()));\r
    if (!t) return false;\r
    return /^([A-Za-z]):[\\\\/](?:(?:[^\\\\/:*?"<>|\\r\\n]+)(?:\\\\|\\/))*[^\\\\/:*?"<>|\\r\\n]+$/i.test(t);\r
}\r
\r
function isEntireBareFilenameLinkable(raw) {\r
    var t = trimTrailingPathPunct(linkifyNormalizePathToken(String(raw || '').trim()));\r
    return isBareWorkspaceFilenameForLink(t);\r
}\r
\r
/** 行内 code 内整段为 \`/工作区相对/路径.ext\` 时亦允许链转（否则反引号路径永不可点） */\r
function isEntireWorkspaceSlashPathLinkable(raw) {\r
    var t = trimTrailingPathPunct(linkifyNormalizePathToken(String(raw || '').trim()));\r
    return workspaceRelativePathAutoLinkOk(t);\r
}\r
\r
function isEntireWorkspaceRelativePathLinkable(raw) {\r
    var t = trimTrailingPathPunct(linkifyNormalizePathToken(String(raw || '').trim()));\r
    return workspaceRelativePathNoSlashAutoLinkOk(t);\r
}\r
\r
/** 行内 code 内整段为 UNC \\\\server\\share\\... 时允许「本机打开」链转 */\r
function isEntireTextNodeUncPath(raw) {\r
    var t = trimTrailingPathPunct(linkifyNormalizePathToken(String(raw || '').trim()));\r
    if (!t) return false;\r
    var u = t.replace(/\\//g, '\\\\');\r
    return /^\\\\\\\\[^\\\\]+\\\\[^\\\\]+(?:\\\\[^\\\\]*)*$/i.test(u);\r
}\r
\r
var _assistMsgLinkifyRe = null;\r
function getAssistMsgLinkifyRegex() {\r
    if (!_assistMsgLinkifyRe) {\r
        // 「/路径」前仅排除 ASCII 字母，避免 2023/文件、中文后接 / 等无法匹配；仍可抑制 ARPU/DOU（U 为字母）\r
        _assistMsgLinkifyRe = new RegExp(\r
            '((["\\'])(?:(?:[A-Za-z]:(?:\\\\\\\\|\\\\/)|\\\\\\\\\\\\\\\\|\\\\/(?![\\\\s\\\\/]))|(?=[^"\\'\\\\r\\\\n]*[\\\\\\\\/]))[^"\\'\\\\r\\\\n]+?\\\\.(?:' + LINKIFY_EXT_FRAGMENT + ')\\\\b\\\\2|' +\r
            'https?:\\\\/\\\\/[^\\\\s<>\\'"]+|' +\r
            '\\\\\\\\\\\\\\\\(?:(?:[^\\\\\\\\\\\\/:*?"<>|\\\\r\\\\n]+)\\\\\\\\)+(?:[^\\\\\\\\\\\\/:*?"<>|\\\\r\\\\n]+)|' +\r
            '[A-Za-z]:(?:\\\\\\\\|\\\\/)(?:(?:[^\\\\\\\\/:*?"<>|\\\\r\\\\n]+)(?:\\\\\\\\|\\\\/))*[^\\\\\\\\/:*?"<>|\\\\r\\\\n]+|' +\r
            '(?<![A-Za-z])\\\\/(?![\\\\s\\\\/])[^\\\\s<>\\'"]+|' +\r
            '(?<![A-Za-z0-9./\\\\\\\\])(?:[^\\\\s<>\\'"/\\\\\\\\:]+(?:[\\\\\\\\/][^\\\\s<>\\'"/\\\\\\\\:]+)+\\\\.(' + LINKIFY_EXT_FRAGMENT + ')\\\\b)|' +\r
            '(?<![A-Za-z0-9./\\\\\\\\])([^\\\\s<>\\'"/\\\\\\\\:]+?\\\\.(' + LINKIFY_EXT_FRAGMENT + ')\\\\b))',\r
            'gi'\r
        );\r
    }\r
    return _assistMsgLinkifyRe;\r
}\r
\r
function tryLinkifyEntirePathTextNode(textNode, raw) {\r
    var token = String(raw || '').trim();\r
    if (!token) return false;\r
    var wsRel = pathTokenToWorkspaceOpenRel(token);\r
    var href = wsRel ? null : makeHrefFromAutoLinkToken(token);\r
    if (!wsRel && !href) return false;\r
    var a = document.createElement('a');\r
    a.className = wsRel ? 'msg-link-auto msg-link-workspace-open' : 'msg-link-auto';\r
    a.textContent = cleanPathTokenForLink(token) || token;\r
    if (wsRel) {\r
        a.href = '#';\r
        a.setAttribute('data-workspace-open', wsRel);\r
        a.setAttribute('data-ui-tip', '在本机打开（工作区文件）');\r
        bindUiHoverTip(a);\r
    } else {\r
        a.href = href;\r
        a.target = '_blank';\r
        a.rel = 'noopener noreferrer';\r
    }\r
    textNode.parentNode.replaceChild(a, textNode);\r
    return true;\r
}\r
\r
function linkifySingleTextNode(textNode) {\r
    var raw = textNode.nodeValue;\r
    if (!raw) return;\r
    var parent = textNode.parentElement;\r
    if (!parent || parent.closest('a, pre, script, style, textarea, svg')) return;\r
    var inInlineCode = !!parent.closest('code');\r
    if (inInlineCode) {\r
        if (!isEntireTextNodeWindowsPath(raw) && !isEntireBareFilenameLinkable(raw) && !isEntireWorkspaceSlashPathLinkable(raw) && !isEntireWorkspaceRelativePathLinkable(raw) && !isEntireTextNodeUncPath(raw)) return;\r
        if (tryLinkifyEntirePathTextNode(textNode, raw)) return;\r
    }\r
    var rawForLink = linkifyNormalizePathToken(raw);\r
    var re = getAssistMsgLinkifyRegex();\r
    re.lastIndex = 0;\r
    var parts = [];\r
    var last = 0;\r
    var m;\r
    while ((m = re.exec(rawForLink)) !== null) {\r
        var matchStart = m.index;\r
        var matchEnd = m.index + m[0].length;\r
        var qBefore = rawForLink.charAt(matchStart - 1);\r
        var qAfter = rawForLink.charAt(matchEnd);\r
        if ((qBefore === '"' || qBefore === "'") && qAfter === qBefore) {\r
            matchStart -= 1;\r
            matchEnd += 1;\r
        }\r
        if (matchStart > last) parts.push({ k: 't', s: rawForLink.slice(last, matchStart) });\r
        parts.push({ k: 'l', s: m[0] });\r
        last = matchEnd;\r
    }\r
    if (last < rawForLink.length) parts.push({ k: 't', s: rawForLink.slice(last) });\r
    var hasLink = false;\r
    for (var pi = 0; pi < parts.length; pi++) {\r
        if (parts[pi].k === 'l') { hasLink = true; break; }\r
    }\r
    if (!hasLink) return;\r
    var frag = document.createDocumentFragment();\r
    parts.forEach(function (p) {\r
        if (p.k === 't') frag.appendChild(document.createTextNode(p.s));\r
        else {\r
            var wsRel = pathTokenToWorkspaceOpenRel(p.s);\r
            var show = cleanPathTokenForLink(p.s);\r
            if (wsRel) {\r
                var aw = document.createElement('a');\r
                aw.href = '#';\r
                aw.setAttribute('data-workspace-open', wsRel);\r
                aw.className = 'msg-link-auto msg-link-workspace-open';\r
                aw.setAttribute('data-ui-tip', '在本机打开（工作区文件）');\r
                bindUiHoverTip(aw);\r
                aw.textContent = show || p.s;\r
                frag.appendChild(aw);\r
                if (p.s.length > (show || '').length) {\r
                    frag.appendChild(document.createTextNode(p.s.slice((show || '').length)));\r
                }\r
            } else {\r
                var href = makeHrefFromAutoLinkToken(p.s);\r
                if (!href) frag.appendChild(document.createTextNode(p.s));\r
                else {\r
                    var ah = document.createElement('a');\r
                    ah.href = href;\r
                    ah.target = '_blank';\r
                    ah.rel = 'noopener noreferrer';\r
                    ah.className = 'msg-link-auto';\r
                    ah.textContent = show || p.s;\r
                    frag.appendChild(ah);\r
                    if (p.s.length > (show || '').length) {\r
                        frag.appendChild(document.createTextNode(p.s.slice((show || '').length)));\r
                    }\r
                }\r
            }\r
        }\r
    });\r
    textNode.parentNode.replaceChild(frag, textNode);\r
}\r
\r
function upgradeWorkspacePathMarkdownLinks(root) {
    if (!root) return;\r
    root.querySelectorAll('a[href]').forEach(function (a) {\r
        if (!a || a.classList.contains('msg-link-workspace-open')) return;
        var href = a.getAttribute('href') || '';
        var marker = /^#ga-workspace-path=(.+)$/i.exec(href);
        if (marker) {
            try { href = decodeURIComponent(marker[1]); } catch (e0) { href = marker[1]; }
        }
        var raw = href;
        try { raw = decodeURI(raw); } catch (e) {}
        var rel = markdownHrefToWorkspaceOpenRel(href);\r
        if (!rel && /^file:\\/\\//i.test(raw)) {\r
            var fsPath = raw.replace(/^file:\\/\\/\\/?/i, '');\r
            try { fsPath = decodeURIComponent(fsPath); } catch (e2) {}\r
            if (/^[A-Za-z]:\\//.test(fsPath)) rel = pathTokenToWorkspaceOpenRel(fsPath);\r
            else rel = pathTokenToWorkspaceOpenRel('/' + fsPath.replace(/^\\/+/, ''));\r
        }\r
        if (!rel) return;\r
        a.href = '#';\r
        a.setAttribute('data-workspace-open', rel);\r
        a.classList.add('msg-link-workspace-open');\r
        a.setAttribute('data-ui-tip', '在本机打开（工作区文件）');\r
        bindUiHoverTip(a);\r
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
        try { raw = decodeURIComponent(marker[1]); } catch (e) { raw = marker[1]; }
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
    var walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT);\r
    var batch = [];\r
    var n;\r
    while ((n = walker.nextNode())) {\r
        var p = n.parentElement;\r
        if (!p || p.closest('a, pre, script, style, textarea, .mermaid')) continue;\r
        if (p.closest('code') && !isEntireTextNodeWindowsPath(n.nodeValue) && !isEntireBareFilenameLinkable(n.nodeValue) && !isEntireWorkspaceSlashPathLinkable(n.nodeValue) && !isEntireWorkspaceRelativePathLinkable(n.nodeValue) && !isEntireTextNodeUncPath(n.nodeValue)) continue;\r
        var nv = n.nodeValue;\r
        var nvNorm = linkifyNormalizePathToken(nv);\r
        if (!nv || (!/https?:\\/\\/|["'][A-Za-z]:[\\\\/]|[A-Za-z]:[\\\\/]|\\/\\S/.test(nvNorm) && !nvNorm.startsWith('\\\\\\\\') && !linkifyKnownExtRegex().test(nvNorm))) continue;\r
        batch.push(n);\r
    }\r
    batch.forEach(linkifySingleTextNode);\r
}\r
\r
function scheduleMermaidRun(root) {\r
    registerMermaidLazy(root);\r
}\r
\r
async function runMermaidElementOnce(el) {\r
    if (!el || !window.mermaid || !el.isConnected) return;\r
    if (el.getAttribute('data-processed') === 'true' || el.classList.contains('mermaid-error')) return;\r
    ensureMermaidInitialized();\r
    var cleaned = normalizeMermaidSource(el.textContent || '');\r
    if (!cleaned) return;\r
    el.textContent = cleaned;\r
    if (!el.id) el.id = 'mermaid-embed-' + (++mermaidIdSeq);\r
    try {\r
        await mermaid.parse(cleaned);\r
    } catch (errParse) {\r
        showMermaidRenderError(el, cleaned, errParse);\r
        return;\r
    }\r
    try {\r
        await mermaid.run({ nodes: [el], suppressErrors: false });\r
    } catch (errRun) {\r
        showMermaidRenderError(el, cleaned, errRun);\r
    }\r
}\r
\r
function ensureMermaidIoObserver() {\r
    if (mermaidIoObserver || typeof IntersectionObserver === 'undefined') return null;\r
    mermaidIoObserver = new IntersectionObserver(function (entries) {\r
        entries.forEach(function (en) {\r
            if (!en.isIntersecting) return;\r
            var el = en.target;\r
            if (!el.classList.contains('mermaid') || el.getAttribute('data-processed') === 'true') {\r
                if (mermaidIoObserver) mermaidIoObserver.unobserve(el);\r
                return;\r
            }\r
            if (mermaidIoObserver) mermaidIoObserver.unobserve(el);\r
            runMermaidElementOnce(el);\r
        });\r
    }, { root: null, rootMargin: '100px 0px 160px 0px', threshold: 0 });\r
    return mermaidIoObserver;\r
}\r
\r
function registerMermaidLazy(root) {\r
    if (!root || !window.mermaid) return;\r
    ensureMermaidInitialized();\r
    var nodes = Array.from(root.querySelectorAll('.mermaid:not([data-processed]):not(.mermaid-error)'));\r
    if (!nodes.length) return;\r
    var obs = ensureMermaidIoObserver();\r
    if (!obs) {\r
        requestAnimationFrame(function () {\r
            (async function () {\r
                for (var i = 0; i < nodes.length; i += 1) {\r
                    await runMermaidElementOnce(nodes[i]);\r
                }\r
            })();\r
        });\r
        return;\r
    }\r
    nodes.forEach(function (el) {\r
        try {\r
            obs.observe(el);\r
        } catch (e) {\r
            runMermaidElementOnce(el);\r
        }\r
    });\r
}\r
\r
function wrapMessageTables(container) {
    if (!container) return;
    container.querySelectorAll('table').forEach(function (table) {
        var parent = table.parentElement;
        if (parent && parent.classList && parent.classList.contains('msg-table-scroll')) return;
        var wrap = document.createElement('div');\r
        wrap.className = 'msg-table-scroll';\r
        if (table.parentNode) table.parentNode.insertBefore(wrap, table);\r
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
    scheduleMermaidRun(div);
}
\r
let markedOptionsApplied = false;
function encodeMarkdownWorkspacePathLinkMatch(match, label, dest) {
    var rawDest = String(dest || '').trim();
    if (!rawDest || rawDest.charAt(0) === '#') return match;
    var decodedDest = decodeMarkdownHrefPathTarget(rawDest);
    if (!decodedDest || /^(https?|mailto|tel|javascript|data|blob):/i.test(decodedDest)) return match;
    if (/^[A-Za-z][A-Za-z0-9+.-]*:/i.test(decodedDest) && !/^[A-Za-z]:[\\\\/]/.test(decodedDest) && !/^file:\\/\\//i.test(decodedDest)) return match;
    var rel = markdownHrefToWorkspaceOpenRel(decodedDest);
    if (!rel) return match;
    return '[' + label + '](#ga-workspace-path=' + encodeURIComponent(rel) + ')';
}

function encodeMarkdownWorkspacePathLinksInPlainText(text) {
    return String(text || '').replace(/\\[([^\\]\\r\\n]+)\\]\\(([^)\\r\\n]+)\\)/g, encodeMarkdownWorkspacePathLinkMatch);
}

function encodeMarkdownWorkspacePathLinks(text) {
    var src = String(text || '');
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
\r
function escapeMarkdownSingleTildes(text) {\r
    var src = String(text || '');\r
    var out = '';\r
    var inFence = false;\r
    var fenceMarker = '';\r
    var inCode = false;\r
    var lineStart = true;\r
    for (var i = 0; i < src.length; i += 1) {\r
        var ch = src.charAt(i);\r
        var rest = src.slice(i);\r
        if (lineStart) {\r
            var fence = /^([ \\t]{0,3})(\`{3,}|~{3,})/.exec(rest);\r
            if (fence) {\r
                var marker = fence[2].charAt(0);\r
                if (!inFence) {\r
                    inFence = true;\r
                    fenceMarker = marker;\r
                } else if (marker === fenceMarker) {\r
                    inFence = false;\r
                    fenceMarker = '';\r
                }\r
            }\r
        }\r
        if (!inFence && ch === '\`') {\r
            var tickEnd = i + 1;\r
            while (tickEnd < src.length && src.charAt(tickEnd) === '\`') tickEnd += 1;\r
            out += src.slice(i, tickEnd);\r
            i = tickEnd - 1;\r
            inCode = !inCode;\r
            lineStart = false;\r
            continue;\r
        }
        if (!inFence && !inCode && ch === '~') {
            out += '&#126;';
        } else {
            out += ch;
        }
        lineStart = ch === '\\n' || ch === '\\r';\r
    }\r
    return out;\r
}\r
\r
function renderMarkdown(text) {\r
    if (!text) return '';\r
    if (typeof marked !== 'undefined' && !markedOptionsApplied) {\r
        markedOptionsApplied = true;\r
        try {\r
            marked.setOptions({ breaks: true, mangle: false, headerIds: false });\r
        } catch (e) { /* ignore */ }\r
    }\r
    return marked.parse(escapeMarkdownSingleTildes(encodeMarkdownWorkspacePathLinks(text)), { mangle: false, headerIds: false });\r
}\r
\r
const TRACE_ROW = {\r
    'log-entry':   { label: '信息', c: 'feed--log' },\r
    'tool-call':   { label: '工具', c: 'feed--tool' },\r
    'error-log':   { label: '错误', c: 'feed--err' },\r
    'llm-response':{ label: '回复', c: 'feed--llm2' },\r
    'llm-reasoning':{ label: '思考', c: 'feed--llm' },\r
    'compact-summary': { label: '压缩', c: 'feed--cmp' },\r
    'context-trim': { label: '裁剪', c: 'feed--trim' },\r
    'context-summary': { label: '压缩', c: 'feed--cmp' },\r
    'key-context': { label: '要点', c: 'feed--key' },\r
    'user-steer':  { label: '追问', c: 'feed--answer' },\r
    'status':      { label: '状态', c: 'feed--st' },\r
};\r
\r
const envKeepLines = Number(window.__UI_LOG_TRUNCATE_KEEP_LINES__);\r
const LOG_TRUNCATE_KEEP_LINES = Number.isFinite(envKeepLines) && envKeepLines > 0 ? Math.floor(envKeepLines) : 100;\r
const LOG_TRUNCATE_HEAD_LINES = LOG_TRUNCATE_KEEP_LINES;\r
const LOG_TRUNCATE_TAIL_LINES = LOG_TRUNCATE_KEEP_LINES;\r
const LOG_TRUNCATE_HEAD_CHARS = 12000;\r
const LOG_TRUNCATE_TAIL_CHARS = 12000;\r
\r
function toolCallDraftKey(parsed) {\r
    var ri = parsed && parsed.react_iter != null ? String(parsed.react_iter) : '';\r
    var idx = parsed && parsed.tool_call_index != null ? String(parsed.tool_call_index) : (parsed && parsed.index != null ? String(parsed.index) : '0');\r
    return ri + ':' + idx;\r
}\r
\r
function findToolDraftRow(ctx, parsed) {\r
    var key = toolCallDraftKey(parsed);\r
    if (!key) return null;\r
    var body = getProcessBody(ctx);\r
    if (!body || typeof CSS === 'undefined' || !CSS.escape) return null;\r
    try { return body.querySelector('.feed-item.feed--tool[data-tool-draft-key="' + CSS.escape(key) + '"]'); } catch (e) { return null; }\r
}\r
\r
function setToolRowText(row, text, ctx, runSessionId) {\r
    if (!row) return;\r
    var sc = row.querySelector('.feed-chunk-scroller');\r
    if (sc) sc.textContent = truncateLogTextForUi(text);\r
    var ch = row.querySelector('.feed-chunk');\r
    if (ch) {\r
        // 工具条目流式生成时也放开高度限制\r
        ch.classList.add('is-streaming');\r
        refreshFeedChunkOverflow(ch);\r
    }\r
    // 遵守自动跟随，不强制拖拽\r
    if (!replayingMessages) scrollContentAreaIfFollow(ctx, runSessionId);\r
}\r
\r
// 移除临时状态消息（移除整个 feed-item 条目）\r
function removeTemporaryStatus(ctx) {\r
    var body = getProcessBody(ctx);\r
    if (!body) return;\r
    var tempStatuses = body.querySelectorAll('[data-temporary-status="1"]');\r
    tempStatuses.forEach(function(el) {\r
        var row = el.closest ? el.closest('.feed-item') : null;\r
        if (row) row.remove(); else el.remove();\r
    });\r
}\r
\r
function appendToolCallDelta(ctx, parsed, runSessionId) {\r
    var key = toolCallDraftKey(parsed);\r
    if (!key) return;\r
    var row = findToolDraftRow(ctx, parsed);\r
    if (!row) {\r
        var so = null;\r
        if (parsed.react_iter != null && Number.isFinite(Number(parsed.react_iter))) so = { reactIter: Number(parsed.react_iter) };\r
        var scNew = createProcessFeedRow(ctx, 'tool-call', '工具调用生成中...', so, runSessionId, '');\r
        row = scNew && scNew.closest ? scNew.closest('.feed-item') : null;\r
        if (row) row.setAttribute('data-tool-draft-key', key);\r
    }\r
    if (!row) return;\r
    if (parsed.id) row.dataset.pendingToolCallId = String(parsed.id);\r
    \r
    // 收到 tool_call_delta 时，移除临时状态，展开折叠的 process-aggregate\r
    removeTemporaryStatus(ctx);\r
    var agg = row.closest('.process-aggregate');\r
    if (agg && agg.classList.contains('is-collapsed')) {\r
        agg.classList.remove('is-collapsed');\r
        var topN = agg.querySelector('.process-aggregate-top');\r
        if (topN) topN.setAttribute('aria-expanded', 'true');\r
    }\r
    \r
    // 累积工具名称和参数\r
    if (parsed.name_delta) {\r
        row.dataset.pendingToolName = (row.dataset.pendingToolName || '') + String(parsed.name_delta);\r
    }\r
    if (parsed.arguments_delta) {\r
        row.dataset.pendingToolArgs = (row.dataset.pendingToolArgs || '') + String(parsed.arguments_delta);\r
    }\r
    \r
    // 生成显示文本\r
    var toolName = row.dataset.pendingToolName || '';\r
    var argsRaw = row.dataset.pendingToolArgs || '';\r
    var displayText = '工具调用生成中...';\r
    \r
    if (toolName) {\r
        // 流式显示：工具名 + 参数原始文本（逐步增长）\r
        var argsPreview = argsRaw;\r
        displayText = toolName + '(' + argsPreview + '\\n生成中...';\r
    }\r
    setToolRowText(row, displayText, ctx, runSessionId);\r
}\r
function formatToolCommandLine(tool, args, commandPreview) {\r
    if (commandPreview != null && String(commandPreview).trim()) return String(commandPreview).trim();\r
    var name = String(tool || 'tool');\r
    var a = args && typeof args === 'object' && !Array.isArray(args) ? args : {};\r
    function j(v) { try { return JSON.stringify(v); } catch (e) { return String(v); } }\r
    function pair(k, v) {\r
        if ((k === 'content' || k === 'contents') && typeof v === 'string' && v.length > 240) v = '<' + v.length + ' chars>';\r
        return j(k) + ': ' + j(v);\r
    }\r
    var preferred = ['path','target_directory','file_path','directory','root','command','args','url','start_line','end_line','pattern','query','search','replace','old_string','new_string','working_dir','timeout','temporary','content','contents'];\r
    var keys = [];\r
    // 路径参数去重：只保留第一个存在的路径参数\r
    var pathKeys = ['path', 'target_directory', 'file_path', 'directory', 'root'];\r
    var firstPathKey = null;\r
    pathKeys.forEach(function (k) {\r
        if (!firstPathKey && Object.prototype.hasOwnProperty.call(a, k)) firstPathKey = k;\r
    });\r
    preferred.forEach(function (k) {\r
        if (Object.prototype.hasOwnProperty.call(a, k)) {\r
            if (pathKeys.indexOf(k) >= 0) {\r
                if (k === firstPathKey) keys.push(k);\r
            } else {\r
                keys.push(k);\r
            }\r
        }\r
    });\r
    Object.keys(a).sort().forEach(function (k) { if (keys.indexOf(k) < 0) keys.push(k); });\r
    if (name === 'run_shell') {\r
        var b = {};\r
        Object.keys(a).forEach(function (k) { b[k] = a[k]; });\r
        var cmd = b.command != null ? String(b.command) : '';\r
        if (Array.isArray(b.args) && b.args.length) cmd += ' ' + b.args.map(function (x) { return String(x); }).join(' ');\r
        b.command = cmd.trim();\r
        delete b.args;\r
        a = b;\r
        keys = [];\r
        preferred.forEach(function (k) { if (Object.prototype.hasOwnProperty.call(a, k)) keys.push(k); });\r
        Object.keys(a).sort().forEach(function (k) { if (keys.indexOf(k) < 0) keys.push(k); });\r
    }\r
    return name + '(' + keys.map(function (k) { return pair(k, a[k]); }).join(', ') + ')';\r
}\r
\r
function formatToolPendingLine(tool, args, commandPreview) {\r
    var cmd = commandPreview != null ? String(commandPreview).trim() : '';\r
    if (!cmd) return '执行中...';\r
    return cmd + '\\n执行中...';\r
}\r
\r
function formatToolDoneLine(tool, args, result, commandPreview) {\r
    return formatToolCommandLine(tool, args, commandPreview) + '\\n执行结果\\n' + String(result != null ? result : '');\r
}\r
\r
function appendToolPendingRow(ctx, parsed, runSessionId) {\r
    var line = formatToolPendingLine(parsed.tool, parsed.args, parsed.command_preview);\r
    var so = null;\r
    if (parsed.react_iter != null && Number.isFinite(Number(parsed.react_iter))) so = { reactIter: Number(parsed.react_iter) };\r
    var draft = findToolDraftRow(ctx, parsed);\r
    if (draft) {
        if (parsed.tool_call_id != null && String(parsed.tool_call_id) !== '') draft.setAttribute('data-tool-call-id', String(parsed.tool_call_id));
        draft.removeAttribute('data-tool-draft-key');
        draft.setAttribute('data-tool-pending', '1');
        draft.dataset.commandPreview = parsed.command_preview != null ? String(parsed.command_preview) : '';
        setToolRowText(draft, line, ctx, runSessionId);
        return;
    }\r
    var sc = createProcessFeedRow(ctx, 'tool-call', line, so, runSessionId, parsed.tool_call_id);
    var row = sc && sc.closest ? sc.closest('.feed-item') : null;
    if (row) {
        row.setAttribute('data-tool-pending', '1');
        row.dataset.commandPreview = parsed.command_preview != null ? String(parsed.command_preview) : '';
    }
}
\r
function appendToolCommandDelta(ctx, parsed, runSessionId) {\r
    var tid = parsed.tool_call_id != null ? String(parsed.tool_call_id) : '';\r
    if (!tid) return;\r
    var body = getProcessBody(ctx);\r
    var row = null;\r
    if (body && typeof CSS !== 'undefined' && CSS.escape) {\r
        try { row = body.querySelector('.feed-item.feed--tool[data-tool-call-id="' + CSS.escape(tid) + '"]'); } catch (e) { row = null; }\r
    }\r
    if (!row) {\r
        appendToolPendingRow(ctx, { tool_call_id: tid, command_preview: '', react_iter: parsed.react_iter }, runSessionId);\r
        body = getProcessBody(ctx);\r
        if (body && typeof CSS !== 'undefined' && CSS.escape) {\r
            try { row = body.querySelector('.feed-item.feed--tool[data-tool-call-id="' + CSS.escape(tid) + '"]'); } catch (e2) { row = null; }\r
        }\r
    }\r
    if (!row) return;\r
    row.dataset.commandPreview = (row.dataset.commandPreview || '') + String(parsed.delta || '');\r
    var text = formatToolPendingLine(parsed.tool, parsed.args, row.dataset.commandPreview);\r
    var sc = row.querySelector('.feed-chunk-scroller');\r
    if (sc) sc.textContent = truncateLogTextForUi(text);\r
    var ch = row.querySelector('.feed-chunk');\r
    if (ch) refreshFeedChunkOverflow(ch);\r
    if (!replayingMessages) scrollContentAreaIfFollow(ctx, runSessionId);\r
}\r
function upsertToolCallResult(ctx, parsed, runSessionId) {\r
    var tid = parsed.tool_call_id != null ? String(parsed.tool_call_id) : '';\r
    var body = getProcessBody(ctx);\r
    var row = null;\r
    if (tid && body && typeof CSS !== 'undefined' && CSS.escape) {\r
        try { row = body.querySelector('.feed-item.feed--tool[data-tool-call-id="' + CSS.escape(tid) + '"]'); } catch (e) { row = null; }\r
    }\r
    if (!row) row = findToolDraftRow(ctx, parsed);\r
    var cmdPreview = parsed.command_preview;\r
    if ((!cmdPreview || !String(cmdPreview).trim()) && row && row.dataset.commandPreview) cmdPreview = row.dataset.commandPreview;\r
    var text = formatToolDoneLine(parsed.tool, parsed.args, parsed.result, cmdPreview);\r
    if (row) {
        if (tid) row.setAttribute('data-tool-call-id', tid);
        row.removeAttribute('data-tool-draft-key');
        row.removeAttribute('data-tool-pending');
        row.dataset.commandPreview = cmdPreview != null ? String(cmdPreview) : '';
        var sc = row.querySelector('.feed-chunk-scroller');\r
        if (sc) sc.textContent = truncateLogTextForUi(text);\r
        var ch = row.querySelector('.feed-chunk');\r
        if (ch) refreshFeedChunkOverflow(ch);\r
        var agg = body.closest('.process-aggregate');\r
        refreshAggregateStatsSmart(agg);\r
        if (!replayingMessages) scrollContentAreaIfFollow(ctx, runSessionId);\r
        return;\r
    }\r
    var ri = uiEventReactIter(parsed);\r
    appendLog(ctx, text, 'tool-call', runSessionId, ri);\r
}\r
\r
/** 去掉首尾「空白行」（整行仅空格/制表也不保留），保留首行正文缩进与中间空行 */\r
function trimSurroundingBlankLines(raw) {\r
    var text = (raw == null) ? '' : String(raw);\r
    if (!text) return text;\r
    var lines = text.split('\\n');\r
    var start = 0;\r
    var end = lines.length;\r
    while (start < end && lines[start].trim() === '') start++;\r
    while (end > start && lines[end - 1].trim() === '') end--;\r
    if (start >= end) return '';\r
    return lines.slice(start, end).join('\\n');\r
}\r
\r
function truncateLogTextForUi(raw) {\r
    const text = (raw == null) ? '' : String(raw);\r
    if (!text) return text;\r
    const lines = text.split('\\n');\r
    if (lines.length > LOG_TRUNCATE_HEAD_LINES + LOG_TRUNCATE_TAIL_LINES) {\r
        const head = lines.slice(0, LOG_TRUNCATE_HEAD_LINES).join('\\n');\r
        const tail = lines.slice(-LOG_TRUNCATE_TAIL_LINES).join('\\n');\r
        const omitted = lines.length - LOG_TRUNCATE_HEAD_LINES - LOG_TRUNCATE_TAIL_LINES;\r
        return head + '\\n\\n... [中间省略 ' + omitted + ' 行] ...\\n\\n' + tail;\r
    }\r
    if (text.length > LOG_TRUNCATE_HEAD_CHARS + LOG_TRUNCATE_TAIL_CHARS) {\r
        const head = text.slice(0, LOG_TRUNCATE_HEAD_CHARS);\r
        const tail = text.slice(-LOG_TRUNCATE_TAIL_CHARS);\r
        const omitted = text.length - LOG_TRUNCATE_HEAD_CHARS - LOG_TRUNCATE_TAIL_CHARS;\r
        return head + '\\n\\n... [中间省略约 ' + omitted + ' 字符] ...\\n\\n' + tail;\r
    }\r
    return text;\r
}\r
\r
function createProcessFeedRow(ctx, type, initialText, streamOpts, runSessionId, toolCallIdOpt) {\r
    streamOpts = streamOpts || {};\r
    if (type == null) type = 'log-entry';\r
    stripWelcome(ctx);\r
    const body = getProcessBody(ctx);\r
    if (!body) return;\r
    const meta = TRACE_ROW[type] || TRACE_ROW['log-entry'];\r
    const row = document.createElement('div');\r
    row.className = 'feed-item ' + meta.c;\r
    row.setAttribute('data-log-type', type);\r
    if (toolCallIdOpt != null && String(toolCallIdOpt) !== '') row.setAttribute('data-tool-call-id', String(toolCallIdOpt));\r
    row.innerHTML = '<div class="feed-row">'\r
        + '<span class="feed-label">' + meta.label + '</span>'\r
        + '<div class="feed-chunk">'\r
        + '<div class="feed-chunk-scroller"></div></div></div>';\r
    const chunk = row.querySelector('.feed-chunk');\r
    const sc = row.querySelector('.feed-chunk-scroller');\r
    var txtForUi = initialText;\r
    if (type === 'llm-reasoning' || type === 'llm-response') txtForUi = trimSurroundingBlankLines(txtForUi);\r
    sc.textContent = truncateLogTextForUi(txtForUi);\r
    if (streamOpts.streaming && (type === 'llm-reasoning' || type === 'llm-response')) chunk.classList.add('is-streaming');\r
    bindFeedChunkInteraction(chunk);\r
    bindFeedChunkScrollChain(sc);\r
    body.appendChild(row);\r
    if (ctx && ctx.currentTurn && body.classList && body.classList.contains('subagent-turn-process')) {\r
        markSubagentTurnHasProcess(ctx.currentTurn);\r
    }\r
    if (type === 'error-log') {\r
        var errHint = document.createElement('div');\r
        errHint.className = 'feed-error-contact-hint';\r
        errHint.textContent = '如需帮助或反馈，请联系GitHub @sugarfreeecho';\r
        body.appendChild(errHint);\r
    }\r
    const agg = body.closest('.process-aggregate');\r
    if (streamOpts.reactIter != null && Number.isFinite(Number(streamOpts.reactIter))) {\r
        var ri = Math.max(1, Math.floor(Number(streamOpts.reactIter)));\r
        row.setAttribute('data-react-iter', String(ri));\r
        bumpAggregateMaxReactIter(agg, ri);\r
    }\r
    if (agg && agg.classList.contains('is-collapsed')) {\r
        updateProcessBrief(agg);\r
    }\r
    else requestAnimationFrame(function () { scheduleFeedChunkOverflowRefresh(chunk); });\r
    refreshAggregateStatsSmart(agg);\r
    if (!streamOpts.streaming) scrollContentAreaIfFollow(ctx, runSessionId);\r
    return sc;\r
}\r
\r
function appendLlmStreamDelta(ctx, ev, runSessionId) {\r
    if (!ctx || !ctx.llm) return;\r
    // 收到 reasoning/content 增量时，移除"正在思考中..."条目\r
    removeTemporaryStatus(ctx);\r
    const l = ctx.llm;\r
    const iter = ev.react_iter;\r
    const seq = Number(ev.stream_seq || 0);\r
    if (l.llmDeltaLastSeq !== null && seq !== l.llmDeltaLastSeq) finalizeLlmStreamChunks(ctx);\r
    l.llmDeltaLastSeq = seq;\r
    const part = ev.type === 'llm_reasoning_delta' ? 'reasoning' : 'response';\r
    const delta = String(ev.delta || '');\r
    if (!delta) return;\r
    if (iter != null) {\r
        var body0 = getProcessBody(ctx);\r
        if (body0) bumpAggregateMaxReactIter(body0.closest('.process-aggregate'), iter);\r
    }\r
    const streamOpt = { streaming: true };\r
    if (iter != null && Number.isFinite(Number(iter))) streamOpt.reactIter = Number(iter);\r
    if (part === 'reasoning') {\r
        if (l.llmStreamReasoningIter !== iter) {\r
            flushLlmDeltaText(ctx);\r
            l.llmStreamReasoningIter = iter;\r
            l.llmStreamReasoningScroller = createProcessFeedRow(ctx, 'llm-reasoning', '', streamOpt, runSessionId);\r
        }\r
        if (!l.llmStreamReasoningScroller) return;\r
        l.llmPendingReasoningDelta = (l.llmPendingReasoningDelta || '') + delta;\r
    } else {\r
        if (l.llmStreamResponseIter !== iter) {\r
            flushLlmDeltaText(ctx);\r
            l.llmStreamResponseIter = iter;\r
            l.llmStreamResponseScroller = createProcessFeedRow(ctx, 'llm-response', '', streamOpt, runSessionId);\r
        }\r
        if (!l.llmStreamResponseScroller) return;\r
        l.llmPendingResponseDelta = (l.llmPendingResponseDelta || '') + delta;\r
    }\r
    scheduleLlmDeltaFlush(ctx, runSessionId);\r
}\r
\r
function upsertLlmFeedRow(ctx, content, logType, runSessionId, reactIter) {\r
    if (!ctx) return null;\r
    var ri = reactIter != null && Number.isFinite(Number(reactIter)) ? Math.max(1, Math.floor(Number(reactIter))) : null;\r
    var body = getProcessBody(ctx);\r
    var txt = truncateLogTextForUi(trimSurroundingBlankLines(String(content || '')));\r
    if (!txt.trim()) return null;\r
    if (body && ri != null) {\r
        var existing = body.querySelector('.feed-item[data-log-type="' + logType + '"][data-react-iter="' + ri + '"]');\r
        if (existing) {\r
            var sc = existing.querySelector('.feed-chunk-scroller');\r
            var ch = existing.querySelector('.feed-chunk');\r
            if (sc) sc.textContent = txt;\r
            if (ch) {\r
                ch.classList.remove('is-streaming');\r
                scheduleFeedChunkOverflowRefresh(ch);\r
            }\r
            if (ctx.llm) resetLlmState(ctx);\r
            scrollContentAreaIfFollow(ctx, runSessionId);\r
            return sc;\r
        }\r
    }\r
    if (ctx.llm) resetLlmState(ctx);\r
    return appendLog(ctx, content, logType, runSessionId, ri);\r
}\r
\r
function parseMessageTimestamp(value) {\r
    if (value == null || value === '') return null;\r
    if (typeof value === 'number' && isFinite(value)) {\r
        return new Date(value > 100000000000 ? value : value * 1000);\r
    }\r
    var d = new Date(String(value));\r
    return isNaN(d.getTime()) ? null : d;\r
}\r
\r
function formatUserMessageTimestamp(value) {\r
    var d = parseMessageTimestamp(value);\r
    if (!d) return '';\r
    try {\r
        return new Intl.DateTimeFormat(undefined, {\r
            year: 'numeric',\r
            month: '2-digit',\r
            day: '2-digit',\r
            hour: '2-digit',\r
            minute: '2-digit',\r
            timeZoneName: 'short',\r
            hour12: false,\r
        }).format(d);\r
    } catch (e) {\r
        return d.toLocaleString();\r
    }\r
}\r
\r
function refreshUserMessageTimes(root) {\r
    var scope = root || document;\r
    if (!scope || !scope.querySelectorAll) return;\r
    scope.querySelectorAll('.user-message-time[data-created-at]').forEach(function (el) {\r
        var raw = el.getAttribute('data-created-at') || '';\r
        var txt = formatUserMessageTimestamp(raw);\r
        if (txt) el.textContent = txt;\r
    });\r
}\r
\r
function ensureUserMessageTimeAutoRefresh() {\r
    if (window.__userMessageTimeAutoRefreshBound) return;\r
    window.__userMessageTimeAutoRefreshBound = true;\r
    window.addEventListener('focus', function () { refreshUserMessageTimes(document); });\r
    document.addEventListener('visibilitychange', function () {\r
        if (!document.hidden) refreshUserMessageTimes(document);\r
    });\r
    setInterval(function () { refreshUserMessageTimes(document); }, 60000);\r
}\r
\r
function appendMessage(ctx, role, content, meta, runSessionId) {\r
    meta = meta || {};\r
    ensureUserMessageTimeAutoRefresh();\r
    stripWelcome(ctx);\r
    const wrap = document.createElement('div');\r
    wrap.className = 'msg-wrap msg-wrap--' + (role === 'user' ? 'user' : 'assistant');\r
    if (role === 'assistant') wrap.classList.add('msg-wrap--answer-frame');\r
    if (meta.eventIndex != null) wrap.setAttribute('data-event-index', String(meta.eventIndex));\r
    var tTrunc = meta.turnTruncateIdx;\r
    if (tTrunc == null) { if (role === 'user' && meta.eventIndex != null) tTrunc = meta.eventIndex; }\r
    if (tTrunc != null && tTrunc >= 0) wrap.setAttribute('data-truncate-from', String(tTrunc));\r
    if (role === 'user') {\r
        if (meta.eventIndex != null && meta.eventIndex >= 0) {\r
            wrap.id = 'user-msg-' + meta.eventIndex;\r
        } else {\r
            const n = (ctx.stream || chatContainer).querySelectorAll('.msg-wrap--user').length;\r
            wrap.id = 'user-msg-' + n;\r
        }\r
    }\r
    const div = document.createElement('div');\r
    div.className = 'message ' + (role === 'user' ? 'user' : 'assistant');\r
    var rawStr = content == null ? '' : String(content);\r
    messageRawMarkdown.set(wrap, rawStr);\r
    if (role === 'user') {\r
        if (userMessageShouldCollapse(rawStr)) {\r
            wrap.classList.add('has-turn-process');\r
            div.classList.add('is-collapsible');\r
            // 摘要\r
            var sum = document.createElement('div');\r
            sum.className = 'user-msg-summary';\r
            sum.textContent = buildUserMessageSummary(rawStr);\r
            linkifyAssistantTextNodes(sum);\r
            // 完整\r
            var ful = document.createElement('div');\r
            ful.className = 'user-msg-full';\r
            ful.textContent = rawStr;\r
            linkifyAssistantTextNodes(ful);\r
            // chevron\r
            var ch = document.createElement('div');\r
            ch.className = 'user-msg-chevron';\r
            var arrow = document.createElement('span');\r
            arrow.className = 'chevron-arrow';\r
            ch.appendChild(arrow);\r
            ch.addEventListener('click', function(e) {\r
                e.stopPropagation();\r
                wrap.classList.toggle('user-msg-expanded');\r
            });\r
            div.appendChild(sum);\r
            div.appendChild(ful);\r
            div.appendChild(ch);\r
        } else {\r
            div.textContent = rawStr;\r
            linkifyAssistantTextNodes(div);\r
        }\r
    }\r
        else {\r
        div.innerHTML = renderMarkdown(rawStr);\r
        enhanceAssistantMessageContent(div);\r
    }\r
    wrap.appendChild(div);\r
    if (role === 'user') {\r
        var createdAt = meta.createdAt || meta.created_at || meta.timestamp || new Date().toISOString();\r
        wrap.setAttribute('data-created-at', String(createdAt));\r
    }\r
    if (role === 'user' && !div.classList.contains('is-collapsible')) {\r
        renderUserMessageContent(wrap, div, rawStr, linkifyAssistantTextNodes);\r
    }\r
    attachMessageToolbar(wrap, role);\r
    (ctx.stream || chatContainer).appendChild(wrap);\r
    if (role === 'assistant') {\r
        if (ctx.currentProcessGroup && ctx.currentProcessGroup.isConnected) {\r
            ctx.currentProcessGroup.classList.add('is-collapsed');\r
            const ttop = ctx.currentProcessGroup.querySelector('.process-aggregate-top');\r
            if (ttop) ttop.setAttribute('aria-expanded', 'false');\r
            updateProcessBrief(ctx.currentProcessGroup);\r
        }\r
        sealProcessGroup(ctx);\r
    }\r
    if (role === 'user' && !replayingMessages) rebuildToc({ localOnly: true });\r
    if (!replayingMessages) {\r
        if (role === 'user') scrollChatToBottomIfFollow(runSessionId, { force: true });\r
        else scrollChatToBottomIfFollow(runSessionId, {});\r
    }\r
}\r
\r
function handleTraceChunkClick(e) {\r
    if (e) e.stopPropagation();\r
    this.classList.toggle('expanded');\r
    var self = this;\r
    requestAnimationFrame(function () {\r
        refreshFeedChunkOverflow(self);\r
        registerMermaidLazy(self);\r
    });\r
}\r
\r
function bindFeedChunkInteraction(ch) {\r
    ch.removeEventListener('click', handleTraceChunkClick);\r
    ch.addEventListener('click', handleTraceChunkClick);\r
}\r
\r
function bindExistingLogs(root) {\r
    const el = root || getVisibleChatStream() || chatContainer;\r
    if (!el) return;\r
    el.querySelectorAll('.feed-chunk').forEach(function (ch) {\r
        bindFeedChunkInteraction(ch);\r
        scheduleFeedChunkOverflowRefresh(ch);\r
        const sc = ch.querySelector('.feed-chunk-scroller');\r
        if (sc) bindFeedChunkScrollChain(sc);\r
    });\r
    el.querySelectorAll('.process-aggregate').forEach(function (agg) {\r
        bindProcessAggregate(agg);\r
        if (agg.classList.contains('is-collapsed')) updateProcessBrief(agg);\r
        refreshAggregateStatsSmart(agg);\r
    });\r
    el.querySelectorAll('.process-aggregate-brief').forEach(bindProcessBriefScrollChain);\r
}\r
\r
function appendLog(ctx, content, type, runSessionId, reactIter) {\r
    if (type == null) type = 'log-entry';\r
    const tStr = (content == null) ? '' : String(content);\r
    if ((type === 'llm-reasoning' || type === 'llm-response') && !trimSurroundingBlankLines(tStr).trim()) return null;\r
    var so = null;\r
    if (reactIter != null && Number.isFinite(Number(reactIter))) so = { reactIter: Number(reactIter) };\r
    return createProcessFeedRow(ctx, type, tStr, so, runSessionId);\r
}\r
\r
function flushProgressDeltaText(ctx, logType) {\r
    if (!ctx || !ctx.progressStream) return;\r
    var st = ctx.progressStream[logType];\r
    if (!st) return;\r
    if (st.flushRaf) {\r
        cancelAnimationFrame(st.flushRaf);\r
        st.flushRaf = 0;\r
    }\r
    if (st.pending && st.scroller && st.scroller.isConnected) {\r
        var merged = (st.scroller.textContent || '') + st.pending;\r
        st.scroller.textContent = truncateLogTextForUi(merged);\r
        var ch = st.scroller.closest('.feed-chunk');\r
        if (ch) refreshFeedChunkOverflow(ch);\r
    }\r
    st.pending = '';\r
}\r
\r
function finalizeProgressStreamChunks(ctx) {\r
    if (!ctx) return;\r
    var types = ctx.progressStream ? Object.keys(ctx.progressStream) : [];\r
    for (var i = 0; i < types.length; i += 1) flushProgressDeltaText(ctx, types[i]);\r
    var streamRoot = (ctx._subagentBody && ctx._subagentBody.isConnected) ? ctx._subagentBody : ctx.stream;\r
    if (streamRoot) {\r
        streamRoot.querySelectorAll('.feed-item .feed-chunk.is-streaming').forEach(function (ch) {\r
            ch.classList.remove('is-streaming');\r
            refreshFeedChunkOverflow(ch);\r
        });\r
    }\r
    ctx.progressStream = {};\r
}\r
\r
function scheduleProgressDeltaFlush(ctx, runSessionId, logType) {\r
    if (!ctx || !ctx.progressStream) return;\r
    var st = ctx.progressStream[logType];\r
    if (!st || st.flushRaf) return;\r
    st.flushRaf = requestAnimationFrame(function () {\r
        st.flushRaf = 0;\r
        flushProgressDeltaText(ctx, logType);\r
        followStreamProcessScroll(ctx, runSessionId);\r
    });\r
}\r
\r
/** 每个压缩阶段（裁剪/压缩/要点）共用一条 feed，状态行与正文在同一 scroller */\r
function ensureProgressScroller(ctx, logType, runSessionId) {\r
    if (!ctx) return null;\r
    if (!ctx.progressScrollers) ctx.progressScrollers = {};\r
    var sc = ctx.progressScrollers[logType];\r
    if (sc && sc.isConnected) return sc;\r
    sc = appendLog(ctx, '', logType, runSessionId);\r
    if (sc) ctx.progressScrollers[logType] = sc;\r
    return sc;\r
}\r
\r
/** 落盘正文：替换流式段或追加到状态行后，与刷新后 ui_events 回放一致 */\r
function applyProgressPersistedBody(ctx, content, logType, runSessionId) {\r
    if (!ctx) return;\r
    var text = String(content || '').trim();\r
    if (!text) return;\r
    var st = ctx.progressStream && ctx.progressStream[logType];\r
    var bodyOffset = st && typeof st.bodyOffset === 'number' ? st.bodyOffset : null;\r
    var hadStream = bodyOffset != null;\r
    finalizeProgressStreamForType(ctx, logType);\r
    var sc = ensureProgressScroller(ctx, logType, runSessionId);\r
    if (!sc) return;\r
    var prevTxt = sc.textContent || '';\r
    var merged;\r
    if (hadStream) {\r
        merged = prevTxt.slice(0, bodyOffset).replace(/\\s+$/, '') + '\\n\\n' + text;\r
    } else if (prevTxt.trim()) {\r
        merged = prevTxt.trim() + '\\n\\n' + text;\r
    } else {\r
        merged = text;\r
    }\r
    sc.textContent = truncateLogTextForUi(merged);\r
    var chSet = sc.closest('.feed-chunk');\r
    if (chSet) {\r
        chSet.classList.remove('is-streaming');\r
        refreshFeedChunkOverflow(chSet);\r
        requestAnimationFrame(function () { refreshFeedChunkOverflow(chSet); });\r
    }\r
    ctx.progressScrollers[logType] = sc;\r
    scrollContentAreaIfFollow(ctx, runSessionId);\r
}\r
\r
/** 压缩/要点执行端输出：在同一 feed 内流式追加正文（不另起 feed 块） */\r
function appendProgressStreamDelta(ctx, delta, logType, runSessionId) {\r
    if (!ctx || !delta) return;\r
    if (!ctx.progressStream) ctx.progressStream = {};\r
    var piece = String(delta);\r
    if (!piece) return;\r
    var sc = ensureProgressScroller(ctx, logType, runSessionId);\r
    if (!sc) return;\r
    var chunk = sc.closest('.feed-chunk');\r
    if (chunk) chunk.classList.add('is-streaming');\r
    var st = ctx.progressStream[logType];\r
    if (!st) {\r
        var head = (sc.textContent || '').trim();\r
        var bodyOffset = sc.textContent.length;\r
        if (head) {\r
            sc.textContent = head + '\\n\\n';\r
            bodyOffset = sc.textContent.length;\r
        }\r
        st = { scroller: sc, pending: '', flushRaf: 0, bodyOffset: bodyOffset };\r
        ctx.progressStream[logType] = st;\r
    }\r
    st.pending += piece;\r
    scheduleProgressDeltaFlush(ctx, runSessionId, logType);\r
}\r
\r
/** 同类型进度行合并追加，实现裁剪/压缩/要点分轨流式展示 */\r
function appendProgressLog(ctx, content, logType, runSessionId) {\r
    if (!ctx) return;\r
    finalizeProgressStreamForType(ctx, logType);\r
    if (!ctx.progressScrollers) ctx.progressScrollers = {};\r
    var line = String(content || '');\r
    if (!line.trim()) return;\r
    var prev = ctx.progressScrollers[logType];\r
    if (prev && prev.isConnected) {\r
        var prevTxt = prev.textContent || '';\r
        prev.textContent = truncateLogTextForUi(prevTxt ? (prevTxt + '\\n' + line) : line);\r
        var chMerge = prev.closest('.feed-chunk');\r
        if (chMerge) {\r
            refreshFeedChunkOverflow(chMerge);\r
            requestAnimationFrame(function () { refreshFeedChunkOverflow(chMerge); });\r
        }\r
        scrollContentAreaIfFollow(ctx, runSessionId);\r
        return;\r
    }\r
    var sc = ensureProgressScroller(ctx, logType, runSessionId);\r
    if (!sc) return;\r
    sc.textContent = truncateLogTextForUi(line);\r
    var chNew = sc.closest('.feed-chunk');\r
    if (chNew) {\r
        refreshFeedChunkOverflow(chNew);\r
        requestAnimationFrame(function () { refreshFeedChunkOverflow(chNew); });\r
    }\r
    scrollContentAreaIfFollow(ctx, runSessionId);\r
}\r
\r
function finalizeProgressStreamForType(ctx, logType) {\r
    if (!ctx || !logType) return;\r
    flushProgressDeltaText(ctx, logType);\r
    if (ctx.progressStream && ctx.progressStream[logType]) {\r
        var st = ctx.progressStream[logType];\r
        if (st.scroller && st.scroller.isConnected) {\r
            var ch = st.scroller.closest('.feed-chunk');\r
            if (ch) {\r
                ch.classList.remove('is-streaming');\r
                refreshFeedChunkOverflow(ch);\r
            }\r
        }\r
        delete ctx.progressStream[logType];\r
    }\r
}\r
\r
/* ── Subagent 浮层 / 过程块 ── */\r
`,Ue=`var subagentPanelOpen = false;
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
    if (t === 'status' && (!c || c === 'New Agent Loop Start' || c === 'Loop finished' || c === 'Subagent Continuation Start')) return true;
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
`,He=`function renderEvent(ctx, event, eventIndex, runSessionId) {
    if (!event || typeof event !== 'object') return;
    var eventSessionId = runSessionId || currentSessionId || '';
    if (eventSessionId && !event.__storeApplied) {
        applyMessageEvent(eventSessionId, event, eventIndex, replayingMessages ? 'history' : 'stream');
        if (event.type === 'subagent_start' || event.type === 'subagent_finish'
            || event.type === 'subagent_started' || event.type === 'subagent_finished') {
            applySubagentLifecycleToStore(eventSessionId, event);
        }
    }
    if (event.type === 'user') {
        if (typeof eventIndex === 'number') ctx.lastUserEventIndex = eventIndex;
        sealProcessGroup(ctx);
        appendMessage(ctx, 'user', event.content || '', {
            eventIndex: eventIndex,
            turnTruncateIdx: eventIndex,
            createdAt: event.created_at || event.createdAt || event.timestamp,
        }, runSessionId);
    } else if (event.type === 'user_steer') {
        appendLog(ctx, event.content || '', 'user-steer', runSessionId);
    } else if (event.type === 'final') {
        appendMessage(ctx, 'assistant', event.content || '', { eventIndex: eventIndex, turnTruncateIdx: ctx.lastUserEventIndex }, runSessionId);
    } else if (event.type === 'process_metrics') {
        applyProcessMetricsFromEvent(ctx, event);
    } else if (event.type === 'cache_stats') {
        applyCacheStatsFromEvent(ctx, event);
    } else if (event.type === 'tool_call') {
        var riTool = uiEventReactIter(event);
        if (event.raw_content) appendLog(ctx, event.raw_content, 'tool-call', runSessionId, riTool);
        else appendLog(ctx, formatToolDoneLine(event.tool, event.args, event.result, event.command_preview), 'tool-call', runSessionId, riTool);
    } else if (event.type === 'validate_final') {
        appendLog(ctx, '验证：' + event.result + (event.reason ? '\\n' + event.reason : ''), 'status', runSessionId);
    } else if (event.type === 'llm_reasoning') {
        upsertLlmFeedRow(ctx, event.content || '', 'llm-reasoning', runSessionId, uiEventReactIter(event));
    } else if (event.type === 'llm_response') {
        upsertLlmFeedRow(ctx, event.content || '', 'llm-response', runSessionId, uiEventReactIter(event));
    } else if (event.type === 'llm_history_rollup' || event.type === 'compact_summary') {
        appendLog(ctx, String(event.content || ''), 'compact-summary', runSessionId);
    } else if (event.type === 'context_trim_progress') {
        appendProgressLog(ctx, event.content, 'context-trim', runSessionId);
    } else if (event.type === 'context_summary_progress') {
        appendProgressLog(ctx, event.content, 'context-summary', runSessionId);
    } else if (event.type === 'context_summary_delta') {
        appendProgressStreamDelta(ctx, event.delta, 'context-summary', runSessionId);
    } else if (event.type === 'context_summary_body') {
        applyProgressPersistedBody(ctx, event.content, 'context-summary', runSessionId);
    } else if (event.type === 'key_context_progress') {
        var keyProg = String(event.content || '');
        if (keyProg.indexOf('正在根据对话更新要点') >= 0) {
            finalizeProgressStreamForType(ctx, 'context-summary');
            resetKeyContextStreamFilter(ctx);
        }
        appendProgressLog(ctx, keyProg, 'key-context', runSessionId);
    } else if (event.type === 'key_context_delta') {
        appendKeyContextStreamDelta(ctx, event.delta, runSessionId);
    } else if (event.type === 'key_context_body') {
        applyProgressPersistedBody(ctx, event.content, 'key-context', runSessionId);
    } else if (event.type === 'error') {
        appendLog(ctx, String(event.content || ''), 'error-log', runSessionId);
    } else if (event.type === 'status') {
        var statusContent = String(event.content || '');
        if (statusContent.indexOf('【自动·长度策略】') >= 0) {
            finalizeProgressStreamChunks(ctx);
            resetKeyContextStreamFilter(ctx);
        }
        if (event.compress_progress) {
            var legacyLogType = 'context-trim';
            if (statusContent.indexOf('【上下文摘要】') >= 0) legacyLogType = 'context-summary';
            else if (statusContent.indexOf('【要点】') >= 0) legacyLogType = 'key-context';
            appendProgressLog(ctx, statusContent, legacyLogType, runSessionId);
            return;
        }
        // 临时状态消息处理：标记"正在思考中..."为临时状态
        var isTemporaryStatus = statusContent.indexOf('正在思考中...') >= 0;
        if (isTemporaryStatus) removeTemporaryStatus(ctx);
        var statusRow = appendLog(ctx, statusContent, 'status', runSessionId);
        if (isTemporaryStatus && statusRow) {
            statusRow.dataset.temporaryStatus = '1';
        }
    } else if (event.type === 'approval_required') {
        var leg = (event.tool_name ? String(event.tool_name) + ' ' : '') + (event.message || '');
        appendLog(ctx, '[历史/旧版事件] ' + leg.trim(), 'status', runSessionId);
    } else if (event.type === 'warning') {
        appendLog(ctx, String(event.content || ''), 'status', runSessionId);
    } else if (event.type === 'subagent_start' || event.type === 'subagent_finish') {
        if (!ctx._subagentBody) {
            handleSubagentLifecycleEvent(event);
            return;
        }
        if (event.type === 'subagent_start') ensureSubagentBlock(ctx, event);
        else updateSubagentBlockFinish(ctx, event);
    } else {
        var fallbackContent = String(event.content || '');
        if (fallbackContent.trim()) appendLog(ctx, fallbackContent, 'log-entry', runSessionId);
    }
}
`,je=`function setSendButtonState() {
    sendBtn.disabled = false;
    if (isSessionRunning(currentSessionId)) {
        const hasDraft = (typeof inputHasSendableText === 'function')
            ? inputHasSendableText()
            : !!(messageInput && String(messageInput.value || '').trim());
        sendBtn.innerHTML = hasDraft ? '追问' : '停止 <span class="loader" aria-hidden="true"></span>';
        sendBtn.classList.add('is-stop');
        sendBtn.classList.toggle('is-followup', hasDraft);
    } else {
        sendBtn.textContent = '发送';
        sendBtn.classList.remove('is-stop');
        sendBtn.classList.remove('is-followup');
    }
}

async function requestInterrupt(sessionId, runId, reason) {
    if (!sessionId) return;
    try {
        await fetch('/sessions/' + sessionId + '/interrupt', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ run_id: runId || '', reason: reason || '' }),
        });
    }
    catch (e) { /* ignore */ }
}

function pauseCurrentRun() {
    if (!currentSessionId) return;
    const run = getSessionRunState(currentSessionId);
    const sid = currentSessionId;
    const activeInfo = sessionStore.getActiveRunInfo(sid) || {};
    const runId = run && run.runId ? run.runId : (activeInfo.run_id || activeInfo.runId || '');
    suppressSessionServerStreamActive(sid);
    if (!run) {
        setSendButtonState();
        syncSessionListIndicatorClasses();
        renderSessionListIfChanged(false);
        void requestInterrupt(sid, runId);
        setTimeout(function () { reconcileRunStateFromServer({ silent: true, respectStopSuppress: true }); }, 3000);
        return;
    }
    const ctx = run.ctx;
    /* 先同步 abort 本地 fetch 与从 sessionStore 摘除，UI 立刻反映为「已停止」状态。
       后端 interrupt 走 fire-and-forget，避免被主线程阻塞时按钮响应迟滞。 */
    abortSessionRun(sid, 'user');
    setSendButtonState();
    syncSessionListIndicatorClasses();
    renderSessionListIfChanged(false);
    appendLog(ctx, '已请求停止当前任务', 'status', sid);
    sealProcessGroup(ctx);
    void requestInterrupt(sid, runId);
    setTimeout(function () { reconcileRunStateFromServer({ silent: true, respectStopSuppress: true }); }, 3000);
}

/** 在当前对话中定位最近一条用户消息并重新发送。返回 true 表示已触发展开发送。 */
function resendLastUserMessage() {
    if (!currentSessionId) return false;
    if (isSessionRunning(currentSessionId)) return false;
    var lastMsg = lastUserMessageBySession[currentSessionId];
    if (!lastMsg || !String(lastMsg).trim()) {
        var chatStream = getVisibleChatStream();
        if (chatStream) {
            var wraps = chatStream.querySelectorAll('.msg-wrap--user');
            if (wraps.length) {
                var lastWrap = wraps[wraps.length - 1];
                lastMsg = messageRawMarkdown.get(lastWrap) || (lastWrap.querySelector('.message.user') && lastWrap.querySelector('.message.user').textContent);
            }
        }
    }
    if (!lastMsg || !String(lastMsg).trim()) {
        lastMsg = draftBySession[currentSessionId];
    }
    if (!lastMsg || !String(lastMsg).trim()) return false;
    messageInput.value = String(lastMsg);
    rewriteInputWorkspacePaths();
    autoResizeTextarea();
    sendMessage();
    return true;
}

function showLoading() {
    resetSessionHistoryPaging();
    clearTocForSessionLoad();
    if (!getVisibleChatStream()) ensureVisibleChatStreamSlot();
    const vs = getVisibleChatStream();
    if (vs) emptyChatStreamKeepingStrip(vs);
    const box = document.createElement('div');
    box.className = 'skeleton';
    box.id = 'chat-loading';
    box.setAttribute('role', 'status');
    box.innerHTML = ''
        + '<div class="skeleton-page" aria-hidden="true">'
        + '<div class="skeleton-mast"><span></span><span></span></div>'
        + '<div class="skeleton-hero"><div class="skeleton-image"></div><div class="skeleton-column"><span></span><span></span><span></span><span></span></div></div>'
        + '<div class="skeleton-grid"><div><span></span><span></span><span></span></div><div><span></span><span></span><span></span></div><div><span></span><span></span><span></span></div></div>'
        + '</div><div class="skeleton-copy">加载中</div>';
    box.setAttribute('data-ui-tip', '加载会话');
    bindUiHoverTip(box);
    (getVisibleChatStream() || chatContainer).appendChild(box);
    scrollToBottom();
}

function hideLoading() { const loader = document.getElementById('chat-loading'); if (loader) loader.remove(); }

/** 根据 sessionStore / 服务端 stream_active / sessionUnreadComplete 更新黄点、绿点 */
function applySessionItemIndicators(itemDiv, sessionId, opts) {
    opts = opts || {};
    if (!itemDiv || !sessionId) return;
    itemDiv.classList.remove('is-generating', 'is-unread-result', 'is-unread-failed');
    var nameEl = itemDiv.querySelector('.session-name');
    if (nameEl) nameEl.removeAttribute('data-ui-tip');
    if (isSessionRunning(sessionId)) {
        itemDiv.classList.add('is-generating');
        if (nameEl) nameEl.setAttribute('data-ui-tip', '生成中…');
    } else {
        var sess = sessionStore.get(sessionId);
        var localUnreadResult = sessionUnreadComplete.has(sessionId);
        var hasUnreadResult = sess ? !!sess.unread_result : localUnreadResult;
        if (!hasUnreadResult) return;
        var failed = !!(sess && sess.unread_result_status === 'failed');
        itemDiv.classList.add(failed ? 'is-unread-failed' : 'is-unread-result');
        if (nameEl) nameEl.setAttribute('data-ui-tip', failed ? '任务失败，点击查看' : '有新回复，点击查看');
    }
    if (nameEl) bindUiHoverTip(nameEl);
}

/** 立即刷新侧栏全部指示点与当前选中项；不依赖 loadSessions 网络往返，与是否切换会话无关 */
function syncSessionListIndicatorClasses() {
    if (!sessionsList) return;
    sessionsList.querySelectorAll('.session-item').forEach(function (div) {
        var el = div.querySelector('.session-name[data-id]');
        if (!el) return;
        var sid = el.getAttribute('data-id');
        div.classList.toggle('active', !!sid && sid === currentSessionId);
        applySessionItemIndicators(div, sid);
    });
}

function sessionSectionExpanded(key) {
    try {
        return localStorage.getItem(LS_SESSION_SECTION_PREFIX + key) !== '0';
    } catch (e) {
        return true;
    }
}
function persistSessionSectionExpanded(key, expanded) {
    try {
        localStorage.setItem(LS_SESSION_SECTION_PREFIX + key, expanded ? '1' : '0');
    } catch (e) { /* ignore */ }
}
function closeAllSessionMenus() {
    document.querySelectorAll('.session-more-wrap.is-open').forEach(function (w) {
        w.classList.remove('is-open');
        var b = w.querySelector('.session-more-btn');
        if (b) b.setAttribute('aria-expanded', 'false');
    });
}
(function bindSessionMenuDocumentCloserOnce() {
    if (window.__myAgentSessionMenuCloser) return;
    window.__myAgentSessionMenuCloser = true;
    document.addEventListener('click', closeAllSessionMenus);
})();

(function bindSessionListDelegatedSwitcherOnce() {
    if (!sessionsList || window.__myAgentSessionListSwitcher) return;
    window.__myAgentSessionListSwitcher = true;
    sessionsList.addEventListener('click', function (e) {
        var target = e.target;
        if (!target || !target.closest) return;
        if (target.closest('button, .session-more-wrap, .session-more-menu, input, textarea, a')) return;
        if (target.isContentEditable) return;
        var row = target.closest('.session-item');
        if (!row || !sessionsList.contains(row)) return;
        var sid = row.dataset.sessionId;
        if (!sid) {
            var nameEl = row.querySelector('.session-name[data-id]');
            sid = nameEl ? nameEl.getAttribute('data-id') : '';
        }
        if (sid && sid !== currentSessionId) {
            Promise.resolve(switchSession(sid)).catch(function (err) {
                console.error('切换会话失败:', err);
            });
        }
    });
})();

/**
 * 创建并绑定单行会话（更多菜单：置顶 → 删除 → 归档在末位）
 */
function buildAndBindSessionRow(sess, allSessions, nextStreamMap) {
    const div = document.createElement('div');
    div.className = 'session-item';
    div.dataset.sessionId = sess.id || '';
    if (currentSessionId === sess.id) div.classList.add('active');
    if (sess.id) nextStreamMap[sess.id] = !!sess.stream_active;
    div.innerHTML = '<div class="session-item-head">'
        + '<span class="session-name" data-id="' + sess.id + '" data-original="' + escapeHtml(sess.name) + '">' + escapeHtml(sess.name) + '</span>'
        + '<div class="session-more-wrap">'
        + '<button type="button" class="session-more-btn" aria-label="更多操作" aria-expanded="false" aria-haspopup="true" data-ui-tip="更多">'
        + '<span class="session-more-dots" aria-hidden="true"><span></span><span></span><span></span></span></button>'
        + '<div class="session-more-menu" role="menu">'
        + '<button type="button" class="session-menu-pin" role="menuitem"></button>'
        + '<button type="button" class="session-menu-delete" role="menuitem">删除</button>'
        + '<button type="button" class="session-menu-archive" role="menuitem"></button>'
        + '</div></div>'
        + '</div>'
        + '<div class="session-last-query"></div>';
    var pinMi = div.querySelector('.session-menu-pin');
    var archMi = div.querySelector('.session-menu-archive');
    if (pinMi) pinMi.textContent = sess.pinned ? '取消置顶' : '置顶';
    if (archMi) archMi.textContent = sess.archived ? '取消归档' : '归档';
    var wsLine = formatSessionListSubtitle(sess);
    var wsEl = div.querySelector('.session-last-query');
    if (wsEl) {
        wsEl.textContent = wsLine;
        wsEl.setAttribute('data-ui-tip', wsLine);
        bindUiHoverTip(wsEl);
    }
    var moreWrap = div.querySelector('.session-more-wrap');
    var moreBtn = div.querySelector('.session-more-btn');
    if (moreBtn) bindUiHoverTip(moreBtn);
    if (moreWrap && moreBtn) {
        moreBtn.addEventListener('click', function (e) {
            e.stopPropagation();
            var wasOpen = moreWrap.classList.contains('is-open');
            closeAllSessionMenus();
            if (pinMi) pinMi.textContent = sess.pinned ? '取消置顶' : '置顶';
            if (archMi) archMi.textContent = sess.archived ? '取消归档' : '归档';
            if (!wasOpen) {
                moreWrap.classList.add('is-open');
                moreBtn.setAttribute('aria-expanded', 'true');
            }
        });
    }
    if (pinMi) {
        pinMi.addEventListener('click', async function (e) {
            e.stopPropagation();
            closeAllSessionMenus();
            try {
                const formData = new FormData();
                const nextPinned = !sess.pinned;
                const previous = applyOptimisticSessionUpdate(sess.id, { pinned: nextPinned });
                formData.append('pinned', nextPinned ? 'true' : 'false');
                const response = await fetch('/sessions/' + encodeURIComponent(sess.id) + '/pin', { method: 'PUT', body: formData });
                if (!response.ok) {
                    if (previous) applyOptimisticSessionUpdate(sess.id, previous);
                    throw new Error('pin failed: ' + response.status);
                }
                void refreshSingleSessionRow(sess.id);
            } catch (err) { console.error('置顶失败', err); }
        });
    }
    if (archMi) {
        archMi.addEventListener('click', async function (e) {
            e.stopPropagation();
            closeAllSessionMenus();
            try {
                const formData = new FormData();
                const nextArchived = !sess.archived;
                const previous = applyOptimisticSessionUpdate(sess.id, { archived: nextArchived });
                formData.append('archived', nextArchived ? 'true' : 'false');
                const response = await fetch('/sessions/' + encodeURIComponent(sess.id) + '/archive', { method: 'PUT', body: formData });
                if (!response.ok) {
                    if (previous) applyOptimisticSessionUpdate(sess.id, previous);
                    throw new Error('archive failed: ' + response.status);
                }
                void refreshSingleSessionRow(sess.id);
            } catch (err) { console.error('归档失败', err); }
        });
    }
    var delMi = div.querySelector('.session-menu-delete');
    if (delMi) {
        delMi.addEventListener('click', async function (e) {
            e.stopPropagation();
            closeAllSessionMenus();
            const okDel = await openUiModal({
                title: '删除会话',
                subtitle: '此操作不可恢复',
                message: '确定删除会话「' + String(sess.name || '未命名') + '」吗？其中的消息与记录将被移除。',
                danger: true,
                confirmText: '删除会话',
                cancelText: '取消',
            });
            if (!okDel) return;
            const wasArchivedLoaded = sessionStore.archivedLoaded;
            const deletedSessionId = String(sess.id || '');
            const nextSession = sessionStore.list().find(function (s) {
                return s && s.id && String(s.id) !== deletedSessionId && !s.archived;
            }) || null;
            sessionStore.markDeletedSession(deletedSessionId);
            if (wasArchivedLoaded) {
                sessionStore.setArchivedLoaded((sessionStore.archivedSessions || []).filter(function (s) {
                    return s && String(s.id) !== deletedSessionId;
                }));
                syncArchivedSessionStateFromStore();
            }
            renderSessionListIfChanged(true);
            if (div && div.parentNode) div.remove();
            sessionUnreadComplete.delete(deletedSessionId);
            persistSessionUnread();
            delete draftBySession[deletedSessionId];
            removeStoredInputDraft(deletedSessionId);
            if (typeof removeStoredFollowupQueue === 'function') removeStoredFollowupQueue(deletedSessionId);
            delete lastUserMessageBySession[deletedSessionId];
            clearContextStateForSession(deletedSessionId);
            if (isSessionRunning(sess.id)) {
                const r = abortSessionRun(sess.id, 'delete');
                if (r && r.ctx && r.ctx.stream && r.ctx.stream.parentNode) r.ctx.stream.remove();
                setSendButtonState();
                syncSessionListIndicatorClasses();
            }
            if (currentSessionId === deletedSessionId) {
                if (nextSession) await switchSession(nextSession.id);
                else await createNewSession();
            }
            void requestInterrupt(deletedSessionId);
            void fetch('/sessions/' + encodeURIComponent(deletedSessionId), { method: 'DELETE' })
                .then(function (resp) {
                    if (!resp.ok) throw new Error('delete failed: ' + resp.status);
                })
                .catch(function (err) {
                    console.error('删除会话失败:', err);
                    sessionStore.clearDeletedSessionTombstone(deletedSessionId);
                    void loadSessions({ skipArchivedRefresh: true });
                    if (wasArchivedLoaded) void loadArchivedSessions({ background: true });
                });
        });
    }
    const nameSpan = div.querySelector('.session-name');
    if (nameSpan) {
        nameSpan.addEventListener('dblclick', function (e) {
            e.stopPropagation();
            if (nameSpan.classList.contains('editing')) return;
            nameSpan.classList.add('editing');
            nameSpan.contentEditable = 'true';
            nameSpan.focus();
            const range = document.createRange();
            range.selectNodeContents(nameSpan);
            const sel = window.getSelection();
            sel.removeAllRanges();
            sel.addRange(range);
        });
        nameSpan.addEventListener('blur', async function () {
            if (!nameSpan.classList.contains('editing')) return;
            nameSpan.classList.remove('editing');
            nameSpan.contentEditable = 'false';
            const newName = nameSpan.innerText.trim();
            if (newName && newName !== nameSpan.dataset.original) {
                const oldName = nameSpan.dataset.original;
                const previous = applyOptimisticSessionUpdate(sess.id, { name: newName });
                nameSpan.dataset.original = newName;
                if (currentSessionId === sess.id) updateSessionTitle();
                try {
                    const formData = new FormData();
                    formData.append('name', newName);
                    const response = await fetch('/sessions/' + encodeURIComponent(sess.id) + '/name', { method: 'PUT', body: formData });
                    if (!response.ok) throw new Error('rename failed: ' + response.status);
                    if (currentSessionId === sess.id) updateSessionTitle();
                } catch (err) {
                    console.error('重命名失败', err);
                    if (previous) applyOptimisticSessionUpdate(sess.id, previous);
                    nameSpan.innerText = oldName;
                    nameSpan.dataset.original = oldName;
                    if (currentSessionId === sess.id) updateSessionTitle();
                }
            } else nameSpan.innerText = nameSpan.dataset.original;
        });
        nameSpan.addEventListener('keydown', function (e) { if (e.key === 'Enter') { e.preventDefault(); nameSpan.blur(); } });
    }
    applySessionItemIndicators(div, sess.id, { serverStreamActive: !!sess.stream_active });
    return div;
}

async function refreshSingleSessionRow(sessionId) {
    if (!sessionId || !sessionsList) return;
    try {
        const response = await fetch('/sessions/' + encodeURIComponent(sessionId));
        if (!response.ok) return;
        const sess = await response.json();
        if (!sess || !sess.id) return;
        applySessionPatch({
            session: sess,
            session_id: sess.id,
            stream_active: !!sess.stream_active,
        });
        setSessionServerStreamActive(sess.id, !!sess.stream_active);
        if (sess.unread_result) {
            if (!sessionUnreadComplete.has(sess.id)) {
                sessionUnreadComplete.add(sess.id);
                persistSessionUnread();
            }
        } else if (sessionUnreadComplete.delete(sess.id)) {
            persistSessionUnread();
        }
        if (Number(sess.subagent_running || 0) > 0) {
            sessionUnreadComplete.delete(sess.id);
            persistSessionUnread();
        }
        renderSessionListIfChanged(false);
    } catch (e) {
        console.error('刷新会话摘要失败:', e);
    }
}

let sessionListLoadEpoch = 0;
let sessionListRenderKey = '';
let createNewSessionQueue = Promise.resolve();
let archivedSessionsLoaded = false;
let archivedSessionsCache = null;
let archivedSessionsCount = 0;
let archivedSessionsLoadEpoch = 0;

function syncArchivedSessionStateFromStore() {
    archivedSessionsLoaded = !!sessionStore.archivedLoaded;
    archivedSessionsCache = sessionStore.archivedSessions;
    archivedSessionsCount = sessionStore.archivedCount;
}

function computeSessionListRenderKey() {
    const sessions = sessionStore.list();
    const parts = [
        'cur=' + String(currentSessionId || ''),
        'archivedLoaded=' + (sessionStore.archivedLoaded ? '1' : '0'),
        'archivedCount=' + String(sessionStore.archivedCount || 0),
    ];
    for (let i = 0; i < sessions.length; i += 1) {
        const s = sessions[i];
        if (!s || !s.id) continue;
        parts.push([
            s.id,
            s.name || '',
            s.pinned ? 'p' : '',
            s.archived ? 'a' : '',
            s.stream_active ? 'r' : '',
            s.unread_result ? ('u:' + (s.unread_result_status || 'success')) : '',
            s.last_activity_at || s.updated_at || '',
            s.last_user_preview || '',
            s.subagent_running || 0,
            s.subagent_pending_continue || 0,
            s.subagent_can_continue ? 'c' : '',
        ].join('\\u001f'));
    }
    const archived = sessionStore.archivedList();
    for (let j = 0; j < archived.length; j += 1) {
        const a = archived[j];
        if (!a || !a.id) continue;
        parts.push('arch=' + [
            a.id,
            a.name || '',
            a.pinned ? 'p' : '',
            a.unread_result ? ('u:' + (a.unread_result_status || 'success')) : '',
            a.last_activity_at || a.updated_at || '',
            a.last_user_preview || '',
        ].join('\\u001f'));
    }
    return parts.join('\\u001e');
}

function renderSessionListIfChanged(force) {
    const nextKey = computeSessionListRenderKey();
    if (!force && nextKey === sessionListRenderKey) {
        syncSessionListIndicatorClasses();
        renderSessionTitleFromStore();
        return;
    }
    sessionListRenderKey = nextKey;
    const nextStreamMap = renderSessionListFromStore();
    applyServerStreamActiveMap(nextStreamMap);
    renderSessionTitleFromStore();
}

function applyOptimisticSessionUpdate(sessionId, patch) {
    const sid = String(sessionId || '');
    const current = sessionStore.get(sid);
    if (!current) return null;
    const prev = Object.assign({}, current);
    const next = Object.assign({}, current, patch || {});
    if (Object.prototype.hasOwnProperty.call(patch || {}, 'pinned')) {
        next.pinned_at = next.pinned ? (next.pinned_at || new Date().toISOString()) : null;
    }
    sessionStore.upsert(next);
    if (prev.archived || next.archived) {
        const archivedList = (sessionStore.archivedSessions || []).filter(function (s) {
            return s && s.id !== sid;
        });
        if (next.archived && sessionStore.archivedLoaded) archivedList.unshift(next);
        if (sessionStore.archivedLoaded) {
            sessionStore.setArchivedLoaded(archivedList);
            syncArchivedSessionStateFromStore();
        }
    }
    renderSessionListIfChanged(true);
    return prev;
}

// 事件计数缓存，用于乐观更新
const uiEventCountCache = {
    cache: new Map(),
    
    get(sessionId) {
        return this.cache.get(sessionId) || 0;
    },
    
    set(sessionId, count) {
        this.cache.set(sessionId, count);
    },
    
    increment(sessionId) {
        const current = this.get(sessionId);
        this.set(sessionId, current + 1);
        return current + 1;
    },
    
    updateFromServer(sessionId, count) {
        this.set(sessionId, count);
    }
};

async function fetchSessionsStateSnapshot(opts) {
    opts = opts || {};
    const url = '/sessions/state' + (opts.includeArchived ? '?include_archived=true' : '');
    const response = await fetchWithTimeout(url, {}, 12000);
    if (!response.ok) throw new Error('sessions state failed: ' + response.status);
    const snapshot = await response.json();
    if (!snapshot || !Array.isArray(snapshot.sessions)) {
        throw new Error('invalid sessions state response');
    }
    snapshot.include_archived = !!opts.includeArchived;
    return snapshot;
}

async function fetchWithTimeout(url, options, timeoutMs) {
    options = options || {};
    const ms = Number(timeoutMs) > 0 ? Number(timeoutMs) : 15000;
    if (options.signal) return fetch(url, options);
    const controller = new AbortController();
    const timer = setTimeout(function () { controller.abort(); }, ms);
    const nextOptions = Object.assign({}, options, { signal: controller.signal });
    try {
        return await fetch(url, nextOptions);
    } finally {
        clearTimeout(timer);
    }
}

async function loadArchivedSessions(opts) {
    opts = opts || {};
    const loadEpoch = ++archivedSessionsLoadEpoch;
    try {
        const response = await fetchWithTimeout('/sessions?include_archived=true', {}, 15000);
        const sessions = await response.json();
        if (loadEpoch !== archivedSessionsLoadEpoch) return;
        const all = Array.isArray(sessions) ? sessions : [];
        sessionStore.setArchivedLoaded(all);
        syncArchivedSessionStateFromStore();
        renderSessionListIfChanged(!!opts.forceRender);
    } catch (err) {
        console.error('加载归档目录失败:', err);
        if (!opts.background) throw err;
    }
}

async function loadSessions(opts) {
    opts = opts || {};
    const loadEpoch = ++sessionListLoadEpoch;
    sessionStore.ui.loadingSessions = true;
    try {
        let allSessions;
        let snapshot = null;
        
        try {
            snapshot = await fetchSessionsStateSnapshot();
            if (loadEpoch !== sessionListLoadEpoch) return;
            allSessions = Array.isArray(snapshot.sessions) ? snapshot.sessions : [];
        } catch (stateErr) {
            console.error('加载会话状态快照失败，回退旧接口:', stateErr);
            const response = await fetchWithTimeout('/sessions', {}, 12000);
            const archivedCountHeader = response.headers.get('X-Archived-Count');
            if (archivedCountHeader != null && archivedCountHeader !== '') {
                const parsedArchivedCount = Number(archivedCountHeader);
                if (Number.isFinite(parsedArchivedCount) && parsedArchivedCount >= 0) {
                    sessionStore.setArchivedCount(parsedArchivedCount);
                    syncArchivedSessionStateFromStore();
                }
            }
            const sessions = await response.json();
            if (loadEpoch !== sessionListLoadEpoch) return;
            allSessions = Array.isArray(sessions) ? sessions : [];
            snapshot = {
                sessions: allSessions,
                archived_count: archivedSessionsCount,
            };
        }
        applySessionSnapshot(snapshot || { sessions: allSessions, archived_count: archivedSessionsCount });
        syncArchivedSessionStateFromStore();
        allSessions = sessionStore.list();
        
        const idSet = new Set();
        for (let si = 0; si < allSessions.length; si += 1) {
            if (allSessions[si] && allSessions[si].id) idSet.add(allSessions[si].id);
        }
        [...sessionUnreadComplete].forEach(function (uid) {
            if (!idSet.has(uid)) sessionUnreadComplete.delete(uid);
        });
        persistSessionUnread();

        renderSessionListIfChanged(!!opts.forceRender);
        sessionStore.ui.loadingSessions = false;
        if (opts.refreshArchived && !opts.skipArchivedRefresh && sessionStore.archivedLoaded) {
            void loadArchivedSessions({ background: true });
        }
        return;
    } catch (error) {
        sessionStore.ui.loadingSessions = false;
        console.error('加载会话列表失败:', error);
        appendLogVisible('加载会话列表失败', 'error-log');
    }
}

async function reconcileRunStateFromServer(opts) {
    opts = opts || {};
    const suppressedBeforeFetch = new Set();
    if (opts.respectStopSuppress) {
        sessionStore.sessionOrder.forEach(function (sid) {
            if (isSessionStreamStopSuppressed(sid)) suppressedBeforeFetch.add(String(sid));
        });
        if (currentSessionId && isSessionStreamStopSuppressed(currentSessionId)) {
            suppressedBeforeFetch.add(String(currentSessionId));
        }
    }
    let snapshot = null;
    try {
        const cur = currentSessionId ? sessionStore.get(currentSessionId) : null;
        snapshot = await fetchSessionsStateSnapshot({
            includeArchived: !!(sessionStore.archivedLoaded || (cur && cur.archived)),
        });
    } catch (e) {
        if (!opts.silent) console.error('reconcile run state failed:', e);
        return;
    }
    applySessionSnapshot(snapshot);
    if (opts.respectStopSuppress) {
        suppressedBeforeFetch.forEach(function (sid) {
            if (isSessionStreamStopSuppressed(sid)) {
                sessionStore.setStreamActive(sid, false);
                const sess = sessionStore.get(sid);
                if (sess) {
                    sess.stream_active = false;
                    sess.run_active = false;
                    sess.run_started_at = null;
                }
                sessionStore.activeRunInfoBySession.delete(sid);
            }
        });
    }
    const active = new Set();
    sessionStore.activeRunInfoBySession.forEach(function (info, sid) {
        if (info && info.run_active === true) active.add(String(sid));
    });
    const localIds = [];
    sessionStore.runsBySession.forEach(function (_run, sid) {
        localIds.push(String(sid));
    });
    localIds.forEach(function (sid) {
        if (!active.has(sid)) {
            abortSessionRun(sid, 'reconcile-finished');
        }
    });
    if (currentSessionId && active.has(currentSessionId)) {
        const info = sessionStore.getActiveRunInfo(currentSessionId) || {};
        const run = getSessionRunState(currentSessionId);
        const ctx = run && run.ctx;
        const agg = ctx && ctx.currentProcessGroup && ctx.currentProcessGroup.isConnected
            ? ctx.currentProcessGroup
            : (getVisibleChatStream() && getVisibleChatStream().querySelector('.process-aggregate:last-of-type'));
        if (agg && info.started_at) applyRunStartedAtToProcessGroup(agg, info.started_at);
    }
    syncSessionListIndicatorClasses();
    setSendButtonState();
    renderSessionListIfChanged(false);
}

async function loadSessionMessages(sessionId, scrollBehavior, opts) {
    scrollBehavior = scrollBehavior || 'saved-or-bottom';
    opts = opts || {};
    const loadToken = ++messageLoadEpoch;
    sessionStore.ui.loadingMessages = true;
    suppressTocDuringSessionLoad = true;
    replayingMessages = true;
    resetSessionHistoryPaging();
    try {
        let url = '/sessions/' + encodeURIComponent(sessionId) + '/messages';
        if (!opts.full) url += '?turns=' + HISTORY_DIALOGUES_PER_PAGE;
        const response = await fetchWithTimeout(url, {}, 15000);
        if (!response.ok) throw new Error('messages failed: ' + response.status);
        const raw = await response.json();
        if (loadToken !== messageLoadEpoch || sessionId !== currentSessionId) return;
        if (getSessionRunState(sessionId) && !opts.allowDuringRun) return;
        document.getElementById('chat-loading')?.remove();
        if (!getVisibleChatStream()) ensureVisibleChatStreamSlot();
        const vis = getVisibleChatStream();
        if (vis) emptyChatStreamKeepingStrip(vis);
        else {
            chatContainer.innerHTML = '';
            ensureVisibleChatStreamSlot();
        }
        let events;
        let pageMeta = null;
        if (Array.isArray(raw)) {
            events = raw;
        } else if (raw && typeof raw === 'object' && Array.isArray(raw.events)) {
            events = raw.events;
            pageMeta = {
                total: Number(raw.total) || 0,
                range_start: Number(raw.range_start) || 0,
                range_end: Number(raw.range_end) || 0,
                has_older: !!raw.has_older,
            };
            uiEventCountCache.updateFromServer(sessionId, pageMeta.total);
        } else {
            events = [];
        }
        beginMessageReplay(sessionId, pageMeta || {
            total: events.length,
            range_start: 0,
            range_end: events.length,
        });
        if (!opts.full && pageMeta) {
            setSessionHistoryPaging({
                sessionId: sessionId,
                total: pageMeta.total,
                range_start: pageMeta.range_start,
                range_end: pageMeta.range_end,
                has_older: !!pageMeta.has_older,
            });
            ensureHistorySentinel(getVisibleChatStream());
        }
        if (events.length === 0) {
            suppressTocDuringSessionLoad = false;
            setWelcome();
            updateSessionTitle();
            scheduleContextTokensAfterPaint(sessionId);
            applyChatScrollAfterHistoryLoad(sessionId, scrollBehavior);
            return;
        }
        const loadCtx = newDomContext(getVisibleChatStream());
        loadCtx.lastUserEventIndex = -1;
        const indexBase = pageMeta ? pageMeta.range_start : 0;
        const batchSize = opts.full ? 64 : 512;
        for (let evi = 0; evi < events.length; evi += 1) {
            const ev = events[evi];
            if (ev && typeof ev === 'object' && ev.type) {
                reduceAndRenderMessageEvent(loadCtx, ev, {
                    sessionId: sessionId,
                    eventIndex: indexBase + evi,
                    source: 'history',
                });
            }
            if (evi > 0 && evi % batchSize === 0) {
                await new Promise(function (resolve) { setTimeout(resolve, 0); });
                if (loadToken !== messageLoadEpoch || sessionId !== currentSessionId) return;
            }
        }
        if (!opts.full && opts.preloadOlderIfShort && pageMeta && pageMeta.has_older && events.length <= 2) {
            await loadOlderHistoryChunk({ keepTocStable: true });
            if (loadToken !== messageLoadEpoch || sessionId !== currentSessionId) return;
        }
        if (historyLoadScrollsToBottom(sessionId, scrollBehavior)) {
            tocScrollBottomOnNextBuild = true;
        }
        suppressTocDuringSessionLoad = false;
        rebuildToc();
        updateSessionTitle();
        updateHistorySentinelVisibility();
        applyChatScrollAfterHistoryLoad(sessionId, scrollBehavior);
        await waitForChatScrollAfterHistoryLoad(sessionId, scrollBehavior);
        if (loadToken !== messageLoadEpoch || sessionId !== currentSessionId) return;
        bindExistingLogs();
        scheduleTocActiveUpdate();
        scheduleContextTokensAfterPaint(sessionId);
        renderTodoPlanForCurrentSession();
    } catch (error) {
        console.error('加载会话消息失败:', error);
        document.getElementById('chat-loading')?.remove();
        appendLogVisible('加载历史消息失败', 'error-log');
    } finally {
        if (loadToken === messageLoadEpoch) sessionStore.ui.loadingMessages = false;
        if (loadToken === messageLoadEpoch) suppressTocDuringSessionLoad = false;
        if (loadToken === messageLoadEpoch) replayingMessages = false;
    }
}

async function switchSession(sessionId) {
    if (currentSessionId === sessionId) return;
    const switchToken = ++switchSessionEpoch;
    suppressTocDuringSessionLoad = true;
    clearTocForSessionLoad();
    clearTodoForSessionLoad();
    pendingRewriteTruncate = null;
    hideRewriteUndoToast();
    clearSessionUnreadState(sessionId);
    const leaving = currentSessionId;
    saveChatScrollForSession(leaving);
    stashInputDraft(leaving);
    prepareStashLeaving(leaving);
    hideSubagentContinueBanner();
    resetSubagentPanelForSession();
    setCurrentSessionState(sessionId);
    localStorage.setItem('lastSessionId', sessionId);
    restoreInputDraft(sessionId);
    if (typeof renderFollowupQueue === 'function') renderFollowupQueue(sessionId);
    if (typeof refreshModelProfileSelector === 'function') refreshModelProfileSelector(sessionId);
    syncSessionListIndicatorClasses();
    setSendButtonState();
    if (restoreStreamForRunningSession(sessionId)) {
        suppressTocDuringSessionLoad = false;
        hideLoading();
        rebuildToc();
        updateSessionTitle();
        scheduleContextTokensAfterPaint(sessionId);
        applyChatScrollAfterHistoryLoad(sessionId, 'saved-or-bottom');
        renderTodoPlanForCurrentSession();
        if (switchToken !== switchSessionEpoch || sessionId !== currentSessionId) return;
        /* 让 rebuildToc 的 /user_turns fetch 先发出，subagent 面板（含 N 个 /messages）延后一帧
           避免抢占带宽与主线程，导致目录最后才就绪。 */
        setTimeout(function () { refreshSubagentTreePanel(sessionId); }, 0);
        void refreshSingleSessionRow(sessionId);
        setSendButtonState();
        maybeStartStreamPollForSession(sessionId, { skipInitialLoad: true });
        return;
    }
    const vs = getVisibleChatStream();
    resetSessionHistoryPaging();
    if (vs) emptyChatStreamKeepingStrip(vs);
    else {
        chatContainer.innerHTML = '';
        ensureVisibleChatStreamSlot();
    }
    showLoading();
    setTimeout(async () => {
        if (switchToken !== switchSessionEpoch || sessionId !== currentSessionId) return;
        try {
            await loadSessionMessages(sessionId, undefined, {
                preloadOlderIfShort: isServerStreamActive(sessionId),
                allowDuringRun: isServerStreamActive(sessionId),
            });
        } catch (error) {
            console.error('切换会话加载失败:', error);
        } finally {
            if (switchToken === switchSessionEpoch && sessionId === currentSessionId) {
                hideLoading();
                sessionStore.ui.loadingMessages = false;
                suppressTocDuringSessionLoad = false;
                replayingMessages = false;
            }
        }
        if (switchToken !== switchSessionEpoch || sessionId !== currentSessionId) return;
        /* loadSessionMessages 内部已发起 rebuildToc()；这里再延后一帧调用 subagent panel
           保证「目录 → 消息 → 子 agent 按钮」的稳定顺序（无 subagent 的会话表现一致）。 */
        setTimeout(function () { refreshSubagentTreePanel(sessionId); }, 0);
        void refreshSingleSessionRow(sessionId);
        setSendButtonState();
        maybeStartStreamPollForSession(sessionId, { skipInitialLoad: true });
    }, 20);
}

async function createNewSession() {
    createNewSessionQueue = createNewSessionQueue.then(
        function () { return createNewSessionInner(); },
        function () { return createNewSessionInner(); }
    );
    return createNewSessionQueue;
}

async function createNewSessionInner() {
    try {
        saveChatScrollForSession(currentSessionId);
        stashInputDraft(currentSessionId);
        prepareStashLeaving(currentSessionId);
        const response = await fetch('/sessions', { method: 'POST' });
        const data = await response.json();
        if (data && data.session) sessionStore.upsert(data.session);
        resetSubagentPanelForSession();
        switchSessionEpoch += 1;
        messageLoadEpoch += 1;
        setCurrentSessionState(data.session_id);
        localStorage.setItem('lastSessionId', currentSessionId);
        restoreInputDraft(currentSessionId);
        if (typeof renderFollowupQueue === 'function') renderFollowupQueue(currentSessionId);
        if (typeof refreshModelProfileSelector === 'function') refreshModelProfileSelector(currentSessionId);
        if (!getVisibleChatStream()) ensureVisibleChatStreamSlot();
        setWelcome();
        replayingMessages = false;
        if (data && data.session) {
            syncArchivedSessionStateFromStore();
            renderSessionListIfChanged(true);
            void refreshSingleSessionRow(data.session_id);
        } else {
            await loadSessions();
        }
        setSendButtonState();
        maybeStartStreamPollForSession(currentSessionId);
        scheduleContextTokensAfterPaint(currentSessionId);
    } catch (error) {
        console.error('创建新会话失败:', error);
        appendLogVisible('创建新会话失败', 'error-log');
    }
}
`,We=`async function consumeAgentSseResponse(response, runCtx, runSessionId, streamEventIdx) {
    if (!response || !response.body) throw new Error('stream response missing body');
    var ct0 = (response.headers && response.headers.get ? (response.headers.get('content-type') || '') : '').toLowerCase();
    if (!response.ok || ct0.indexOf('text/event-stream') < 0) {
        throw new Error('stream response failed: ' + (response.status || 'no status'));
    }
    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = '';
    while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\\n');
        buffer = lines.pop();
        for (const line of lines) {
            if (!line.startsWith('data: ')) continue;
            const data = line.slice(6);
            if (data === '[DONE]') {
                finalizeLlmStreamChunks(runCtx);
                finalizeProgressStreamChunks(runCtx);
                await ensureFinalVisibleAfterRun(runSessionId, runCtx, { delayMs: 80 });
                streamEventIdx = await reconcileProjectedMessagesAfter(runSessionId, runCtx, streamEventIdx - 1);
                sealProcessGroup(runCtx);
                markSessionRunInactive(runSessionId);
                if (getSessionRunState(runSessionId)) clearSessionRunState(runSessionId);
                syncSessionListIndicatorClasses();
                setSendButtonState();
                if (runSessionId === currentSessionId) renderTodoPlanForCurrentSession();
                scheduleFollowupQueueDrain(runSessionId, 0);
                if (liveAutoFollow) {
                    scrollProcessBodyToBottom(runCtx, runSessionId);
                    scrollChatToBottomIfFollow(runSessionId, {});
                }
                return streamEventIdx;
            }
            try {
                let parsed = JSON.parse(data);
                if (parsed && parsed.protocol === 'runtime_v2') {
                    const envelopeSessionId = parsed.session_id || parsed.sessionId || runSessionId;
                    if (!sessionStore.shouldAcceptSseEvent(envelopeSessionId, parsed.seq)) continue;
                    if (parsed.skip_ui) continue;
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
                if (parsed.protocol !== 'runtime_v2' && !sessionStore.shouldAcceptSseEvent(eventSessionId, parsed.seq)) continue;
                if (parsed.type === 'user_steer' && parsed.steer) {
                    var steerEventIndex = parsed.ephemeral && Number.isFinite(Number(parsed.seq)) ? Number(parsed.seq) : streamEventIdx;
                    try {
                        applyMessageEvent(eventSessionId, parsed, steerEventIndex, 'sse');
                    } catch (eStoreSteer) {
                        console.error('store user steer event failed:', eStoreSteer);
                    }
                    removeConsumedFollowupSteer(eventSessionId, parsed);
                    appendLog(runCtx, parsed.content || '', 'user-steer', runSessionId);
                    streamEventIdx += 1;
                    continue;
                }
                const reduced = applySessionEvent(parsed, {
                    sessionId: eventSessionId,
                    eventIndex: parsed.ephemeral && Number.isFinite(Number(parsed.seq)) ? Number(parsed.seq) : streamEventIdx,
                    source: 'sse',
                });
                if (reduced.runStateChanged) {
                    if (parsed.type === 'run_finished' || parsed.type === 'run_interrupted' || parsed.type === 'run_failed') {
                        finalizeLlmStreamChunks(runCtx);
                        finalizeProgressStreamChunks(runCtx);
                        if (parsed.type === 'run_finished') {
                            await ensureFinalVisibleAfterRun(eventSessionId, runCtx, { delayMs: 80 });
                        }
                        sealProcessGroup(runCtx);
                        if (eventSessionId === runSessionId && getSessionRunState(runSessionId)) {
                            clearSessionRunState(runSessionId);
                        }
                        syncSessionListIndicatorClasses();
                        setSendButtonState();
                        if (eventSessionId === runSessionId) scheduleFollowupQueueDrain(runSessionId, 0);
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
                        discardLlmStreamChunks(runCtx, parsed);
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
                        finalizeLlmStreamChunks(runCtx);
                        removeTemporaryStatus(runCtx);
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
                    else if (parsed.type === 'context_tokens') applyContextTokenLabelForCurrentSession();
                    else if (parsed.type === 'cache_stats' && runSessionId === currentSessionId) applyCacheStatsFromEvent(runCtx, parsed);
                    else if (parsed.type === 'todo_plan' && runSessionId === currentSessionId) renderTodoPlanForCurrentSession();
                    else if (parsed.type === 'status') {
                        var statusContent = String(parsed.content || '');
                        var isTemporaryStatus = statusContent.indexOf('正在思考中...') >= 0;
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
                    streamEventIdx += 1;
                    continue;
                }
                renderMessageRecord(runCtx, reduced.messageRecord || {
                    index: streamEventIdx,
                    event: parsed,
                    source: 'sse',
                }, runSessionId);
                if (parsed.type === 'final' && eventSessionId === runSessionId) {
                    finalizeLlmStreamChunks(runCtx);
                    finalizeProgressStreamChunks(runCtx);
                    markSessionRunInactive(runSessionId);
                    if (getSessionRunState(runSessionId)) clearSessionRunState(runSessionId);
                    syncSessionListIndicatorClasses();
                    setSendButtonState();
                    scheduleFollowupQueueDrain(runSessionId, 250);
                }
                streamEventIdx += 1;
            } catch (e) { console.error('解析事件失败:', e); }
        }
    }
    await ensureFinalVisibleAfterRun(runSessionId, runCtx, { delayMs: 120 });
    streamEventIdx = await reconcileProjectedMessagesAfter(runSessionId, runCtx, streamEventIdx - 1);
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
        var renderCtx = ctx || newDomContext(stream);
        renderCtx.stream = stream;
        renderCtx.lastUserEventIndex = Math.max(renderCtx.lastUserEventIndex || -1, lastUserIdx);
        renderMessageRecord(renderCtx, storedFinal, sid);
        if (hasVisibleFinalAfterUser(stream, lastUserIdx)) return true;
    }
    var delayMs = Math.max(0, Number(opts.delayMs) || 0);
    if (delayMs) await new Promise(function (resolve) { setTimeout(resolve, delayMs); });
    if (sid !== currentSessionId) return false;
    stream = getVisibleChatStream();
    if (!stream || hasVisibleFinalAfterUser(stream, lastUserIdx)) return true;
    try {
        await loadSessionMessages(sid, 'bottom', { full: true });
        return true;
    } catch (e) {
        console.error('final visibility reconcile failed:', e);
        return false;
    }
}

async function reconcileProjectedMessagesAfter(sessionId, ctx, afterIndex) {
    var sid = String(sessionId || '');
    var idx = Number(afterIndex);
    if (!sid || !Number.isFinite(idx)) return Number.isFinite(idx) ? idx + 1 : 0;
    var nextIndex = Math.max(0, Math.floor(idx) + 1);
    var renderCtx = ctx || null;
    var pageAfter = Math.floor(idx);
    var safety = 0;
    while (safety < 6) {
        safety += 1;
        try {
            var url = '/sessions/' + encodeURIComponent(sid)
                + '/messages?after_index=' + encodeURIComponent(String(pageAfter))
                + '&limit=500';
            var response = await fetch(url);
            var data = await response.json().catch(function () { return null; });
            if (!response.ok || !data || typeof data !== 'object') break;
            var events = Array.isArray(data.events) ? data.events : [];
            var rangeStart = Number.isFinite(Number(data.range_start)) ? Math.floor(Number(data.range_start)) : (pageAfter + 1);
            for (var i = 0; i < events.length; i += 1) {
                var ev = events[i];
                var eventIndex = rangeStart + i;
                nextIndex = Math.max(nextIndex, eventIndex + 1);
                if (!ev || typeof ev !== 'object' || !ev.type) continue;
                var existing = selectMessageEventsInRange(sid, eventIndex, eventIndex + 1);
                if (existing && existing.length) continue;
                if (!renderCtx) {
                    var stream = sid === currentSessionId ? getVisibleChatStream() : null;
                    if (stream) renderCtx = newDomContext(stream);
                }
                if (renderCtx && renderCtx.stream && renderCtx.stream.isConnected) {
                    reduceAndRenderMessageEvent(renderCtx, ev, {
                        sessionId: sid,
                        eventIndex: eventIndex,
                        source: 'projected-reconcile',
                    });
                } else {
                    applySessionEvent(ev, {
                        sessionId: sid,
                        eventIndex: eventIndex,
                        source: 'projected-reconcile',
                    });
                }
            }
            if (!data.has_newer || !events.length) break;
            pageAfter = nextIndex - 1;
        } catch (e) {
            console.error('projected message reconcile failed:', e);
            break;
        }
    }
    return nextIndex;
}

async function startContinueAfterSubagents(sessionId) {
    if (!sessionId || sessionId !== currentSessionId) return;
    delete subagentContinueDismissedForSession[sessionId];
    if (isSessionRunning(sessionId) || subagentContinueInFlight) {
        updateSubagentContinueBanner(sessionId);
        return;
    }
    if (sendPipelineLock && sendPipelineLockSessionId === sessionId) {
        updateSubagentContinueBanner(sessionId);
        return;
    }
    hideSubagentContinueBanner();
    subagentContinueInFlight = true;
    var runCtx = null;
    var runSessionId = sessionId;
    try {
    var banner = document.getElementById('subagent-continue-banner');
    var continueMode = banner && banner.dataset && banner.dataset.continueMode === 'react' ? 'react' : 'subagents';
    var continueUrl = continueMode === 'react'
        ? '/sessions/' + encodeURIComponent(sessionId) + '/continue'
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
        const preCount = await getUiEventCount();
        if (!getVisibleChatStream()) ensureVisibleChatStreamSlot();
        runCtx = newDomContext(getVisibleChatStream());
        runCtx.runStartedAt = new Date().toISOString();
        if (getSessionRunState(runSessionId) && getSessionRunState(runSessionId).ctx) {
            runCtx = getSessionRunState(runSessionId).ctx;
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
                console.error('续接 subagent 失败:', error);
                const msg = (error && error.message) ? String(error.message) : String(error);
                appendLog(runCtx, '续接失败: ' + msg, 'error-log', runSessionId);
            }
        } finally {
            finalizeLlmStreamChunks(runCtx);
            finalizeProgressStreamChunks(runCtx);
            if (runSessionId === currentSessionId && getRunAbortReason(runSessionId, runCtx) !== 'user') {
                await ensureFinalVisibleAfterRun(runSessionId, runCtx, { delayMs: 120 });
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
        }
        hideSubagentContinueBanner();
        if (!subagentContinueDismissedForSession[sessionId]) updateSubagentContinueBanner(sessionId);
    } finally {
        subagentContinueInFlight = false;
    }
}

async function attachSessionEventStream(sessionId, opts) {
    opts = opts || {};
    if (!sessionId || getSessionRunState(sessionId)) return;
    if (!isServerStreamActive(sessionId)) return;
    var runSessionId = sessionId;
    var runCtx = null;
    try {
        if (runSessionId !== currentSessionId) return;
        if (!opts.skipInitialLoad) {
            await loadSessionMessages(runSessionId, 'saved-or-bottom', { preloadOlderIfShort: true });
            if (runSessionId !== currentSessionId) return;
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
        finalizeLlmStreamChunks(runCtx);
        const ac = new AbortController();
        setSessionRunState(runSessionId, { controller: ac, ctx: runCtx, reattached: true });
        setSendButtonState();
        syncSessionListIndicatorClasses();
        liveAutoFollow = true;
        streamProcNearBottom = true;
        const preCount = await getUiEventCount(runSessionId);
        const streamUrl = '/sessions/' + encodeURIComponent(runSessionId)
            + '/stream?after_index=' + encodeURIComponent(String(preCount - 1));
        const response = await fetch(streamUrl, { signal: ac.signal });
        await consumeAgentSseResponse(response, runCtx, runSessionId, preCount);
    } catch (error) {
        if (error && error.name === 'AbortError') return;
        console.error('reattach stream failed:', error);
        const msg = (error && error.message) ? String(error.message) : String(error);
        if (runCtx && runSessionId === currentSessionId) appendLog(runCtx, '恢复实时流失败: ' + msg, 'error-log', runSessionId);
    } finally {
        if (runCtx) {
            finalizeLlmStreamChunks(runCtx);
            finalizeProgressStreamChunks(runCtx);
        }
        if (runSessionId === currentSessionId && getRunAbortReason(runSessionId, runCtx) !== 'user') {
            await ensureFinalVisibleAfterRun(runSessionId, runCtx, { delayMs: 120 });
        }
        if (getSessionRunState(runSessionId) && getSessionRunState(runSessionId).reattached) {
            clearSessionRunState(runSessionId);
        }
        setSendButtonState();
        syncSessionListIndicatorClasses();
        void refreshSingleSessionRow(runSessionId);
        setTimeout(function () { reconcileRunStateFromServer({ silent: true }); }, 800);
        applyContextTokenLabelForCurrentSession();
        if (runSessionId === currentSessionId) {
            clearSessionUnreadState(runSessionId);
            updateSubagentContinueBanner(runSessionId);
        }
    }
}

async function processRewriteTruncateAsync(pr) {
    try {
        const anchor = document.querySelector('.msg-wrap--user[data-truncate-from="' + String(pr.before) + '"]');
        const res = await truncateSessionOnServer(pr.before, { sessionId: pr.sessionId, backup: false });
        if (!res || !res.ok) {
            showUiAlert({
                title: '截断失败',
                message: describeServerSyncFailure(res, '无法同步服务器，改写未生效。'),
                variant: 'error'
            });
            return false;
        }
        if (currentSessionId === pr.sessionId) {
            scheduleContextTokensAfterPaint(pr.sessionId);
            if (anchor) {
                removeMessagesFromNode(anchor);
                if (activeInlineRewriteWrap === anchor) activeInlineRewriteWrap = null;
                syncDisconnectedProcessGroups();
                rebuildToc();
            }
        }
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

function normalizeStoredFollowupItem(item) {
    if (!item || typeof item !== 'object') return null;
    var text = String(item.text || '').trim();
    if (!text) return null;
    var display = String(item.display || item.text || '').trim();
    return {
        id: item.id || ('stored-followup-' + (followupQueueSeq++)),
        text: text,
        display: display || text,
        createdAt: Number(item.createdAt) || Date.now(),
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
    var pending = q.filter(function (item) {
        var status = item && item.status ? String(item.status) : '';
        return item && item.text && !status;
    }).map(function (item) {
        return {
            id: item.id,
            text: item.text,
            display: item.display || item.text,
            createdAt: item.createdAt || Date.now(),
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
    try { localStorage.removeItem(followupQueueStorageKey(sid)); } catch (e) { /* ignore */ }
}

function inputHasSendableText() {
    if (!messageInput) return false;
    return String(messageInput.value || '').replace(/[\\u200B-\\u200D\\uFEFF]/g, '').trim().length > 0;
}

function ensureFollowupQueueHost() {
    var existing = document.getElementById('followup-queue-panel');
    if (existing) return existing;
    var panel = document.createElement('div');
    panel.id = 'followup-queue-panel';
    panel.className = 'followup-queue-panel';
    panel.setAttribute('aria-live', 'polite');
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
    panel.innerHTML = '';
    panel.dataset.sessionId = sid;
    panel.classList.toggle('is-visible', !!q.length);
    if (!q.length) {
        positionFollowupQueuePanel();
        return;
    }
    q.forEach(function (item, idx) {
        var row = document.createElement('div');
        row.className = 'followup-queue-row';
        row.classList.toggle('is-sending', item.status === 'sending' || item.status === 'submitting');
        row.classList.toggle('is-accepted', item.status === 'accepted');
        row.classList.toggle('is-sent', item.status === 'sent');
        row.dataset.id = String(item.id);
        var order = document.createElement('div');
        order.className = 'followup-queue-order';
        order.textContent = String(idx + 1);
        var text = document.createElement('div');
        text.className = 'followup-queue-text';
        text.textContent = item.display || item.text || '';
        var status = document.createElement('div');
        status.className = 'followup-queue-status';
        status.textContent = getFollowupStatusText(item);
        var sendNow = document.createElement('button');
        sendNow.type = 'button';
        sendNow.className = 'followup-queue-action followup-queue-send';
        sendNow.textContent = '立即发送';
        sendNow.disabled = !!item.status;
        var undo = document.createElement('button');
        undo.type = 'button';
        undo.className = 'followup-queue-action followup-queue-undo';
        undo.textContent = '撤回';
        undo.disabled = item.status === 'sent' || item.status === 'withdrawing';
        sendNow.addEventListener('click', function (ev) {
            ev.preventDefault();
            sendFollowupNow(String(item.id));
        });
        undo.addEventListener('click', function (ev) {
            ev.preventDefault();
            withdrawFollowup(String(item.id));
        });
        row.appendChild(order);
        row.appendChild(text);
        row.appendChild(status);
        row.appendChild(sendNow);
        row.appendChild(undo);
        panel.appendChild(row);
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
    if (status === 'accepted') return '已接收，等待插入';
    if (status === 'sending') return '发送中';
    if (status === 'sent') return '已发送';
    return '待发送';
}

function enqueueCurrentInputAsFollowup() {
    const sid = currentSessionId;
    if (!sid) return false;
    rewriteInputWorkspacePaths();
    const visibleMessage = messageInput.value;
    const rawMessage = expandInputPathTokens(visibleMessage);
    if (!String(rawMessage).trim()) return false;
    getFollowupQueue(sid).push({
        id: followupQueueSeq++,
        text: rawMessage,
        display: visibleMessage,
        createdAt: Date.now(),
    });
    persistFollowupQueue(sid);
    messageInput.value = '';
    persistInputDraft(sid, '');
    clearInputPathTokens();
    autoResizeTextarea();
    renderFollowupQueue(sid);
    setSendButtonState();
    return true;
}

function takeFollowupItem(sessionId, itemId) {
    var q = getFollowupQueue(sessionId);
    var idx = q.findIndex(function (item) { return String(item.id) === String(itemId); });
    if (idx < 0) return null;
    var item = q.splice(idx, 1)[0] || null;
    persistFollowupQueue(sessionId);
    return item;
}

function withdrawFollowup(itemId) {
    const sid = currentSessionId;
    var q = getFollowupQueue(sid);
    var pendingItem = q.find(function (entry) { return String(entry.id) === String(itemId); });
    if (pendingItem && (pendingItem.status === 'sending' || pendingItem.status === 'submitting' || pendingItem.status === 'accepted')) {
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
    const existing = String(messageInput.value || '');
    const returned = String(item.display || item.text || '');
    messageInput.value = existing.trim() ? (returned + '\\n' + existing) : returned;
    rewriteInputWorkspacePaths();
    persistInputDraft(sid, messageInput.value);
    autoResizeTextarea();
    renderFollowupQueue(sid);
    setSendButtonState();
    messageInput.focus();
}

async function sendSteerMessage(sessionId, text, clientId) {
    var r = await fetch('/sessions/' + encodeURIComponent(sessionId) + '/steer', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: text, client_id: clientId || '' }),
    });
    var j = await r.json().catch(function () {
        return { ok: false, error: 'steer failed' };
    });
    if (!r.ok || !j.ok) throw new Error((j && j.error) || 'steer failed');
    return j;
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
    return true;
}

function scheduleFollowupQueueDrain(sessionId, delayMs) {
    const sid = String(sessionId || '');
    if (!sid) return;
    setTimeout(function () { drainFollowupQueue(sid); }, Math.max(0, Number(delayMs) || 0));
}

async function sendFollowupNow(itemId) {
    const sid = currentSessionId;
    if (!sid) return;
    var q = getFollowupQueue(sid);
    var idx = q.findIndex(function (item) { return String(item.id) === String(itemId); });
    if (idx < 0) return;
    const item = q[idx];
    if (!item) return;
    item.clientId = item.clientId || ('followup-' + item.id + '-' + Date.now());
    item.status = 'submitting';
    persistFollowupQueue(sid);
    renderFollowupQueue(sid);
    try {
        item.steerInFlight = true;
        var steerResult = await sendSteerMessage(sid, item.text, item.clientId);
        item.steerInFlight = false;
        item.steerId = steerResult && steerResult.item && steerResult.item.id ? String(steerResult.item.id) : '';
        if (item.cancelRequested) {
            await cancelSteerMessage(sid, item);
            var withdrawn = takeFollowupItem(sid, item.id);
            if (withdrawn) returnFollowupToInput(sid, withdrawn);
            return;
        }
        item.status = 'accepted';
        persistFollowupQueue(sid);
        renderFollowupQueue(sid);
        return;
    } catch (e) {
        item.steerInFlight = false;
        var msg = (e && e.message) ? String(e.message) : String(e);
        var canFallbackToChat = /session is not running/i.test(msg);
        if (!canFallbackToChat) {
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
    item.status = 'sent';
    persistFollowupQueue(sid);
    renderFollowupQueue(sid);
    setTimeout(function () {
        takeFollowupItem(sid, itemId);
        renderFollowupQueue(sid);
    }, 1200);
    return sendMessage({ message: item.text, fromQueue: true });
}

function drainFollowupQueue(sessionId) {
    const sid = String(sessionId || '');
    if (!sid || followupQueueDraining[sid]) return;
    if (isSessionRunning(sid) || (sendPipelineLock && sendPipelineLockSessionId === sid)) return;
    var q = getFollowupQueue(sid);
    if (!q.length) {
        renderFollowupQueue(sid);
        return;
    }
    var nextIdx = q.findIndex(function (item) { return !item.status; });
    if (nextIdx < 0) {
        renderFollowupQueue(sid);
        return;
    }
    var item = q[nextIdx];
    followupQueueDraining[sid] = true;
    var attemptedId = String(item.id);
    Promise.resolve(sendFollowupNow(item.id))
        .finally(function () {
            delete followupQueueDraining[sid];
            var q2 = getFollowupQueue(sid);
            var same = q2.find(function (entry) { return String(entry.id) === attemptedId; });
            if (same && same.status && same.status !== 'sent') return;
            if (same && !same.status) return;
            if (q2.some(function (entry) { return !entry.status; })) {
                scheduleFollowupQueueDrain(sid, 0);
            }
        });
}

async function sendMessage(options) {
    options = options || {};
    messageLoadEpoch += 1;
    /* 立即快照「提交会话」：之后所有 await 都不能改变它，避免用户在 await 空隙切走后消息发到新会话。
       关键不变式：runSessionId === submitSessionId 全程恒等。 */
    const submitSessionIdInitial = options.sessionId || currentSessionId;
    if (!options.fromQueue && !options.fromInlineRewrite) rewriteInputWorkspacePaths();
    const visibleMessage = options.message != null ? String(options.message) : messageInput.value;
    const rawMessage = (options.fromQueue || options.fromInlineRewrite) ? visibleMessage : expandInputPathTokens(visibleMessage);
    if (!String(rawMessage).trim()) return;
    if (isSessionRunning(submitSessionIdInitial)) return;
    if (sendPipelineLock && sendPipelineLockSessionId === submitSessionIdInitial) return;

    /* 立即上锁：阻止后续连击；锁的 key 是提交时的会话，而非当前会话。 */
    sendPipelineLock = true;
    sendPipelineLockSessionId = submitSessionIdInitial;
    let submittedRunCtx = null;
    let submittedRunSessionId = submitSessionIdInitial;
    try {

    if (pendingRewriteTruncate && pendingRewriteTruncate.sessionId === submitSessionIdInitial) {
        const pendingRewrite = pendingRewriteTruncate;
        const truncated = await processRewriteTruncateAsync(pendingRewrite);
        if (!truncated) {
            pendingRewriteTruncate = null;
            return;
        }
        pendingRewriteTruncate = null;
        uiEventCountCache.updateFromServer(submitSessionIdInitial, pendingRewrite.before);
    }
    hideRewriteUndoToast();

    hideSubagentContinueBanner();
    const userSentAt = new Date().toISOString();

    let submitSessionId = submitSessionIdInitial;
    if (!submitSessionId) {
        await createNewSession();
        submitSessionId = currentSessionId;
        if (!submitSessionId) return;
        sendPipelineLockSessionId = submitSessionId;
    }
    // 使用缓存的事件计数，实现乐观更新
    let preCount = uiEventCountCache.get(submitSessionId);
    try {
        const serverCountBeforeSend = preCount;
        if (Number.isFinite(Number(serverCountBeforeSend))) {
            preCount = Math.max(preCount, Number(serverCountBeforeSend));
            uiEventCountCache.updateFromServer(submitSessionId, preCount);
        }
    } catch (err) {
        console.error('获取事件计数失败:', err);
    }
    const existingStreamForIndex = (submitSessionId === currentSessionId) ? getVisibleChatStream() : null;
    if (existingStreamForIndex) {
        existingStreamForIndex.querySelectorAll('.msg-wrap--user[data-event-index]').forEach(function (wrap) {
            const n = Number(wrap.getAttribute('data-event-index'));
            if (Number.isFinite(n)) preCount = Math.max(preCount, Math.floor(n) + 1);
        });
    }
    const runSessionId = submitSessionId;
    submittedRunSessionId = runSessionId;
    if (sessionStore && typeof sessionStore.resetSseSeq === 'function') {
        sessionStore.resetSseSeq(runSessionId);
    }
    const clientRunId = (window.crypto && window.crypto.randomUUID)
        ? window.crypto.randomUUID()
        : ('run-' + Date.now() + '-' + Math.random().toString(16).slice(2));

    /* 用户在 createNewSession / getUiEventCount 期间切走：
       后台仍然发起 /chat（消息已属于 runSessionId），但不要往当前可见 stream 画用户气泡。 */
    const switchedAway = currentSessionId !== runSessionId;
    let runCtx;
    if (switchedAway) {
        const offscreen = document.createElement('div');
        offscreen.className = 'chat-stream is-offscreen';
        if (typeof offscreenRoot !== 'undefined' && offscreenRoot) offscreenRoot.appendChild(offscreen);
        runCtx = newDomContext(offscreen);
    } else {
        if (!getVisibleChatStream()) ensureVisibleChatStreamSlot();
        runCtx = newDomContext(getVisibleChatStream());
    }
    submittedRunCtx = runCtx;
    runCtx.runStartedAt = userSentAt;
    runCtx.lastUserEventIndex = preCount;
    resetLlmState(runCtx);
    finalizeLlmStreamChunks(runCtx);
    sealProcessGroup(runCtx);
    const ac = new AbortController();
    if (typeof clearSessionStreamStopSuppress === 'function') clearSessionStreamStopSuppress(runSessionId);
    setSessionRunState(runSessionId, { controller: ac, ctx: runCtx, runId: clientRunId });
    setSendButtonState();
    syncSessionListIndicatorClasses();
    applySessionEvent({ type: 'user', content: rawMessage, created_at: userSentAt }, {
        sessionId: runSessionId,
        eventIndex: preCount,
        source: 'local-send',
    });
        if (!switchedAway) {
        liveAutoFollow = true;
        streamChatNearBottom = true;
        streamProcNearBottom = true;
        appendMessage(runCtx, 'user', rawMessage, { eventIndex: preCount, turnTruncateIdx: preCount, createdAt: userSentAt }, runSessionId);
        if (!options.fromQueue && !options.preserveInput) {
            messageInput.value = '';
            persistInputDraft(runSessionId, '');
            clearInputPathTokens();
            autoResizeTextarea();
            setSendButtonState();
        }
    }
    updateSidebarLastUserPreviewImmediate(runSessionId, rawMessage);
    lastUserMessageBySession[runSessionId] = rawMessage;
    const formData = new FormData();
    formData.append('message', rawMessage);
    formData.append('session_id', runSessionId);
    formData.append('client_run_id', clientRunId);
    formData.append('stream_protocol', 'runtime_v2');
    /* 保留右上角 token 进度条上一快照，直至 SSE /context_tokens 推送新估值，避免每次发送闪零 */
    if (!switchedAway) scheduleContextTokensAfterPaint(runSessionId);
    let streamEventIdx = preCount + 1;
    
    // 异步更新事件计数缓存（从服务器获取真实计数）
    getUiEventCount(submitSessionId).then(function(serverCount) {
        uiEventCountCache.updateFromServer(submitSessionId, serverCount);
    }).catch(function(err) {
        console.error('更新事件计数缓存失败:', err);
    });
    try {
        const response = await fetch('/chat', { method: 'POST', body: formData, signal: ac.signal });
        streamEventIdx = await consumeAgentSseResponse(response, runCtx, runSessionId, streamEventIdx);
    } catch (error) {
        if (error.name === 'AbortError') {
            if (getRunAbortReason(runSessionId, runCtx) === 'user') appendLog(runCtx, '任务已中断', 'status', runSessionId);
        }
        else {
            console.error('请求失败:', error);
            const msg = (error && error.message) ? String(error.message) : String(error);
            appendLog(runCtx, '请求失败: ' + msg, 'error-log', runSessionId);
        }
    } finally {
        finalizeLlmStreamChunks(runCtx);
        finalizeProgressStreamChunks(runCtx);
        if (!switchedAway && runSessionId === currentSessionId && getRunAbortReason(runSessionId, runCtx) !== 'user') {
            await ensureFinalVisibleAfterRun(runSessionId, runCtx, { delayMs: 120 });
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
            clearSessionRunState(runSessionId);
        }
        if (runSessionId !== currentSessionId) {
            const el = runCtx.stream;
            if (el && el.parentNode) el.remove();
        }
        setSendButtonState();
        syncSessionListIndicatorClasses();
        void refreshSingleSessionRow(runSessionId);
        applyContextTokenLabelForCurrentSession();
        if (runSessionId === currentSessionId && countRunningSubagentCards() > 0) {
            scheduleSubagentIncrementalSync();
        }
    }
    } finally {
        sendPipelineLock = false;
        sendPipelineLockSessionId = null;
        var stoppedByUser = getRunAbortReason(submittedRunSessionId, submittedRunCtx) === 'user';
        if (!stoppedByUser && (!options.fromQueue || getFollowupQueue(submittedRunSessionId).length)) {
            setTimeout(function () { drainFollowupQueue(submittedRunSessionId); }, 0);
        }
    }
}

messageInput.addEventListener('keydown', function onFollowupInputKeydown(e) {
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
    e.preventDefault();
    if (isSessionRunning(currentSessionId)) {
        enqueueCurrentInputAsFollowup();
        return;
    }
    sendMessage();
}, true);

messageInput.addEventListener('keydown', function onInputKeydown(e) {
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
    // 纯 Enter → 发送
    if (isSessionRunning(currentSessionId)) return;
    e.preventDefault();
    sendMessage();
});
chatContainer.addEventListener('scroll', function () {
    refreshLiveAutoFollowPins();
    scheduleTocActiveUpdate();
}, { passive: true });
sendBtn.addEventListener('click', function (e) {
    e.stopImmediatePropagation();
    if (isSessionRunning(currentSessionId)) {
        if (inputHasSendableText()) enqueueCurrentInputAsFollowup();
        else pauseCurrentRun();
        return;
    }
    sendMessage();
}, true);
sendBtn.addEventListener('click', function () {
    if (isSessionRunning(currentSessionId)) pauseCurrentRun();
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
                const r = await fetch('/sessions/' + encodeURIComponent(s.data.sessionId) + '/append_ui_events',
                    { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ events: s.data.tail }) });
                if (!r.ok) { alert('撤销失败，请重试。'); return; }
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
`,ze=`newSessionBtn.addEventListener('click', async () => { await createNewSession(); });

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
    await loadSessions();
    const sessions = sessionStore.list();
    let lastSessionId = localStorage.getItem('lastSessionId');
    let targetSession = null;
    if (lastSessionId && sessions.some(s => s.id === lastSessionId)) targetSession = lastSessionId;
    else if (sessions.length > 0) targetSession = sessions[0].id;
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
`,Ge=[Se,he,be,ye,Ie,xe,we,Ce,ke,Te,Ee,_e,Le,Ae,Pe,Re,Fe,Be,Me,Ne,Oe,De,qe,Ue,He,je,We,ze];Function(`"use strict";
`+Ge.join(`

`)+`
//# sourceURL=myagent-ui.js`)();typeof initUiHoverTips=="function"&&initUiHoverTips(document);
