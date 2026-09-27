// Smooth streaming primitives. This file is concatenated into the shared UI
// runtime before session-scroll-history.js; keep the helpers dependency-free.

const SMOOTH_STREAM_CONFIG = Object.freeze({
    revealDivisor: 8,
    referenceFrameMs: 16.67,
    followTargetEpsilonPx: 0.25,
    followDurationMs: 160,
    maxFollowStepPx: 20,
    unpinWheelPx: 8,
    gestureWindowMs: 800,
});

// Text wrapping and whole-row layout changes use the same finite glide.
function smoothFollowEaseOutCubic(progress) {
    var remaining = 1 - smoothStreamClamp(progress, 0, 1);
    return 1 - remaining * remaining * remaining;
}

function smoothStreamClamp(value, min, max) {
    return Math.min(max, Math.max(min, value));
}

function isSmoothStreamEnabled() {
    return !!(window.__MYAGENT_FEATURES__ && window.__MYAGENT_FEATURES__.smoothStream === true);
}

function prefersReducedSmoothStreamMotion() {
    return !!(
        window.matchMedia
        && window.matchMedia('(prefers-reduced-motion: reduce)').matches
    );
}

function isSmoothStreamActive() {
    return isSmoothStreamEnabled() && !prefersReducedSmoothStreamMotion();
}

function computeSmoothRevealCount(backlog, dtMs) {
    var remaining = Math.max(0, Number(backlog) || 0);
    var elapsed = Math.max(0, Number(dtMs) || 0);
    if (remaining <= 0 || elapsed <= 0) return 0;
    return Math.min(
        remaining,
        Math.max(1, Math.ceil(
            (remaining / SMOOTH_STREAM_CONFIG.revealDivisor)
            * (elapsed / SMOOTH_STREAM_CONFIG.referenceFrameMs)
        ))
    );
}

/** Take whole Unicode code points without splitting a surrogate pair. */
function takeSmoothTextPrefix(text, charCount) {
    var source = String(text || '');
    var wanted = Math.max(0, Math.floor(Number(charCount) || 0));
    if (!source || wanted <= 0) return { segment: '', rest: source, count: 0 };
    var offset = 0;
    var count = 0;
    while (offset < source.length && count < wanted) {
        var point = source.codePointAt(offset);
        offset += point != null && point > 0xFFFF ? 2 : 1;
        count += 1;
    }
    return {
        segment: source.slice(0, offset),
        rest: source.slice(offset),
        count: count,
    };
}

function createSmoothFollowController() {
    var states = new WeakMap();
    var activePorts = new Set();
    var rafId = 0;
    var lastFrameMs = 0;

    function stateFor(port) {
        var state = states.get(port);
        if (state) return state;
        state = {
            following: false,
            readerDetached: false,
            animatedTop: 0,
            lastFloor: null,
            slideFrom: 0,
            slideTo: 0,
            slideStartMs: 0,
            lastWrittenTop: 0,
            ownedUntil: 0,
            awayPx: 0,
            gestureTimer: 0,
            touchY: null,
            pointerDown: false,
            pointerStartTop: 0,
            onUnpin: null,
            bound: false,
        };
        states.set(port, state);
        bindPort(port, state);
        return state;
    }

    function clearGestureSoon(state) {
        if (state.gestureTimer) clearTimeout(state.gestureTimer);
        state.gestureTimer = setTimeout(function () {
            state.gestureTimer = 0;
            state.awayPx = 0;
            state.touchY = null;
        }, SMOOTH_STREAM_CONFIG.gestureWindowMs);
    }

    function unpin(port, state) {
        if (!state.following) return;
        state.following = false;
        state.readerDetached = true;
        state.awayPx = 0;
        activePorts.delete(port);
        port.removeAttribute('data-smooth-follow-owned');
        var callback = state.onUnpin;
        if (typeof callback === 'function') callback(port);
    }

    function bindPort(port, state) {
        if (state.bound || !port || !port.addEventListener) return;
        state.bound = true;
        port.addEventListener('wheel', function (event) {
            if (!state.following || Number(event.deltaY) >= 0) return;
            state.awayPx += -Number(event.deltaY || 0);
            clearGestureSoon(state);
            if (state.awayPx >= SMOOTH_STREAM_CONFIG.unpinWheelPx) unpin(port, state);
        }, { passive: true });
        port.addEventListener('touchstart', function (event) {
            var touch = event.touches && event.touches[0];
            state.touchY = touch ? Number(touch.clientY) : null;
            clearGestureSoon(state);
        }, { passive: true });
        port.addEventListener('touchmove', function (event) {
            if (!state.following) return;
            var touch = event.touches && event.touches[0];
            if (!touch || state.touchY == null) return;
            var nextY = Number(touch.clientY);
            var pullUp = nextY - state.touchY;
            state.touchY = nextY;
            if (pullUp > 0) state.awayPx += pullUp;
            clearGestureSoon(state);
            if (state.awayPx >= SMOOTH_STREAM_CONFIG.unpinWheelPx) unpin(port, state);
        }, { passive: true });
        port.addEventListener('pointerdown', function () {
            state.pointerDown = true;
            state.pointerStartTop = Number(port.scrollTop) || 0;
            clearGestureSoon(state);
        }, { passive: true });
        function clearPointer() { state.pointerDown = false; }
        port.addEventListener('pointerup', clearPointer, { passive: true });
        port.addEventListener('pointercancel', clearPointer, { passive: true });
        port.addEventListener('scroll', function () {
            if (
                state.following
                && state.pointerDown
                && Number(port.scrollTop) < state.pointerStartTop - 2
            ) unpin(port, state);
        }, { passive: true });
        port.addEventListener('keydown', function (event) {
            if (!state.following) return;
            if (event.key === 'ArrowUp' || event.key === 'PageUp' || event.key === 'Home') {
                unpin(port, state);
            }
        }, { passive: true });
    }

    function schedule() {
        if (rafId || activePorts.size === 0) return;
        rafId = requestAnimationFrame(frame);
    }

    function frame(now) {
        rafId = 0;
        var frameStartedAt = performance.now();
        if (lastFrameMs > 0 && typeof uiPerformance !== 'undefined') {
            uiPerformance.sample(currentSessionId, 'follow.frameGap', now - lastFrameMs);
        }
        var dtMs = lastFrameMs > 0
            ? smoothStreamClamp(now - lastFrameMs, 1, 50)
            : SMOOTH_STREAM_CONFIG.referenceFrameMs;
        lastFrameMs = now;
        activePorts.forEach(function (port) {
            var state = states.get(port);
            if (!state || !state.following || !port.isConnected) {
                activePorts.delete(port);
                if (state && !port.isConnected) state.following = false;
                if (port && port.removeAttribute) port.removeAttribute('data-smooth-follow-owned');
                return;
            }
            var floor = Math.max(0, Number(port.scrollHeight) - Number(port.clientHeight));
            // A shrinking scroll range can force the browser to clamp scrollTop.
            // Keep our float position within that range before retargeting.
            state.animatedTop = Math.min(floor, Math.max(0, state.animatedTop));
            if (
                state.lastFloor == null
                || Math.abs(floor - state.lastFloor) > SMOOTH_STREAM_CONFIG.followTargetEpsilonPx
            ) {
                state.lastFloor = floor;
                state.slideFrom = state.animatedTop;
                state.slideTo = floor;
                // Advance on this very frame. Row-height animations can move
                // the floor every frame; starting at now would keep p at zero.
                state.slideStartMs = now - dtMs;
            }
            var lag = floor - state.animatedTop;
            if (lag <= SMOOTH_STREAM_CONFIG.followTargetEpsilonPx) {
                state.animatedTop = floor;
                state.lastWrittenTop = floor;
                state.ownedUntil = now + 100;
                if (Math.abs((Number(port.scrollTop) || 0) - floor) > 0.1) {
                    port.scrollTop = floor;
                }
                // Reaching the current floor only means that this glide has no
                // displacement for the moment. Keep both ownership and the
                // lightweight rAF observer alive for the lifetime of the
                // stream: row insertion animations, temporary-status swaps and
                // async card content can change scrollHeight without issuing a
                // new token delta. cancel()/unpin() releases the observer at the
                // actual stream or reader boundary.
                port.setAttribute('data-smooth-follow-owned', '1');
                return;
            }
            var progress = (now - state.slideStartMs) / SMOOTH_STREAM_CONFIG.followDurationMs;
            var desiredTop = state.slideFrom
                + (state.slideTo - state.slideFrom) * smoothFollowEaseOutCubic(progress);
            var previousTop = state.animatedTop;
            state.animatedTop = Math.min(
                floor,
                Math.max(state.animatedTop, desiredTop),
                previousTop + SMOOTH_STREAM_CONFIG.maxFollowStepPx
            );
            // Finish tiny residuals only when the total frame displacement
            // still fits under the cap. Large backlogs take additional frames.
            if (
                floor - state.animatedTop <= SMOOTH_STREAM_CONFIG.followTargetEpsilonPx
                && floor - previousTop <= SMOOTH_STREAM_CONFIG.maxFollowStepPx
            ) state.animatedTop = floor;
            state.lastWrittenTop = state.animatedTop;
            state.ownedUntil = now + 100;
            port.setAttribute('data-smooth-follow-owned', '1');
            port.scrollTop = state.animatedTop;
        });
        if (typeof uiPerformance !== 'undefined') uiPerformance.sample(currentSessionId, 'follow.work', performance.now() - frameStartedAt);
        if (activePorts.size > 0) schedule();
        else lastFrameMs = 0;
    }

    function request(port, options) {
        if (!port) return;
        options = options || {};
        if (
            typeof isHistorySmoothScrollActive === 'function'
            && isHistorySmoothScrollActive()
        ) return;
        if (!isSmoothStreamActive()) {
            port.scrollTop = port.scrollHeight;
            return;
        }
        var state = stateFor(port);
        if (state.readerDetached && options.force !== true) return;
        if (!state.following) {
            state.animatedTop = Math.max(0, Number(port.scrollTop) || 0);
            state.lastFloor = null;
        }
        state.following = true;
        state.onUnpin = typeof options.onUnpin === 'function' ? options.onUnpin : state.onUnpin;
        activePorts.add(port);
        port.setAttribute('data-smooth-follow-owned', '1');
        schedule();
    }

    function release(port) {
        if (!port) return;
        var state = states.get(port);
        if (state) unpin(port, state);
    }

    /** Stop programmatic follow without treating it as a reader gesture. */
    function cancel(port) {
        if (!port) return;
        var state = states.get(port);
        if (!state) return;
        state.following = false;
        activePorts.delete(port);
        port.removeAttribute('data-smooth-follow-owned');
        if (activePorts.size === 0) {
            if (rafId) cancelAnimationFrame(rafId);
            rafId = 0;
            lastFrameMs = 0;
        }
    }

    /** A session boundary clears both programmatic and reader ownership. */
    function reset(port) {
        cancel(port);
        var state = port ? states.get(port) : null;
        if (!state) return;
        if (state.gestureTimer) clearTimeout(state.gestureTimer);
        state.gestureTimer = 0;
        state.readerDetached = false;
        state.pointerDown = false;
        state.touchY = null;
        state.awayPx = 0;
        state.onUnpin = null;
    }

    /** End-of-stream convergence: no easing tail after generation is done. */
    function snapToBottom(port) {
        if (!port) return false;
        var state = states.get(port);
        if (state && state.readerDetached) {
            cancel(port);
            return false;
        }
        cancel(port);
        var floor = Math.max(0, Number(port.scrollHeight) - Number(port.clientHeight));
        if (state) {
            state.animatedTop = floor;
            state.lastFloor = floor;
            state.lastWrittenTop = floor;
        }
        var hasInlineStyle = !!(port.style && typeof port.style === 'object');
        var previousBehavior = hasInlineStyle ? port.style.scrollBehavior : '';
        if (hasInlineStyle) port.style.scrollBehavior = 'auto';
        else port.setAttribute('data-smooth-follow-owned', '1');
        port.scrollTop = floor;
        requestAnimationFrame(function () {
            var latest = states.get(port);
            if (latest && latest.following) return;
            if (hasInlineStyle) port.style.scrollBehavior = previousBehavior;
            else port.removeAttribute('data-smooth-follow-owned');
        });
        return true;
    }

    function isFollowing(port) {
        var state = port ? states.get(port) : null;
        return !!(state && state.following);
    }

    function isReaderDetached(port) {
        var state = port ? states.get(port) : null;
        return !!(state && state.readerDetached);
    }

    function clearReaderDetached(port) {
        var state = port ? states.get(port) : null;
        if (state) state.readerDetached = false;
    }

    function isOwnedScroll(port) {
        var state = port ? states.get(port) : null;
        if (!state || !state.following) return false;
        return performance.now() <= state.ownedUntil
            && Math.abs((Number(port.scrollTop) || 0) - state.lastWrittenTop) <= 2;
    }

    return {
        request: request,
        release: release,
        cancel: cancel,
        reset: reset,
        snapToBottom: snapToBottom,
        isFollowing: isFollowing,
        isReaderDetached: isReaderDetached,
        clearReaderDetached: clearReaderDetached,
        isOwnedScroll: isOwnedScroll,
    };
}

const smoothFollowController = createSmoothFollowController();

// Feed rows change the height of the nested execution viewport. Animate that
// layout delta independently from the scroll follower so insertion/collapse
// cannot move the viewport floor in a single frame.
var smoothTraceLayoutAnimations = new WeakMap();

function cancelSmoothTraceLayoutAnimation(row) {
    if (!row) return;
    var animation = smoothTraceLayoutAnimations.get(row);
    if (animation && typeof animation.cancel === 'function') animation.cancel();
    smoothTraceLayoutAnimations.delete(row);
    if (row.style) row.style.removeProperty('overflow');
    if (row.removeAttribute) row.removeAttribute('data-smooth-trace-layout-owned');
}

function animateSmoothTraceRowHeight(row, fromHeight, toHeight, options) {
    options = options || {};
    var from = Math.max(0, Number(fromHeight) || 0);
    var to = Math.max(0, Number(toHeight) || 0);
    if (!row || !isSmoothStreamActive() || typeof row.animate !== 'function') return false;
    if (Math.abs(to - from) < 0.5) return false;
    cancelSmoothTraceLayoutAnimation(row);
    row.style.overflow = 'clip';
    row.setAttribute('data-smooth-trace-layout-owned', '1');
    var insertion = options.insertion === true;
    var animation = row.animate([
        { height: from + 'px', opacity: insertion ? 0.45 : 1 },
        { height: to + 'px', opacity: 1 },
    ], {
        duration: insertion ? 190 : 230,
        easing: 'cubic-bezier(0.22, 1, 0.36, 1)',
    });
    smoothTraceLayoutAnimations.set(row, animation);
    function cleanup() {
        if (smoothTraceLayoutAnimations.get(row) !== animation) return;
        smoothTraceLayoutAnimations.delete(row);
        row.style.removeProperty('overflow');
        row.removeAttribute('data-smooth-trace-layout-owned');
    }
    animation.onfinish = cleanup;
    animation.oncancel = cleanup;
    return true;
}

function animateSmoothTraceRowInsertion(row) {
    if (!row || !row.isConnected || !row.getBoundingClientRect) return false;
    var targetHeight = row.getBoundingClientRect().height;
    return animateSmoothTraceRowHeight(row, 0, targetHeight, { insertion: true });
}

function mutateSmoothTraceRowHeight(row, mutation) {
    if (!row || typeof mutation !== 'function') return;
    if (!isSmoothStreamActive() || !row.isConnected || !row.getBoundingClientRect) {
        mutation();
        return;
    }
    var fromHeight = row.getBoundingClientRect().height;
    cancelSmoothTraceLayoutAnimation(row);
    mutation();
    var toHeight = row.getBoundingClientRect().height;
    animateSmoothTraceRowHeight(row, fromHeight, toHeight);
}

function settleSmoothTraceHeightAnimations(root) {
    if (!root || !root.querySelectorAll) return;
    root.querySelectorAll('[data-smooth-trace-layout-owned]').forEach(function (row) {
        cancelSmoothTraceLayoutAnimation(row);
    });
}
