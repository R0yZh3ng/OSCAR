// Downsamples the mic (44.1/48 kHz on iOS) to 16 kHz mono int16 and posts ~100 ms chunks.
class PcmWorklet extends AudioWorkletProcessor {
  constructor() {
    super();
    this.ratio = sampleRate / 16000;
    this.pos = 0;          // fractional read position into the carried-over input
    this.carry = new Float32Array(0);
    this.out = new Int16Array(1600);
    this.n = 0;
    this.sumSq = 0;
  }
  process(inputs) {
    const ch = inputs[0][0];
    if (!ch) return true;
    const buf = new Float32Array(this.carry.length + ch.length);
    buf.set(this.carry);
    buf.set(ch, this.carry.length);
    // box-average each output sample's window: cheap anti-aliasing before decimation
    while (this.pos + this.ratio <= buf.length) {
      const a = Math.floor(this.pos), b = Math.min(buf.length, Math.floor(this.pos + this.ratio));
      let s = 0;
      for (let i = a; i < b; i++) s += buf[i];
      const v = Math.max(-1, Math.min(1, s / Math.max(1, b - a)));
      this.out[this.n++] = v < 0 ? v * 0x8000 : v * 0x7fff;
      this.sumSq += v * v;
      this.pos += this.ratio;
      if (this.n === this.out.length) {
        this.port.postMessage({ pcm: this.out.buffer, rms: Math.sqrt(this.sumSq / this.n) }, [this.out.buffer]);
        this.out = new Int16Array(1600);
        this.n = 0;
        this.sumSq = 0;
      }
    }
    const used = Math.floor(this.pos);
    this.carry = buf.slice(used);
    this.pos -= used;
    return true;
  }
}
registerProcessor("pcm-worklet", PcmWorklet);
