(function(){const C=document.createElement("link").relList;if(C&&C.supports&&C.supports("modulepreload"))return;for(const v of document.querySelectorAll('link[rel="modulepreload"]'))E(v);new MutationObserver(v=>{for(const h of v)if(h.type==="childList")for(const L of h.addedNodes)L.tagName==="LINK"&&L.rel==="modulepreload"&&E(L)}).observe(document,{childList:!0,subtree:!0});function F(v){const h={};return v.integrity&&(h.integrity=v.integrity),v.referrerPolicy&&(h.referrerPolicy=v.referrerPolicy),v.crossOrigin==="use-credentials"?h.credentials="include":v.crossOrigin==="anonymous"?h.credentials="omit":h.credentials="same-origin",h}function E(v){if(v.ep)return;v.ep=!0;const h=F(v);fetch(v.href,h)}})();(function(x){var C='<svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M3 7a2 2 0 0 1 2-2h4l2 2h8a2 2 0 0 1 2 2v9a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V7z"></path></svg>';function F(){if(!document.getElementById("myagent-path-picker-styles")){var t=document.createElement("style");t.id="myagent-path-picker-styles",t.textContent='.path-input-row{display:flex;align-items:stretch;gap:.35rem;width:100%;}.path-input-row>.ip,.path-input-row>.tx,.path-input-row>input[type="text"],.path-input-row>input:not([type]){flex:1;min-width:0;}.path-browse-btn{flex-shrink:0;width:2.35rem;padding:0;border:1px solid var(--border-glass,rgba(255,255,255,.08));border-radius:var(--radius-sm,8px);background:var(--surface-glass2,rgba(40,40,60,.94));color:var(--text-secondary,#a6adc8);cursor:pointer;display:inline-flex;align-items:center;justify-content:center;transition:color .18s,border-color .18s,background .18s;}.path-browse-btn:hover{color:var(--text-primary,#cdd6f4);border-color:var(--border-brand-accent,rgba(124,111,247,.35));background:rgba(108,92,231,.12);}.path-browse-btn:disabled{opacity:.45;cursor:not-allowed;}.path-browse-btn--ghost{background:transparent;border-color:transparent;box-shadow:none;width:2.1rem;}.path-browse-btn--ghost:hover{background:rgba(108,92,231,.1);border-color:transparent;color:var(--accent-2,#d4b8fc);}.input-wrapper .path-browse-btn--ghost{align-self:center;margin-right:-.15rem;}.input-wrapper.is-drag-over{border-color:rgba(203,166,247,.62);box-shadow:0 0 0 3px rgba(203,166,247,.12),0 0 28px rgba(139,92,246,.18);}.workspace-file-popover{position:fixed;display:none;z-index:260;width:min(46rem,calc(100vw - 1.2rem));height:min(44rem,82vh);max-height:min(44rem,82vh);border:1px solid rgba(203,166,247,.24);border-radius:14px;background:linear-gradient(145deg,rgba(31,31,49,.88),rgba(19,20,31,.78));box-shadow:0 24px 70px rgba(0,0,0,.38),0 0 0 1px rgba(255,255,255,.045) inset,0 0 34px rgba(139,92,246,.16);overflow:hidden;backdrop-filter:blur(22px);-webkit-backdrop-filter:blur(22px);}.workspace-file-popover:before{content:"";position:absolute;inset:0;pointer-events:none;background:radial-gradient(circle at 18% 0%,rgba(203,166,247,.18),transparent 30%),radial-gradient(circle at 92% 18%,rgba(99,102,241,.16),transparent 28%);}.workspace-file-popover.is-open{display:flex;flex-direction:column;}.workspace-file-search{position:relative;width:100%;box-sizing:border-box;border:0;border-bottom:1px solid rgba(255,255,255,.08);background:rgba(255,255,255,.055);color:var(--text-primary,#cdd6f4);padding:.56rem .72rem;font:inherit;font-size:.78rem;outline:none;}.workspace-file-search::placeholder{color:var(--text-muted,#6c7086);}.workspace-file-list{position:relative;flex:1;min-height:0;overflow:auto;padding:.36rem .38rem .2rem;}.workspace-file-item{width:100%;display:grid;grid-template-columns:1.05rem minmax(0,1fr) auto;gap:.2rem .38rem;align-items:center;text-align:left;border:0;border-radius:8px;background:transparent;color:var(--text-secondary,#a6adc8);padding:.22rem .36rem;cursor:pointer;font:inherit;font-size:.74rem;}.workspace-file-item:hover,.workspace-file-item.is-active{background:rgba(139,92,246,.13);color:var(--text-primary,#cdd6f4);}.workspace-file-item.is-selected{background:rgba(99,102,241,.18);color:var(--text-primary,#cdd6f4);}.workspace-file-check{width:.82rem;height:.82rem;border:1px solid rgba(203,166,247,.38);border-radius:4px;display:inline-flex;align-items:center;justify-content:center;color:#fff;font-size:.62rem;line-height:1;background:transparent;}.workspace-file-item.is-selected .workspace-file-check{background:linear-gradient(135deg,#6366f1,#a78bfa);border-color:transparent;color:#fff;}.workspace-file-dir-row{grid-template-columns:1.05rem minmax(0,1fr) auto;color:var(--text-primary,#cdd6f4);font-weight:650;}.workspace-file-dir-row .workspace-file-tree{grid-column:2/3;}.workspace-file-file-row{grid-template-columns:1.05rem minmax(0,1fr) auto;}.workspace-file-tree{min-width:0;display:flex;align-items:center;gap:.24rem;}.workspace-file-indent{flex:0 0 auto;width:var(--indent,0);}.workspace-file-chevron{width:.8rem;min-width:.8rem;color:var(--text-muted,#6c7086);font-size:.72rem;text-align:center;border:0;background:transparent;padding:0;cursor:pointer;}.workspace-file-icon{position:relative;width:.98rem;min-width:.98rem;height:.74rem;margin-top:.04rem;border-radius:3px;border:1px solid rgba(203,166,247,.28);background:linear-gradient(135deg,rgba(203,166,247,.18),rgba(99,102,241,.1));box-shadow:inset 0 .12rem .26rem rgba(255,255,255,.08);}.workspace-file-icon:before{content:"";position:absolute;left:.06rem;right:.06rem;top:.12rem;height:.16rem;border-radius:999px;background:rgba(203,166,247,.34);}.workspace-file-icon:after{content:"";position:absolute;left:.06rem;right:.06rem;bottom:.11rem;height:.24rem;border-radius:2px;background:rgba(99,102,241,.16);}.workspace-file-icon.is-file{width:.82rem;min-width:.82rem;height:1rem;margin-top:0;border-radius:3px;background:transparent;border:1.5px solid rgba(166,173,200,.58);box-shadow:none;color:var(--text-muted,#6c7086);}.workspace-file-icon.is-file:before{left:auto;right:-1.5px;top:-1.5px;width:.3rem;height:.3rem;border:0;border-left:1.5px solid rgba(166,173,200,.58);border-bottom:1.5px solid rgba(166,173,200,.58);border-radius:0 3px 0 3px;background:var(--surface-glass2,rgba(40,40,60,.94));}.workspace-file-icon.is-file:after{display:none;}.workspace-file-icon.is-folder-svg{width:1rem;min-width:1rem;height:1rem;margin-top:0;border:0;background:transparent;box-shadow:none;color:var(--text-muted,#6c7086);display:inline-flex;align-items:center;justify-content:center;}.workspace-file-icon.is-folder-svg:before,.workspace-file-icon.is-folder-svg:after{display:none;}.workspace-file-icon.is-folder-svg svg{width:1rem;height:1rem;display:block;}.workspace-file-icon.is-image{border-color:rgba(45,212,191,.72);}.workspace-file-icon.is-image:after{display:block;left:.12rem;right:.12rem;bottom:.15rem;height:.24rem;clip-path:polygon(0 100%,38% 38%,56% 66%,76% 24%,100% 100%);background:rgba(45,212,191,.72);}.workspace-file-icon.is-audio{border-color:rgba(251,191,36,.76);}.workspace-file-icon.is-audio:after{display:block;left:.17rem;right:auto;bottom:.18rem;width:.36rem;height:.4rem;border-radius:0;background:rgba(251,191,36,.76);clip-path:polygon(0 32%,45% 32%,100% 0,100% 100%,45% 68%,0 68%);}.workspace-file-name{min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;font-size:.74rem;}.workspace-file-dir{grid-column:2/-1;color:var(--text-muted,#6c7086);font-size:.68rem;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;}.workspace-file-meta{color:var(--text-muted,#6c7086);font-size:.68rem;white-space:nowrap;}.workspace-file-footer{position:relative;display:flex;align-items:center;justify-content:space-between;gap:.5rem;padding:.42rem .52rem;border-top:1px solid rgba(255,255,255,.08);background:rgba(255,255,255,.035);font-size:.72rem;color:var(--text-muted,#6c7086);}.workspace-file-outside{flex-shrink:0;border:1px solid rgba(203,166,247,.24);border-radius:8px;padding:.28rem .58rem;background:rgba(203,166,247,.1);color:var(--text-primary,#cdd6f4);font:inherit;font-size:.7rem;font-weight:700;cursor:pointer;transition:background .16s,border-color .16s,color .16s;}.workspace-file-outside:hover{background:rgba(203,166,247,.18);border-color:rgba(203,166,247,.42);color:#fff;}.workspace-file-insert{border:0;border-radius:8px;padding:.34rem .62rem;background:linear-gradient(135deg,#6366f1,#8b5cf6);color:#fff;font-size:.72rem;font-weight:700;cursor:pointer;}.workspace-file-insert:disabled{opacity:.45;cursor:not-allowed;}.workspace-file-empty{padding:1rem;text-align:center;color:var(--text-muted,#6c7086);font-size:.78rem;}.theme-light .workspace-file-popover{background:linear-gradient(145deg,rgba(255,255,255,.93),rgba(244,247,252,.86));box-shadow:0 24px 64px rgba(31,35,52,.16),0 0 28px rgba(99,102,241,.12);}.theme-light .workspace-file-search,.theme-light .workspace-file-footer{background:rgba(34,40,58,.035);}',document.head.appendChild(t)}}async function E(t,o,i){var c=typeof AbortController<"u"?new AbortController:null,u=c?setTimeout(function(){c.abort()},5e4):null,f;try{f=await fetch("/api/pick-path",{method:"POST",headers:{"Content-Type":"application/json"},credentials:"same-origin",body:JSON.stringify({kind:t||"directory",initial:o||"",multiple:!!i}),signal:c?c.signal:void 0})}finally{u&&clearTimeout(u)}var p=await f.json().catch(function(){return{ok:!1,error:"请求失败"}});if(!f.ok||!p.ok){if(p&&p.cancelled)return null;var r=p&&p.error||"无法打开选择对话框";if(/取消|cancelled|800704c7|2147023673/i.test(r))return null;throw new Error(r)}return i?Array.isArray(p.paths)?p.paths:p.path?[p.path]:[]:p.path||null}async function v(t,o,i,c,u){t.disabled=!0;try{var f=await E(o,i||"",!!u);c&&c(f)}catch{return}finally{t.disabled=!1}}function h(t){var o=String(t||"").trim();return o?((o.charAt(0)==='"'&&o.charAt(o.length-1)==='"'||o.charAt(0)==="'"&&o.charAt(o.length-1)==="'")&&(o=o.slice(1,-1)),'"'+o.replace(/"/g,'\\"')+'"'):""}function L(t){var o=String(t||"").toLowerCase().split(".").pop()||"";return/^(png|jpe?g|gif|webp|bmp|svg|tiff?|ico|avif)$/.test(o)?"is-image":/^(mp3|wav|flac|aac|m4a|ogg|oga|opus|wma|aiff?)$/.test(o)?"is-audio":""}function N(t,o){var i=t.selectionStart,c=t.selectionEnd,u=t.value.slice(0,i),f=t.value.slice(c),p=String(o||"");u.length&&!/\s$/.test(u)&&(p=" "+p),f.length&&!/^\s/.test(f)&&(p=p+" "),t.value=u+p+f;var r=u.length+p.length;t.selectionStart=t.selectionEnd=r,t.dispatchEvent(new Event("input",{bubbles:!0})),t.focus()}async function J(t){var o=Array.prototype.slice.call(t||[]).filter(Boolean);if(!o.length)return[];var i=new FormData;o.forEach(function(f){i.append("files",f,f.name||"upload.bin")});var c=await fetch("/api/upload-chat-files",{method:"POST",credentials:"same-origin",body:i}),u=await c.json().catch(function(){return{ok:!1,error:"上传失败"}});if(!c.ok||!u.ok)throw new Error(u&&u.error||"上传失败");return Array.isArray(u.files)?u.files:[]}function ee(t){return t=Number(t||0),!isFinite(t)||t<=0?"":t<1024?t+" B":t<1024*1024?Math.round(t/102.4)/10+" KB":t<1024*1024*1024?Math.round(t/104857.6)/10+" MB":Math.round(t/1073741824e-1)/10+" GB"}async function U(t,o,i){var c=[];t?c.push("q="+encodeURIComponent(t)):o&&c.push("dir="+encodeURIComponent(o));var u="/api/workspace-files"+(c.length?"?"+c.join("&"):""),f=await fetch(u,{credentials:"same-origin",signal:i}),p=await f.json().catch(function(){return{ok:!1,error:"读取工作区文件失败"}});if(!f.ok||!p.ok)throw new Error(p&&p.error||"读取工作区文件失败");return Array.isArray(p.files)?p.files:[]}function H(t,o){return J(o).then(function(i){var c=i.map(function(u){return h(u.path||u.rel||u.name)}).join(" ");c&&N(t,c)})}function ne(t,o){var i=document.createElement("div");i.className="workspace-file-popover",i.setAttribute("aria-hidden","true"),i.innerHTML='<input class="workspace-file-search" type="text" autocomplete="off" spellcheck="false" placeholder="搜索工作区文件"><div class="workspace-file-list" role="listbox"></div><div class="workspace-file-footer"><span class="workspace-file-count">未选择文件</span><button type="button" class="workspace-file-outside">选择工作目录外文件</button></div>',document.body.appendChild(i);var c=i.querySelector(".workspace-file-search"),u=i.querySelector(".workspace-file-list"),f=i.querySelector(".workspace-file-count"),p=i.querySelector(".workspace-file-outside"),r={items:[],visible:[],active:0,open:!1,debounce:null,controller:null,selected:Object.create(null),expanded:Object.create(null),loadedDirs:Object.create(null),itemMap:Object.create(null)};function y(){var e=t.closest?t.closest(".input-wrapper"):t,n=e.getBoundingClientRect(),s=8,d=Math.min(Math.max(n.width,520),window.innerWidth-16),a=Math.max(8,Math.min(n.left,window.innerWidth-d-8)),m=document.querySelector(".titlebar"),l=m?m.getBoundingClientRect().bottom:44,g=parseFloat(getComputedStyle(document.documentElement).fontSize||"16")||16,S=Math.min(44*g,window.innerHeight*.82),I=Math.max(1,n.top-l-s),b=Math.min(S,I),_=n.top-b-s;if(b<96){var A=Math.max(1,window.innerHeight-n.bottom-s-8);b=Math.min(S,A),_=n.bottom+s}i.style.left=a+"px",i.style.top=Math.max(l,_)+"px",i.style.width=d+"px",i.style.height=Math.max(1,Math.floor(b))+"px",i.style.maxHeight=Math.max(1,Math.floor(b))+"px"}function w(){var e=Object.keys(r.selected).length;f.textContent=e?"已选择 "+e+" 项":"未选择文件",u.querySelectorAll(".workspace-file-item").forEach(function(n){var s=n.getAttribute("data-path-key")||"",d=!!r.selected[s];n.classList.toggle("is-selected",d);var a=n.querySelector(".workspace-file-check");a&&(a.textContent=d?"✓":"")})}function k(e){var n=u.querySelectorAll(".workspace-file-item");if(!n.length){r.active=0;return}r.active=Math.max(0,Math.min(e,n.length-1));for(var s=0;s<n.length;s++)n[s].classList.toggle("is-active",s===r.active),n[s].setAttribute("aria-selected",s===r.active?"true":"false");var d=n[r.active];d&&typeof d.scrollIntoView=="function"&&d.scrollIntoView({block:"nearest"})}function M(){r.open=!1,i.classList.remove("is-open"),i.setAttribute("aria-hidden","true"),r.debounce&&clearTimeout(r.debounce),r.controller&&r.controller.abort()}function D(e){return e&&(e.path||e.rel||e.name)||""}function W(e){return h(D(e))}function se(e,n){var s=D(e);if(!s)return!1;var d=String(e&&e.rel||"");return n.indexOf(W(e))>=0||n.indexOf(s)>=0||d&&n.indexOf(h(d))>=0||d&&n.indexOf(d)>=0}function ae(e,n){e=String(e||""),n=String(n||"");for(var s=0;s<e.length&&s<n.length&&e.charAt(s)===n.charAt(s);)s++;for(var d=e.length-1,a=n.length-1;d>=s&&a>=s&&e.charAt(d)===n.charAt(a);)d--,a--;return n.slice(s,a+1).trim()}function ie(e,n){if(n){var s=String(t.value||"");if(!(s.indexOf(n)>=0)){var d=t.value;N(t,n);var a=ae(d,t.value);e&&a&&(e._inputToken=a)}}}function oe(e,n){if(!n&&!e)return;var s=String(t.value||""),d=[];function a(l){l=String(l||"").trim(),l&&d.indexOf(l)<0&&d.push(l)}a(e&&e._inputToken),a(n),a(e&&e.path),a(e&&e.rel),a(e&&e.path&&h(e.path)),a(e&&e.rel&&h(e.rel));var m=s;d.sort(function(l,g){return g.length-l.length}).forEach(function(l){var g=l.replace(/[.*+?^${}()|[\]\\]/g,"\\$&"),S=new RegExp("(?:^|\\s)"+g+"(?=\\s|$)","g");m=m.replace(S,function(I){return I.charAt(0)&&/\s/.test(I.charAt(0))?" ":""})}),m=m.replace(/[ \t]{2,}/g," ").trim(),m!==s&&(t.value=m,t.selectionStart=t.selectionEnd=t.value.length,t.dispatchEvent(new Event("input",{bubbles:!0})))}function B(e){if(e){var n=D(e);if(n){var s=W(e);if(r.selected[n]){var d=r.selected[n];delete r.selected[n],oe(d,s)}else r.selected[n]=e,ie(e,s);w()}}}function z(){var e=String(t.value||"");Object.keys(r.selected).forEach(function(n){var s=r.selected[n];se(s,e)||delete r.selected[n]})}function le(){z(),w()}t.addEventListener("input",le),p&&p.addEventListener("click",function(e){e.preventDefault(),e.stopPropagation(),typeof o=="function"&&o()});function V(){var e=String(x.__WORK_DIR__||"workspace"),n=e.split(/[\\/]+/).filter(Boolean);return n[n.length-1]||"workspace"}function G(e,n,s){return{type:"dir",name:e,rel:n,root:!!s,path:"",dirs:Object.create(null),files:[],children:[],loaded:!1}}function de(e,n){var s=String(e&&e.path||""),d=String(n||"").replace(/\//g,"\\");return s&&d&&s.toLowerCase().slice(-d.length)===d.toLowerCase()?s.slice(0,Math.max(0,s.length-d.length)).replace(/[\\/]+$/,""):String(x.__WORK_DIR__||"").replace(/[\\/]+$/,"")}function K(e,n){var s=String(e||"").replace(/[\\/]+$/,""),d=String(n||"").replace(/[\\/]+/g,"/");if(!d)return s;var a=s.indexOf("\\")>=0?"\\":"/";return s?s+a+d.replace(/\//g,a):d}function P(e){return{kind:"directory",name:e.name||e.rel||V(),rel:e.rel||"",path:e.path||K(String(x.__WORK_DIR__||""),e.rel||"")}}function ce(e){var n=G(V(),"",!0);n.path=String(x.__WORK_DIR__||"").replace(/[\\/]+$/,""),n.loaded=!!r.loadedDirs.__root__;function s(a,m){for(var l=n,g=[],S=0;S<a.length;S++)g.push(a[S]),l.dirs[a[S]]||(l.dirs[a[S]]=G(a[S],g.join("/"),!1),l.dirs[a[S]].path=K(m||n.path,g.join("/"))),l=l.dirs[a[S]],l.loaded=!!r.loadedDirs[l.rel||"__root__"];return l}(e||[]).forEach(function(a){var m=String(a.rel||a.path||a.name||"").replace(/\\/g,"/"),l=m.split("/").filter(Boolean);if(l.length){var g=de(a,m);if(!n.path&&g&&(n.path=g),a.kind==="directory"){var S=s(l,g||n.path);S.name=a.name||S.name,S.path=a.path||S.path;return}var I=s(l.slice(0,-1),g||n.path);I.files.push({type:"file",name:a.name||l[l.length-1]||m,rel:m,item:a})}});function d(a){var m=Object.keys(a.dirs).map(function(l){return a.dirs[l]}).sort(function(l,g){return l.name.localeCompare(g.name,void 0,{sensitivity:"base"})});m.forEach(d),a.files.sort(function(l,g){return l.name.localeCompare(g.name,void 0,{sensitivity:"base"})}),a.children=m.concat(a.files)}return d(n),n}function Q(e,n,s){if(!(!e||e.type!=="dir")){s=Number(s||0);var d=e.rel||"__root__";n?r.expanded[d]=!0:typeof r.expanded[d]>"u"&&(r.expanded[d]=s===0),n&&e.children.forEach(function(a){a.type==="dir"&&Q(a,n,s+1)})}}function ue(e){var n=[];function s(d,a){n.push({type:"dir",node:d,depth:a}),r.expanded[d.rel||"__root__"]&&d.children.forEach(function(m){m.type==="dir"?s(m,a+1):n.push({type:"file",node:m,depth:a+1})})}return s(e,0),n}function pe(e){return String(e&&(e.kind||"file")||"file")+":"+String(e&&(e.rel||e.path||e.name)||"")}function $(e){(e||[]).forEach(function(n){var s=pe(n);s!==":"&&(r.itemMap[s]=n)}),r.items=Object.keys(r.itemMap).map(function(n){return r.itemMap[n]}),r.items.sort(function(n,s){return String(n.rel||"").localeCompare(String(s.rel||""),void 0,{sensitivity:"base"})})}function fe(e){if(e){var n=e.rel||"__root__";r.expanded[n]=!r.expanded[n],T(r.items,!1),r.expanded[n]&&!c.value&&!r.loadedDirs[n]&&ge(e.rel||"")}}function T(e,n,s){if(z(),r.items=(e||[]).slice().sort(function(a,m){return String(a.rel||"").localeCompare(String(m.rel||""),void 0,{sensitivity:"base"})}),u.innerHTML="",r.visible=[],n){u.innerHTML='<div class="workspace-file-empty">加载中</div>';return}if(s){u.innerHTML='<div class="workspace-file-empty">'+String(s)+"</div>";return}if(!r.items.length){u.innerHTML='<div class="workspace-file-empty">没有匹配文件</div>';return}var d=ce(r.items);Q(d,!!c.value),r.visible=ue(d),r.visible.forEach(function(a,m){var l=a.node,g=document.createElement("button");g.type="button",g.className="workspace-file-item "+(a.type==="dir"?"workspace-file-dir-row":"workspace-file-file-row"),g.setAttribute("role","option"),g.setAttribute("data-row-index",String(m)),g.setAttribute("data-path-key",a.type==="dir"?P(l).path||P(l).rel||P(l).name||"":l.item.path||l.item.rel||l.item.name||"");var S=document.createElement("div");S.className="workspace-file-tree";var I=document.createElement("span");I.className="workspace-file-indent",I.style.setProperty("--indent",Math.min(a.depth,10)*.86+"rem");var b=document.createElement("span");b.className="workspace-file-chevron",b.textContent=a.type==="dir"?r.expanded[l.rel||"__root__"]?"▾":"▸":"",a.type==="dir"?(b.setAttribute("aria-label",r.expanded[l.rel||"__root__"]?"折叠文件夹":"展开文件夹"),b.setAttribute("role","button"),b.addEventListener("click",function(R){R.preventDefault(),R.stopPropagation(),fe(l)})):b.setAttribute("tabindex","-1");var _=document.createElement("span");_.className="workspace-file-icon"+(a.type==="file"?" is-file "+L(l.item&&l.item.name):" is-folder-svg"),a.type==="dir"&&(_.innerHTML=C);var A=document.createElement("div");A.className="workspace-file-name",A.textContent=l.name||l.rel||"";var q=document.createElement("div");q.className="workspace-file-meta",q.textContent=a.type==="dir"?"":ee(l.item.size),S.appendChild(I),S.appendChild(b),S.appendChild(_),S.appendChild(A);var Z=document.createElement("span");Z.className="workspace-file-check",g.appendChild(Z),g.appendChild(S),g.appendChild(q),g.addEventListener("mouseenter",function(){k(m)}),g.addEventListener("click",function(R){R.preventDefault(),R.stopPropagation(),a.type==="dir"?B(P(l)):B(l.item)}),u.appendChild(g)}),k(0),w()}function X(){var e=c.value||"";r.controller&&r.controller.abort(),r.controller=typeof AbortController<"u"?new AbortController:null,T(r.items,!0),U(e,"",r.controller?r.controller.signal:void 0).then(function(n){r.open&&(e?T(n,!1):(r.loadedDirs.__root__=!0,$(n),T(r.items,!1)))}).catch(function(n){n&&n.name==="AbortError"||r.open&&T([],!1,n&&n.message||"读取失败")})}function ge(e){var n=e||"__root__";r.loadedDirs[n]||(r.loadedDirs[n]=!0,U("",e||"",void 0).then(function(s){!r.open||c.value||($(s),T(r.items,!1))}).catch(function(){delete r.loadedDirs[n]}))}function me(){r.debounce&&clearTimeout(r.debounce),r.debounce=setTimeout(X,120)}function Y(){if(r.open){y();try{c.focus(),c.select()}catch{}return}r.open=!0,i.classList.add("is-open"),i.setAttribute("aria-hidden","false"),c.value="",r.expanded=Object.create(null),r.loadedDirs=Object.create(null),r.itemMap=Object.create(null),r.items=[],T([],!0),y(),X(),setTimeout(function(){y();try{c.focus()}catch{}},0)}function Se(){r.open?M():Y()}return c.addEventListener("input",me),c.addEventListener("keydown",function(e){if(e.key==="ArrowDown")e.preventDefault(),k(r.active+1);else if(e.key==="ArrowUp")e.preventDefault(),k(r.active-1);else if(e.key==="Enter"){e.preventDefault();var n=r.visible[r.active];n&&n.type==="dir"?B(P(n.node)):n&&n.type==="file"&&B(n.node.item)}else e.key==="Escape"&&(e.preventDefault(),M(),t.focus())}),document.addEventListener("click",function(e){r.open&&(i.contains(e.target)||M())}),window.addEventListener("resize",function(){r.open&&y()}),window.addEventListener("scroll",function(){r.open&&y()},!0),{panel:i,open:Y,close:M,toggle:Se}}function j(t,o,i){if(!t||t.dataset.pathBrowseWrapped==="1")return t;F();var c=document.createElement("div");c.className="path-input-row";var u=t.parentNode;if(!u)return t;u.insertBefore(c,t),c.appendChild(t);var f=document.createElement("button");f.type="button",f.className="path-browse-btn",f.innerHTML=C;var p=i||"浏览路径";return f.setAttribute("aria-label",p),typeof bindUiHoverTip=="function"?(f.setAttribute("data-ui-tip",p),f.removeAttribute("title"),bindUiHoverTip(f)):f.title=p,f.addEventListener("click",function(r){r.stopPropagation();var y=t.getAttribute("data-path-kind")||o;y!=="file"&&y!=="directory"&&(y="directory"),v(f,y,t.value||"",function(w){if(w){var k=Array.isArray(w)?w[0]||"":String(w);k&&(t.value=k,t.dispatchEvent(new Event("input",{bubbles:!0})),t.dispatchEvent(new Event("change",{bubbles:!0})))}})}),c.appendChild(f),t.dataset.pathBrowseWrapped="1",t}function te(t){var o=t.closest?t.closest(".input-wrapper"):t;!o||o.dataset.fileDropBound==="1"||(o.dataset.fileDropBound="1",["dragenter","dragover"].forEach(function(i){o.addEventListener(i,function(c){!c.dataTransfer||!c.dataTransfer.files||!c.dataTransfer.files.length||(c.preventDefault(),o.classList.add("is-drag-over"))})}),["dragleave","drop"].forEach(function(i){o.addEventListener(i,function(){o.classList.remove("is-drag-over")})}),o.addEventListener("drop",function(i){!i.dataTransfer||!i.dataTransfer.files||!i.dataTransfer.files.length||(i.preventDefault(),H(t,i.dataTransfer.files).catch(function(){}))}))}function re(t,o){if(!(!t||!o)){F(),te(o),t.classList.add("path-browse-btn","path-browse-btn--ghost"),t.innerHTML=C,t.setAttribute("aria-label","工作区文件"),t.setAttribute("data-ui-tip","工作区文件"),t.dataset.silentPickerUnavailable="1",t.removeAttribute("title");var i=document.createElement("input");i.type="file",i.multiple=!0,i.style.display="none",i.setAttribute("aria-hidden","true"),document.body.appendChild(i),i.addEventListener("change",function(){var u=i.files;!u||!u.length||(t.disabled=!0,H(o,u).finally(function(){i.value="",t.disabled=!1}))});var c=ne(o,function(){i.click()});t.addEventListener("click",function(u){if(u.stopPropagation(),u.preventDefault(),u.altKey){i.click();return}if(!u.shiftKey){c.toggle();return}var f=x&&typeof x.__WORK_DIR__=="string"?x.__WORK_DIR__:"";v(t,"file",f,function(p){var r=Array.isArray(p)?p:p?[p]:[];r.length&&N(o,r.map(function(y){return h(y)}).join(" "))},!1)})}}function O(t){t=t||document;for(var o=t.querySelectorAll("[data-path-kind]"),i=0;i<o.length;i++){var c=o[i],u=c.getAttribute("data-path-kind");(u==="file"||u==="directory")&&j(c,u)}}x.MyAgentPathPicker={pickPath:E,wrapInputWithBrowse:j,attachChatPicker:re,scan:O},document.readyState==="loading"?document.addEventListener("DOMContentLoaded",function(){O(document)}):O(document)})(typeof window<"u"?window:globalThis);const ve=`// ═══════════════════════════════════════════════════════════
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

function clearSessionRunStateIfMatch(sessionId, runId) {
    const sid = String(sessionId || '');
    if (!sid) return;
    const expected = String(runId || '');
    if (!expected) {
        clearSessionRunState(sid);
        return;
    }
    const run = getSessionRunState(sid);
    if (!run || String(run.runId || '') === expected) {
        clearSessionRunState(sid);
    }
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
`,_e=`function setSubagentCardEventCount(agentId, count) {
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
`,Ee=`function subagentMoreDotsHtml() {
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
`,Pe=`var subagentCardViewportObserver = null;
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
`,Ae=`var subagentCardSyncTimer = null;
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
`,Me=`const contextStore = {
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
`,Be=`function markUiEventStoreApplied(event) {
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
        html += '<button type="button" class="composer-model-option" disabled><span class="composer-model-option-meta">暂无已保存模型配置，可到模型配置页中保存</span></button>';
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
        var cachedTokens = selectContextTokens(currentSessionId);
        var nextThreshold = activeProfileContextWindow();
        if (cachedTokens && cachedTokens.estimated != null) {
            recordContextTokens(
                currentSessionId,
                cachedTokens.estimated,
                nextThreshold != null ? nextThreshold : cachedTokens.threshold
            );
        } else {
            scheduleContextTokensAfterPaint(currentSessionId);
        }
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
    window.addEventListener('resize', () => {
        var fresh = els();
        if (fresh.menu && fresh.menu.classList.contains('is-open')) constrainModelMenuToTitlebar();
    });
    refreshModelProfileSelectorInBackground(currentSessionId);
}

initModelProfileSwitcher();
window.refreshModelProfileSelector = refreshModelProfileSelector;
window.loadModelProfilesForSwitcher = loadModelProfilesForSwitcher;
`,Oe=`let skillPickerCache = null;
let skillPickerRefreshPromise = null;
let selectedSkillNames = [];
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

function selectedSkillSet() {
    var out = {};
    selectedSkillNames.forEach(function (name) { out[String(name)] = true; });
    return out;
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

function syncSkillPickerButton() {
    var e = skillPickerEls();
    if (!e.button) return;
    var count = selectedSkillNames.length;
    e.button.classList.toggle('is-active', count > 0);
    e.button.textContent = count > 0 ? ('SKILL ' + count) : 'SKILL';
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

function renderSkillPicker() {
    var e = skillPickerEls();
    if (!e.popover) return;
    var skills = (skillPickerCache && skillPickerCache.skills) || [];
    if (!skills.length) {
        e.popover.innerHTML = '<div class="skill-picker-empty">当前没有已注册 Skill</div>';
        return;
    }
    var active = selectedSkillSet();
    var selectedCount = selectedSkillNames.length;
    var html = '<div class="skill-picker-head">'
        + '<div class="skill-picker-title">选择 Skill <span class="skill-picker-total">已选 ' + skillPickerEscape(selectedCount) + ' / 共 ' + skillPickerEscape(skills.length) + '</span></div>'
        + '<button type="button" class="skill-picker-clear">清空</button>'
        + '</div>'
        + '<div class="skill-picker-list">';
    skills.forEach(function (skill) {
        var name = String(skill && skill.name || '');
        var checked = active[name] ? ' checked' : '';
        html += '<label class="skill-picker-option">'
            + '<input type="checkbox" value="' + skillPickerEscape(name) + '"' + checked + '>'
            + '<span class="skill-picker-option-body">'
            + '<span class="skill-picker-option-name">' + skillPickerEscape(name) + '</span>'
            + '<span class="skill-picker-option-desc">' + skillPickerEscape(skill && skill.description || '') + '</span>'
            + '</span>'
            + '</label>';
    });
    html += '</div>';
    e.popover.innerHTML = html;
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
    var clear = e.popover.querySelector('.skill-picker-clear');
    if (clear) {
        clear.addEventListener('click', function () {
            selectedSkillNames = [];
            persistSkillPickerDraft(currentSessionId);
            syncSkillPickerButton();
            renderSkillPicker();
        });
    }
}

async function loadSkillPickerSkills() {
    const response = await fetch('/api/skills', { credentials: 'same-origin' });
    const data = await response.json();
    if (!data || !data.ok) throw new Error((data && data.error) || 'Skill 加载失败');
    skillPickerCache = data;
    return data;
}

function refreshSkillPickerSkills() {
    if (skillPickerRefreshPromise) return skillPickerRefreshPromise;
    skillPickerRefreshPromise = loadSkillPickerSkills()
        .then(function () { renderSkillPicker(); })
        .catch(function (err) { renderSkillPickerError(err); })
        .finally(function () { skillPickerRefreshPromise = null; });
    return skillPickerRefreshPromise;
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
window.refreshSkillPickerSkills = refreshSkillPickerSkills;
window.stashSkillPickerDraft = stashSkillPickerDraft;
window.restoreSkillPickerDraft = restoreSkillPickerDraft;
`,De=`function formatTokenCompact(n) {\r
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
            + '）。预估进入模型的上下文规模，含历史与系统提示；分母为触发压缩摘要的门限，可在.env文件中 CONTEXT_WINDOW 修改。'\r
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
function scrollChatToBottomIfFollow(runSessionId, opts) {\r
    opts = opts || {};\r
    if (shouldGateScrollByRunSession(null, runSessionId)) return;\r
    if (!opts.force && !liveAutoFollow) return;\r
    if (chatContainer) chatContainer.scrollTop = chatContainer.scrollHeight;\r
}\r
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
function persistHistoryPagingToStream(streamEl, paging) {\r
    if (!streamEl) return;\r
    if (!paging || paging.sessionId !== currentSessionId) {\r
        delete streamEl.dataset.historyPaging;\r
        return;\r
    }\r
    streamEl.dataset.historyPaging = JSON.stringify({\r
        sessionId: paging.sessionId,\r
        total: Number(paging.total) || 0,\r
        range_start: Number(paging.range_start) || 0,\r
        range_end: Number(paging.range_end) || 0,\r
        has_older: !!paging.has_older,\r
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
            range_start: Number(raw.range_start) || 0,\r
            range_end: Number(raw.range_end) || 0,\r
            has_older: !!raw.has_older,\r
        };\r
    } catch (_e) {\r
        delete streamEl.dataset.historyPaging;\r
        return null;\r
    }\r
}\r
\r
function setSessionHistoryPaging(paging) {\r
    sessionHistoryPaging = paging || null;\r
    persistHistoryPagingToStream(getVisibleChatStream(), sessionHistoryPaging);\r
    updateHistorySentinelVisibility();\r
}\r
\r
function ensureHistorySentinel(streamEl) {\r
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
    btn.textContent = '更早 ' + HISTORY_DIALOGUES_PER_PAGE + ' 轮对话';\r
    btn.addEventListener('click', function () { loadOlderHistoryChunk(); });\r
    el.appendChild(btn);\r
    streamEl.insertBefore(el, streamEl.firstChild);\r
    return el;\r
}\r
\r
function getHistoryScrollAnchor(container) {\r
    if (!container) return null;\r
    var cr = container.getBoundingClientRect();\r
    var nodes = container.querySelectorAll('.msg-wrap, .process-aggregate, .welcome');\r
    for (var i = 0; i < nodes.length; i += 1) {\r
        var n = nodes[i];\r
        if (!n || !n.isConnected || n.id === 'chat-loading') continue;\r
        var r = n.getBoundingClientRect();\r
        if (r.bottom >= cr.top + 4) return { el: n, top: r.top };\r
    }\r
    return null;\r
}\r
\r
function updateHistorySentinelVisibility() {\r
    var strip = document.getElementById('history-load-sentinel');\r
    var btn = strip && strip.querySelector('.history-load-older-btn');\r
    var ph = sessionHistoryPaging;\r
    if (!strip || !btn) return;\r
    if (!ph || !ph.has_older || ph.sessionId !== currentSessionId) {\r
        strip.hidden = true;\r
        btn.disabled = false;\r
        btn.textContent = '更早 ' + HISTORY_DIALOGUES_PER_PAGE + ' 轮对话';\r
        return;\r
    }\r
    strip.hidden = false;\r
    btn.disabled = historyOlderLoading;\r
    btn.textContent = historyOlderLoading ? '加载中…' : ('更早 ' + HISTORY_DIALOGUES_PER_PAGE + ' 轮对话');\r
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
    replayingMessages = true;\r
    updateHistorySentinelVisibility();\r
    var cc = chatContainer;\r
    var prevScrollTop = cc ? cc.scrollTop : 0;\r
    var anchor = getHistoryScrollAnchor(cc);\r
    var loadedOlder = false;\r
    try {\r
        var pageTurns = Math.max(1, Math.min(Number(opts.turns) || HISTORY_DIALOGUES_PER_PAGE, 50));\r
        var url = '/sessions/' + encodeURIComponent(sid) + '/messages?turns=' + encodeURIComponent(String(pageTurns)) + '&before_index=' + ph.range_start;\r
        var response = await fetch(url);\r
        var data = await response.json();\r
        if (!response.ok || !data || typeof data !== 'object') return;\r
        var events = data.events;\r
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
        }\r
        var sen = stream && stream.querySelector('#history-load-sentinel');\r
        if (stream && frag.childNodes.length) {\r
            stream.insertBefore(frag, sen ? sen.nextSibling : stream.firstChild);\r
        }\r
        loadedOlder = true;\r
        setSessionHistoryPaging({\r
            sessionId: sid,\r
            total: typeof data.total === 'number' ? data.total : ph.total,\r
            range_start: typeof data.range_start === 'number' ? data.range_start : ph.range_start,\r
            range_end: ph.range_end,\r
            has_older: !!data.has_older,\r
        });\r
    } catch (e) {\r
        console.error('加载更早消息失败:', e);\r
    } finally {\r
        historyOlderLoading = false;\r
        updateHistorySentinelVisibility();\r
        if (cc && stream && stream.parentNode === cc) {\r
            if (anchor && anchor.el && anchor.el.isConnected) {\r
                var nextTop = anchor.el.getBoundingClientRect().top;\r
                setScrollTopImmediate(cc, cc.scrollTop + (nextTop - anchor.top));\r
            } else {\r
                setScrollTopImmediate(cc, prevScrollTop);\r
            }\r
        }\r
        if (loadedOlder) {\r
            bindExistingLogs(stream);\r
            if (!opts.keepTocStable) rebuildToc();\r
            scheduleTocActiveUpdate();\r
        }\r
        replayingMessages = prevReplaying;\r
    }\r
}\r
\r
function insertNewEmptyChatStream() { ensureVisibleChatStreamSlot(); }

async function loadHistoryWindowAroundEventIndex(sessionId, eventIndex, opts) {
    opts = opts || {};
    var sid = String(sessionId || '');
    var ei = Number(eventIndex);
    if (!sid || !Number.isFinite(ei)) return false;
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
        if (!getVisibleChatStream()) ensureVisibleChatStreamSlot();
        var stream = getVisibleChatStream();
        if (!stream) return false;
        emptyChatStreamKeepingStrip(stream);
        var pageMeta = {
            total: Number(data.total) || 0,
            range_start: Number(data.range_start) || 0,
            range_end: Number(data.range_end) || 0,
            has_older: !!data.has_older,
        };
        beginMessageReplay(sid, pageMeta);
        setSessionHistoryPaging({
            sessionId: sid,
            total: pageMeta.total,
            range_start: pageMeta.range_start,
            range_end: pageMeta.range_end,
            has_older: !!pageMeta.has_older,
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
function trimCachedSessionStreams() {\r
    if (!offscreenRoot) return;\r
    while (cachedSessionStreamOrder.length > SESSION_STREAM_CACHE_LIMIT) {\r
        var sid = cachedSessionStreamOrder.shift();\r
        var cached = offscreenRoot.querySelector('.chat-stream[data-cache-session-id="' + cssEscapeIdent(sid) + '"]');\r
        if (cached && cached.parentNode) cached.remove();\r
    }\r
}\r
\r
function stashVisibleStreamForSession(sessionId, opts) {\r
    opts = opts || {};\r
    var sid = String(sessionId || '');\r
    if (!sid || !offscreenRoot) return false;\r
    const el = getVisibleChatStream();\r
    if (!el || !el.parentNode) return false;\r
    if (!opts.force && el.dataset.sessionLoadOk !== '1') return false;\r
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
function prepareStashLeaving(leavingId) {\r
    if (!leavingId) return;\r
    if (isSessionRunning(leavingId)) {\r
        stashVisibleStreamForSession(leavingId, { force: true });\r
        insertNewEmptyChatStream();\r
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
    if (st.dataset && (st.dataset.partialBackgroundRun === '1' || st.dataset.sessionLoadOk !== '1')) {
        abortSessionRun(enteringId, 'reattach-incomplete-background');
        if (st.parentNode) st.remove();
        return false;
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
function restoreCachedSessionStream(enteringId) {\r
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
    return true;\r
}\r
\r
function restoreCachedSessionScrollPosition(sessionId) {\r
    if (!chatContainer || !sessionId) return;\r
    requestAnimationFrame(function () {\r
        if (sessionId !== currentSessionId) return;\r
        var saved = (typeof getSavedScrollPosition === 'function') ? getSavedScrollPosition(sessionId) : null;\r
        if (saved !== null && Number.isFinite(Number(saved)) && Number(saved) > 0) {\r
            setScrollTopImmediate(chatContainer, Number(saved));\r
        } else {\r
            chatContainer.scrollTop = chatContainer.scrollHeight;\r
        }\r
        refreshLiveAutoFollowPins();\r
        scheduleTocActiveUpdate();\r
    });\r
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
function discardLlmStreamChunks(ctx, ev) {\r
    if (!ctx) return;\r
    if (ctx.llm) {\r
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
    var reactIter = ev && ev.react_iter != null && Number.isFinite(Number(ev.react_iter))\r
        ? String(Math.max(1, Math.floor(Number(ev.react_iter))))\r
        : '';\r
    bodies.forEach(function (body) {\r
        body.querySelectorAll('.feed-item.feed--llm, .feed-item.feed--llm2').forEach(function (el) {\r
            var ch = el.querySelector('.feed-chunk');\r
            if (ch && ch.classList.contains('is-streaming')) el.remove();\r
        });\r
        body.querySelectorAll('.feed-item.feed--tool[data-tool-pending="1"]').forEach(function (el) {\r
            el.remove();\r
        });\r
        if (reactIter) {\r
            var sel = '.feed-item[data-react-iter="' + reactIter + '"]';\r
            body.querySelectorAll(sel).forEach(function (el) {\r
                if (\r
                    el.classList.contains('feed--tool')\r
                    || el.classList.contains('feed--llm')\r
                    || el.classList.contains('feed--llm2')\r
                ) {\r
                    el.remove();\r
                }\r
            });\r
        }\r
    });\r
}\r
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
    l.llmPendingReasoningDelta = '';\r
    if (l.llmPendingResponseDelta && l.llmStreamResponseScroller) {\r
        var rsp = trimSurroundingBlankLines((l.llmStreamResponseScroller.textContent || '') + l.llmPendingResponseDelta);\r
        l.llmStreamResponseScroller.textContent = truncateLogTextForUi(rsp);\r
    }\r
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
        const r = await fetch('/sessions/' + encodeURIComponent(sid) + '/messages/count');
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
async function scrollToUserTurnOrLoadOlder(eventIndex, opts) {\r
    opts = opts || {};\r
    var ei = Number(eventIndex);\r
    if (!Number.isFinite(ei)) return false;\r
    var silent = !!opts.silent;\r
    var allowFullReload = opts.allowFullReload !== false && !silent;\r
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
    function findWrap() {\r
        var stream = getVisibleChatStream();\r
        if (!stream) return null;\r
        return stream.querySelector('.msg-wrap--user[data-event-index="' + ei + '"]')\r
            || stream.querySelector('#user-msg-' + ei);\r
    }\r
    async function loadFullHistoryForTarget(sid) {\r
        if (!allowFullReload) return;\r
        if (sid !== currentSessionId || typeof loadSessionMessages !== 'function') return;\r
        try {\r
            await loadSessionMessages(sid, 'saved-or-bottom', {\r
                full: true,\r
                allowDuringRun: typeof isServerStreamActive === 'function' && isServerStreamActive(sid),\r
            });\r
        } catch (e) {\r
            console.error('reload full history for toc target failed:', e);\r
        }\r
    }\r
    setTocJumpLoading(true);\r
    try {\r
        var wrap = findWrap();\r
        if (wrap) {
            wrap.scrollIntoView({ behavior: 'smooth', block: 'start' });
            return true;
        }
        var sid = currentSessionId;
        if (allowFullReload) {
            var loadedTargetWindow = await loadHistoryWindowAroundEventIndex(sid, ei, { turns: 50 });
            if (loadedTargetWindow && sid === currentSessionId) {
                wrap = findWrap();
                if (wrap) {
                    wrap.scrollIntoView({ behavior: 'smooth', block: 'start' });
                    return true;
                }
            }
        }
        var safety = 0;
        var olderLoads = 0;\r
        var pagingCoveredTarget = false;\r
        while (sid === currentSessionId && safety < 120) {\r
            safety += 1;\r
            wrap = findWrap();\r
            if (wrap) {\r
                wrap.scrollIntoView({ behavior: 'smooth', block: 'start' });\r
                return true;\r
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
        wrap = findWrap();\r
        if (wrap) {\r
            wrap.scrollIntoView({ behavior: 'smooth', block: 'start' });\r
            return true;\r
        }\r
        if (allowFullReload && sid === currentSessionId && pagingCoveredTarget) {\r
            await loadFullHistoryForTarget(sid);\r
            if (sid !== currentSessionId) return false;\r
            wrap = findWrap();\r
            if (wrap) {\r
                wrap.scrollIntoView({ behavior: 'smooth', block: 'start' });\r
                return true;\r
            }\r
            rebuildToc();\r
        }\r
        if (wrap) wrap.scrollIntoView({ behavior: 'smooth', block: 'start' });\r
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
`,qe=`function ensureUiHoverTooltipEl() {
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
`,Ue=`function removeMessagesFromNode(startWrap) {
    const stream = getVisibleChatStream() || chatContainer;
    if (!stream) return;
    const kids = Array.from(stream.children);
    const i = kids.indexOf(startWrap);
    if (i < 0) return;
    for (let j = kids.length - 1; j >= i; j--) kids[j].remove();
    syncDisconnectedProcessGroups();
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
        const raw = messageRawMarkdown.get(wrap);
        const toCopy = raw !== undefined ? String(raw) : plain;
        const done = function () { showCopyFeedback(); };
        if (navigator.clipboard && navigator.clipboard.writeText) {
            navigator.clipboard.writeText(toCopy).then(done).catch(function () {
                try {
                    const ta = document.createElement('textarea');
                    ta.value = toCopy;
                    ta.setAttribute('readonly', 'readonly');
                    document.body.appendChild(ta);
                    ta.select();
                    document.execCommand('copy');
                    document.body.removeChild(ta);
                    done();
                } catch (e) { /* ignore */ }
            });
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
                removeMessagesFromNode(wrap);
                syncDisconnectedProcessGroups();
                rebuildToc();
                scheduleContextTokensAfterPaint(currentSessionId);
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
    var html = '<button type="button" class="msg-tb" data-act="copy" data-ui-tip="复制">复制</button>'
        + '<button type="button" class="msg-tb" data-act="delete" data-ui-tip="删除">删除</button>';
    if (role === 'assistant') {
        html += '<button type="button" class="msg-tb" data-act="branch" data-ui-tip="分支">分支</button>';
    }
    if (role === 'user') html += '<button type="button" class="msg-tb" data-act="rewrite" data-ui-tip="改写">改写</button>';
    bar.insertAdjacentHTML('beforeend', html);
    bar.querySelectorAll('.msg-tb').forEach(bindUiHoverTip);
    bar.addEventListener('click', function (e) {
        var t = e.target;
        if (!t || t.tagName !== 'BUTTON' || !t.getAttribute) return;
        e.preventDefault();
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

function pushBriefLine(lines, line) {
    if (!line || !String(line).trim()) return;
    var t = String(line);
    if (lines.length && lines[lines.length - 1] === t) return;
    lines.push(t);
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
        if (!t || !String(t).trim()) return;
        const row = document.createElement('div');
        row.className = 'process-brief-item';
        row.textContent = t;
        brief.appendChild(row);
    });
}

function updateProcessBrief(agg) {
    if (!agg || !agg.isConnected) return;
    const body = agg.querySelector('.process-aggregate-body');
    const brief = agg.querySelector('.process-aggregate-brief');
    if (!body || !brief) return;
    const items = Array.from(body.querySelectorAll('.feed-item'));
    const lines = [];
    var i = 0;
    while (i < items.length) {
        var el = items[i];
        var raw = getFeedItemText(el);
        if (el.classList.contains('feed--llm')) {
            if (raw) pushBriefLine(lines, '思·' + raw);
            i += 1;
        } else if (el.classList.contains('feed--llm2')) {
            if (raw) pushBriefLine(lines, '答·' + raw);
            i += 1;
        } else if (el.classList.contains('feed--tool')) {
            var countMap = {};
            var order = [];
            while (i < items.length && items[i].classList.contains('feed--tool')) {
                var tname = extractToolNameFromLog(getFeedItemText(items[i]));
                if (countMap[tname] === undefined) { countMap[tname] = 0; order.push(tname); }
                countMap[tname] += 1;
                i += 1;
            }
            for (var oi = 0; oi < order.length; oi += 1) {
                var nm = order[oi];
                var n = countMap[nm] || 0;
                if (n > 0) pushBriefLine(lines, '调用工具 ' + nm + ' ' + n + '次');
            }
        } else { i += 1; }
    }
    if (lines.length) setBriefRows(brief, lines);
    else {
        var st = body.querySelector('.feed-item.feed--st .feed-chunk-scroller, .feed-item.feed--st .feed-chunk');
        var tSt = st ? st.textContent.trim() : '';
        if (tSt) setBriefRows(brief, [tSt]);
        else {
            var any = body.querySelector('.feed-chunk-scroller, .feed-chunk');
            var tAny = any ? any.textContent.trim() : '';
            setBriefRows(brief, [tAny || '本段过程已折叠']);
        }
    }
}

function bindProcessAggregate(agg) {
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
            agg.classList.toggle('is-collapsed');
            const expanded = !agg.classList.contains('is-collapsed');
            top.setAttribute('aria-expanded', expanded ? 'true' : 'false');
            if (agg.classList.contains('is-collapsed')) {
                updateProcessBrief(agg);
            } else {
                requestAnimationFrame(function () {
                    requestAnimationFrame(function () {
                        agg.querySelectorAll('.process-aggregate-body .feed-chunk').forEach(refreshFeedChunkOverflow);
                        registerMermaidLazy(agg);
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
    el.innerHTML = '<span>' + parts.join(' · ') + '</span><span>' + escapeHtml(modelStr) + ' · ' + escapeHtml(pctStr) + '</span>';
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
    el.innerHTML = '<span>' + parts.join(' · ') + '</span><span>' + cacheLine + '</span>';
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
        + '<div class="process-aggregate-body"></div>';
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

function autoResizeTextarea() {
    messageInput.style.height = 'auto';
    messageInput.style.height = Math.min(messageInput.scrollHeight, 120) + 'px';
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

function getScrollPositionKey(sessionId) {
    return LS_SCROLL_POSITION_PREFIX + sessionId;
}

function getScrollAnchorKey(sessionId) {
    return LS_SCROLL_ANCHOR_PREFIX + sessionId;
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
            return;
        }
        var rect = chatContainer.getBoundingClientRect();
        var wraps = chatContainer.querySelectorAll('.msg-wrap--user[data-event-index]');
        var best = null;
        for (var i = 0; i < wraps.length; i += 1) {
            var wr = wraps[i];
            var ei = Number(wr.getAttribute('data-event-index'));
            if (!Number.isFinite(ei)) continue;
            var top = wr.getBoundingClientRect().top;
            if (top <= rect.top + 8) best = ei;
            else if (best == null) {
                best = ei;
                break;
            }
        }
        if (best != null) localStorage.setItem(getScrollAnchorKey(sessionId), String(best));
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

/**
 * @param {string} sessionId
 * @param {'saved-or-bottom'|'bottom'} mode — saved-or-bottom：有离开记录则恢复，否则置底；bottom：始终置底
 */
function applyChatScrollAfterHistoryLoad(sessionId, mode) {
    if (!chatContainer || !sessionId) return;
    
    // 如果会话正在运行，执行过程块默认置底
    if (isSessionRunning(sessionId)) {
        var run = getSessionRunState(sessionId);
        if (run && run.ctx && run.ctx.stream) {
            var agg = run.ctx.stream.querySelector('.process-aggregate:last-of-type');
            if (agg) {
                var procBody = agg.querySelector('.process-aggregate-body');
                if (procBody) {
                    // 延迟一帧确保DOM已渲染
                    requestAnimationFrame(function() {
                        procBody.scrollTop = procBody.scrollHeight;
                    });
                }
            }
        }
    }
    
    if (mode === 'saved-or-bottom') {
        var savedPosition = getSavedScrollPosition(sessionId);
        var savedAnchor = getSavedScrollAnchorPosition(sessionId);
        if (savedAnchor != null && typeof scrollToUserTurnOrLoadOlder === 'function') {
            requestAnimationFrame(function () {
                if (sessionId !== currentSessionId) return;
                void scrollToUserTurnOrLoadOlder(savedAnchor, {
                    silent: true,
                    allowFullReload: false,
                    maxOlderLoads: 2,
                }).then(function (ok) {
                    if (ok || sessionId !== currentSessionId || !chatContainer) return;
                    if (savedPosition !== null && savedPosition > 0) {
                        chatContainer.scrollTop = clampChatScrollTop(savedPosition);
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
        if (savedPosition !== null && savedPosition > 0) {
            // 恢复保存的滚动位置
            chatContainer.scrollTop = savedPosition;
            streamChatNearBottom = isNearBottom(chatContainer, STREAM_CHAT_NEAR_BOTTOM_PX);
            streamProcNearBottom = true;
            liveAutoFollow = streamChatNearBottom;
            return;
        }
    }
    
    // 默认行为：滚动到底部
    streamChatNearBottom = true;
    streamProcNearBottom = true;
    liveAutoFollow = true;
    scrollToBottom({ smooth: mode === 'saved-or-bottom' });
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
    if (mode === 'saved-or-bottom') {
        var savedAnchor = getSavedScrollAnchorPosition(sessionId);
        if (savedAnchor != null) return false;
        var savedPosition = getSavedScrollPosition(sessionId);
        if (savedPosition !== null && savedPosition > 0) return false;
    }
    return true;
}

function waitForChatScrollAfterHistoryLoad(sessionId, mode) {
    if (!chatContainer || !sessionId) return Promise.resolve(false);
    if (sessionId !== currentSessionId) return Promise.resolve(false);
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
    'sql|graphql|proto|thrift|cmake|gradle|mk|dockerfile|' +
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

function ensureMermaidInitialized() {
    if (mermaidInitialized || !window.mermaid) return;
    try {
        var light = document.documentElement.classList.contains('theme-light');
        mermaid.initialize({
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
    var rel = String(wsRel || raw || '').replace(/\\\\/g, '/').replace(/^\\/+/, '');
    if (/^[A-Za-z]:\\//.test(rel) || /^\\\\\\\\/.test(rel)) return rel.replace(/\\//g, '\\\\');
    var w = (typeof window.__WORK_DIR__ === 'string') ? window.__WORK_DIR__ : '';
    if (!w || !rel) return rel || raw;
    return pathJoinBaseName(w, rel).replace(/\\//g, '\\\\');
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
    if (!el || !window.mermaid || !el.isConnected) return;
    if (el.getAttribute('data-processed') === 'true' || el.classList.contains('mermaid-error')) return;
    ensureMermaidInitialized();
    var cleaned = normalizeMermaidSource(el.textContent || '');
    if (!cleaned) return;
    el.textContent = cleaned;
    if (!el.id) el.id = 'mermaid-embed-' + (++mermaidIdSeq);
    try {
        await mermaid.parse(cleaned);
    } catch (errParse) {
        showMermaidRenderError(el, cleaned, errParse);
        return;
    }
    try {
        await mermaid.run({ nodes: [el], suppressErrors: false });
        enhanceMermaidZoom(el);
    } catch (errRun) {
        showMermaidRenderError(el, cleaned, errRun);
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
    if (!root || !window.mermaid) return;
    ensureMermaidInitialized();
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

function normalizeExplicitMarkdownPathLinksInPlainText(text) {
    return String(text || '')
        .replace(/\`\\[([^\\]\\r\\n]+)\\]\\(([^)\\r\\n]+)\\)\`/g, '[$1]($2)')
        .replace(/\`\\[([^\\]\\r\\n]+)\\]\`\\(([^)\\r\\n]+)\\)/g, '[$1]($2)')
        .replace(/\\[([^\\]\\r\\n]+)\\]\`\\(([^)\\r\\n]+)\\)\`/g, '[$1]($2)')
        .replace(/\\[([^\\]\\r\\n]+)\\]\\(\`([^\`\\r\\n]+)\`\\)/g, '[$1]($2)')
        .replace(/\\[\`([^\`\\]\\r\\n]+)\`\\]\\(([^)\\r\\n]+)\\)/g, '[$1]($2)');
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
    if (typeof marked !== 'undefined' && !markedOptionsApplied) {
        markedOptionsApplied = true;
        try {
            marked.setOptions({ breaks: true, mangle: false, headerIds: false });
        } catch (e) { /* ignore */ }
    }
    return marked.parse(escapeMarkdownSingleTildes(encodeMarkdownWorkspacePathLinks(text)), { mangle: false, headerIds: false });
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

function toolCallDraftKey(parsed) {
    var ri = parsed && parsed.react_iter != null ? String(parsed.react_iter) : '';
    var idx = parsed && parsed.tool_call_index != null ? String(parsed.tool_call_index) : (parsed && parsed.index != null ? String(parsed.index) : '0');
    return ri + ':' + idx;
}

function findToolDraftRow(ctx, parsed) {
    var key = toolCallDraftKey(parsed);
    if (!key) return null;
    var body = getProcessBody(ctx);
    if (!body || typeof CSS === 'undefined' || !CSS.escape) return null;
    try { return body.querySelector('.feed-item.feed--tool[data-tool-draft-key="' + CSS.escape(key) + '"]'); } catch (e) { return null; }
}

function deltaDedupeKey(parsed, scope) {
    if (!parsed || parsed.delta_seq == null) return '';
    var ds = Number(parsed.delta_seq);
    if (!Number.isFinite(ds) || ds <= 0) return '';
    var ss = Number(parsed.stream_seq || 0);
    var ri = parsed.react_iter != null ? String(parsed.react_iter) : '';
    var part = String(scope || parsed.type || '');
    var id = String(parsed.tool_call_id || parsed.id || parsed.index || parsed.tool_call_index || '');
    return part + ':' + (Number.isFinite(ss) ? Math.floor(ss) : 0) + ':' + ri + ':' + id + ':' + Math.floor(ds);
}

function hasSeenStreamDelta(ctx, parsed, scope) {
    if (!ctx) return false;
    var key = deltaDedupeKey(parsed, scope);
    if (!key) return false;
    if (!ctx._seenStreamDeltaKeys) ctx._seenStreamDeltaKeys = new Set();
    if (ctx._seenStreamDeltaKeys.has(key)) return true;
    ctx._seenStreamDeltaKeys.add(key);
    return false;
}

function setToolRowText(row, text, ctx, runSessionId) {
    if (!row) return;
    var sc = row.querySelector('.feed-chunk-scroller');
    if (sc) sc.textContent = truncateLogTextForUi(text);
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
    var body = getProcessBody(ctx);
    if (!body) return;
    var tempStatuses = body.querySelectorAll('[data-temporary-status="1"]');
    tempStatuses.forEach(function(el) {
        var row = el.closest ? el.closest('.feed-item') : null;
        if (row) row.remove(); else el.remove();
    });
}

function appendToolCallDelta(ctx, parsed, runSessionId) {
    if (hasSeenStreamDelta(ctx, parsed, 'tool_call_delta')) return;
    var key = toolCallDraftKey(parsed);
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
    var body = getProcessBody(ctx);
    if (!body) return;
    var iter = ev && ev.react_iter != null && Number.isFinite(Number(ev.react_iter))
        ? Math.max(1, Math.floor(Number(ev.react_iter)))
        : null;
    var rows = body.querySelectorAll('.feed-item.feed--tool[data-tool-draft-key], .feed-item.feed--tool[data-tool-pending="1"]');
    rows.forEach(function (row) {
        if (iter != null) {
            var rowIter = Number(row.getAttribute('data-react-iter'));
            if (!Number.isFinite(rowIter) || Math.floor(rowIter) !== iter) return;
        }
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
        if ((k === 'content' || k === 'contents') && typeof v === 'string' && v.length > 240) v = '<' + v.length + ' chars>';
        return j(k) + ': ' + j(v);
    }
    var preferred = ['path','target_directory','file_path','directory','root','command','args','url','start_line','end_line','pattern','query','search','replace','old_string','new_string','working_dir','timeout','temporary','content','contents'];
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
        draft.removeAttribute('data-tool-draft-key');
        draft.setAttribute('data-tool-pending', '1');
        draft.dataset.commandPreview = parsed.command_preview != null ? String(parsed.command_preview) : '';
        setToolRowText(draft, line, ctx, runSessionId);
        return;
    }
    var sc = createProcessFeedRow(ctx, 'tool-call', line, so, runSessionId, parsed.tool_call_id);
    var row = sc && sc.closest ? sc.closest('.feed-item') : null;
    if (row) {
        row.setAttribute('data-tool-pending', '1');
        row.dataset.commandPreview = parsed.command_preview != null ? String(parsed.command_preview) : '';
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
    if (sc) sc.textContent = truncateLogTextForUi(text);
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
    var text = formatToolDoneLine(parsed.tool, parsed.args, parsed.result, cmdPreview);
    if (row) {
        if (tid) row.setAttribute('data-tool-call-id', tid);
        row.removeAttribute('data-tool-draft-key');
        row.removeAttribute('data-tool-pending');
        row.dataset.commandPreview = cmdPreview != null ? String(cmdPreview) : '';
        var sc = row.querySelector('.feed-chunk-scroller');
        if (sc) sc.textContent = truncateLogTextForUi(text);
        var ch = row.querySelector('.feed-chunk');
        if (ch) refreshFeedChunkOverflow(ch);
        var agg = body.closest('.process-aggregate');
        refreshAggregateStatsSmart(agg);
        if (!replayingMessages) scrollContentAreaIfFollow(ctx, runSessionId);
        return;
    }
    var ri = uiEventReactIter(parsed);
    appendLog(ctx, text, 'tool-call', runSessionId, ri);
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
    if (toolCallIdOpt != null && String(toolCallIdOpt) !== '') row.setAttribute('data-tool-call-id', String(toolCallIdOpt));
    row.innerHTML = '<div class="feed-row">'
        + '<span class="feed-label">' + meta.label + '</span>'
        + '<div class="feed-chunk">'
        + '<div class="feed-chunk-scroller"></div></div></div>';
    const chunk = row.querySelector('.feed-chunk');
    const sc = row.querySelector('.feed-chunk-scroller');
    var txtForUi = initialText;
    if (type === 'llm-reasoning' || type === 'llm-response') txtForUi = trimSurroundingBlankLines(txtForUi);
    sc.textContent = truncateLogTextForUi(txtForUi);
    if (streamOpts.streaming && (type === 'llm-reasoning' || type === 'llm-response')) {
        chunk.classList.add('is-streaming');
        row.setAttribute('data-llm-live-row', '1');
    }
    bindFeedChunkInteraction(chunk);
    bindFeedChunkScrollChain(sc);
    body.appendChild(row);
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
        row.setAttribute('data-react-iter', String(ri));
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
        l.llmPendingReasoningDelta = (l.llmPendingReasoningDelta || '') + pieceText;
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
        l.llmPendingResponseDelta = (l.llmPendingResponseDelta || '') + pieceText;
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
    var txt = truncateLogTextForUi(trimSurroundingBlankLines(String(content || '')));
    if (!txt.trim()) return null;
    var existing = findExistingLlmFeedRow(ctx, logType, ri);
    if (existing) {
        var sc = existing.querySelector('.feed-chunk-scroller');
        var ch = existing.querySelector('.feed-chunk');
        if (sc) sc.textContent = txt;
        if (ch) {
            ch.classList.remove('is-streaming');
            scheduleFeedChunkOverflowRefresh(ch);
        }
        existing.removeAttribute('data-llm-live-row');
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
    if (reactIter != null) selector += '[data-react-iter="' + reactIter + '"]';
    else selector += '[data-llm-live-row="1"]';
    if (opts.liveOnly) selector += '[data-llm-live-row="1"]';
    var roots = [];
    if (ctx.currentProcessGroup && ctx.currentProcessGroup.isConnected) roots.push(ctx.currentProcessGroup);
    if (!replayingMessages && ctx.stream && ctx.stream.querySelectorAll) roots.push(ctx.stream);
    for (var r = 0; r < roots.length; r += 1) {
        var matches = roots[r].querySelectorAll(selector);
        if (matches && matches.length) return matches[matches.length - 1];
    }
    return null;
}

function removeDuplicateLlmFeedRows(ctx, keepRow, logType, reactIter) {
    if (!ctx || !ctx.stream || !ctx.stream.querySelectorAll || !keepRow) return;
    var selector = '.feed-item[data-log-type="' + logType + '"]';
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
            sum.textContent = buildUserMessageSummary(rawStr);
            linkifyAssistantTextNodes(sum);
            // 完整
            var ful = document.createElement('div');
            ful.className = 'user-msg-full';
            ful.textContent = rawStr;
            linkifyAssistantTextNodes(ful);
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
    }
        else {
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
        if (ctx.currentProcessGroup && ctx.currentProcessGroup.isConnected) {
            ctx.currentProcessGroup.classList.add('is-collapsed');
            const ttop = ctx.currentProcessGroup.querySelector('.process-aggregate-top');
            if (ttop) ttop.setAttribute('aria-expanded', 'false');
            updateProcessBrief(ctx.currentProcessGroup);
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

function bindFeedChunkInteraction(ch) {
    ch.removeEventListener('click', handleTraceChunkClick);
    ch.addEventListener('click', handleTraceChunkClick);
}

function bindExistingLogs(root) {
    const el = root || getVisibleChatStream() || chatContainer;
    if (!el) return;
    el.querySelectorAll('.feed-chunk').forEach(function (ch) {
        bindFeedChunkInteraction(ch);
        scheduleFeedChunkOverflowRefresh(ch);
        const sc = ch.querySelector('.feed-chunk-scroller');
        if (sc) bindFeedChunkScrollChain(sc);
    });
    el.querySelectorAll('.process-aggregate').forEach(function (agg) {
        bindProcessAggregate(agg);
        if (agg.classList.contains('is-collapsed')) updateProcessBrief(agg);
        refreshAggregateStatsSmart(agg);
    });
    el.querySelectorAll('.process-aggregate-brief').forEach(bindProcessBriefScrollChain);
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
    var prev = String(sc.textContent || '').trim();
    if (prev.indexOf(content) < 0) {
        sc.textContent = truncateLogTextForUi(prev ? (prev + '\\n' + content) : content);
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
        var merged = (st.scroller.textContent || '') + st.pending;
        st.scroller.textContent = truncateLogTextForUi(merged);
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
    var prevTxt = sc.textContent || '';
    var merged;
    if (hadStream) {
        merged = prevTxt.slice(0, bodyOffset).replace(/\\s+$/, '') + '\\n\\n' + text;
    } else if (prevTxt.trim()) {
        merged = prevTxt.trim() + '\\n\\n' + text;
    } else {
        merged = text;
    }
    sc.textContent = truncateLogTextForUi(merged);
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
        var head = (sc.textContent || '').trim();
        var bodyOffset = sc.textContent.length;
        if (head) {
            sc.textContent = head + '\\n\\n';
            bodyOffset = sc.textContent.length;
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
        var prevTxt = prev.textContent || '';
        prev.textContent = truncateLogTextForUi(prevTxt ? (prevTxt + '\\n' + line) : line);
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
    sc.textContent = truncateLogTextForUi(line);
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
`,He=`var subagentPanelOpen = false;
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
`,je=`function renderEvent(ctx, event, eventIndex, runSessionId) {\r
    if (!event || typeof event !== 'object') return;\r
    var eventSessionId = runSessionId || currentSessionId || '';\r
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
    } else if (event.type === 'user_steer') {\r
        appendLog(ctx, event.content || '', 'user-steer', runSessionId);\r
    } else if (event.type === 'final') {\r
        var finalStream = ctx && ctx.stream ? ctx.stream : getVisibleChatStream();\r
        var userIdx = (ctx && Number.isFinite(Number(ctx.lastUserEventIndex))) ? Number(ctx.lastUserEventIndex) : latestVisibleUserEventIndex(finalStream);\r
        if (typeof hasDuplicateVisibleFinal === 'function' && hasDuplicateVisibleFinal(finalStream, userIdx, event.content)) return;\r
        if (typeof splitThinkTagsForUi === 'function') {\r
            var finalThinkSplit = splitThinkTagsForUi(event.content || '');\r
            if (finalThinkSplit.reasoning && finalThinkSplit.reasoning.trim()) {\r
                upsertLlmFeedRow(ctx, finalThinkSplit.reasoning, 'llm-reasoning', runSessionId, uiEventReactIter(event));\r
            }\r
        }\r
        appendMessage(ctx, 'assistant', event.content || '', {\r
            eventIndex: eventIndex,\r
            turnTruncateIdx: ctx.lastUserEventIndex,\r
            runtimeSeq: event.runtime_seq || event.runtimeSeq,\r
            runtimeEventType: event.runtime_event_type || event.runtimeEventType,\r
            truncateBeforeSeq: ctx.lastUserRuntimeSeq,\r
        }, runSessionId);\r
    } else if (event.type === 'process_metrics') {\r
        applyProcessMetricsFromEvent(ctx, event);\r
    } else if (event.type === 'cache_stats') {\r
        applyCacheStatsFromEvent(ctx, event, runSessionId);\r
    } else if (event.type === 'tool_call') {\r
        var riTool = uiEventReactIter(event);\r
        if (event.raw_content) appendLog(ctx, event.raw_content, 'tool-call', runSessionId, riTool);\r
        else appendLog(ctx, formatToolDoneLine(event.tool, event.args, event.result, event.command_preview), 'tool-call', runSessionId, riTool);\r
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
        var statusRow = appendLog(ctx, statusContent, 'status', runSessionId);\r
        if (isTemporaryStatus && statusRow) {\r
            statusRow.dataset.temporaryStatus = '1';\r
        }\r
    } else if (event.type === 'approval_required') {\r
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
`,We=`\uFEFFfunction setSendButtonState() {\r
    sendBtn.disabled = false;\r
    if (isSessionRunning(currentSessionId)) {\r
        const run = typeof getSessionRunState === 'function' ? getSessionRunState(currentSessionId) : null;
        const suppressFollowup = !!(run && run.suppressFollowupButton);
        const hasDraft = (typeof inputHasSendableText === 'function')
            ? inputHasSendableText()\r
            : !!(messageInput && String(messageInput.value || '').trim());\r
        const followupEnabled = (typeof isMyAgentFeatureEnabled === 'function') && isMyAgentFeatureEnabled('followupRestart', false);\r
        sendBtn.innerHTML = (followupEnabled && hasDraft && !suppressFollowup) ? '追问' : '停止 <span class="loader" aria-hidden="true"></span>';
        sendBtn.classList.add('is-stop');\r
        sendBtn.classList.toggle('is-followup', followupEnabled && hasDraft && !suppressFollowup);
    } else {\r
        sendBtn.textContent = '发送';\r
        sendBtn.classList.remove('is-stop');\r
        sendBtn.classList.remove('is-followup');\r
    }\r
}\r
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
function pauseCurrentRun() {\r
    if (!currentSessionId) return;\r
    const run = getSessionRunState(currentSessionId);\r
    const sid = currentSessionId;\r
    const activeInfo = sessionStore.getActiveRunInfo(sid) || {};\r
    const runId = run && run.runId ? run.runId : (activeInfo.run_id || activeInfo.runId || '');\r
    suppressSessionServerStreamActive(sid);\r
    if (!run) {\r
        setSendButtonState();\r
        syncSessionListIndicatorClasses();\r
        renderSessionListIfChanged(false);\r
        void requestInterrupt(sid, runId);\r
        setTimeout(function () { reconcileRunStateFromServer({ silent: true, respectStopSuppress: true }); }, 3000);\r
        return;\r
    }\r
    const ctx = run.ctx;\r
    /* 先同步 abort 本地 fetch 与从 sessionStore 摘除，UI 立即反映「已停止」状态；\r
       后端 interrupt 走 fire-and-forget，避免被主线程阻塞时按钮响应卡顿。*/\r
    abortSessionRun(sid, 'user');\r
    setSendButtonState();\r
    syncSessionListIndicatorClasses();\r
    renderSessionListIfChanged(false);\r
    appendLog(ctx, '已请求停止当前任务', 'status', sid);\r
    sealProcessGroup(ctx);\r
    void requestInterrupt(sid, runId);\r
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
function syncSessionListIndicatorClasses() {\r
    if (!sessionsList) return;\r
    sessionsList.querySelectorAll('.session-item').forEach(function (div) {\r
        var el = div.querySelector('.session-name[data-id]');\r
        if (!el) return;\r
        var sid = el.getAttribute('data-id');\r
        div.classList.toggle('active', !!sid && sid === currentSessionId);\r
        applySessionItemIndicators(div, sid);\r
    });\r
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
function buildAndBindSessionRow(sess, allSessions, nextStreamMap) {\r
    const div = document.createElement('div');\r
    div.className = 'session-item';\r
    div.dataset.sessionId = sess.id || '';\r
    if (currentSessionId === sess.id) div.classList.add('active');\r
    if (sess.id) nextStreamMap[sess.id] = !!sess.stream_active;\r
    div.innerHTML = '<div class="session-item-head">'\r
        + '<span class="session-name" data-id="' + sess.id + '" data-original="' + escapeHtml(sess.name) + '">' + escapeHtml(sess.name) + '</span>'\r
        + '<div class="session-more-wrap">'\r
        + '<button type="button" class="session-more-btn" aria-label="更多操作" aria-expanded="false" aria-haspopup="true" data-ui-tip="更多">'\r
        + '<span class="session-more-dots" aria-hidden="true"><span></span><span></span><span></span></span></button>'\r
        + '<div class="session-more-menu" role="menu">'\r
        + '<button type="button" class="session-menu-pin" role="menuitem"></button>'\r
        + '<button type="button" class="session-menu-delete" role="menuitem">删除</button>'\r
        + '<button type="button" class="session-menu-archive" role="menuitem"></button>'\r
        + '</div></div>'\r
        + '</div>'\r
        + '<div class="session-last-query"></div>';\r
    var pinMi = div.querySelector('.session-menu-pin');\r
    var archMi = div.querySelector('.session-menu-archive');\r
    if (pinMi) pinMi.textContent = sess.pinned ? '取消置顶' : '置顶';\r
    if (archMi) archMi.textContent = sess.archived ? '取消归档' : '归档';\r
    var wsLine = formatSessionListSubtitle(sess);\r
    var wsEl = div.querySelector('.session-last-query');\r
    if (wsEl) {\r
        wsEl.textContent = wsLine;\r
        wsEl.setAttribute('data-ui-tip', wsLine);\r
        bindUiHoverTip(wsEl);\r
    }\r
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
            const nextSession = sessionStore.list().find(function (s) {\r
                return s && s.id && String(s.id) !== deletedSessionId && !s.archived;\r
            }) || null;\r
            sessionStore.markDeletedSession(deletedSessionId);\r
            if (wasArchivedLoaded) {\r
                sessionStore.setArchivedLoaded((sessionStore.archivedSessions || []).filter(function (s) {\r
                    return s && String(s.id) !== deletedSessionId;\r
                }));\r
                syncArchivedSessionStateFromStore();\r
            }\r
            renderSessionListIfChanged(true);\r
            if (div && div.parentNode) div.remove();\r
            sessionUnreadComplete.delete(deletedSessionId);\r
            persistSessionUnread();\r
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
            void requestInterrupt(deletedSessionId);\r
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
            } else nameSpan.innerText = nameSpan.dataset.original;\r
        });\r
        nameSpan.addEventListener('keydown', function (e) { if (e.key === 'Enter') { e.preventDefault(); nameSpan.blur(); } });\r
    }\r
    applySessionItemIndicators(div, sess.id, { serverStreamActive: !!sess.stream_active });\r
    return div;\r
}\r
\r
async function refreshSingleSessionRow(sessionId) {\r
    if (!sessionId || !sessionsList) return;\r
    try {\r
        const response = await fetch('/sessions/' + encodeURIComponent(sessionId));\r
        if (!response.ok) return;\r
        const sess = await response.json();\r
        if (!sess || !sess.id) return;\r
        applySessionPatch({\r
            session: sess,\r
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
        }\r
        renderSessionListIfChanged(false);\r
    } catch (e) {\r
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
function computeSessionListRenderKey() {\r
    const sessions = sessionStore.list();\r
    const parts = [\r
        'cur=' + String(currentSessionId || ''),\r
        'archivedLoaded=' + (sessionStore.archivedLoaded ? '1' : '0'),\r
        'archivedCount=' + String(sessionStore.archivedCount || 0),\r
    ];\r
    for (let i = 0; i < sessions.length; i += 1) {\r
        const s = sessions[i];\r
        if (!s || !s.id) continue;\r
        parts.push([\r
            s.id,\r
            s.name || '',\r
            s.pinned ? 'p' : '',\r
            s.archived ? 'a' : '',\r
            s.stream_active ? 'r' : '',\r
            s.unread_result ? ('u:' + (s.unread_result_status || 'success')) : '',\r
            s.last_activity_at || s.updated_at || '',\r
            s.last_user_preview || '',\r
            s.subagent_running || 0,\r
            s.subagent_pending_continue || 0,\r
            s.subagent_can_continue ? 'c' : '',\r
        ].join('\\u001f'));\r
    }\r
    const archived = sessionStore.archivedList();\r
    for (let j = 0; j < archived.length; j += 1) {\r
        const a = archived[j];\r
        if (!a || !a.id) continue;\r
        parts.push('arch=' + [\r
            a.id,\r
            a.name || '',\r
            a.pinned ? 'p' : '',\r
            a.unread_result ? ('u:' + (a.unread_result_status || 'success')) : '',\r
            a.last_activity_at || a.updated_at || '',\r
            a.last_user_preview || '',\r
        ].join('\\u001f'));\r
    }\r
    return parts.join('\\u001e');\r
}\r
\r
function renderSessionListIfChanged(force) {\r
    const nextKey = computeSessionListRenderKey();\r
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
function applyOptimisticSessionUpdate(sessionId, patch) {\r
    const sid = String(sessionId || '');\r
    const current = sessionStore.get(sid);\r
    if (!current) return null;\r
    const prev = Object.assign({}, current);\r
    const next = Object.assign({}, current, patch || {});\r
    if (Object.prototype.hasOwnProperty.call(patch || {}, 'pinned')) {\r
        next.pinned_at = next.pinned ? (next.pinned_at || new Date().toISOString()) : null;\r
    }\r
    sessionStore.upsert(next);\r
    if (prev.archived || next.archived) {\r
        const archivedList = (sessionStore.archivedSessions || []).filter(function (s) {\r
            return s && s.id !== sid;\r
        });\r
        if (next.archived && sessionStore.archivedLoaded) archivedList.unshift(next);\r
        if (sessionStore.archivedLoaded) {\r
            sessionStore.setArchivedLoaded(archivedList);\r
            syncArchivedSessionStateFromStore();\r
        }\r
    }\r
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
async function loadArchivedSessions(opts) {\r
    opts = opts || {};\r
    const loadEpoch = ++archivedSessionsLoadEpoch;\r
    try {\r
        const response = await fetchWithTimeout('/sessions?include_archived=true', {}, 15000);\r
        const sessions = await response.json();\r
        if (loadEpoch !== archivedSessionsLoadEpoch) return;\r
        const all = Array.isArray(sessions) ? sessions : [];\r
        sessionStore.setArchivedLoaded(all);\r
        syncArchivedSessionStateFromStore();\r
        renderSessionListIfChanged(!!opts.forceRender);\r
        clearSessionListError();\r
    } catch (err) {\r
        console.error('加载归档目录失败:', err);\r
        if (!opts.background) throw err;\r
    }\r
}\r
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
                    + '/history_snapshot?turns=' + encodeURIComponent(String(HISTORY_DIALOGUES_PER_PAGE));
                const snapshotResp = await fetchWithTimeout(snapshotUrl, {}, 15000);
                if (snapshotResp.ok) {
                    const snapshot = await snapshotResp.json();
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
                    }
                }
            } catch (snapshotErr) {
                console.warn('history snapshot unavailable, falling back to messages:', snapshotErr);
            }
        }
        if (!raw) {
            let url = '/sessions/' + encodeURIComponent(sessionId) + '/messages';
            if (!opts.full) url += '?turns=' + HISTORY_DIALOGUES_PER_PAGE;
            const response = await fetchWithTimeout(url, {}, 15000);
            if (!response.ok) throw new Error('messages failed: ' + response.status);
            raw = await response.json();
        }
        if (loadToken !== messageLoadEpoch || sessionId !== currentSessionId) return;
        if (getSessionRunState(sessionId) && !opts.allowDuringRun) return;\r
        document.getElementById('chat-loading')?.remove();\r
        if (!getVisibleChatStream()) ensureVisibleChatStreamSlot();\r
        const vis = getVisibleChatStream();\r
        if (vis) emptyChatStreamKeepingStrip(vis);\r
        else {\r
            chatContainer.innerHTML = '';\r
            ensureVisibleChatStreamSlot();\r
        }\r
        markVisibleSessionStreamLoadState(sessionId, 'loading');\r
        let events;\r
        let pageMeta = null;\r
        if (Array.isArray(raw)) {\r
            events = raw;\r
        } else if (raw && typeof raw === 'object' && Array.isArray(raw.events)) {\r
            events = raw.events;\r
            pageMeta = {\r
                total: Number(raw.total) || 0,\r
                range_start: Number(raw.range_start) || 0,\r
                range_end: Number(raw.range_end) || 0,\r
                has_older: !!raw.has_older,\r
            };\r
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
                range_start: pageMeta.range_start,\r
                range_end: pageMeta.range_end,\r
                has_older: !!pageMeta.has_older,\r
            });\r
            ensureHistorySentinel(getVisibleChatStream());\r
        }\r
        if (events.length === 0) {\r
            suppressTocDuringSessionLoad = false;\r
            setWelcome();\r
            updateSessionTitle();\r
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
        for (let evi = 0; evi < events.length; evi += 1) {\r
            const ev = events[evi];\r
            if (ev && typeof ev === 'object' && ev.type) {\r
                reduceAndRenderMessageEvent(loadCtx, ev, {\r
                    sessionId: sessionId,\r
                    eventIndex: indexBase + evi,\r
                    source: 'history',\r
                });\r
            }\r
            if (evi > 0 && evi % batchSize === 0) {\r
                await new Promise(function (resolve) { setTimeout(resolve, 0); });\r
                if (loadToken !== messageLoadEpoch || sessionId !== currentSessionId) return;\r
            }\r
        }\r
        if (!opts.full && opts.preloadOlderIfShort && pageMeta && pageMeta.has_older && events.length <= 2) {\r
            await loadOlderHistoryChunk({ keepTocStable: true });\r
            if (loadToken !== messageLoadEpoch || sessionId !== currentSessionId) return;\r
        }\r
        if (historyLoadScrollsToBottom(sessionId, scrollBehavior)) {\r
            tocScrollBottomOnNextBuild = true;\r
        }
        suppressTocDuringSessionLoad = false;
        if (snapshotTocTurns) rebuildToc({ turns: snapshotTocTurns });
        else if (!opts.tocAlreadyStarted) rebuildToc();
        updateSessionTitle();\r
        updateHistorySentinelVisibility();\r
        applyChatScrollAfterHistoryLoad(sessionId, scrollBehavior);\r
        await waitForChatScrollAfterHistoryLoad(sessionId, scrollBehavior);\r
        if (loadToken !== messageLoadEpoch || sessionId !== currentSessionId) return;\r
        bindExistingLogs();
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
    } catch (error) {\r
        console.error('加载会话消息失败:', error);\r
        document.getElementById('chat-loading')?.remove();\r
        appendLogVisible('加载历史消息失败', 'error-log');\r
        markVisibleSessionStreamLoadState(sessionId, 'failed');\r
        showSessionLoadRetry(sessionId);\r
        return false;\r
    } finally {\r
        if (loadToken === messageLoadEpoch) sessionStore.ui.loadingMessages = false;\r
        if (loadToken === messageLoadEpoch) suppressTocDuringSessionLoad = false;\r
        if (loadToken === messageLoadEpoch) replayingMessages = false;\r
    }
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
        'open_session_timing session=%s source=%s total=%sms events=%s backend_total=%sms read_page=%sms count=%sms user_turns=%sms',
        sessionId,
        data.source || 'unknown',
        frontendTotal,
        Number(data.events || 0),
        backendTotal,
        Number(timing.read_page || 0),
        Number(timing.count || 0),
        Number(timing.user_turns || 0)
    );
}

function beforeSessionMessageSnapshotAvailable() {
    return true;
}

async function switchSession(sessionId, opts) {
    opts = opts || {};\r
    if (currentSessionId === sessionId && !opts.forceReload) return;\r
    if (opts.forceReload && typeof discardCachedSessionStream === 'function') discardCachedSessionStream(sessionId);\r
    const switchToken = ++switchSessionEpoch;\r
    suppressTocDuringSessionLoad = true;\r
    clearTocForSessionLoad();\r
    clearTodoForSessionLoad();\r
    pendingRewriteTruncate = null;\r
    hideRewriteUndoToast();\r
    clearSessionUnreadState(sessionId);\r
    const leaving = currentSessionId;
    saveChatScrollForSession(leaving);
    stashInputDraft(leaving);
    if (typeof stashSkillPickerDraft === 'function') stashSkillPickerDraft(leaving);
    prepareStashLeaving(leaving);
    hideSubagentContinueBanner();\r
    resetSubagentPanelForSession();
    setCurrentSessionState(sessionId);
    localStorage.setItem('lastSessionId', sessionId);
    if (typeof applyContextTokenLabelForCurrentSession === 'function') applyContextTokenLabelForCurrentSession();
    restoreInputDraft(sessionId);
    if (typeof restoreSkillPickerDraft === 'function') restoreSkillPickerDraft(sessionId);
    if (typeof renderFollowupQueue === 'function') renderFollowupQueue(sessionId);
    if (typeof refreshModelProfileSelector === 'function') refreshModelProfileSelector(sessionId);\r
    syncSessionListIndicatorClasses();\r
    setSendButtonState();\r
    var restoredFromCache = false;\r
    if (!opts.forceReload && (restoreStreamForRunningSession(sessionId) || (restoredFromCache = restoreCachedSessionStream(sessionId)))) {\r
        suppressTocDuringSessionLoad = false;\r
        hideLoading();\r
        rebuildToc();\r
        updateSessionTitle();
        scheduleContextTokensAfterPaint(sessionId);
        if (restoredFromCache) restoreCachedSessionScrollPosition(sessionId);
        else applyChatScrollAfterHistoryLoad(sessionId, 'saved-or-bottom');
        if (typeof refreshTodoPlanPanel === 'function') void refreshTodoPlanPanel();
        else renderTodoPlanForCurrentSession();
        if (switchToken !== switchSessionEpoch || sessionId !== currentSessionId) return;
        /* 让 rebuildToc 的 /user_turns fetch 先发出，subagent 面板（含 N 个 /messages）顺序后置，\r
           避免抢占带宽与主线程，让目录最后才稳态。*/\r
        setTimeout(function () { refreshSubagentTreePanel(sessionId); }, 0);\r
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
            var loadedOk = await loadSessionMessages(sessionId, undefined, {\r
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
        setTimeout(function () { refreshSubagentTreePanel(sessionId); }, 0);\r
        void refreshSingleSessionRow(sessionId);\r
        setSendButtonState();\r
        maybeStartStreamPollForSession(sessionId, { skipInitialLoad: true });\r
        resolve(true);\r
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
        setCurrentSessionState(data.session_id);\r
        localStorage.setItem('lastSessionId', currentSessionId);
        restoreInputDraft(currentSessionId);
        if (typeof restoreSkillPickerDraft === 'function') restoreSkillPickerDraft(currentSessionId);
        if (typeof renderFollowupQueue === 'function') renderFollowupQueue(currentSessionId);
        if (typeof refreshModelProfileSelector === 'function') refreshModelProfileSelector(currentSessionId);\r
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
`,ze=`const SSE_IDLE_TIMEOUT_MS = 45000;

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
    finalizeLlmStreamChunks(ctx);
    finalizeProgressStreamChunks(ctx);
    if (opts.reconcileFinal !== false) {
        scheduleFinalVisibleAfterRunIfEnabled(sid, ctx, { delayMs: opts.finalDelayMs != null ? opts.finalDelayMs : 80 });
    }
    sealProcessGroup(ctx);
    markSessionRunInactive(sid);
    if (getSessionRunState(sid)) {
        clearSessionRunStateIfMatch(sid, opts.runId || (ctx && ctx.runId));
    }
    syncSessionListIndicatorClasses();
    setSendButtonState();
    if (sid === currentSessionId) renderTodoPlanForCurrentSession();
    if (opts.drainFollowup !== false) scheduleFollowupQueueDrain(sid, opts.followupDelayMs || 0);
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
                timer = setTimeout(function () {
                    var err = new Error('SSE idle timeout after ' + String(timeoutMs) + 'ms');
                    err.name = 'SseIdleTimeout';
                    try { reader.cancel(err).catch(function () { /* ignore */ }); } catch (e) { /* ignore */ }
                    reject(err);
                }, timeoutMs);
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
                endRunForClient(runSessionId, runCtx, { finalDelayMs: 80, followupDelayMs: 0 });
                return streamEventIdx;
            }
            try {
                let parsed = JSON.parse(data);
                if (parsed && (parsed.type === 'sse_keepalive' || parsed.keepalive === true)) continue;
                if (parsed && parsed.protocol === 'runtime_v2') {
                    const envelopeSessionId = parsed.session_id || parsed.sessionId || runSessionId;
                    if (!sessionStore.shouldAcceptSseEvent(envelopeSessionId, parsed.seq)) continue;
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
                if (shouldApplySseSeqFilter(parsed) && !sessionStore.shouldAcceptSseEvent(eventSessionId, parsed.seq)) continue;
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
                        endRunForClient(eventSessionId, runCtx, {
                            finalDelayMs: 80,
                            followupDelayMs: 0,
                            runId: parsed.run_id || parsed.runId || (runCtx && runCtx.runId),
                            reconcileFinal: parsed.type === 'run_finished',
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
                        discardLlmStreamChunks(runCtx, parsed);
                        removeAbortedToolDraftRows(runCtx, parsed);
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
                    if (parsed.type === 'tool_pending') continue;
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
        const preCount = await getUiEventCount(runSessionId, { preferCache: true });
        if (!getVisibleChatStream()) ensureVisibleChatStreamSlot();
        runCtx = newDomContext(getVisibleChatStream());
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
                console.error('续接 subagent 失败:', error);
                const msg = (error && error.message) ? String(error.message) : String(error);
                appendLog(runCtx, '续接失败: ' + msg, 'error-log', runSessionId);
            }
        } finally {
            finalizeLlmStreamChunks(runCtx);
            finalizeProgressStreamChunks(runCtx);
            if (runSessionId === currentSessionId && getRunAbortReason(runSessionId, runCtx) !== 'user') {
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
        }
        hideSubagentContinueBanner();
        if (!subagentContinueDismissedForSession[sessionId]) updateSubagentContinueBanner(sessionId);
    } finally {
        subagentContinueInFlight = false;
    }
}

function nowPipelineMs() {
    return (typeof performance !== 'undefined' && performance.now) ? performance.now() : Date.now();
}

function isClientPipelineTerminalStep(label, step) {
    var s = String(step || '');
    var l = String(label || '');
    if (l.indexOf('client_send_pipeline') >= 0) {
        return s === 'release_send_lock_and_schedule_followup';
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
    if (!runtimeEvent || runtimeEvent.type !== 'message_user') return;
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
        console.error('reattach stream failed:', error);
        const msg = (error && error.message) ? String(error.message) : String(error);
        if (runCtx && runSessionId === currentSessionId) appendLog(runCtx, '恢复实时流失败: ' + msg, 'error-log', runSessionId);
    } finally {
        if (runCtx) {
            finalizeLlmStreamChunks(runCtx);
            finalizeProgressStreamChunks(runCtx);
        }
        if (runSessionId === currentSessionId && getRunAbortReason(runSessionId, runCtx) !== 'user') {
            scheduleFinalVisibleAfterRunIfEnabled(runSessionId, runCtx, { delayMs: 120 });
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

function scheduleActiveSessionReconnect(sessionId, opts) {
    if (!isMyAgentFeatureEnabled('streamReconnect', true)) return;
    opts = opts || {};
    var sid = String(sessionId || '');
    if (!sid) return;
    var delayMs = Math.max(0, Number(opts.delayMs) || 0);
    setTimeout(async function () {
        if (sid !== currentSessionId) return;
        try {
            if (typeof reconcileRunStateFromServer === 'function') {
                await reconcileRunStateFromServer({ silent: true });
            }
            if (sid !== currentSessionId) return;
            if ((isServerStreamActive(sid) || isSessionRunning(sid)) && typeof maybeStartStreamPollForSession === 'function') {
                maybeStartStreamPollForSession(sid, { skipInitialLoad: true });
            }
        } catch (e) {
            /* keep current UI state; normal polling or user action can retry later */
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
    var skills = Array.isArray(item.skills)
        ? item.skills.map(function (skill) { return String(skill || '').trim(); }).filter(Boolean)
        : [];
    return {
        id: item.id || ('stored-followup-' + (followupQueueSeq++)),
        text: text,
        display: display || text,
        skills: skills,
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
            skills: Array.isArray(item.skills) ? item.skills : [],
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
        sendNow.disabled = !!item.status || idx !== 0;
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
    if (status === 'accepted') return '已接收，等待插入';
    if (status === 'sending') return '发送中';
    if (status === 'sent') return '已发送';
    return '待发送';
}

function enqueueCurrentInputAsFollowup() {
    if (!isMyAgentFeatureEnabled('followupRestart', false)) return false;
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
    getFollowupQueue(sid).push({
        id: followupQueueSeq++,
        text: rawMessage,
        display: visibleMessage,
        skills: selectedSkills,
        createdAt: Date.now(),
    });
    persistFollowupQueue(sid);
    messageInput.value = '';
    persistInputDraft(sid, '');
    clearInputPathTokens();
    autoResizeTextarea();
    renderFollowupQueue(sid);
    setSendButtonState();
    scheduleFollowupQueueDrain(sid, 0);
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

async function sendSteerMessage(sessionId, text, clientId, selectedSkills, uiContent) {
    var r = await fetch('/sessions/' + encodeURIComponent(sessionId) + '/steer', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: text, client_id: clientId || '', selected_skills: selectedSkills || [], ui_content: uiContent || text }),
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
    scheduleFollowupQueueDrain(sid, 0);
    return true;
}

function scheduleFollowupQueueDrain(sessionId, delayMs) {
    const sid = String(sessionId || '');
    if (!sid) return;
    setTimeout(function () { drainFollowupQueue(sid); }, Math.max(0, Number(delayMs) || 0));
}

function scheduleAcceptedFollowupWatch(sid, itemId) {
    setTimeout(function () {
        var queued = getFollowupQueue(sid).find(function (entry) {
            return String(entry.id) === String(itemId);
        });
        if (!queued || queued.status !== 'accepted') return;
        refreshFollowupRunState(sid).finally(function () {
            var latest = getFollowupQueue(sid).find(function (entry) {
                return String(entry.id) === String(itemId);
            });
            if (!latest || latest.status !== 'accepted') return;
            if (isSessionRunning(sid) || isServerStreamActive(sid)) {
                scheduleActiveSessionReconnect(sid, { delayMs: 0 });
                scheduleActiveSessionReconnect(sid, { delayMs: 1200 });
            }
        });
    }, 1200);
}

async function sendFollowupNow(itemId, sessionId) {
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
    if (idx !== 0) return;
    if (item.status === 'submitting' || item.status === 'accepted' || item.status === 'sent' || item.status === 'withdrawing') {
        return;
    }
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
        var steerResult = await sendSteerMessage(sid, item.text, item.clientId, item.skills || [], item.display || item.text);
        item.steerInFlight = false;
        item.steerId = steerResult && steerResult.item && steerResult.item.id ? String(steerResult.item.id) : '';
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
            item.status = 'sent';
            persistFollowupQueue(sid);
            renderFollowupQueue(sid);
            setSendButtonState();
            syncSessionListIndicatorClasses();
            setTimeout(function () {
                takeFollowupItem(sid, itemId);
                renderFollowupQueue(sid);
            }, 1200);
            reportClientPipelineStep(followupTimingCtx, 'followup_restart_takeover', _followupStepStart, {
                hadPreviousRun: !!previousRun
            });
            return sendMessage({
                message: item.text,
                displayMessage: item.display || item.text,
                selectedSkills: item.skills || [],
                fromQueue: true,
                sessionId: sid,
                forceStart: true,
                preserveInput: true,
                asSteer: true,
            });
        }
        item.status = 'accepted';
        persistFollowupQueue(sid);
        renderFollowupQueue(sid);
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
                    var retrySteerResult = await sendSteerMessage(sid, item.text, item.clientId, item.skills || [], item.display || item.text);
                    item.steerInFlight = false;
                    item.steerId = retrySteerResult && retrySteerResult.item && retrySteerResult.item.id ? String(retrySteerResult.item.id) : '';
                    item.status = 'accepted';
                    persistFollowupQueue(sid);
                    renderFollowupQueue(sid);
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
    item.status = 'sent';
    persistFollowupQueue(sid);
    renderFollowupQueue(sid);
    setTimeout(function () {
        takeFollowupItem(sid, itemId);
        renderFollowupQueue(sid);
    }, 1200);
    reportClientPipelineStep(followupTimingCtx, 'followup_fallback_to_chat', followupTimingStartedAt);
    return sendMessage({ message: item.text, displayMessage: item.display || item.text, selectedSkills: item.skills || [], fromQueue: true, sessionId: sid, forceStart: true });
}

function drainFollowupQueue(sessionId) {
    const sid = String(sessionId || '');
    if (!sid || followupQueueDraining[sid]) return;
    if (sendPipelineLock && sendPipelineLockSessionId === sid) {
        scheduleFollowupQueueDrain(sid, 120);
        return;
    }
    var q = getFollowupQueue(sid);
    if (!q.length) {
        renderFollowupQueue(sid);
        return;
    }
    var item = q[0];
    if (!item || item.status) {
        renderFollowupQueue(sid);
        return;
    }
    followupQueueDraining[sid] = true;
    var attemptedId = String(item.id);
    Promise.resolve(sendFollowupNow(item.id, sid))
        .finally(function () {
            delete followupQueueDraining[sid];
            var q2 = getFollowupQueue(sid);
            var same = q2.find(function (entry) { return String(entry.id) === attemptedId; });
            if (!same && q2.length && !q2[0].status) {
                scheduleFollowupQueueDrain(sid, 0);
            }
        });
}

async function sendMessage(options) {
    options = options || {};
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
    if (sendPipelineLock && sendPipelineLockSessionId === submitSessionIdInitial && !options.forceStart) return;
    if (options.forceStart && submitSessionIdInitial) {
        var previousRun = getSessionRunState(submitSessionIdInitial);
        if (previousRun) abortSessionRun(submitSessionIdInitial, 'followup-restart');
    }
    var selectedSkillsForRun = [];
    if (Array.isArray(options.selectedSkills)) {
        selectedSkillsForRun = options.selectedSkills.map(function (skill) { return String(skill || '').trim(); }).filter(Boolean);
    } else if (!options.fromQueue && !options.fromInlineRewrite && typeof window.consumeSelectedSkillsForSend === 'function') {
        selectedSkillsForRun = window.consumeSelectedSkillsForSend();
    }
    var displayMessage = options.displayMessage != null ? String(options.displayMessage) : rawMessage;
    if (selectedSkillsForRun && selectedSkillsForRun.length) {
        displayMessage = displayMessage + '\\n\\n已选择 Skill：' + selectedSkillsForRun.join('、');
    }
    reportClientPipelineStep(clientTimingCtx, 'preflight_checks', _clientStepStart, {
        forceStart: !!options.forceStart,
        fromQueue: !!options.fromQueue,
        fromInlineRewrite: !!options.fromInlineRewrite,
        asSteer: !!options.asSteer
    });

    /* 立即上锁：阻止后续连击；锁的 key 是提交时的会话，而非当前会话。 */
    _clientStepStart = nowPipelineMs();
    sendPipelineLock = true;
    sendPipelineLockSessionId = submitSessionIdInitial;
    let submittedRunCtx = null;
    let submittedRunSessionId = submitSessionIdInitial;
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
        sendPipelineLockSessionId = submitSessionId;
    }
    clientTimingCtx.sessionId = submitSessionId || clientTimingCtx.sessionId;
    const runSessionId = submitSessionId;
    submittedRunSessionId = runSessionId;
    _clientStepStart = nowPipelineMs();
    const clientRunId = (window.crypto && window.crypto.randomUUID)
        ? window.crypto.randomUUID()
        : ('run-' + Date.now() + '-' + Math.random().toString(16).slice(2));
    clientTimingCtx.runId = clientRunId;
    const ac = new AbortController();
    if (typeof clearSessionStreamStopSuppress === 'function') clearSessionStreamStopSuppress(runSessionId);
    var optimisticRunState = { controller: ac, ctx: null, runId: clientRunId, optimistic: true, suppressFollowupButton: true };
    setSessionRunState(runSessionId, optimisticRunState);
    setSendButtonState();
    syncSessionListIndicatorClasses();
    reportClientPipelineStep(clientTimingCtx, 'prepare_client_run_id_and_optimistic_state', _clientStepStart);
    // 缓存过期时用轻量 count 校准，避免乐观 user index 和服务端 ui_events 分叉。
    _clientStepStart = nowPipelineMs();
    let preCount = await getUiEventCount(submitSessionId, { preferCache: true, maxAgeMs: 10000 });
    if (ac.signal.aborted || optimisticRunState.abortReason) return;
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
    applySessionEvent({ type: renderAsSteer ? 'user_steer' : 'user', content: displayMessage, created_at: userSentAt, steer: renderAsSteer }, {
        sessionId: runSessionId,
        eventIndex: preCount,
        source: 'local-send',
    });
    uiEventCountCache.updateFromServer(runSessionId, preCount + 1);
    if (!switchedAway) {
        liveAutoFollow = true;
        streamChatNearBottom = true;
        streamProcNearBottom = true;
        if (renderAsSteer) {
            appendLog(runCtx, displayMessage, 'user-steer', runSessionId);
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
    formData.append('ui_message', displayMessage);
    formData.append('session_id', runSessionId);
    formData.append('client_run_id', clientRunId);
    formData.append('stream_protocol', 'runtime_v2');
    if (selectedSkillsForRun && selectedSkillsForRun.length) {
        formData.append('selected_skills', JSON.stringify(selectedSkillsForRun));
    }
    if (renderAsSteer) formData.append('followup_steer', 'true');
    /* 发送后优先使用本轮 API usage/cache_stats 刷新 token；缺少 usage 时仍保留上一快照。 */
    if (!switchedAway) applyContextTokenLabelForCurrentSession();
    let streamEventIdx = preCount + 1;
    let streamDisconnectedUnexpectedly = false;
    try {
        reportClientPipelineStep(clientTimingCtx, 'build_form_data', _clientStepStart, { followupSteer: !!renderAsSteer });
        _clientStepStart = nowPipelineMs();
        const response = await fetch('/chat', { method: 'POST', body: formData, signal: ac.signal });
        reportClientPipelineStep(clientTimingCtx, 'fetch_chat_response_headers', _clientStepStart, { status: response && response.status });
        _clientStepStart = nowPipelineMs();
        streamEventIdx = await consumeAgentSseResponse(response, runCtx, runSessionId, streamEventIdx);
        reportClientPipelineStep(clientTimingCtx, 'consume_sse_until_done', _clientStepStart, { streamEventIdx: streamEventIdx });
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
            scheduleActiveSessionReconnect(runSessionId, { delayMs: 500 });
            scheduleActiveSessionReconnect(runSessionId, { delayMs: 2500 });
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
        reportClientPipelineStep(clientTimingCtx, 'finalize_visible_state', _clientStepStart, {
            disconnected: !!streamDisconnectedUnexpectedly,
            currentSession: runSessionId === currentSessionId
        });
    }
    } finally {
        _clientStepStart = nowPipelineMs();
        sendPipelineLock = false;
        sendPipelineLockSessionId = null;
        var stoppedByUser = getRunAbortReason(submittedRunSessionId, submittedRunCtx) === 'user'
            || (optimisticRunState && optimisticRunState.abortReason === 'user');
        if (!stoppedByUser && (!options.fromQueue || getFollowupQueue(submittedRunSessionId).length)) {
            setTimeout(function () { drainFollowupQueue(submittedRunSessionId); }, 0);
        }
        reportClientPipelineStep(clientTimingCtx, 'release_send_lock_and_schedule_followup', _clientStepStart, {
            stoppedByUser: !!stoppedByUser,
            fromQueue: !!options.fromQueue
        });
    }
}

messageInput.addEventListener('keydown', function onFollowupInputKeydown(e) {
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
        if (isMyAgentFeatureEnabled('followupRestart', false) && inputHasSendableText()) enqueueCurrentInputAsFollowup();
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
`,Ve=`newSessionBtn.addEventListener('click', async () => { await createNewSession(); });

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
`,Ge=[ve,he,be,ye,Ie,xe,we,Ce,ke,Te,_e,Ee,Le,Pe,Ae,Re,Fe,Me,Be,Ne,Oe,De,qe,Ue,He,je,We,ze,Ve];Function(`"use strict";
`+Ge.join(`

`)+`
//# sourceURL=myagent-ui.js`)();typeof initUiHoverTips=="function"&&initUiHoverTips(document);
