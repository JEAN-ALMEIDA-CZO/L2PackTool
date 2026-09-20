# Multisell: an NPC's list of trades

A **multisell** is the list that opens when you talk to a trading NPC: on one
side what the player **pays**, on the other what he **receives**. Adena for a
weapon, materials for armour, a +0 item for a +8 one.

It is an XML file on the server, and that is all. **There is no client file** --
the client only draws what the packet sends.


## The file name is the key

This comes from your server's own code, and it is not obvious:

```java
final int id = file.getName().replaceAll(".xml", "").hashCode();
```

**There is no id field inside the XML.** The list's identifier is the file name.
It is how the NPC opens it:

```
multisell 1000          in the NPC's HTML bypass
exc_multisell 1000      only shows what the player already has on him
```

Three practical consequences:

- **Renaming changes the list's identity.** The old bypass stops finding it.
- **Two lists with the same name are the SAME list**, even in different
  folders: the second to load wipes the first.
- The name need not be a number. Use letters, digits, `-` and `_` -- a space
  will not do, because the bypass would break.

The screen shows the ready-made bypass beside the name field, to copy.


## Building a trade

The **The trade** box has both sides. On each one:

- **+ item** opens the client's item list, with icon, name and filter
- **Amount…** changes the number and the enchant of the marked item
- **Remove** takes it out

The amount is **per trade**: `1000` Adena means each click costs the player a
thousand.

An **enchant** of zero is not written to the file -- it is the server's default.
On an item the player *receives*, it comes out already refined; on an item he
*pays* with, only an item at that exact +N will do.

One side can hold several items: `500,000 Adena + 5 Blessed SoE → 1 Dragon
Slayer` is a single trade.

**Add to the list** sends the trade to the checkout below. Double-click a trade
in the checkout to bring it back for editing; **Up** and **Down** change the
order the player sees.

Each checkout row shows both sides, with the icon beside every item's name:

```
3 ▸  [] Gold Bar x 30  +  [] Dark Ticket x 30,000   →   [] Saint Spear x 1 +5
```

A trade with many items will not fit on one row, and the last name would come
out cut. The **triangle** in front of the number opens the list:

```
1 ▾  5 items                                        →   1 item
        [] Titanium Breastplate x 1                        [] Dark Coin x 1
        [] Event Coin Lv.1 x 50
        [] Golden Enchant: Armor x 500
        [] Tournament Point's Lv.1 x 1,000
        [] Dark Ticket x 50,000
```

The triangle only shows up where there is something to open: a one-for-one
trade already says everything on its own row. Clicking the triangle opens and
closes it; clicking the rest of the row only marks the trade, and a double
click sends it back for editing.


## The NPCs

The **NPCs** field takes the ids that may open this list, separated by spaces or
commas.

> **Blank, ANY NPC opens it.** That is how the core works:
>
> ```java
> public boolean isNpcAllowed(int npcId) {
>     return _npcsAllowed == null || _npcsAllowed.contains(npcId);
> }
> ```
>
> The list only becomes restricted once it has at least one NPC. And once
> restricted, it can no longer be opened **without** an NPC -- from a community
> board, for instance.


## The two options

| option | what it does |
| --- | --- |
| `charge the castle tax` | takes the region's tax out of the trade |
| `keep the enchant` | the received item comes out at the same +N as the one given |

`keep the enchant` is for weapon-for-weapon trades: hand in a +8 and get the new
one at +8. Without it, the item comes out at whatever +N the trade says.


## The check, and what it catches

**Check** cross-references the list with the client tables and warns about:

- an item that **does not exist in the client** -- in game that row would come
  out with no name and no picture, and nobody would know why
- an amount of zero or less
- a trade with only one side
- an invalid file name, or one **already used by another list**

That is why it is worth opening the client tables first: without them the screen
works with ids alone, and you lose this check.


## Generating and installing

**See the XML** shows the finished file, with a readable comment on each trade:

```xml
<!-- 500000 Adena + 5 Blessed Scroll of Escape -> 1 Dragon Slayer -->
<item>
    <ingredient id="57" count="500000"/>
    <ingredient id="1538" count="5"/>
    <production id="81" count="1" enchant="8"/>
</item>
```

**Install on the server** writes into its multisell folder -- where that is
comes from the server itself, read from its files. A copy always stays in
`multisell_gerada/`, to recover from if someone edits the server's by hand.

Then, in game:

```
//reload multisell
```

And the bypass in the NPC's HTML, which the screen shows ready.


## Where the client comes in

There is no multisell file in the client. What the client needs is to **know the
items** used: id, name and icon. An item made on the Items tab shows up here by
name, with its picture, as soon as the tables are opened.

If you build a trade with an item that only exists on the server, the check
warns you -- and in game that row would come out empty.
