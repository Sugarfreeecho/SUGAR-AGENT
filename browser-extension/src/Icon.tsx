import React from 'react';
const paths: Record<string, React.ReactNode> = {
  down: <path d="m6 9 6 6 6-6" />,
  shield: <><path d="M12 3 4 6v6c0 5 8 9 8 9s8-4 8-9V6Z" /><path d="m8 12 3 3 5-6" /></>,
  'permission-ask': <path d="M12 3l7 3v5c0 4.5-3 8.3-7 10-4-1.7-7-5.5-7-10V6z" />,
  'permission-auto': <><path d="M12 3l7 3v5c0 4.5-3 8.3-7 10-4-1.7-7-5.5-7-10V6z" /><path d="M9.2 11.8l2 2 3.8-4" /></>,
  'permission-full': <><path d="M12 3l7 3v5c0 4.5-3 8.3-7 10-4-1.7-7-5.5-7-10V6z" /><path d="M12 8v4" /><circle cx="12" cy="16" r="0.9" fill="currentColor" stroke="none" /></>,
  folder: <path d="M3 7V5h7l2 3h9v11H3Z" />,
  plugin: <><path d="M9 4h6v4h4v5h-4v7H9v-7H5V8h4Z" /><path d="M10 1v3m4-3v3" /></>,
  more: <><circle cx="5" cy="12" r="1" /><circle cx="12" cy="12" r="1" /><circle cx="19" cy="12" r="1" /></>,
  alert: <><circle cx="12" cy="12" r="9" /><path d="M12 7v6m0 4v.1" /></>,
  plus: <path d="M12 5v14M5 12h14" />,
  skill: <path d="M12 5c-3-2-6-2-9-1v15c3-1 6-1 9 1 3-2 6-2 9-1V4c-3-1-6-1-9 1Zm0 0v15" />,
  edit: <><path d="m15 4 5 5-10 10-6 1 1-6Z" /><path d="m13 6 5 5" /></>,
  settings: <><path d="M4 7h16M4 17h16" /><circle cx="9" cy="7" r="3" /><circle cx="15" cy="17" r="3" /></>,
  history: <><path d="M3 11a9 9 0 1 1 2.6 7M3 4v7h7M12 7v5l3 2" /></>,
  chevron: <path d="m9 5 7 7-7 7" />,
  globe: <><circle cx="12" cy="12" r="9" /><path d="M3 12h18M12 3a18 18 0 0 1 0 18 18 18 0 0 1 0-18" /></>,
  attach: <path d="m8 13 6-6a3 3 0 0 1 4 4l-8 8a5 5 0 0 1-7-7l9-9" />,
  tabs: <><rect x="3" y="7" width="14" height="14" rx="3" /><path d="M7 3h11a3 3 0 0 1 3 3v11" /></>,
  agents: <><rect x="9" y="3" width="6" height="5" rx="1"/><path d="M12 8v5M5 13h14M5 13v3m14-3v3"/><rect x="2" y="16" width="6" height="5" rx="1"/><rect x="16" y="16" width="6" height="5" rx="1"/></>,
  arrow: <path d="M12 19V5m-6 6 6-6 6 6" />,
  external: <><path d="M14 4h6v6m0-6-10 10M10 4H6a2 2 0 0 0-2 2v12a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-4" /></>,
  copy: <><rect x="8" y="8" width="12" height="12" rx="2" /><path d="M15 8V4H4v11h4" /></>,
  stop: <rect x="6" y="6" width="12" height="12" rx="2" fill="currentColor" stroke="none" />,
  interrupt: <path d="m13 3-8 11h6l-1 7 9-12h-6Z" />,
  check: <path d="m5 12 4 4L19 6" />,
};
export function Icon({ name, size = 18, strokeWidth = 1.6 }: { name: string; size?: number; strokeWidth?: number }) {
  return <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={strokeWidth} strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">{paths[name] || paths.globe}</svg>;
}
export const toolLabel = (name: string) => ({ browser_get_context: '读取浏览器上下文', browser_snapshot: '读取网页', browser_find: '查找页面内容', browser_click: '点击页面元素', browser_type: '填写内容', browser_navigate: '打开网页', browser_tabs: '查看标签页', browser_take_screenshot: '截取页面', browser_file_upload: '上传文件', browser_wait_for: '等待页面', browser_fill_form: '填写表单', browser_press_key: '键盘操作' } as Record<string, string>)[name] || name;
