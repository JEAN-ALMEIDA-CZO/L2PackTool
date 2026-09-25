# Creating a skill: what to fill in

A skill lives in the same two places an item does — the **client** knows how to
draw it, the **server** knows what it does — and the **id** ties them together.

The difference that changes everything: a skill has **levels**. It is not one
row, it is a block of rows, one per level, in each table:

| File | What it holds |
| --- | --- |
| `skillgrp.dat` | icon, mana, range, cast time — per level |
| `skillname-e.dat` | name and description — per level |

In this client that is 3,067 skills across 42,019 rows. Copying a skill copies
all of its levels, in both tables, at once. Half a copy gives you the skill that
exists up to level 12 and vanishes at 13.


## Editing or creating

The screen has a **mode**, written in large letters at the top of the right-hand
panel:

```
Editing skill 1086 — Might
New skill 90000, copied from 1086
```

**Clicking a skill in the list edits that skill.** The fields fill with its
data, the id locks to its own, and the button becomes **Rewrite the skill**. The
id locks on purpose: changing the number there would really be creating another
one.

**Creating goes through the New skill… window.** It asks for the id (with
Suggest), name, description, icon and the level cut; it refuses an id that
already exists without the replace tick; it warns when the id falls inside the
game range. What comes out of it fills the panel, and the fields stay editable —
it is a guided start, not a fence.

After generating, the screen switches to **editing what just came out**: that is
what you do next, see how it turned out and adjust.


## 1. Pick the base skill

The list shows **one row per skill**, not per level — it would be 42 thousand
rows with the same skill repeated forty times. The "levels" column says how many
the copy will take.

Search by name, by id or by icon name. Pick a base close to what you want: the
mode (active, passive, toggle), the cast time and the animation come from it.


## 2. Identification

### id

**Suggest** finds the first free one from **90000** up. That range stays away
from two things: the game's own ids and the **enchant routes**, which occupy
50000 and up.

### name and description

The name goes the same on every level, which is what the game does.

The game's description changes from level to level — it is the "Power 25" that
becomes "Power 27". Leaving the description blank makes each level inherit the
description of the same level of the base skill, which is usually closest to
right. Writing one puts it on every level.

### icon

`package.object`, as with items — skill icons are usually `icon.skill0003`.

In the **New skill…** window the icon is picked **by sight**: there is a grid of
thumbnails on the right, which opens on the `icon.skill*` because it starts from
the base skill's icon. It shows 240 at a time; the label says how many were left
out and the search narrows it — nothing is hidden.

Just below, **Use an image of my own** takes a drawing of yours; see the last
section.

### copy up to level

Blank, the copy takes every real level.

Fill it in when the base has many levels and you only want the first few.


### the enchant routes

An enchant route is **not another skill**: they are high levels of the same one —
101, 102, 103 for the first route; 201 for the second, and so on. High Five has
eight routes, up into the 800s.

Two things follow from that.

**The level count is of real levels only.** Skill 1 has 37 levels and 247 rows in
the client: the other 210 are routes. Adding everything up wrote `levels="247"`
into the XML — a server promising a level the client cannot draw. Checked against
the datapack: 7,576 skills right before, **8,102 of 8,136** now. The label of the
selected skill states both counts when there are routes.

**The copy leaves the routes out unless you tick the box.** Their `ench_skill_id`
points at the **original's** partner skill — copied, the client starts offering an
enchantment the new server does not have, pointing at another skill. Without
them, the `is_ench` mark is zeroed too: leaving it without the routes would open
an empty enchant window.

The box is greyed out when the selected skill has no routes at all.


## 3. Server XML

**Already filled in** is what is in `skillgrp`: mode, mana per use, range and
cast time. The client's `hit_time` is in seconds and the server counts in
milliseconds; the conversion is done for you.

The rest is your choice, always from a list.

### skill type

What the skill does. It is the most important field — it decides which server
code runs.

| type | what it is |
| --- | --- |
| `PDAM` | physical damage |
| `MDAM` | magical damage |
| `BLOW` | blow from behind |
| `DRAIN` | damage that returns health |
| `HEAL` / `HOT` | healing, at once or over time |
| `MANAHEAL` / `MANARECHARGE` | restores mana |
| `BUFF` | improves a stat for a while |
| `DEBUFF` | worsens a stat on the target |
| `PASSIVE` | always on, never cast |
| `CONT` | continuous effect while active |
| `STUN`, `ROOT`, `SLEEP`, `FEAR`, `PARALYZE` | control |
| `POISON`, `BLEED` | damage over time |
| `RESURRECT` | resurrects |
| `AGGDAMAGE` / `AGGDEBUFF` | aggression |

### mode

`ACTIVE` is cast; `PASSIVE` is always on; `TOGGLE` switches on and off and
drains mana while on. It comes from the client.

### target

`SELF`, `ONE` on a target, `PARTY`, `CLAN`, `AURA` on everything around,
`AREA` around the target. There are 28 options in the list.

### power

For damage it is the base damage; for healing it is how much it heals; for a
control effect it is the chance. What it means depends on the skill type.

### magic level

The character level from which the skill has full efficiency. Using a skill
whose magic level is well above yours reduces the effect.

### mana per use, mana on start, health per use

Cost. `mana on start` is spent when the cast begins — the rest when it
completes.

### range, effect range, radius

`range` is how far you can be to cast it. `effect range` is how far the effect
reaches. `radius` is the size of the area for area skills.

### cast time, cool time, reuse

In milliseconds. `cast time` is the animation; `cool time` is the lock right
after; `reuse` is how long until it can be cast again.

### element

`FIRE`, `WATER`, `WIND`, `EARTH`, `HOLY`, `DARK`. It makes the damage count
against the matching resistance on the target.

### weapons allowed

Restricts the skill to a weapon type in hand — `SWORD`, `BOW`, `DUAL`. Blank,
any weapon works.

### is magic

`true` makes the skill count as magic: it is interrupted by damage and uses
spiritshots instead of soulshots.

### aggression

How much hate the skill generates on monsters.


## Read from the server

**Power, reuse and skill type do not exist in the client.** The `skillgrp` keeps
icon, mana, range and cast time, and nothing else.

The **Read from the server** button, on the XML tab, brings the rest. It reads
the skill **selected in the list** — not the one in the **new id** box. The
box says where the skill is going; the list says where it comes from. To read
back one you created, select it in the list: it is there once you generate.

If it is not there, it says the skill does not exist on the server side yet.

A warning appears when the skill uses per-level values: the `<set>` carries the
alias (`#power`) and the table stays off screen. The alias is shown as it is.

## 4. Stats the skill gives

The `<for>` block, same as items: **operation**, **stat**, **value**.

This is what makes a `BUFF` worth anything. A buff that raises attack is
`skillType BUFF` plus `mul` on `pAtk` with value `1.15` — 15% more.

For `PASSIVE` it is usually `add` or `mul` straight on the stat.

**Double-clicking a row in the table** sends operation, stat and value back to
the fields above, and the button becomes **Save**. Changing `1.30` to `1.25` no
longer means removing the row and typing all three fields again.

**Mind the scale**: `mul` multiplies (`1.15` = plus 15%), `add` adds the raw
number. An `add` of `1.15` on `pAtk` adds one point of attack, not 15%.

The stat list is the same as for items, and closed for the same reason: a name
the server does not know brings down the loading of the whole skill table.


## Per-level values

The game writes progression with `<table>`: the "Power 25" that becomes "Power
27" is not a number, it is a list with one value per level.

**Just type the values separated by spaces**, in any XML field or in the `value`
column of a stat:

```
431 458 486 516 547
```

The program builds the table and points the `<set>` at it:

```xml
<table name="#power"> 431 458 486 516 547 </table>
<set name="power" val="#power"/>
```

Commas and semicolons count as spaces. A field holding text, like
`SWORD,BLUNT`, stays a single value — that is a list of weapons, not a
progression.

**The count has to match the number of levels.** A table with fewer values than
the skill has levels raises no error on save: it is the server that drops the
skill, or hands out the wrong level, much later. The program checks and warns
before generating.

**Reading from the server opens the tables.** `#power` comes back as its
numbers, which is what the field takes back — you can read a finished skill,
change level 5 and rewrite it.


## 5. What this screen does not do

**Effects.** An `<effect>` inside the `<for>` — poison ticking every second, a
transformation, a summon — is also left out. The generated XML is the correct
base; the effect goes on top.

**Conditions.** The `<cond>` requiring a weapon, class or state is not
generated.


## 6. Generate, install, and the next one

**Generate** writes the tables and the `<id>-skill.xml` into a separate folder.
Nothing in the client changes yet.

**Install in the client** puts the tables in place, keeping the originals in
`system/backup_skills` the first time. **Restore originals** undoes it.

The XML goes by hand into the server's skill folder — usually
`data/xml/skills/` — and the gameserver restarts.

After generating, the screen gets ready for the next one: it suggests the next
id and clears name, description, level cut and stats.

**Close the client before installing.**


## 7. Your own icon

In the icon window, the **Your own image** tab takes a drawing of yours — PNG,
JPG, BMP, TGA, DDS.

What happens: the image is fitted to 32x32 (without stretching — a non-square
image is centred on a transparent square), compressed to DXT, built into a
`.utx` package. The icon field receives the finished reference.

The package is left **prepared, not installed**: it comes out in the output
folder with the tables and enters `systextures` on the same **Install into the
client**. One action, one place — installing right away would leave an icon
inside the client while the rest does not exist anywhere yet.

**The package is yours.** The program never writes inside the game's `Icon.utx`
or `Icon.u`, and refuses if you try: a mistake in your own package costs one
icon; in the game's it would cost all fourteen thousand. Nothing is lost — the
client loads as many icon packages as there are, and yours already has several.

Adding a second icon to the same package **rebuilds the whole package**, with
the ones already inside. It is slower and it is the only honest way: half a
rebuild would lose the old ones.

The package and icon names take letters, digits and underscores. The file name
really matters — the `.utx` encryption key derives from it — so renaming the
package after it is created corrupts it. If you need another name, create it
again.
