import { markup } from './view.js?v=20261030-native';
import { mountConsole } from './app.js?v=20261030-native';
import { mountNativeSettings } from '/static/workflow-console.js?v=20261030-native';

export function mountSettings({ root, settings }) {
    return mountNativeSettings({ root, settings, markup, mountConsole, kind: 'goal' });
}
