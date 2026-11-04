import React, { useEffect, useId, useLayoutEffect, useRef, useState } from 'react';

export function Popover({ label, trigger, children, className = '', triggerClassName = '', disabled = false, onOpen, value, placement = 'top', align = 'start', width = 280, role = 'dialog', autoOpenKey }: {
  label: string; trigger: React.ReactNode; children: (close: () => void) => React.ReactNode;
  className?: string; triggerClassName?: string; disabled?: boolean; onOpen?: () => void; value?: string;
  placement?: 'top' | 'bottom'; align?: 'start' | 'end'; width?: number; role?: 'dialog' | 'menu' | 'alert'; autoOpenKey?: string;
}) {
  const [open, setOpen] = useState(false), [position, setPosition] = useState<React.CSSProperties>({ visibility: 'hidden' });
  const root = useRef<HTMLDivElement>(null), button = useRef<HTMLButtonElement>(null), panel = useRef<HTMLElement>(null);
  const id = useId();
  const close = () => { setOpen(false); button.current?.focus(); };
  useEffect(() => { if (autoOpenKey) setOpen(true); }, [autoOpenKey]);
  useLayoutEffect(() => {
    if (!open || !button.current || !panel.current) return;
    const place = () => {
      const anchor = button.current!.getBoundingClientRect(), menu = panel.current!;
      const viewport = window.visualViewport;
      const left = viewport?.offsetLeft || 0, top = viewport?.offsetTop || 0;
      const vw = viewport?.width || innerWidth, vh = viewport?.height || innerHeight;
      const w = Math.min(width, vw - 24), above = anchor.top - top - 20, below = top + vh - anchor.bottom - 20;
      const preferred = placement === 'top' ? above : below, alternate = placement === 'top' ? below : above;
      const side = preferred >= Math.min(menu.scrollHeight, 160) || preferred >= alternate ? placement : placement === 'top' ? 'bottom' : 'top';
      const maxHeight = Math.max(0, Math.min(360, side === 'top' ? above : below));
      const height = Math.min(menu.scrollHeight + 2, maxHeight);
      const x = Math.max(left + 12, Math.min(align === 'end' ? anchor.right - w : anchor.left, left + vw - w - 12)), y = side === 'top' ? anchor.top - height - 8 : anchor.bottom + 8;
      setPosition(previous => previous.left === x && previous.top === y && previous.width === w && previous.maxHeight === maxHeight && previous.visibility === 'visible' ? previous : { position: 'fixed', width: w, maxHeight, right: 'auto', bottom: 'auto', left: x, top: y, visibility: 'visible' });
    };
    place();
    const observer = new ResizeObserver(place); observer.observe(panel.current); observer.observe(button.current);
    window.addEventListener('resize', place); window.visualViewport?.addEventListener('resize', place);
    return () => { observer.disconnect(); window.removeEventListener('resize', place); window.visualViewport?.removeEventListener('resize', place); };
  }, [open, placement, align, width, children]);
  useLayoutEffect(() => { if (open) panel.current?.querySelector<HTMLElement>('input,button:not(:disabled)')?.focus(); }, [open]);
  useEffect(() => {
    if (!open) return;
    const ancestors: string[] = [];
    let ancestor = root.current?.parentElement?.closest<HTMLElement>('[data-menu-id]');
    while (ancestor) { ancestors.push(ancestor.dataset.menuId!); ancestor = ancestor.parentElement?.closest<HTMLElement>('[data-menu-id]'); }
    document.dispatchEvent(new CustomEvent('sugar-menu-open', { detail: { id, ancestors } }));
    const outside = (event: Event) => { if (!root.current?.contains(event.target as Node)) setOpen(false); };
    const otherMenu = (event: Event) => { const menu = (event as CustomEvent).detail; if (menu.id !== id && !menu.ancestors.includes(id)) setOpen(false); };
    const escape = (event: KeyboardEvent) => { if (event.key === 'Escape' && !root.current?.querySelector('.popover-root[data-open]')) { event.preventDefault(); close(); } };
    document.addEventListener('pointerdown', outside); document.addEventListener('focusin', outside);
    document.addEventListener('keydown', escape); document.addEventListener('sugar-menu-open', otherMenu);
    return () => { document.removeEventListener('pointerdown', outside); document.removeEventListener('focusin', outside); document.removeEventListener('keydown', escape); document.removeEventListener('sugar-menu-open', otherMenu); };
  }, [open, id]);
  return <div ref={root} className={'popover-root ' + className} data-menu-id={id} data-open={open || undefined}><button ref={button} type="button" className={'popover-trigger ' + triggerClassName} data-value={value} aria-label={label} title={label} aria-haspopup={role === 'menu' ? 'menu' : 'dialog'} aria-expanded={open} aria-controls={open ? id : undefined} disabled={disabled} onClick={() => { if (!open) onOpen?.(); setOpen(!open); }}>{trigger}</button>
    {open && <section ref={panel} id={id} className="popover-panel" style={position} role={role} aria-label={label} onKeyDown={event => {
      if (event.defaultPrevented) return;
      if (event.target instanceof HTMLTextAreaElement || !['ArrowDown', 'ArrowUp', 'Home', 'End'].includes(event.key)) return;
      if (event.target instanceof HTMLInputElement && !['ArrowDown', 'ArrowUp'].includes(event.key)) return;
      const items = [...event.currentTarget.querySelectorAll<HTMLButtonElement>('button:not(:disabled)')];
      const index = items.indexOf(document.activeElement as HTMLButtonElement); if (!items.length) return;
      event.preventDefault(); items[event.key === 'Home' ? 0 : event.key === 'End' ? items.length - 1 : index < 0 ? event.key === 'ArrowDown' ? 0 : items.length - 1 : (index + (event.key === 'ArrowDown' ? 1 : -1) + items.length) % items.length]?.focus();
    }}>{children(close)}</section>}
  </div>;
}
