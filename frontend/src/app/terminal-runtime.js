import { Terminal } from '@xterm/xterm';
import { FitAddon } from '@xterm/addon-fit';
import '@xterm/xterm/css/xterm.css';

// Bundled host panels load through the plugin asset gateway. Publish only the
// terminal constructor, avoiding an external CDN or a second frontend bundle.
globalThis.MyAgentTerminal = { Terminal, FitAddon };
