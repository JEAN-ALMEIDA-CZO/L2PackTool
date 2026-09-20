# NPC: creating an NPC in the client

This tab creates a new NPC in the **client** — its appearance: which mesh it
uses, which name it shows, and which effect glows around it. What the NPC **is**
— HP, drop, spawn, shop — belongs to the tab below, `2 - Server`.

The screen has three parts, in the order you use them:

1. the NPCs the client already has, to choose whose appearance to copy
2. the effects the client already has, to choose what will glow
3. the form for the new NPC, with the two buttons


## Choosing who to copy

`Load` reads `npcgrp.dat` and lists the client's NPCs with each one's mesh. The
right-hand column says what that NPC has: `Mesh x2, Sprite x1` means two meshes
and one effect.

Copying from an NPC that already works is the short path: the mesh, the texture
and the animations come ready, and what you change is the id, the name and the
effect.


## The effect

The effect list comes from the client's own packages. `Add the selected effect`
attaches an effect to the new NPC; `Apply to the ticked one` puts it on an
existing one.

The **height (Z)** moves the effect up or down relative to the chosen bone. The
drawing beside it shows where it sits on the mesh — an effect at the wrong `Z`
comes out of the feet or floats above the head.

**Obey the height** makes the effect scale along with the mesh. Without it, an
effect drawn for a normal-sized character is tiny on a giant.


## Script or quick

| mode | what it does |
| --- | --- |
| **Script (compiles)** | generates its own class and compiles an `FX_<id>.u` package |
| **Quick (.dat only)** | writes only the line in `npcgrp.dat` |

Quick mode is simpler and creates no new file, but you cannot attach an effect
to it. Script mode is the one that allows an effect, and that is why it is the
default when an effect is chosen.

> An NPC with its own class usually shows as `NoNameNPC` in the viewer, even
> with the name written into `npcname-e.dat`. That is not a fault: the viewer
> resolves the name differently from the game. The way out is to tick **the
> server sends the name and the title** in the server tab.


## Seeing it in game

The viewer opens the mesh with its texture and plays the animations. It **does
not show the effect**: a particle emitter is not among the resources it opens,
and no Lineage 2 viewer draws Unreal Engine 2 particles — only the game engine
does that.

To really see the effect, the path is the client's own development mode. The
commands it recognises are listed in the tab.


## Generating and installing

These are separate steps on purpose.

**Generate** writes everything to an output folder and does not touch the
client. You see what came out — the tables, the package, the name — and only
then authorise it.

**Install into the client** copies it in. Anything overwritten goes first to
`system/backup_npc`.

Installing by accident into a client you play on shows up when you log in, which
is too late.


## NPCs created in this client

The button opens the list of what this program has already put into this client,
with the option to remove. Removing takes the line out of `npcgrp.dat`, the name
out of `npcname-e.dat` and the `FX_<id>.u` package — all with a copy made first.

On the server side, that NPC's XML is still there, and it has to be deleted by
hand and followed by `//reload npc`. The window says so at the time.
