# Check Client: what the tables ask for and is not there

The client does not tell you when something is missing. With the texture gone,
it draws the white figure and carries on. With the whole package gone, it shows
the item with no model and writes nothing anywhere.

This screen answers three questions, in this order — which is the order they
come up for whoever is assembling a client:

1. **what is missing?** — the check, which only reads
2. **where do I find it?** — the search through a folder of other clients
3. **install it for me** — the copy into the client


## The check

`Load` reads the client tables, gathers every package reference they make —
mesh, texture, icon, sound — and checks them one by one against what is in the
folders.

The summary comes out as cards, to be read from a distance before any list. Only
then comes the report, split by situation:

| situation | what it means |
| --- | --- |
| **missing packages** | the client asks for the file and it is in no folder |
| **missing objects** | the file is there, but does not contain what the table asks for |
| **present, contents not opened** | a `Lineage2Ver111` package, which only opens whole — the check confirms the file exists and stops there |

The report comes out **complete**, with nothing abbreviated. If a package is
asked for by 86 references, all 86 appear — it exists to be checked, and half a
list checks nothing.


## Reading the report

Each missing-package block carries the name, how many references ask for it, and
which table the request comes from:

```
ArmorSet_Custom                   86 referencias   (armorgrp.dat)
    ArmorSet_Custom.Drop_Custom_CAP_b_m00
    ArmorSet_Custom.FD_Custom_CAP_b_m00
    ...
```

The table in brackets says where to look for the origin. `armorgrp.dat` is
armour; `weapongrp.dat`, weapons; `npcgrp.dat`, NPCs.

**A missing package with many references** is usually a pack that was installed
halfway — the tables arrived, the files did not.

**A missing object inside a package that is present** is narrower: someone
replaced the package with a version that does not have that object, or the table
points at a misspelled name.


## Searching and installing

Point at a folder holding other clients and the screen searches it for the
missing files and shows what it found. From there you can copy them into the
client.

The copy always goes **inwards**: the source client is not touched.


## What the check does not do

It does not open a `Ver111` package to look inside. Those only open whole, and
doing it for every reference would cost minutes per file. That is why the
"present, contents not opened" category exists: there the check confirms the
file exists and stops.

It also does not check the server. To cross client and server — an item that
exists on one side and not the other — the way is this tab's `Load` with the
project pointing at both.
