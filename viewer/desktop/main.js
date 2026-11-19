// @ts-check
import { View, div, image } from "gpui-kit";
import { theme, props, readTextFile, watchFolder, exec, checking } from "herdr";

const DATA = __VIEWER_DATA__;
const BIN = __VIEWER_BIN__;
const HOME = __VIEWER_HOME__;

export default class ImageViewer extends View {
  init(_props, cx) {
    this.source = props()?.source || "manual";
    this.snapshot = null;
    this.index = 0;
    this.zoom = 0;
    this.size = { width: 500, height: 650 };
    this.closed = false;
    this.error = "";
    if (checking()) return;
    cx.spawn(async (cx) => {
      while (!this.closed) {
        try {
          const text = await readTextFile(`${DATA}/state/${this.source}.json`);
          const next = text ? JSON.parse(text) : null;
          if (next?.source !== this.source) this.snapshot = null;
          else if (JSON.stringify(next) !== JSON.stringify(this.snapshot)) {
            this.snapshot = next; this.index = 0; this.zoom = 0;
          }
          this.error = "";
        } catch (e) { this.snapshot = null; this.error = String(e); }
        cx.notify();
        this.watch = watchFolder(`${DATA}/state`);
        await this.watch;
      }
    });
  }
  close() { this.closed = true; this.watch?.cancel(); }
  button(label, id, action) {
    const t = theme();
    return div().id(id).px(9).py(6).rounded(5).cursor_pointer()
      .hover(s => s.bg(t.hover)).on_click((_e, cx) => { action(cx); cx.notify(); }).child(label);
  }
  render(_cx) {
    const t = theme();
    const items = this.snapshot?.images || [];
    const current = items[this.index];
    const toolbar = div().flex().items_center().gap(4).p(6).flex_none()
      .child(div().flex_1().text_color(t.foreground).child("Images"))
      .child(this.button("‹", "previous", () => { this.index = Math.max(0, this.index - 1); this.zoom = 0; }))
      .child(div().text_color(t.muted).child(items.length ? `${this.index + 1} / ${items.length}` : "0 / 0"))
      .child(this.button("›", "next", () => { this.index = Math.min(items.length - 1, this.index + 1); this.zoom = 0; }))
      .child(this.button("Fit", "fit", () => { this.zoom = 0; }))
      .child(this.button("100%", "actual", () => { this.zoom = 1; }))
      .child(this.button("−", "out", () => { this.zoom = Math.max(0.1, (this.zoom || 1) / 1.25); }))
      .child(this.button("+", "in", () => { this.zoom = Math.min(8, (this.zoom || 1) * 1.25); }));
    const root = div().id("image-viewer").flex().flex_col().size_full().bg(t.surface)
      .text_size(13).text_color(t.foreground).on_size_change((size, cx) => {
        if (this.size.width !== size.width || this.size.height !== size.height) { this.size = size; cx.notify(); }
      }).child(toolbar);
    if (!current) return root.child(div().p(20).text_color(t.muted)
      .child(this.error || this.snapshot?.message || "Waiting for an image reply from this Codex session…"));
    const fit = Math.min(1, Math.max(40, this.size.width - 24) / current.width,
      Math.max(40, this.size.height - 140) / current.height);
    const scale = this.zoom || fit;
    return root
      .child(div().px(12).pb(8).text_color(t.muted).child(`${current.name} · ${current.width} × ${current.height} · ${Math.round(scale * 100)}%`))
      .child(div().id("image-scroll").flex_1().min_h(0).overflow_scroll().p(8)
        .child(image(`data/herdr-image-viewer/images/${current.preview.split(/[\\/]/).pop()}`).w(current.width * scale).h(current.height * scale)))
      .child(div().flex_none().px(8).py(4).child(this.button("Open original", "original", cx => {
        cx.spawn(async (cx) => {
          const r = await exec(BIN, ["--app-home", HOME, "open-original", "--source", this.source, "--index", String(this.index)]);
          if (r.code) this.error = r.stderr; cx.notify();
        });
      })))
      .child(div().px(12).pb(8).text_color(t.muted).child(this.error || this.snapshot?.message || ""));
  }
}
