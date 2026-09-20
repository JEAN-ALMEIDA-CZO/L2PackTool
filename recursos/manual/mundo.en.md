# NPC and shop: the server side

The client knows how to **draw** the NPC — mesh, texture, sound. That is the NPC
Effects tab's job. What it does not know is **what the NPC is**: how much health
it has, what it drops on death, where it spawns, what it sells. None of that
exists in the client.

This tab generates that half.


## Pick the server first

The Lineage 2 client is one; the emulator is not.

| Format | Who uses it | Where it keeps things |
| --- | --- | --- |
| **XML** | aCis, L2jServer, Mobius, Lisvus | `data/xml/npcs`, `data/xml/multisell` |
| **Database** | L2jFrozen and the older datapack cores | tables `npc`, `droplist`, `spawnlist` |

It is not only the format: the names differ. Where aCis writes
`<set name="pAtk" val="700"/>`, the database has a `patk` column. Where aCis
says `type="Monster"`, the database says `L2Monster`.

The **Server** box at the top picks one, and the same form comes out in the
right format.

Its first option is not a core: **Detect from the server** reads the folder you
pointed at and builds the profile from it — which folders things live in,
whether the skill target carries a prefix, how the drop group is written, in
what unit the chance goes. It takes about two seconds, and **what it saw appears
next to the box**.

It is the starting option because "which core is mine?" often has no simple
answer: whoever sets up a server takes a core, renames it and changes what they
want. A server with a name of its own can be aCis underneath, with four differences —
and those differences are written in its own files.

The ready-made cores stay in the list, and picking one decides. Detecting is the
default, not a rule.

**A core that is not in the list** is also added by dropping a `.json` into
`recursos/servidores/`. The file says the format, the folders or tables, and the
field mapping. There is no code to touch.

One thing worth knowing: the `INSERT` comes out with **the column names**, not
by position. An emulator schema is not fixed, and one extra column in the middle
would make a positional insert put price where weight goes — no error, no
warning.


## Read from the server

The **Read from the server** button, at the top of step 2, looks for this NPC in
the server data folder and brings what it has: stats, drop, spawn and shop.

It reads the NPC **selected in the list** — not the one in the **new id**
box. The box says where the NPC is going; the list says where it comes from.
That is how you copy the stats of a monster that already works: the client never
kept health or attack, so you do not have to type them.

If it is not there, the program says the NPC does not exist on the server side
yet. That is not an error: it is the case for filling it in and generating.

It works on both formats. On an `INSERT` that does not name its columns — and
almost every `.sql` going around is like that — the program uses the column
order declared in the profile. If the profile does not carry that order, it says
it could not read it, instead of guessing by position.

The name and the title go back to step 1. What **you typed** is never erased;
what came from an earlier read is replaced.

## Stats

Pick the base NPC from the list — it serves as the appearance and id reference.
The fields arrive with plausible starting values for a level 70 NPC; adjust
them.

The **id** must match the client's. If you created the NPC in the NPC Effects
tab, use the same id here: that is what ties the two sides together.

**type** decides the behaviour: `Monster` attacks, `Folk` stands and talks,
`Merchant` opens a shop, `Teleporter` teleports, `RaidBoss` is a boss. On a
database server the name comes out with the `L2` prefix automatically.

**health, mana, attack, defence** are the combat numbers. For an NPC that only
talks they do not matter; for a monster they are everything.

**collision radius and height** come from the size of the model. Wrong, the
character walks through the NPC or gets stuck far from it.

**experience and SP** is what the player gains on the kill. Zero for a town NPC.

**aggro range** at zero makes the NPC not attack on its own.


## Drop

What the NPC drops on death.

The **chance is a percentage**: `2.5` is 2.5%. For a database server the number
is converted to its own scale (where 1,000,000 is 100%) — you type percentages
in both cases.

The **drawer** separates:

| drawer | what it is |
| --- | --- |
| `DROP` | the item falls on the ground on death |
| `CURRENCY` | adena — item 57 |
| `SPOIL` | only comes out with the spoil skill |

Adena is item **57**. An ordinary monster has one `CURRENCY` row with adena and
a few `DROP` rows.


## Spawn

Where the NPC spawns. The coordinates come from in game, with the command that
shows your position.

**heading** is which way it faces, 0 to 65535. **respawn in** is in seconds.

Tick **generate the spawn too** for the file to come out. Without it only the
NPC is generated — which is what you want when you are going to place it in game
with the spawn command.


## Shop

The multisell: what the player pays and what they get.

It is XML on both server formats — even the database cores keep the shop in a
file.

**Adena is item 57.** An ordinary sale is paying adena and getting the item. A
trade is paying one item and getting another. You can add several rows; each one
is an option in the shop window.

The **shop id** is the file name. For the NPC to open the shop, the server has
to know about it — usually through a script or through the `Merchant` type with
the shop tied to the id. That varies from core to core and falls outside what
this screen generates.


## Generate

**See what comes out** shows everything first. **Generate** writes into the
chosen folder.

What comes out:

- `<id>-npc.xml` or `<id>-npc.sql` — the NPC, with the drop inside it in the XML
  case
- `<id>-spawn.xml` or `.sql` — if you ticked it
- `<shop id>.xml` — the multisell

Copy them into the server folders; on a database core, run the `.sql` there. The
gameserver has to restart.

**Nothing is written to the client by this tab.** It only writes the server
side.
