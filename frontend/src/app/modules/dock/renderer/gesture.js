/**
 * Pointer ownership shared by the docked surface and the float layer.
 *
 * Capture is hardening, not the mechanism: the window listeners carry the
 * gesture either way. Capture is what stops a scroll container the pointer
 * crosses from claiming it, which Chromium reports as a cancelled pointer and
 * an abandoned drag. Environments without the API simply go unhardened.
 */

/**
 * Take ownership of the pointer for the rest of the gesture.
 * @param {Element} element The element the gesture started on.
 * @param {number} pointerId The pointer to capture.
 */
function dockCapturePointer(element, pointerId) {
    if (!element || typeof element.setPointerCapture !== 'function') return;
    try {
        element.setPointerCapture(pointerId);
    } catch (error) {
        // A pointer that already left cannot be captured; the window listeners still carry the gesture.
    }
}

/**
 * Capture the pointer, then follow it on the window until release or cancel.
 * Only that pointer's events count: a second finger or a pen beside the mouse
 * neither moves nor ends the gesture. The listeners remove themselves before
 * `up` or `cancel` runs; the returned callback ends the gesture early.
 * @param {Element} element The element the gesture started on.
 * @param {number} pointerId The pointer to capture and follow.
 * @param {{move:Function,up:Function,cancel:Function}} followers Listeners for move, release, and cancel.
 * @returns {Function} detach callback removing the listeners.
 */
function dockFollowPointer(element, pointerId, followers) {
    dockCapturePointer(element, pointerId);
    const controller = typeof AbortController === 'function' ? new AbortController() : null;
    const options = controller ? { signal: controller.signal } : undefined;
    const own = (event) => event.pointerId === pointerId;
    const onMove = (event) => { if (own(event)) followers.move(event); };
    const onUp = (event) => {
        if (!own(event)) return;
        stop();
        followers.up(event);
    };
    const onCancel = (event) => {
        if (!own(event)) return;
        stop();
        followers.cancel();
    };
    function stop() {
        if (controller) controller.abort();
        else {
            window.removeEventListener('pointermove', onMove);
            window.removeEventListener('pointerup', onUp);
            window.removeEventListener('pointercancel', onCancel);
        }
    }
    window.addEventListener('pointermove', onMove, options);
    window.addEventListener('pointerup', onUp, options);
    window.addEventListener('pointercancel', onCancel, options);
    return stop;
}

/**
 * One pointer gesture at a time for a component. A gesture ends on release, on
 * cancel, or when a new press supersedes it; `reset` runs at each of those ends
 * so the component clears its preview. Unmounting mid-gesture removes the
 * listeners without resetting anything.
 * @param {Function} reset Clears the component's gesture preview.
 * @returns {Function} the gesture starter, called from a pointer-down handler:
 *   `begin(element, pointerId, { move, up })`.
 */
function dockCreateGestureController(reset) {
    let inFlight;
    return function begin(element, pointerId, followers) {
        if (inFlight) inFlight.end();
        const settle = () => {
            inFlight = undefined;
            reset();
        };
        const stop = dockFollowPointer(element, pointerId, {
            move: followers.move,
            up: (event) => {
                settle();
                followers.up(event);
            },
            cancel: settle,
        });
        inFlight = {
            stop: stop,
            end: () => {
                stop();
                settle();
            },
        };
    };
}
