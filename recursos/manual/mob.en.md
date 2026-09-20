# Mob: the stats, the skills and the drop list

A server mob lives in an `<npc>` block inside `data/xml/npcs`, and each file
carries up to a thousand of them. The three things you edit — the stats, the
skills and what it drops — sit hundreds of lines apart.

This tab opens that block, edits all three, and **rewrites only it**. The other
thousand NPCs in the file are not touched in a single byte.


## Opening

**Server** is the server folder, or its `npcs` folder directly — the screen
finds the path from either. **Open the mobs** reads everything:

```
4000 mobs in ...\data\xml\npcs.
```

The core reads `npcs` and then `raidboss`, `grandboss`, `farmzone`, `custom`
and `events`, in that order. **A repeated id means the last one to load wins** —
the earlier definition is discarded silently. The screen warns when it finds
repeats, because that is the kind of thing that has someone editing a mob all
afternoon without understanding why the game does not change.

**Client** is not required, but it is worth it: it is where the name and the
picture of each drop item come from, and it is what lets the check warn you
when a drop points at an item that does not exist.


## Finding the mob

The list filters by text (name or id), by **type** and by **level range**. The
three add up. The type box fills with the types your pack actually uses — 79 of
them, in this case, not a fixed list.


## Stats

The first box is the identity; the second, the `<set>` fields; the third, the
`<ai>`.

The stats appear in the order you think about them — level, type, exp, HP, the
attributes — and whatever else your mob has goes at the end, instead of
disappearing.

> **The `<ai>` block is the silent trap.** The core reads `type`, `ssCount`,
> `ssRate`, `spsCount`, `spsRate`, `aggro`, `canMove` and `seedable` **without
> checking whether they exist**:
>
> ```java
> set.set("canMove", Boolean.parseBoolean(attrs.getNamedItem("canMove").getNodeValue()));
> ```
>
> With one missing, that is a `NullPointerException` at load time. The check
> demands all eight. With `clan` present, `clanRange` becomes required for the
> same reason.


## Skills

The race sits in its own field, not in the skill list. The reason:

```java
if (skillId == L2Skill.SKILL_NPC_RACE)   // 4416
{
    set.set("raceId", level);
    continue;                            // registers no skill at all
}
```

**The line `<skill id="4416" level="9"/>` is not a skill.** The core reads its
`level` as the mob's race — 9 is Demon — and moves on. Sitting among the
skills, it would be an invitation to delete the race while thinking you were
removing an attack.

The real skills are in the list below. A skill that does not exist in the
server's table is ignored with a warning in the log — worth checking the log
after a reload.


## Drop

Each category is a drawer; inside it, the items with the icon beside the name.

> **The chance is per million.** `DropData.MAX_CHANCE` is `1000000`, so:
>
> | in the file | in practice |
> | --- | --- |
> | `1000000` | 100% |
> | `79637` | 7.9637% |
> | `5` | 0.0005% |
>
> This is the most common drop-list mistake: writing `5` meaning 5% makes the
> item never drop. In the drop window both fields sit together, and changing
> one corrects the other.

**Category `-1` is spoil** (sweep), and the core always visits it. From `0` up
they are ordinary drop groups, and the core picks **one item per group** —
putting ten items in a single category makes them compete with each other
rather than drop together.

A drop of an item the client does not know is discarded by the core:

```java
if (ItemTable.getInstance().getTemplate(data.getItemId()) == null)
{
    _log.warning(" Droplist data for undefined itemId: " + data.getItemId());
    continue;
}
```

In game the mob simply does not drop it, and without reading the log nobody
finds out why. Open the client tables and the check catches it beforehand.


## Minions

The mobs that spawn alongside this one. The `id` belongs to another NPC; `min`
and `max` are how many come.


## What the screen does not edit

`<petdata>` — the pet's level table, a hundred lines of it — and `<teachTo>`
are not edited here. **They come back byte for byte.** When they exist, the
screen says so in the corner:

```
kept untouched: petdata
```

That is a promise worth checking: `See the XML` shows the whole block exactly
as it will be written.


## Saving

**Check** cross-references the mob with the client and with what the core
demands. **See the XML** shows the finished block. **Save to the server**
replaces only that `<npc>` inside the file and leaves a dated copy beside it:

```
20000-20999.xml.20260917-174900.bak
```

Then, in game:

```
//reload npc
```
