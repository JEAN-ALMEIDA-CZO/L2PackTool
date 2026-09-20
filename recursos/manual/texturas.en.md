# Texture Upscaler: enlarging a package's textures

This tab takes a texture package from the client, enlarges each image with a
neural network and rebuilds the package. The full path is this:

```
encrypted .utx
  -> decrypt
  -> extract the textures
  -> convert to PNG
  -> upscale (upscayl)
  -> compress to DXT5 with mipmaps
  -> rebuild the package
  -> encrypt again
```

Each step is a separate tool, and they all live in `ferramentas/`. If one is
missing, the tab names it when you start processing.


## Opening a package

**Open a .utx…** picks one file. **Batch: pick a folder…** processes every
`.utx` in a folder at once.

Once the package is open, the list shows each texture with its size. Clicking
one brings the preview up on the right, with the buttons to replace the image,
upscale just that one, or export it.


## The scale is the decision that matters

> **The Lineage 2 client is 32-bit.** Scale 2x **quadruples** texture memory;
> 4x multiplies it by sixteen.
>
> This is not about disk space: it is the memory the game process can address.
> Past that point the client closes by itself — and it closes on entering a
> particular area, not on loading the package, which makes the cause hard to
> connect to the effect.

In practice: tick **what the player sees up close** — weapon, armour, face — and
leave scenery and distant things alone. A whole package at 4x is the most common
recipe for a client that closes.


## The model

`upscayl-standard-4x` is the default and the best starting point. The others
suit different materials: some preserve smooth surfaces, others soften stone and
cloth. Each one's description appears as you select it.

The model's scale and the requested scale are separate things — a `4x` model
used at scale `2x` enlarges and shrinks back, which usually gives a better
result than enlarging straight to 2x.


## Processing

**Tick all** / **Untick all**, then **Process**. The progress shows which
texture it is on and how much is left.

Only the ticked textures are enlarged. The others go into the rebuilt package as
they were — nothing is lost by not being ticked.

The result lands in a working folder. The client's package is not touched until
you install.


## What comes out different from what went in

The rebuilt package is not byte-for-byte identical to the original, even in the
textures you did not tick: it is reconstructed from scratch by `ucc`. That is
normal, and it is the reason the original is kept.

A texture with transparency keeps its alpha channel. A texture already in DXT is
decompressed, enlarged and compressed again — and recompression always costs a
little quality, which is one more argument for ticking only what matters.
