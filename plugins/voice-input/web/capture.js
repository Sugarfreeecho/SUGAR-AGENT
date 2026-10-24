/** Browser capture; recording bytes and media resources belong to one operation. */
export class SpeechCapture {
    constructor() {
        this.cancelled = false;
        this.chunks = [];
        this.bytes = 0;
    }

    async start(onFailure) {
        if (!navigator.mediaDevices || typeof MediaRecorder === 'undefined') {
            throw new Error('unavailable');
        }
        const stream = await navigator.mediaDevices.getUserMedia({
            audio: { echoCancellation: true, noiseSuppression: true }, video: false,
        });
        if (this.cancelled) {
            stream.getTracks().forEach(track => track.stop());
            throw new Error('cancelled');
        }
        this.stream = stream;
        try {
            this.context = new AudioContext();
            this.analyser = this.context.createAnalyser();
            this.analyser.fftSize = 256;
            this.levelSamples = new Float32Array(256);
            this.context.createMediaStreamSource(stream).connect(this.analyser);
            this.recorder = new MediaRecorder(stream);
            this.recorder.ondataavailable = event => {
                if (this.cancelled || !event.data.size) return;
                this.bytes += event.data.size;
                if (this.bytes > 8 * 1024 * 1024) { onFailure(new Error('too-large')); return; }
                this.chunks.push(event.data);
            };
            this.recorder.onerror = () => onFailure(new Error('device-lost'));
            stream.getTracks().forEach(track => { track.onended = () => onFailure(new Error('device-lost')); });
            this.recorder.start(250);
        } catch (error) {
            await this.dispose();
            throw error;
        }
    }

    level() {
        if (!this.analyser) return 0;
        this.analyser.getFloatTimeDomainData(this.levelSamples);
        let sum = 0;
        for (const sample of this.levelSamples) sum += sample * sample;
        return Math.sqrt(sum / this.levelSamples.length);
    }

    async stop(maxSeconds) {
        try {
            if (!this.recorder || this.recorder.state !== 'recording') throw new Error('empty');
            await new Promise((resolve, reject) => {
                this.recorder.onstop = resolve;
                this.recorder.onerror = () => reject(new Error('device-lost'));
                this.recorder.stop();
            });
            if (this.cancelled) throw new Error('cancelled');
            this.stream.getTracks().forEach(track => { track.onended = null; track.stop(); });
            const blob = new Blob(this.chunks, { type: this.recorder.mimeType });
            if (!blob.size) throw new Error('empty');
            const decoded = await this.context.decodeAudioData(await blob.arrayBuffer());
            if (this.cancelled) throw new Error('cancelled');
            const offline = new OfflineAudioContext(1, Math.max(1, Math.floor(Math.min(decoded.duration, maxSeconds) * 16000)), 16000);
            const source = offline.createBufferSource();
            source.buffer = decoded;
            source.connect(offline.destination);
            source.start();
            const rendered = await offline.startRendering();
            if (this.cancelled) throw new Error('cancelled');
            return encodeSpeechWave(rendered.getChannelData(0));
        } finally { await this.dispose(); }
    }

    dispose() {
        if (this.disposal) return this.disposal;
        this.cancelled = true;
        this.disposal = this.release();
        return this.disposal;
    }

    async release() {
        if (this.stream) this.stream.getTracks().forEach(track => { track.onended = null; track.stop(); });
        if (this.recorder) {
            this.recorder.ondataavailable = null;
            this.recorder.onerror = null;
            // A stop already being awaited must still receive its final stop event.
            if (this.recorder.state === 'recording') this.recorder.stop();
        }
        if (this.context && this.context.state !== 'closed') await this.context.close();
        this.analyser = null;
        this.chunks = [];
    }
}

/** Encode 16 kHz mono floating-point samples without a server-side codec. */
export function encodeSpeechWave(samples) {
    const bytes = new Uint8Array(44 + samples.length * 2);
    const view = new DataView(bytes.buffer);
    function tag(offset, value) { for (let i = 0; i < value.length; i++) bytes[offset + i] = value.charCodeAt(i); }
    tag(0, 'RIFF'); view.setUint32(4, bytes.length - 8, true); tag(8, 'WAVE'); tag(12, 'fmt ');
    view.setUint32(16, 16, true); view.setUint16(20, 1, true); view.setUint16(22, 1, true);
    view.setUint32(24, 16000, true); view.setUint32(28, 32000, true);
    view.setUint16(32, 2, true); view.setUint16(34, 16, true); tag(36, 'data');
    view.setUint32(40, samples.length * 2, true);
    samples.forEach((sample, i) => {
        const value = Math.max(-1, Math.min(1, sample));
        view.setInt16(44 + i * 2, Math.round(value * (value < 0 ? 32768 : 32767)), true);
    });
    return bytes;
}
