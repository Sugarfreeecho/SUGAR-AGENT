// Smooth streaming primitives. This file is concatenated into the shared UI
// runtime before session-scroll-history.js; keep the helpers dependency-free.

const SMOOTH_STREAM_CONFIG = Object.freeze({
    revealDivisor: 8,
    referenceFrameMs: 16.67,
    traceHeightEpsilonPx: 0.25,
    traceHeightStableMs: 50,
    unpinWheelPx: 8,
    gestureWindowMs: 800,
});

// Text wrapping and whole-row layout changes share one scrollTop writer, but
// intentionally use separate motion profiles. Text keeps the original easing
// (including its natural tail); rows keep the newer minimum tail velocity.
const SMOOTH_STREAM_FOLLOW_PROFILES = Object.freeze({
    text: Object.freeze({
        followDtMs: 18,
        followLagRefPx: 160,
        followMinLerp: 0.05,
        followMaxLerp: 0.25,
        followSpeedRefCps: 35,
        followSpeedFactorMin: 0.7,
        followSpeedFactorMax: 2.2,
        minFollowSpeedPxPerSec: 0,
        maxFollowSpeedPxPerSec: 1200,
    }),
    row: Object.freeze({
        followDtMs: 18,
        followLagRefPx: 160,
        followMinLerp: 0.05,
        followMaxLerp: 0.25,
        followSpeedRefCps: 35,
        followSpeedFactorMin: 0.7,
        followSpeedFactorMax: 2.2,
        minFollowSpeedPxPerSec: 60,
        maxFollowSpeedPxPerSec: 1200,
    }),
});

function smoothFollowProfile(channel) {
    return channel === 'text'
        ? SMOOTH_STREAM_FOLLOW_PROFILES.text
        : SMOOTH_STREAM_FOLLOW_PROFILES.row;
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

function computeSmoothFollowStep(lagPx, dtMs, revealCps, channel) {
    var lag = Math.max(0, Number(lagPx) || 0);
    var elapsed = Math.max(0, Number(dtMs) || 0);
    if (lag <= 0.1 || elapsed <= 0) return { advancePx: 0, lerpStep: 0 };
    var profile = smoothFollowProfile(channel);
    var speed = Number(revealCps) > 0
        ? Number(revealCps)
        : profile.followSpeedRefCps;
    var speedFactor = smoothStreamClamp(
        speed / profile.followSpeedRefCps,
        profile.followSpeedFactorMin,
        profile.followSpeedFactorMax
    );
    var baseLerp = smoothStreamClamp(
        (lag / profile.followLagRefPx) * speedFactor,
        profile.followMinLerp,
        profile.followMaxLerp
    );
    var lerpStep = baseLerp * (1 - Math.exp(-elapsed / profile.followDtMs));
    var minAdvance = profile.minFollowSpeedPxPerSec * elapsed / 1000;
    var cappedAdvance = profile.maxFollowSpeedPxPerSec * elapsed / 1000;
    return {
        advancePx: Math.min(lag, Math.max(lag * lerpStep, minAdvance), cappedAdvance),
        lerpStep: lerpStep,
    };
}

/** Measure only execution-trace entries, excluding viewport/chrome height. */
function measureSmoothTraceItemsHeight(root) {
    if (!root || !root.querySelectorAll) return null;
    var total = 0;
    var count = 0;
    root.querySelectorAll('.feed-item').forEach(function (row) {
        var parentRow = row.parentElement && row.parentElement.closest
            ? row.parentElement.closest('.feed-item')
            : null;
        if (parentRow) return;
        var rect = row.getBoundingClientRect ? row.getBoundingClientRect() : null;
        var height = rect ? Number(rect.height) : Number(row.offsetHeight);
        if (!Number.isFinite(height)) return;
        total += Math.max(0, height);
        count += 1;
    });
    return count ? total : 0;
}

function isSmoothTraceHeightStillActive(root) {
    return !!(
        root
        && root.querySelector
        && root.querySelector(
            '.feed-chunk.is-streaming, [data-smooth-trace-layout-owned]'
        )
    );
}

function isSmoothTraceRowLayoutActive(root) {
    return !!(
        root
        && root.querySelector
        && root.querySelector('[data-smooth-trace-layout-owned]')
    );
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
            speedCps: smoothFollowProfile('row').followSpeedRefCps,
            requestedChannel: 'row',
            activeChannel: 'row',
            lastFloor: null,
            lastWrittenTop: 0,
            ownedUntil: 0,
            awayPx: 0,
            gestureTimer: 0,
            touchY: null,
            pointerDown: false,
            pointerStartTop: 0,
            traceHeightSource: null,
            lastTraceItemsHeight: null,
            traceHeightStableSince: 0,
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
        // The inner process viewport and outer chat share a trace root.
        // Read its row geometry once per frame, even when both follow it.
        var traceMeasurements = new Map();
        function measureTrace(root) {
            if (!traceMeasurements.has(root)) {
                traceMeasurements.set(root, measureSmoothTraceItemsHeight(root));
                if (root && typeof uiPerformance !== 'undefined') uiPerformance.count(currentSessionId, 'follow.traceScans');
            }
            return traceMeasurements.get(root);
        }
        activePorts.forEach(function (port) {
            var state = states.get(port);
            if (!state || !state.following || !port.isConnected) {
                activePorts.delete(port);
                if (state && !port.isConnected) state.following = false;
                if (port && port.removeAttribute) port.removeAttribute('data-smooth-follow-owned');
                return;
            }
            var floor = Math.max(0, Number(port.scrollHeight) - Number(port.clientHeight));
            if (
                state.lastFloor == null
                || Math.abs(floor - state.lastFloor) > SMOOTH_STREAM_CONFIG.traceHeightEpsilonPx
            ) {
                // Attribute each actual height delta, not merely each request.
                // A row WAAPI animation has priority while it owns layout;
                // otherwise the caller identifies text wrapping versus rows.
                state.activeChannel = isSmoothTraceRowLayoutActive(state.traceHeightSource)
                    ? 'row'
                    : state.requestedChannel;
                state.lastFloor = floor;
            }
            var traceItemsHeight = measureTrace(state.traceHeightSource);
            if (traceItemsHeight != null) {
                if (
                    state.lastTraceItemsHeight == null
                    || Math.abs(traceItemsHeight - state.lastTraceItemsHeight)
                        > SMOOTH_STREAM_CONFIG.traceHeightEpsilonPx
                ) {
                    state.lastTraceItemsHeight = traceItemsHeight;
                    state.traceHeightStableSince = now;
                } else if (!state.traceHeightStableSince) {
                    state.traceHeightStableSince = now;
                }
            }
            state.animatedTop = Math.min(floor, Math.max(0, state.animatedTop));
            var lag = floor - state.animatedTop;
            if (lag <= 0.25) {
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
            var step = computeSmoothFollowStep(
                lag,
                dtMs,
                state.speedCps,
                state.activeChannel
            );
            var advancePx = step.advancePx;
            var traceHeightStable = traceItemsHeight != null
                && !isSmoothTraceHeightStillActive(state.traceHeightSource)
                && now - state.traceHeightStableSince >= SMOOTH_STREAM_CONFIG.traceHeightStableMs;
            if (traceHeightStable) {
                // A trace block that has left streaming/layout-animation state
                // and whose entries no longer change height has finished its
                // visual growth. End only the residual follower lag; ordinary
                // token wrapping keeps the original interpolation untouched.
                advancePx = lag;
            }
            state.animatedTop = Math.min(floor, state.animatedTop + advancePx);
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
        var requestedChannel = options.channel === 'text' ? 'text' : 'row';
        if (!state.following) {
            state.animatedTop = Math.max(0, Number(port.scrollTop) || 0);
            state.activeChannel = requestedChannel;
            state.lastFloor = null;
            state.lastTraceItemsHeight = null;
            state.traceHeightStableSince = 0;
        }
        if (options.traceHeightSource && options.traceHeightSource.querySelectorAll) {
            state.traceHeightSource = options.traceHeightSource;
        }
        state.following = true;
        state.requestedChannel = requestedChannel;
        state.speedCps = Number(options.speedCps) > 0
            ? Number(options.speedCps)
            : smoothFollowProfile(requestedChannel).followSpeedRefCps;
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
        state.traceHeightSource = null;
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
