"use strict";

// Persistent newline-delimited JSON worker for MyAgent Plugin API v1.
const fs = require("fs");
const path = require("path");
const readline = require("readline");
const { pathToFileURL } = require("url");

const API_VERSION = "1";
const TOOL_NAME = /^[A-Za-z0-9_-]{1,64}$/;
const HOOK_EVENTS = new Set([
  "SessionStart", "SessionEnd", "UserPromptSubmit", "PreToolUse",
  "PostToolUse", "PostToolUseFailure", "Stop", "RunFailed",
  "SubagentStart", "SubagentStop", "PreCompact", "PostCompact",
  "GoalCreated", "GoalBeforeContinue", "GoalCompleted", "GoalBlocked",
]);
const FAILURE_POLICIES = new Set(["ignore", "warn", "block", "pause"]);
const protocolWrite = process.stdout.write.bind(process.stdout);
console.log = (...args) => console.error(...args);

function parseArgs(argv) {
  const result = {};
  for (let index = 0; index < argv.length; index += 2) {
    const key = argv[index];
    const value = argv[index + 1];
    if (!key || !key.startsWith("--") || value === undefined) {
      throw new Error("Invalid worker arguments");
    }
    result[key.slice(2)] = value;
  }
  return result;
}

class PluginRegistry {
  constructor() {
    this.tools = new Map();
    this.hooks = new Map();
    this.commands = new Map();
    this.activateHandlers = [];
    this.deactivateHandlers = [];
    this.deferredPollHandler = null;
    this.deferredCancelHandler = null;
    this.httpHandler = null;
    this.backgroundServices = new Map();
    this.backgroundTasks = new Map();
    this.backgroundStatus = new Map();
  }

  registerTool(spec, handler) {
    if (typeof spec === "string") {
      spec = { name: spec };
    }
    if (!spec || typeof spec !== "object") {
      throw new Error("Tool specification must be an object");
    }
    const name = String(spec.name || "").trim();
    if (!TOOL_NAME.test(name)) {
      throw new Error(
        "Tool name must use 1-64 ASCII letters, digits, underscores, or hyphens"
      );
    }
    if (this.tools.has(name)) {
      throw new Error(`Duplicate plugin tool: ${name}`);
    }
    if (typeof handler !== "function") {
      throw new Error(`Tool handler for ${name} must be a function`);
    }
    const inputSchema = spec.inputSchema || spec.input_schema || {
      type: "object",
      properties: {},
      additionalProperties: false,
    };
    if (!inputSchema || typeof inputSchema !== "object" || (inputSchema.type || "object") !== "object") {
      throw new Error(`Tool inputSchema for ${name} must be an object schema`);
    }
    const effect = String(spec.effect || "").trim().toLowerCase();
    if (!["", "read", "workspace_write", "external_write"].includes(effect)) {
      throw new Error(`Unsupported tool effect for ${name}: ${effect}`);
    }
    const resourceArguments = spec.resourceArguments || spec.resource_arguments || [];
    const pathArguments = spec.pathArguments || spec.path_arguments || [];
    const workspaceRootArgument = String(
      spec.workspaceRootArgument || spec.workspace_root_argument || ""
    ).trim();
    this.tools.set(name, {
      name,
      description: String(spec.description || "").trim(),
      input_schema: inputSchema,
      effect,
      resource_arguments: Array.isArray(resourceArguments)
        ? resourceArguments.map(String).filter(Boolean)
        : [String(resourceArguments)].filter(Boolean),
      path_arguments: Array.isArray(pathArguments)
        ? pathArguments.map(String).filter(Boolean)
        : [String(pathArguments)].filter(Boolean),
      workspace_root_argument: workspaceRootArgument,
      worktree_compatible: Boolean(
        spec.worktreeCompatible || spec.worktree_compatible || workspaceRootArgument
      ),
      handler,
    });
    return handler;
  }

  tool(spec, handler) {
    return this.registerTool(spec, handler);
  }

  describeTools() {
    return [...this.tools.values()]
      .sort((left, right) => left.name.localeCompare(right.name))
      .map(({
        name,
        description,
        input_schema,
        effect,
        resource_arguments,
        path_arguments,
        workspace_root_argument,
        worktree_compatible,
      }) => ({
        name,
        description,
        input_schema,
        effect,
        resource_arguments,
        path_arguments,
        workspace_root_argument,
        worktree_compatible,
      }));
  }

  registerHook(spec, handler) {
    if (!spec || typeof spec !== "object") {
      throw new Error("Hook specification must be an object");
    }
    const event = String(spec.event || "").trim();
    const id = String(spec.id || spec.hookId || handler.name || "").trim();
    if (!HOOK_EVENTS.has(event)) {
      throw new Error(`Unsupported hook event: ${event}`);
    }
    if (!TOOL_NAME.test(id)) {
      throw new Error(
        "Hook id must use 1-64 ASCII letters, digits, underscores, or hyphens"
      );
    }
    const key = `${event}:${id}`;
    if (this.hooks.has(key)) {
      throw new Error(`Duplicate plugin hook: ${key}`);
    }
    const failurePolicy = String(
      spec.failurePolicy || spec.failure_policy || "warn"
    ).toLowerCase();
    if (!FAILURE_POLICIES.has(failurePolicy)) {
      throw new Error(`Unsupported hook failure policy: ${failurePolicy}`);
    }
    if (typeof handler !== "function") {
      throw new Error(`Hook handler for ${key} must be a function`);
    }
    this.hooks.set(key, {
      id,
      event,
      matcher: String(spec.matcher || ""),
      priority: Number.isInteger(spec.priority) ? spec.priority : 100,
      failure_policy: failurePolicy,
      handler,
    });
    return handler;
  }

  hook(spec, handler) {
    return this.registerHook(spec, handler);
  }

  registerCommand(spec, handler) {
    if (typeof spec === "string") {
      spec = { name: spec };
    }
    if (!spec || typeof spec !== "object") {
      throw new Error("Command specification must be an object");
    }
    const name = String(spec.name || "").trim();
    if (!TOOL_NAME.test(name)) {
      throw new Error(
        "Command name must use 1-64 ASCII letters, digits, underscores, or hyphens"
      );
    }
    if (this.commands.has(name)) {
      throw new Error(`Duplicate plugin command: ${name}`);
    }
    if (typeof handler !== "function") {
      throw new Error(`Command handler for ${name} must be a function`);
    }
    this.commands.set(name, {
      name,
      description: String(spec.description || "").trim(),
      usage: String(spec.usage || "").trim(),
      handler,
    });
    return handler;
  }

  command(spec, handler) {
    return this.registerCommand(spec, handler);
  }

  onActivate(handler) {
    if (typeof handler !== "function") {
      throw new Error("Activation handler must be a function");
    }
    this.activateHandlers.push(handler);
    return handler;
  }

  onDeactivate(handler) {
    if (typeof handler !== "function") {
      throw new Error("Deactivation handler must be a function");
    }
    this.deactivateHandlers.push(handler);
    return handler;
  }

  onDeferredPoll(handler) {
    if (typeof handler !== "function") {
      throw new Error("Deferred poll handler must be a function");
    }
    if (this.deferredPollHandler) {
      throw new Error("Only one deferred poll handler may be registered");
    }
    this.deferredPollHandler = handler;
    return handler;
  }

  onDeferredCancel(handler) {
    if (typeof handler !== "function") {
      throw new Error("Deferred cancel handler must be a function");
    }
    if (this.deferredCancelHandler) {
      throw new Error("Only one deferred cancel handler may be registered");
    }
    this.deferredCancelHandler = handler;
    return handler;
  }

  onHttpRequest(handler) {
    if (typeof handler !== "function") {
      throw new Error("HTTP handler must be a function");
    }
    if (this.httpHandler) {
      throw new Error("Only one HTTP handler may be registered");
    }
    this.httpHandler = handler;
    return handler;
  }

  registerBackgroundService(spec, handler) {
    if (typeof spec === "string") {
      spec = { name: spec };
    }
    if (!spec || typeof spec !== "object" || typeof handler !== "function") {
      throw new Error("Background service requires a specification and handler");
    }
    const name = String(spec.name || "").trim();
    if (!TOOL_NAME.test(name) || this.backgroundServices.has(name)) {
      throw new Error(`Invalid or duplicate background service: ${name}`);
    }
    const failurePolicy = String(
      spec.failurePolicy || spec.failure_policy || "restart"
    ).toLowerCase();
    if (!["restart", "stop"].includes(failurePolicy)) {
      throw new Error("Background service failurePolicy must be restart or stop");
    }
    const intervalSeconds = Math.max(
      0.05,
      Math.min(86400, Number(spec.intervalSeconds || spec.interval_seconds || 60))
    );
    const registration = {
      name,
      handler,
      interval_seconds: intervalSeconds,
      run_on_start: spec.runOnStart !== false && spec.run_on_start !== false,
      failure_policy: failurePolicy,
    };
    this.backgroundServices.set(name, registration);
    this.backgroundStatus.set(name, {
      name,
      state: "registered",
      runs: 0,
      failures: 0,
      last_error: "",
      last_started_monotonic: 0,
      last_finished_monotonic: 0,
    });
    return handler;
  }

  backgroundService(spec, handler) {
    return this.registerBackgroundService(spec, handler);
  }

  describeBackgroundServices() {
    return [...this.backgroundServices.values()]
      .sort((left, right) => left.name.localeCompare(right.name))
      .map(({ name, interval_seconds, run_on_start, failure_policy }) => ({
        name, interval_seconds, run_on_start, failure_policy,
      }));
  }

  async runBackgroundService(registration, context, control) {
    if (!registration.run_on_start) {
      await control.sleep(registration.interval_seconds * 1000);
    }
    while (!control.cancelled) {
      const status = this.backgroundStatus.get(registration.name);
      status.state = "running";
      status.last_started_monotonic = Number(process.hrtime.bigint()) / 1e9;
      try {
        await registration.handler({ ...(context || {}) });
        status.runs += 1;
        status.last_error = "";
        status.state = "sleeping";
      } catch (error) {
        status.failures += 1;
        status.last_error = String(error && error.message ? error.message : error).slice(0, 2000);
        status.state = "failed";
        if (registration.failure_policy === "stop") {
          return;
        }
      } finally {
        status.last_finished_monotonic = Number(process.hrtime.bigint()) / 1e9;
      }
      await control.sleep(registration.interval_seconds * 1000);
    }
    this.backgroundStatus.get(registration.name).state = "stopped";
  }

  startBackgroundServices(context) {
    if (!context || !context.background_services_enabled) {
      return;
    }
    for (const registration of this.backgroundServices.values()) {
      if (this.backgroundTasks.has(registration.name)) continue;
      let wake = null;
      const control = {
        cancelled: false,
        sleep: (milliseconds) => new Promise((resolve) => {
          const timer = setTimeout(() => {
            wake = null;
            resolve();
          }, milliseconds);
          wake = () => {
            clearTimeout(timer);
            wake = null;
            resolve();
          };
        }),
        cancel: () => {
          control.cancelled = true;
          if (wake) wake();
        },
      };
      const promise = this.runBackgroundService(registration, context, control);
      this.backgroundTasks.set(registration.name, { control, promise });
    }
  }

  async stopBackgroundServices() {
    const tasks = [...this.backgroundTasks.values()];
    this.backgroundTasks.clear();
    for (const task of tasks) task.control.cancel();
    await Promise.allSettled(tasks.map((task) => task.promise));
  }

  backgroundServiceStatus() {
    return [...this.backgroundStatus.keys()]
      .sort()
      .map((name) => ({ ...this.backgroundStatus.get(name) }));
  }

  describeHooks() {
    return [...this.hooks.values()]
      .sort((left, right) =>
        `${left.event}:${left.id}`.localeCompare(`${right.event}:${right.id}`)
      )
      .map(({ id, event, matcher, priority, failure_policy }) => ({
        id, event, matcher, priority, failure_policy,
      }));
  }

  describeCommands() {
    return [...this.commands.values()]
      .sort((left, right) => left.name.localeCompare(right.name))
      .map(({ name, description, usage }) => ({ name, description, usage }));
  }

  async invokeTool(name, argumentsObject, context) {
    const registration = this.tools.get(String(name || ""));
    if (!registration) {
      throw new Error(`Unknown plugin tool: ${name}`);
    }
    return await registration.handler(
      { ...(argumentsObject || {}) },
      { ...(context || {}) }
    );
  }

  async invokeHook(event, id, payload) {
    const registration = this.hooks.get(`${event}:${id}`);
    if (!registration) {
      throw new Error(`Unknown plugin hook: ${event}:${id}`);
    }
    return await registration.handler({ ...(payload || {}) });
  }

  async invokeCommand(name, argumentsText, context) {
    const registration = this.commands.get(String(name || ""));
    if (!registration) {
      throw new Error(`Unknown plugin command: ${name}`);
    }
    return await registration.handler(String(argumentsText || ""), { ...(context || {}) });
  }

  async pollDeferred(token, context) {
    if (!this.deferredPollHandler) {
      throw new Error("Plugin did not register a deferred poll handler");
    }
    return await this.deferredPollHandler(String(token || ""), { ...(context || {}) });
  }

  async cancelDeferred(token, reason, context) {
    if (!this.deferredCancelHandler) {
      return null;
    }
    return await this.deferredCancelHandler(
      String(token || ""),
      String(reason || "cancelled"),
      { ...(context || {}) }
    );
  }

  async handleHttp(request, context) {
    if (!this.httpHandler) {
      throw new Error("Plugin did not register an HTTP handler");
    }
    return await this.httpHandler({ ...(request || {}) }, { ...(context || {}) });
  }

  async activate(context) {
    for (const handler of this.activateHandlers) {
      await handler({ ...(context || {}) });
    }
    this.startBackgroundServices(context || {});
  }

  async deactivate(context) {
    await this.stopBackgroundServices();
    for (const handler of [...this.deactivateHandlers].reverse()) {
      await handler({ ...(context || {}) });
    }
  }
}

async function loadEntrypoint(entrypoint) {
  try {
    return require(entrypoint);
  } catch (error) {
    if (!error || error.code !== "ERR_REQUIRE_ESM") {
      throw error;
    }
    return await import(pathToFileURL(entrypoint).href);
  }
}

async function loadRegistry(entrypoint) {
  const loaded = await loadEntrypoint(entrypoint);
  const setup =
    (loaded && loaded.setup) ||
    (loaded && typeof loaded.default === "function" ? loaded.default : null) ||
    (loaded && loaded.default && loaded.default.setup);
  if (typeof setup !== "function") {
    throw new Error(
      "Node plugin entrypoint must export `setup(plugin)` or a default setup function"
    );
  }
  const registry = new PluginRegistry();
  const configured = await setup(registry);
  return configured instanceof PluginRegistry ? configured : registry;
}

function zodToJsonSchema(schema) {
  if (!schema || typeof schema !== "object") return {};
  if (typeof schema.type === "string") return { ...schema };
  if (typeof schema.toJSONSchema === "function") {
    try {
      return schema.toJSONSchema();
    } catch (_) {
      // Fall through to structural inspection.
    }
  }
  const def = schema._zod && schema._zod.def ? schema._zod.def : schema._def || {};
  const rawType = String(def.type || def.typeName || "").toLowerCase();
  if (rawType.includes("string")) return { type: "string" };
  if (rawType.includes("number") || rawType.includes("float")) return { type: "number" };
  if (rawType.includes("int")) return { type: "integer" };
  if (rawType.includes("boolean")) return { type: "boolean" };
  if (rawType.includes("array")) {
    return { type: "array", items: zodToJsonSchema(def.element || def.type) };
  }
  if (rawType.includes("enum")) {
    const values = def.values || Object.values(def.entries || {});
    return { type: "string", enum: values };
  }
  if (rawType.includes("optional") || rawType.includes("default")) {
    return zodToJsonSchema(def.innerType);
  }
  if (rawType.includes("object") && def.shape) {
    const shape = typeof def.shape === "function" ? def.shape() : def.shape;
    return openCodeArgsSchema(shape);
  }
  return {};
}

function openCodeArgsSchema(args) {
  if (args && args.type === "object" && args.properties) return args;
  const properties = {};
  const required = [];
  for (const [name, schema] of Object.entries(args || {})) {
    properties[name] = zodToJsonSchema(schema);
    const def = schema && (schema._zod && schema._zod.def ? schema._zod.def : schema._def);
    const rawType = String((def && (def.type || def.typeName)) || "").toLowerCase();
    if (!rawType.includes("optional") && !rawType.includes("default")) {
      required.push(name);
    }
  }
  return {
    type: "object",
    properties,
    required,
    additionalProperties: false,
  };
}

async function loadOpenCodeRegistry(entrypoint, root) {
  const loaded = await loadEntrypoint(entrypoint);
  const candidates = new Set();
  if (typeof loaded === "function") candidates.add(loaded);
  for (const value of Object.values(loaded || {})) {
    if (typeof value === "function") candidates.add(value);
  }
  if (loaded && typeof loaded.default === "function") candidates.add(loaded.default);
  if (!candidates.size) {
    throw new Error("OpenCode plugin must export at least one plugin function");
  }
  const registry = new PluginRegistry();
  const unavailable = () => {
    throw new Error("This OpenCode host API is unavailable in MyAgent");
  };
  const hostContext = {
    project: { name: path.basename(root), path: root },
    directory: root,
    worktree: root,
    client: new Proxy({}, { get: () => unavailable }),
    $: unavailable,
  };
  let hookIndex = 0;
  for (const pluginFunction of candidates) {
    const hooks = await pluginFunction(hostContext);
    if (!hooks || typeof hooks !== "object") continue;
    const tools = hooks.tool;
    if (tools && typeof tools === "object") {
      for (const [name, definition] of Object.entries(tools)) {
        if (!definition || typeof definition.execute !== "function") continue;
        registry.registerTool(
          {
            name,
            description: String(definition.description || ""),
            inputSchema: openCodeArgsSchema(definition.args || {}),
          },
          async (args) =>
            await definition.execute(args, {
              directory: root,
              worktree: root,
              sessionID: "",
              messageID: "",
              agent: "myagent",
            })
        );
      }
    }
    const before = hooks["tool.execute.before"];
    if (typeof before === "function") {
      hookIndex += 1;
      registry.registerHook(
        {
          event: "PreToolUse",
          id: `opencode-before-${hookIndex}`,
          priority: 100,
        },
        async (payload) => {
          const output = { args: { ...(payload.tool_input || {}) } };
          await before(
            {
              tool: payload.tool_name || "",
              sessionID: payload.session_id || "",
              callID: payload.tool_call_id || "",
            },
            output
          );
          return { decision: "allow", updated_input: output.args };
        }
      );
    }
    const after = hooks["tool.execute.after"];
    if (typeof after === "function") {
      hookIndex += 1;
      registry.registerHook(
        {
          event: "PostToolUse",
          id: `opencode-after-${hookIndex}`,
          priority: 100,
        },
        async (payload) => {
          const output = {
            title: "",
            output: payload.tool_output || payload.result || "",
            metadata: {},
          };
          await after(
            {
              tool: payload.tool_name || "",
              sessionID: payload.session_id || "",
              callID: payload.tool_call_id || "",
            },
            output
          );
          return {};
        }
      );
    }
    const compacting = hooks["experimental.session.compacting"];
    if (typeof compacting === "function") {
      hookIndex += 1;
      registry.registerHook(
        {
          event: "PreCompact",
          id: `opencode-compact-${hookIndex}`,
          priority: 100,
        },
        async (payload) => {
          const output = { context: [] };
          await compacting(
            { sessionID: payload.session_id || "" },
            output
          );
          return { additional_context: output.context.join("\n") };
        }
      );
    }
  }
  return registry;
}

async function handle(registry, request) {
  const method = String(request.method || "");
  if (method === "plugin.describe") {
    return {
      api_version: API_VERSION,
      tools: registry.describeTools(),
      hooks: registry.describeHooks(),
      commands: registry.describeCommands(),
      deferred_results: Boolean(registry.deferredPollHandler),
      http: Boolean(registry.httpHandler),
      background_services: registry.describeBackgroundServices(),
    };
  }
  if (method === "plugin.ping") {
    return { api_version: API_VERSION, status: "ready" };
  }
  if (method === "plugin.shutdown") {
    return { status: "stopping" };
  }
  if (method === "background.status") {
    return { services: registry.backgroundServiceStatus() };
  }
  if (method === "tool.call") {
    const params = request.params;
    if (!params || typeof params !== "object" || Array.isArray(params)) {
      throw new Error("tool.call params must be an object");
    }
    const args = params.arguments === undefined ? {} : params.arguments;
    if (!args || typeof args !== "object" || Array.isArray(args)) {
      throw new Error("tool.call arguments must be an object");
    }
    const context = params.context === undefined ? {} : params.context;
    if (!context || typeof context !== "object" || Array.isArray(context)) {
      throw new Error("tool.call context must be an object");
    }
    return await registry.invokeTool(params.name, args, context);
  }
  if (method === "hook.call") {
    const params = request.params;
    if (!params || typeof params !== "object" || Array.isArray(params)) {
      throw new Error("hook.call params must be an object");
    }
    const payload = params.payload === undefined ? {} : params.payload;
    if (!payload || typeof payload !== "object" || Array.isArray(payload)) {
      throw new Error("hook.call payload must be an object");
    }
    return await registry.invokeHook(params.event, params.hook_id, payload);
  }
  if (method === "command.call") {
    const params = request.params;
    if (!params || typeof params !== "object" || Array.isArray(params)) {
      throw new Error("command.call params must be an object");
    }
    const context = params.context === undefined ? {} : params.context;
    if (!context || typeof context !== "object" || Array.isArray(context)) {
      throw new Error("command.call context must be an object");
    }
    return await registry.invokeCommand(params.name, params.arguments, context);
  }
  if (method === "deferred.poll" || method === "deferred.cancel") {
    const params = request.params;
    if (!params || typeof params !== "object" || Array.isArray(params)) {
      throw new Error(`${method} params must be an object`);
    }
    const context = params.context === undefined ? {} : params.context;
    if (!context || typeof context !== "object" || Array.isArray(context)) {
      throw new Error(`${method} context must be an object`);
    }
    const token = String(params.token || "");
    if (!token) {
      throw new Error(`${method} token must not be empty`);
    }
    if (method === "deferred.poll") {
      return await registry.pollDeferred(token, context);
    }
    return await registry.cancelDeferred(token, params.reason, context);
  }
  if (method === "http.handle") {
    const params = request.params;
    if (!params || typeof params !== "object" || Array.isArray(params)) {
      throw new Error("http.handle params must be an object");
    }
    const httpRequest = params.request;
    if (!httpRequest || typeof httpRequest !== "object" || Array.isArray(httpRequest)) {
      throw new Error("http.handle request must be an object");
    }
    const context = params.context === undefined ? {} : params.context;
    if (!context || typeof context !== "object" || Array.isArray(context)) {
      throw new Error("http.handle context must be an object");
    }
    return await registry.handleHttp(httpRequest, context);
  }
  throw new Error(`Unknown worker method: ${method}`);
}

function writeResponse(payload) {
  protocolWrite(`${JSON.stringify(payload)}\n`);
}

async function main() {
  let requestId = null;
  let registry = null;
  let hostContext = {};
  try {
    const args = parseArgs(process.argv.slice(2));
    const root = fs.realpathSync(args["plugin-root"]);
    const entrypoint = fs.realpathSync(args.entrypoint);
    const relative = path.relative(root, entrypoint);
    if (relative.startsWith("..") || path.isAbsolute(relative)) {
      throw new Error("Plugin entrypoint must stay inside the plugin root");
    }
    registry =
      String(args.adapter || "native") === "opencode"
        ? await loadOpenCodeRegistry(entrypoint, root)
        : await loadRegistry(entrypoint);
    hostContext = {
      plugin_id: String(args["plugin-id"] || ""),
      plugin_data_dir: String(args["plugin-data-dir"] || ""),
      plugin_cache_dir: String(args["plugin-cache-dir"] || ""),
      plugin_temp_dir: String(args["plugin-temp-dir"] || ""),
      workspace_root: String(args["workspace-root"] || ""),
      background_services_enabled: ["1", "true", "yes", "on"].includes(
        String(args["background-services-enabled"] || "0").toLowerCase()
      ),
    };
    await registry.activate({ plugin_root: root, entrypoint, ...hostContext });
    const reader = readline.createInterface({ input: process.stdin, crlfDelay: Infinity });
    for await (const line of reader) {
      requestId = null;
      try {
        const request = JSON.parse(line);
        if (!request || typeof request !== "object" || Array.isArray(request)) {
          throw new Error("Worker request must be a JSON object");
        }
        requestId = request.id;
        const result = await handle(registry, request);
        writeResponse({ id: requestId, ok: true, result });
        if (String(request.method || "") === "plugin.shutdown") {
          reader.close();
          break;
        }
      } catch (error) {
        writeResponse({
          id: requestId,
          ok: false,
          error: {
            type: error && error.name ? error.name : "Error",
            message: error && error.message ? error.message : String(error),
            traceback: error && error.stack ? error.stack : "",
          },
        });
      }
    }
    return 0;
  } catch (error) {
    writeResponse({
      id: requestId,
      ok: false,
      error: {
        type: error && error.name ? error.name : "Error",
        message: error && error.message ? error.message : String(error),
        traceback: error && error.stack ? error.stack : "",
      },
    });
    return 1;
  } finally {
    if (registry) {
      try {
        await registry.deactivate({ ...hostContext, reason: "worker_exit" });
      } catch (error) {
        console.error(error && error.stack ? error.stack : String(error));
      }
    }
  }
}

main().then((code) => {
  process.exitCode = code;
});
