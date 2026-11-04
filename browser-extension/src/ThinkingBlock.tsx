import React, { useLayoutEffect, useRef, useState } from 'react';
import {Icon} from './Icon';
import {ProcessElapsed} from './ProcessElapsed';
import {useNestedSmoothFollow} from './useSmoothFollow';

export const ThinkingBlock=React.memo(function ThinkingBlock({ block }: { block: any }) {
  const [open, setOpen] = useState(!!block.active);
  const scrolling=useNestedSmoothFollow<HTMLPreElement>(!!block.active,open);
  const wasActive = useRef(!!block.active);
  useLayoutEffect(() => {
    if (wasActive.current !== !!block.active) { setOpen(!!block.active); wasActive.current = !!block.active; }
  }, [block.active]);
  return <details className="process-block reason" open={open} onToggle={event => setOpen(event.currentTarget.open)}><summary><span className="chevron entry-chevron"><Icon name="chevron" size={12} /></span><span className="process-title">思考</span><span className="entry-meta secondary"><span>{block.active ? '正在思考' : ''}</span><ProcessElapsed block={block} placeholder="" /></span></summary><pre ref={scrolling.ref} onScroll={scrolling.onScroll} tabIndex={0}>{block.content}</pre></details>;
});
