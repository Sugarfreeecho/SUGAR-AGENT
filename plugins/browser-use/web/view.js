export const markup = `
<header class="page-header"><div><div class="eyebrow">SUGARAGENT · BROWSER</div><h1>连接你的浏览器</h1><p>继续使用已登录的网页，把浏览器里的工作交给 Agent。<span id="extension-version" class="header-version" hidden></span></p></div><span id="overall" class="badge">正在检查</span></header>
<div class="progress" aria-label="连接进度"><span id="progress-bar"></span></div><p id="error" role="alert" hidden></p>
<ol class="steps">
<li class="step" id="step-service"><button class="step-heading" aria-expanded="true"><span class="number">1</span><span><strong>准备好本机服务</strong><small id="service-summary">检查插件与运行组件</small></span><span class="step-state" id="service-state">检查中</span><span class="chevron">⌄</span></button><div class="step-body">
<div class="check-row"><div><strong>SugarAgent 后端</strong><small id="backend-detail">正在检测服务版本…</small></div><button id="refresh" class="text-button">重新检测</button></div>
<div class="check-row"><div><strong>浏览器连接插件</strong><small id="plugin-detail">正在检查</small></div><button id="enable" hidden>启用插件</button><span id="plugin-ok" class="check" hidden>✓ 已启用</span></div>
<div class="check-row"><div><strong>运行组件</strong><small id="runtime-detail">正在检查</small></div><button id="install" hidden>安装运行组件</button><span id="runtime-ok" class="check" hidden>✓ 已就绪</span></div>
<div class="service-actions"><button id="restart" class="text-button">重启开发后端</button><small id="restart-note">首次更新后端后可在这里重启。</small></div>
<details class="advanced"><summary>高级信息</summary><div id="manual-runtime"><p>源码开发环境需要 Node.js 22.18 或更高版本。</p><code>cd plugins/browser-use/node<br>npm ci</code></div><p id="build-help" hidden>扩展尚未构建：在 browser-extension 目录运行 npm ci、npm run build 和 npm run package。</p></details>
<div class="step-actions"><button id="next-service" class="primary" disabled>继续加载扩展 →</button></div>
</div></li>
<li class="step" id="step-extension"><button class="step-heading" aria-expanded="false"><span class="number">2</span><span><strong>把扩展加载到浏览器</strong><small id="extension-summary">只需安装一次，Chrome 与 Edge 均可使用</small></span><span class="step-state" id="extension-state">待完成</span><span class="chevron">⌄</span></button><div class="step-body" hidden>
<div class="segmented" role="group" aria-label="选择浏览器"><button class="selected" id="chrome">Chrome</button><button id="edge">Edge</button></div>
<div class="instruction"><span>01</span><div><strong>进入扩展管理页，打开开发者模式</strong><div class="copy-field"><code id="browser-url">chrome://extensions</code><button data-copy="browser-url">复制地址</button></div><small>将地址粘贴到浏览器地址栏打开。</small></div></div>
<div class="instruction"><span>02</span><div><strong>选择「加载已解压的扩展程序」</strong><p>打开下方文件夹，选择整个 <code>dist</code> 目录。使用 ZIP 时，先解压再选择解压目录。</p><div class="button-row"><button id="reveal">打开扩展文件夹</button><a id="download" class="button" href="/api/browser/v1/setup/download" download>下载扩展 ZIP</a></div><div class="copy-field directory"><code id="directory">正在查找扩展目录…</code><button data-copy="directory">复制路径</button></div></div></div>
<div class="instruction"><span>03</span><div><strong>在工具栏固定 SugarAgent</strong><p>点击浏览器的扩展图标，固定 SugarAgent，再点击它打开侧栏。</p></div></div>
<div class="step-actions"><button id="loaded" class="primary">已加载扩展，继续配对 →</button></div>
</div></li>
<li class="step" id="step-pair"><button class="step-heading" aria-expanded="false"><span class="number">3</span><span><strong>配对，让两边连起来</strong><small id="pair-summary">在侧栏输入地址与一次性配对码</small></span><span class="step-state" id="pair-state">待配对</span><span class="chevron">⌄</span></button><div class="step-body" hidden>
<label class="field-label">本机服务地址</label><div class="copy-field"><code id="server-url"></code><button data-copy="server-url">复制地址</button></div>
<form id="pair"><label class="field-label" for="name">为这个浏览器起个名字</label><div class="form-row"><input id="name" value="我的浏览器" maxlength="100" placeholder="例如：工作 Chrome" required><button id="generate" class="primary">生成配对码</button></div></form>
<div class="pairing-code" id="code-panel" hidden><div><small>在 SugarAgent 侧栏中输入</small><output id="code" aria-live="polite"></output><span id="expiry"></span></div><button data-copy="code">复制配对码</button></div>
<p class="hint" id="pair-hint">打开侧栏，填写上方服务地址与配对码，点击「配对并连接」。这里会自动检测连接结果。</p>
</div></li>
<li class="step" id="step-ready"><button class="step-heading" aria-expanded="false"><span class="number">4</span><span><strong>准备开始</strong><small id="ready-summary">在侧栏继续会话，或从主程序发起网页任务</small></span><span class="step-state" id="ready-state">等待连接</span><span class="chevron">⌄</span></button><div class="step-body" hidden>
<div class="success-note"><span>✓</span><div><strong>浏览器与 Agent 已连通</strong><p>侧栏和主程序使用同一份会话。关闭侧栏后，任务仍会继续。</p></div></div>
<div class="prompt-sample"><small>可以从这个任务开始</small><p id="example">查看我打开的网页，整理关键内容，先不要修改页面。</p><button data-copy="example">复制这条任务</button></div><a href="/" target="_top" class="button primary">打开主程序 ↗</a>
</div></li>
</ol>
<section class="connections"><div class="section-heading"><div><h2>你的浏览器</h2><p>默认浏览器用于主程序新发起的任务。</p></div><button id="add-browser" class="text-button">＋ 添加浏览器</button></div><div id="devices"></div></section>
<div id="toast" role="status" hidden></div>
<dialog id="restart-dialog"><form method="dialog"><h2>重启开发后端</h2><p id="restart-impact">正在检查影响…</p><p class="hint">重启期间连接会暂时中断，页面会自动等待服务恢复。</p><div class="button-row"><button value="cancel">取消</button><button id="confirm-restart" type="button" class="primary">确认重启</button></div></form></dialog>
<dialog id="revoke-dialog"><form method="dialog"><h2>断开这个浏览器？</h2><p>此浏览器将无法继续操作网页，再次使用时需要重新配对。</p><div class="button-row"><button value="cancel">取消</button><button id="confirm-revoke" type="button" class="danger">撤销配对</button></div></form></dialog>
`;
