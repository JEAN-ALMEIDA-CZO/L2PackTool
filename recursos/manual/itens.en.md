# Creating an item: what to fill in

A Lineage 2 item lives in two places at once, and both have to agree:

- the **client** knows how to draw it — mesh, texture, icon, sound;
- the **server** knows what it does — damage, defence, weight, price.

What ties them together is the **id**. If only one side has the item, no error
shows up: confusion does. An item with no name, a blank icon, or an item the
server hands out and the client cannot draw.

This tab handles both sides. The client tables come out ready to install; the
server XML comes with them, and you copy it into your server's item folder.


## Editing or creating

The screen has a **mode**, written in large letters at the top of the right-hand
panel:

```
Editing item 1 — Short Sword
New item 30000, copied from 1
```

**Clicking an item in the list edits that item.** The fields fill with its data,
the id locks to its own, and the button becomes **Rewrite the item**. The id
locks on purpose: changing the number there would really be creating another
one.

**Creating goes through the New item… window.** It asks for the id (with
Suggest), name, description and icon; it refuses an id that already exists
without the replace tick; it warns when the id falls inside the game range. What
comes out of it fills the panel, and the fields stay editable.

After generating, the screen switches to **editing what just came out**.


## 1. Pick the base item

Every new item is born as a copy of one that already works. This is not
laziness: a row of `armorgrp.dat` has **332 columns**, and most have nothing to
do with appearance — weight, equip sound, crystal type, and the mesh and
texture for each of the twelve race-and-sex combinations. Inventing those
values gives you an item that exists and is wrong.

Search the list by name, by id or by icon name. Click a row: the icon shows up
in the corner, and the XML fields fill in with whatever can be read from the
client table.

**Pick a base close to what you want.** A new sword copied from a sword
inherits the grip, the swing sound and the animation. Copied from a hat, it
does not.


## 2. Identification

### id

The number the client and the server use to talk about the same item.

**Suggest** finds the first free id from **30000** up, away from the original
game range. Use it. An id inside the game range overwrites a real item — and
then the sword you made becomes somebody's Adena.

The program warns you when the id you chose falls below 30000.

### name

What the player reads. It comes filled in with the base item's name; change it.

### description

The text shown when the mouse rests on the item in the inventory. It can stay
empty.

### icon

The reference has the form `package.object` — for example
`icon.weapon_long_sword_i00`. It is the 32×32 drawing that shows in the
inventory.

In the **New item…** window the icon is picked **by sight**: there is a grid of
thumbnails on the right, with the art at the size the game draws it. Click one
to pick it.

The grid opens on the icons **closest to the base item's** — copying a sword, it
starts on weapons — and shows 240 at a time; the label says how many were left
out and the search narrows it. Nothing is hidden: the search box reaches all
13,690.

The icon does not have to be the base item's. Changing only the icon is the
cheapest way to give a copied item a new face, without touching any model.

Just below the grid, **Use an image of my own** takes a drawing of yours — see
the last section.

### replace if the id already exists

Leave it **unchecked**. Checked, it deletes whatever item sits on that id
instead of refusing — which is only useful when you are redoing an item you
created before.


## 3. Server XML

Anything left blank **is not written**. The server has a default for every
field, and a missing field means that default. Filling in only what matters
keeps the file readable.

### type on the server

`Weapon`, `Armor` or `EtcItem`. It comes filled in.

One case that trips people up: **a shield lives in the client's `weapongrp`,
but to the server it is `Armor`**. The program detects it from the base item
and marks the right type. Marked as `Weapon`, the character wields the shield
as a weapon.

### action on click

What a double click in the inventory does. `equip` for weapons and armor;
`skill_reduce` for potions; `none` for materials and quest items.

### body part

Where the item is worn:

| value | where |
| --- | --- |
| `rhand` | right hand — one-handed weapon |
| `lrhand` | both hands — greatsword, bow, polearm |
| `lhand` | left hand — shield |
| `chest`, `legs`, `feet`, `gloves`, `head` | the armor pieces |
| `fullarmor` | chest and legs in one piece |
| `neck` | necklace |
| `rfinger;lfinger` | ring |
| `rear;lear` | earring |
| `none` | not worn |

### material

What the item is made of. Not decoration: the material decides the sound it
makes when struck, and it counts towards some resistances. It comes from the
client and matches on 100% of the items checked.

### grade

`D`, `C`, `B`, `A`, `S`, or empty for an item with no grade. It controls which
crystals the item gives back and from which level it can be used.

### weight

In game units — the Short Sword weighs `1600`. It comes filled in.

### price

What the NPC charges. It **does not come from the client**, so it arrives
empty: fill it in or leave it at zero.

### crystals

How many crystals the item returns when broken.

### weapon type

`SWORD`, `BLUNT`, `DAGGER`, `BOW`, `POLE`, `DUAL`, `DUALFIST`, `FIST`,
`BIGSWORD`, `BIGBLUNT`, `ETC`, `FISHINGROD`.

It decides which skills the character can use with the item in hand and which
attack animation plays. It comes filled in, and the program already tells a
sword from a greatsword by the number of hands.

### armor type

`LIGHT`, `HEAVY`, `MAGIC`. It decides the class penalties: a mage in heavy
armor loses mana regeneration.

### random damage, soulshots, spiritshots

They come from the client. `soulshots` and `spiritshots` are how many shots the
item consumes per blow.

### tradable, dropable, sellable, destroyable, depositable

Leave them blank for the default (everything allowed). Set `false` on whatever
you want locked — an event item is usually `is_tradable false` and
`is_dropable false`.


## Read from the server

The client holds appearance, weight and material. **Damage, defence and price do
not exist in it.** The **Read from the server** button, on the XML tab, looks for
the item in the server data folder and brings the fields and the stats.

It reads the item **selected in the list** — not the one in the **new id**
box. The box says where the item is going; the list says where it comes from.
To read back an item you created, select it in the list: it is there once you
generate.

If it is not there, it says the item does not exist on the server side yet.
That is not an error: it is the case for filling it in and generating.

It works on both formats. On database cores the combat columns (`p_dam`,
`p_def`, `critical`) come back into the stats block, which is where the XML puts
them.

## 4. Stats the item gives the player

This is the part that makes the item **worth something**. Without it the new
sword has the right look and no damage at all.

Each row has three parts: **operation**, **stat** and **value**.

### The operation

It says how the value enters the calculation:

| operation | what it does |
| --- | --- |
| `add` | adds to the total already calculated |
| `baseadd` | adds to the base, before the multipliers |
| `sub` | subtracts |
| `mul` | multiplies (`1.1` = plus 10%) |
| `basemul` | multiplies the base |
| `div` | divides |
| `set` | fixes the value, ignoring what was there |
| `enchant` | the share that grows with each enchant |

**In practice**, following what the game itself does:

- weapon: `set` for `pAtk`, `mAtk`, `rCrit` and `pAtkSpd`;
- armor: `baseadd` for `pDef` or `mDef`, and `enchant` for the part that rises
  with the enchant;
- shield: `set` for `sDef` and `rShld`, `sub` for `rEvas`;
- accessory: `baseadd` for `mDef`, `add` for bonuses such as `maxMp`.

### The order

Beside the operation there is the **order**: the moment in the sum that value
enters. It is filled in for you with what the game uses for each operation:

| operation | order | what it means |
| --- | --- | --- |
| `set` | `0x08` | fixes the base |
| `enchant` | `0x0C` | what grows with every +1, right after the base |
| `add` / `sub` | `0x10` | adds before the multipliers |
| `mul` / `basemul` | `0x30` | multiplies |
| — | `0x40` | adds **after** the multipliers |

The numbers are not a style choice: they come from counting the datapack, where
`set` appears with `0x08` in all 4,736 stats, without one exception.

**It is mandatory.** The server reads the attribute without checking that it
exists:

```java
String order = n.getAttributes().getNamedItem("order").getNodeValue();
```

Leave it out and the read throws, and the **whole item table** stops loading.
Anyone with an item generated by an earlier version of this program, with stats
and no order, needs to write it again.

Change it only if you know why. `0x40` is for a bonus that should enter after
the class calculations -- it is what the game does with `maxMp` on accessories.

### The stat

Pick it from the list. It is grouped by subject — health and mana, attack and
defence, rates and evasion, attributes, PvP, resistances, vulnerabilities,
reflection, against creature type, limits.

The most used ones:

| stat | what it is |
| --- | --- |
| `pAtk` / `mAtk` | physical / magical attack |
| `pDef` / `mDef` | physical / magical defence |
| `pAtkSpd` / `mAtkSpd` | attack / casting speed |
| `rCrit` | critical rate (10 = 1%) |
| `cAtk` | critical damage |
| `accCombat` / `rEvas` | accuracy / evasion |
| `maxHp` / `maxMp` / `maxCp` | maximum health, mana and CP |
| `regHp` / `regMp` | regeneration |
| `runSpd` | running speed |
| `sDef` / `rShld` | shield defence and block rate |
| `STR`, `CON`, `DEX`, `INT`, `WIT`, `MEN` | attributes |

**Why this matters**: a stat name the server does not know is not ignored. It
brings down the loading of the **whole item table** — every item on the server,
not just the new one.

The list belongs to the program, and not every core has all of its names. The
**Check against the server** button reads the folder you pointed at and marks
with ⚠ the ones yours lacks. When the source code sits beside the data folder,
the answer comes from its `Stats.java` and is complete; when there are only the
`.jar` files, it comes from the `stat="..."` the datapack uses — smaller, but
every name there is proof that it loads.

### The value

A number. It can have a decimal point (`1.15`) and it can be negative for a
penalty.

Mind the scale: `rCrit` counts in tenths of a percent (`80` is 8%), and
`pAtkSpd` is an absolute number (an ordinary weapon sits near `379`). When in
doubt, look at a similar item on your server.

### See the XML

It shows the finished file before generating. It is always worth a look before
installing.


## 5. Skills the item carries

A weapon can grant a skill to whoever equips it, or fire one on a hit. On this
server that is **not** a `<skill>` inside the item: they are `<set>` fields,
with the id and the level written together.

| field | when it applies | how many |
| --- | --- | --- |
| `item_skill` | while the item is equipped | several, separated by `;` |
| `enchant4_skill` | from +4 on | one |
| `oncrit_skill` | on a critical hit | one |
| `oncast_skill` | on cast | one |

The value is `id-level`: `3599-1`. For several, `3599-1;3600-2`.

### The chance, which swallows in silence

`oncrit_skill` and `oncast_skill` **require** the chance alongside --
`oncrit_chance`, `oncast_chance`, in percent. The server does:

```java
if (id > 0 && level > 0 && chance > 0)
```

Without the chance, or with it at zero, the skill is **dropped without one line
of log**. No error, the server starts normally, and the weapon simply does
nothing. Whoever tests it will blame the skill, not the missing field. That is
why the **Check** button exists, and why the window asks before letting it
through.


## 6. The client's numbers (weapons)

In the **New item** window, when the base is a weapon, a **Numbers** page
appears. Those are the `weapongrp.dat` columns -- **what the inventory tooltip
shows**.

That is not the same as the Stats. The Stats belong to the server: what the hit
actually does. The Numbers belong to the client: what the player reads. **The
two can disagree without either one complaining.** This client's Draconic Bow
shows 581 P.Atk in the tooltip; the server uses 561.

Beside each box is the grey name of the matching stat:

| client | server |
| --- | --- |
| `patt` / `matt` | `pAtk` / `mAtk` |
| `critical` | `rCrit` |
| `speed` | `pAtkSpd` |
| `hit_mod` | `accCombat` |
| `avoid_mod` | `rEvas` |
| `shield_pdef` / `shield_rate` | `sDef` / `rShld` |

`hit_mod` and `avoid_mod` are the only ones carrying a sign on the client side.
On the server the sign becomes the **operation**: `-3` on the client is
`<sub stat="accCombat" val="3">`.

**Copy to the Stats** does that translation and writes it all on the Stats page,
already with the right operation and order. It is the short way to make both
sides tell the same story.


## 7. Generate, install, and the next item

**Generate** writes the changed tables and the `<id>-item.xml` into a separate
folder. **Nothing in the client changes yet.**

**Install in the client** puts the tables in place. The first time, the
originals go to `system/backup_itens`; **Restore originals** brings them back
and undoes everything at once.

You copy the XML by hand into the server's item folder — usually
`data/xml/items/` — and restart the gameserver.

After generating, the screen gets ready for the next one: it suggests the next
free id, clears name, description and stats, and keeps the base item selected.
Ten items made in a row come out in a single `weapongrp.dat`, installed in one
go.

**Close the client before installing.** The running game keeps the tables in
memory and writes over them when it exits.



## 8. Your own icon

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

## If something goes wrong

**"The round trip does not reproduce the original"** — the table definition
does not describe this client, and writing is blocked on purpose. Usually the
client is from another chronicle. Nothing was written.

**Item with no name in game** — the tables were installed half way. They pair
up by id and have to go together. Use **Restore originals** and generate again.

**The server will not start after the XML** — almost always a stat or material
name typed by hand outside the list. Look at the gameserver log: it names the
one it did not recognise.

**The item shows up with no icon** — the icon reference points at an object
that does not exist. Use **Choose…** instead of typing, or run the **Check
Client** tab, which lists everything the tables ask for and is not installed.

**The icon is missing on screen but shows up in game** — some packs ship a
protected icon package: a non-standard header that no outside reader opens. The
game opens it because it holds the key; this program does not.

The icon then stays **blank**, and the log says which package failed to open:

```
o pacote PacoteCustom nao abriu; os icones dele nao vao aparecer
```

The program does not borrow a drawing from another package to fill the gap. The
object usually exists in `Icon.u` under the same name, but nothing guarantees
it is the same artwork — and a wrong drawing that looks right would wipe out the
one sign that there is a package to deal with. Decrypt the package and rebuild
it as a `.utx`, and the icon shows up.
