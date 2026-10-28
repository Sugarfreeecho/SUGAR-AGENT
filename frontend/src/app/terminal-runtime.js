import { Terminal } from '@xterm/xterm';
import { FitAddon } from '@xterm/addon-fit';
import terminalStyles from '@xterm/xterm/css/xterm.css?inline';

// The main app and the execution console share this local bundle entry.
const style = document.createElement('style');
style.dataset.myagentTerminalStyle = '';
style.textContent = terminalStyles;
document.head.appendChild(style);
globalThis.MyAgentTerminal = { Terminal, FitAddon };
