# Architecture

Two native components share a small reference convention, not a new daemon or network service.

1. Codex parses completed visible assistant Markdown for local image references.
   It validates local raster files, deduplicates canonical paths, and bounds the image count.
2. The existing terminal graphics pipeline reserves rows and transmits bounded previews.
   Each image is clipped independently during scrolling; copy/search retain original text.
3. Original-file references are OSC 8 file URLs tagged with `#codex-image-original`,
   attached to the reserved image cells. Draft text and submitted attachments are unchanged.
4. Herdr associates a clicked bitmap with the reference at that terminal coordinate.
   The terminal address determines the source machine, so a remote file is not guessed locally.
5. The native preview immediately shows transmitted pixels, loads the original in the
   background, then provides fit/actual zoom and panning. Its keys do not reach the terminal.

Remote originals are read through existing Herdr core execution, in 1 MiB chunks.
The Unix reader checks regular-file type, file size, and a device/inode/size/time token
around each read. It does not interpolate file paths into shell source. Closing a preview
cancels subsequent chunks; closing its parent closes the preview.

The source patches are independently buildable. Rich inline previews need only the
Codex component and a compatible terminal. Original-file inspection uses both ends.
The current implementations depend on native rendering/event code, so marketplace
metadata alone cannot deploy the complete behavior.
