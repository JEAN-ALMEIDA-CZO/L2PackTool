# Glow: the shine on a weapon

The **glow** is the particle effect attached to a weapon — the streak of light
that follows the blade, the halo on a bow, the aura on boss weapons. It belongs
to the **client**: it lives in `weapongrp.dat`, not on the server. Whoever
equips the weapon sees the glow because their client has the altered table; a
player with the original client sees nothing.

That has a practical consequence: **the glow has to go in the client patch**,
along with the textures and the meshes. Changing only the server does nothing.


## Where the numbers live

Every weapon has room for **two** effects, each with five adjustments:

```
effect         LineageEffect.c_u006    which particle
along the blade                        from hilt to tip
height                                 up and down
side                                   left and right
size                                   how much the effect grows
intensity                              how brightly it burns
```

In this client, **282 of 1,346 weapons** already have a glow, in 48 different
combinations of those five numbers — meaning they really are tuned weapon by
weapon, not copied from one template.

The range the game uses on its own weapons:

| adjustment      | game range     |
|-----------------|----------------|
| along the blade | -20 to 4       |
| size            | 0.80 to 1.55   |
| intensity       | 0.20 to 1.00   |

**These are not limits.** They are a reference: type 40 for the length and the
program accepts it, and the effect ends up off the weapon. The ruler says so
when that happens.


## The ruler

On the right is the **blade lying flat**, hilt at one end, tip at the other.
The two numbers at the ends are not guesses: they come from **this weapon's
mesh**, exported from the client package and measured vertex by vertex.

A weapon lies along its longest axis. The Dragon Slayer, for example, runs from
**-17.8 to 40.8** on the X axis: the hilt sits behind zero, the whole blade in
front of it. That is the axis the *along the blade* adjustment moves on — which
is why the orange circle slides as you type.

The circle's size follows the **size** field.

**The ruler does not draw the effect.** Only the game engine draws Unreal
Engine 2 particles — not even umodel opens them. The ruler tells you **where**
the glow will sit; what it *looks like*, only in game.


## Viewing the weapon in 3D

**View the weapon in 3D** opens the mesh in umodel's viewer: you can turn it,
see the shape and work out where the tip is. It helps you pick a value for
*along the blade* with some idea of what you are doing, especially on long
weapons.

The glow does **not** appear there, for the reason above.


## Choosing the effect

The list on the right starts with the **only the ones the game uses on
weapons** box ticked -- and that is how it should stay most of the time.

The client has **1,812 installed effects**, and the overwhelming majority were
not made for a weapon: they are NPC auras, ground effects, spells. Put on a
sword they come out the wrong size, in the wrong place, or simply do not show
up. Several belong to newer chronicles and do not work in Interlude -- that is
the warning the community tutorial gives, and it is right.

> **Not every effect in the full list is compatible.** The ticked list shows
> the ones **this client already draws on weapons** -- that is not an opinion,
> it is a count of its own `weapongrp.dat`.

### How the suggestion is built

The program counts, in your client, which effect the game uses on each weapon
type. If the client put `c_u002` on nine daggers and on nothing else, that is
the dagger's effect -- and it works, because the game draws it every day.

In this client the count gives:

| effect | where the game uses it |
| --- | --- |
| `c_u001` | fist (22) |
| `c_u002` | dagger (9) |
| `c_u003` / `c_u008` | bow (9 and 20) |
| `c_u004` | sword, dagger, two-hander, dual (54 in total) |
| `c_u005` / `c_u007` | mace, hammer, pole |
| `c_u006` | sword (18) |
| `c_u000` | two-handed sword (5) |
| `e_u092_a` … `e_u092_k` | the **hero glow**, one per weapon type |
| `SHEV_weapon_shadow_*` | shadow weapons from a custom pack |

The hero glow mapping matches the one the tutorial publishes -- a = sword,
b = two-hander, g = dagger, h = fist, i = bow, j = dual sword. The difference is
that here it was **measured in your client**, not copied.

Pick a weapon and the effects for that type rise to the top, with the **used
on** column saying on how many weapons like it the game uses each one.

### Copying from a weapon that already works

The five numbers cannot be guessed. The effect ends up in the wrong place -- in
the middle of the body, behind the weapon, far too big -- and there is no way to
tell which of the five is wrong.

If some weapon in the game already has its glow sitting right, **its numbers are
the answer**. `Copy from another weapon…` opens the client's weapon list, with
icon and filter, and brings that one's effect and five adjustments into the
fields.

It is the shortest way when what you want is "like that one, in another colour".

The log warns when the source weapon is of **another type** -- copying from a
two-hander to a dual, say. The numbers are still valid, but one mesh is not the
size of the other, and the framing may not carry over.

### The five numbers come with it

Put a suggested effect on and the five adjustments are filled in with **the
ones the game uses with that effect** -- not with 0 and 1. The glow is born
framed on the blade instead of shrunk at the hilt.

Untick the box and the list goes back to all 1,812. Worth it for someone who
knows what they are looking for.


## Creating a new weapon, instead of touching one that exists

Putting a glow on one of the game's weapons changes **that weapon for
everyone**. Anyone who equips a Dragon Slayer, any of them, will see the new
glow. Sometimes that is the point; most of the time it is not.

**Create a new weapon…** copies the chosen weapon to an id of its own, already
carrying the glow on screen. The original is not touched.

The window asks for the id, the name, the description and the icon. The copy
takes the whole `weapongrp.dat` row: mesh, texture, sound, type, weight and the
client's numbers all come from the base.

Use an id **above 30000**, well clear of the game's range. Writing over an item
that exists is the most expensive mistake here.

The server's `<id>-item.xml` comes out alongside -- but **only with what can be
read from the client**: type, body part, weight, material, grade, shots. Damage,
defence and price do not exist in `weapongrp.dat`; they belong to the server.

To finish it, go to the **Items** tab, pick the new weapon in the list and use
the **New item** window, which has the Numbers, Stats and Skills pages. That is
where this belongs, and having two places that do the same thing would give you
two places to fix when it changes.

## The "Weapons created" page

Lists the client's weapons with an id **above 30000** -- the range the game does
not use. It comes from `weapongrp.dat` itself, not from a registry kept on the
side: a registry would go stale when you switched clients, restored a backup or
copied the folder to another machine, and the screen would start showing
weapons that do not exist and hiding the ones that do.

That also shows custom weapons made by other programs -- and rightly so:
whoever opens this page wants to see the client's custom weapons, not only the
ones that went through here.

| column | what it says |
| --- | --- |
| type | sword, bow, dagger… read from the client |
| glow | the effect it has today |
| XML | whether one exists, in the output folder or the server's |

**Edit this one's glow** takes the weapon to the other page, already picked and
with the glow it has.

**See the XML** builds the XML on the spot from the client's row and shows it.
It carries only what can be read from there -- damage, defence and price belong
to the server.

**Write the XML to the server** writes into its items folder. Where that folder
is comes from the server itself: the program reads its files to find out. If it
cannot, it says so and writes nothing -- better not to write than to write in
the wrong place. Then, in game: `//reload item`.

**The subfolder matters.** `custom` is the L2J datapack convention, but not
everyone's: some packs split the items folder by kind -- `weapons`, `armors`,
`accessories`, `etcitems` -- and **do not read weapons from `custom`**. Writing
there hands the file to a folder the server ignores, and the symptom is "I made
the weapon and it does not exist".

The box beside the Server field lists the subfolders that **exist** on your
server and already picks the one that matches the item's kind -- `weapons` for a
weapon, when it is there. The choice is remembered.

**Delete** takes the weapon out of the tables in memory, and deletes the
server's XML with it. The client only changes in **Install in the client**, so
until then you can undo it by closing the program without generating.

Tick **write the XML to the server** at the top of the screen and a new weapon's
XML is delivered as part of creating it.

## Generating and installing

As on the other tabs, these are two steps on purpose:

1. **Generate** writes the altered `weapongrp.dat` to a separate folder.
   Nothing is copied to the client.
2. **Install in the client** copies it. The first time, the original goes to
   `backup_itens/`, and **Restore originals** undoes everything.

Before anything is written, the table is rebuilt from the definition and
compared with the original binary **byte for byte**. If the round trip does not
reproduce it, the definition does not describe this client and nothing is
written — that is what keeps a broken `weapongrp.dat` from reaching the client.

The client reads `weapongrp.dat` **only at start-up**. After installing, close
and reopen the game.


## The "Enchanting" page

> **This applies to EVERY weapon on the server.** It is not an item setting.

The glow on the other pages belongs to **the weapon**: a Dragon Slayer with
`c_u000` shines all the time, already at +0. The **enchant** glow is something
else -- the halo any weapon gains when it is refined, the blue at +4, the gold
at +7 -- and it lives in `env.int`, one file for the whole client.

### The two numbers

| field | what it does | in the original game |
| --- | --- | --- |
| `EnchantMeshShow` | from +N on, the weapon takes colour | 4 |
| `EnchantEffectShow` | from +N on, the flame appears | 7 |

They are independent: the weapon can take colour without a flame, and the other
way round. **Below the first number, changing that level's colour changes
nothing on screen** -- it is the most common reason for "I edited it and nothing
happened".

Drop the second one to 4 and every +4 weapon starts to glow. The two are
independent: the mesh can change without a glow, and the other way round.

### The colour of each level

The stock client carries **21 levels**, `Enchant0` to `Enchant20`, with two
colours each -- the game makes the glow vary between them -- plus opacity and
intensity.

**The strip at the top** shows them all at once, each split into its two
colours. In this client you can see the whole progression at a glance: grey up
to +3, blue from +4 to +15, red from +16 to +20. Click a column to edit that
level.

### Above +20

Right below the series there is an **`Enchant=`** line, with no number. It is
what the client uses for **any enchant above the last level written**. In this
client it is the same as +20 -- which is why a +40 today has the same colour as
a +20.

A server that enchants higher has two ways:

1. **Change only `Enchant=`.** Tick the `this is Enchant=` box, pick the colour
   and save. One line covers everything above +20.
2. **Give each level its own colour**, up to **+60**. Pick the level in the
   field and edit as usual. The program writes `Enchant21` on into the file, in
   order, right before `Enchant=`.

In the strip, the **dashed** levels do not have a line of their own yet: the
colour shown on them is borrowed from `Enchant=`. Go into one and the fields
already carry that colour -- it is what the level has today, not a blank.

> **One caveat.** Whether the client *reads* `Enchant21` on cannot be proven
> outside the game -- only by testing. What can be said is that writing them
> breaks nothing: an unknown key in an Unreal `.int` is ignored, and if it is
> ignored then `Enchant=` still applies, exactly as today.

**Copy to the ones above** repeats the current level on every level above it
**and on the `Enchant=` line** -- the short way to "from +20 on, all gold".

### Picking the colour

> **What the game does with the two colours, this manual does not claim** --
> it cannot be proven outside the game, and claiming without proof has already
> cost dearly here.
>
> What is known, and how:
>
> - In the 21 stock levels colour 2 is **always the same colour as 1, a little
>   darker** -- `(40,87,126)` and `(30,70,110)` at +7, `(220,0,0)` and
>   `(195,0,0)` at +20. True for all 21, without exception.
> - `env.int` points at the material
>   `LineageEffectsTextures.Etc.Enchant_Aura001_Shader01`, whose chain runs
>   through a `FadeColor` -- the Unreal class that goes back and forth between
>   two colours. **But the colours baked into that FadeColor are different
>   ones**: `(7,20,69)`/`(5,15,48)`, `(24,41,46)`/`(34,45,47)`,
>   `(90,122,128)`/`(80,109,115)`. None is any level's colour. The material has
>   its own pulse, with its own colours.
> - `EnchantMeshShow`, `EnchantEffectShow` and the `Enchant*` lines **are not in
>   any `.u`'s name table**: they are read by the executable's native code, not
>   UnrealScript. There is nothing to read.
>
> To find out: put two very different colours on a level the client certainly
> reads and look in game. It is the only answer that counts.

**If you changed the colour and nothing happened**, the likeliest reason is not
the colour -- it is the file. See the next section.

### Lines in the wrong place

An earlier version of this program wrote new levels **before the file's first
section header**, outside any section, where the game never reads them. The
symptom was exactly "I edited it and nothing changed".

Reading an `env.int` like that, the screen warns and says how many lines are out
of place. **Generating and installing again cleans the file** and puts
everything inside `[EnchantEffect]`. To start from scratch instead: **Restore
original** and redo it.

Each colour has a swatch and three sliders -- red, green and blue. The slider
writes the number and the number moves the slider: they are the same value, not
two copies of it.

Below, **the file's line writes itself**, on every movement:

```
Enchant7=(R1=40,G1=87,B1=126,R2=30,G2=70,B2=110,Opacity=0.4,Num=0.3)
```

That is exactly what will be written. **Copy** puts it on the clipboard, for
anyone who wants to take it elsewhere.

None of this touches the file yet: **Save the level** keeps it in memory,
**Back to the original** undoes that level only with what the file had when it
was read, and **Copy to the ones above** repeats the current level on every
level above it -- the short way to "from +7 on, all red" without touching
fourteen levels by hand.

### Opacity and intensity

They run from 0.1 to 1 -- and **the game never goes above 1** on either. In
this client:

| level | opacity | intensity |
| --- | --- | --- |
| +0 to +6 | 0.1 | 0.1 |
| +7 | 0.4 | 0.3 |
| +10 | 0.7 | 0.8 |
| +13 on | 1 | 1 |

There are tutorials around suggesting values well above that, with a warning
that it "can lag the server". The high-value part is right; the server part is
not. A particle is drawn by the **client**, every frame, on every enchanted
weapon on screen -- the cost lands on the player's machine, all the more in a
crowded town.

### Generate, install, restore

The same three steps as the other pages, with one extra check: before the file
is called ready, it is **encrypted and decrypted back**, and the result compared
with what was meant to be written. If it does not match, nothing is installed.

That matters more here than on the tables: a broken `env.int` leaves the client
with **no lighting at all**, and the symptom looks nothing like the cause.

The original goes to `backup_env/` on the first install, and **Restore
original** brings it back byte for byte.

The client reads `env.int` **only at start-up**.

## What this screen does not do

**It does not create new effects.** The list shows what the client already has.
A brand-new effect is a new particle package, built elsewhere.


## Cost

A particle is drawn **every frame**, on **every weapon like this one** that is
on screen. High *size* and *intensity* on a common weapon in a busy server cost
more than on a boss weapon one person carries. Worth testing with a crowd
before releasing.
