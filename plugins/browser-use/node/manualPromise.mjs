// Compatibility seam for the vendored upstream relay, not a browser implementation.
export class ManualPromise extends Promise {
  constructor() {
    let resolve, reject;
    super((yes, no) => { resolve = yes; reject = no; });
    this._done = false;
    this._resolve = resolve;
    this._reject = reject;
  }
  static get [Symbol.species]() { return Promise; }
  isDone() { return this._done; }
  resolve(value) { this._done = true; this._resolve(value); }
  reject(error) { this._done = true; this._reject(error); }
}
