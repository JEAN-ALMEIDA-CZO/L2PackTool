# L2Crypt: opening and closing a client file

Almost everything in the Lineage 2 client is encrypted: `.dat`, `.utx`, `.u`,
`.unr`, `.ini`. No ordinary editor opens that. The program already needed to
decrypt in order to do the rest of its work — this tab puts that ability in your
hands, in both directions.


## The original is never touched

What goes in is **read**. What comes out is **a new copy, in another folder**.
There is no path in which this tab writes over the file you picked.


## Decrypting

Pick the file and the output folder. The method is recognised from the file's
own header, which states the version:

| header | how it opens |
| --- | --- |
| `Lineage2Ver111` | Blowfish |
| `Lineage2Ver120` | XOR by byte position |
| `Lineage2Ver121` | XOR with a key taken from the file name |
| `Lineage2Ver411` to `414` | RSA, in blocks, with the contents compressed |

A file that is already open — without that header — is copied as it is.


## Encrypting

There are two surprises here, and both have the same cause: **an opened file
keeps no record anywhere of what it was**.

> **The method comes from the extension**, not from what was in the file. A
> `.utx` opened by hand records nowhere that it was `Ver121`; what decides is
> the extension of the name you gave it.
>
> **The output file's name matters.** The `Ver121` key derives from it. The same
> contents saved under two different names produce two different files, and the
> game only reads the one with the name it expects.

In practice: to give a file back to the client, save it under **the same name**
it had.


## What to do with the opened file

An opened `.dat` is still binary — it does not turn into readable text. To edit
client tables there are the Items, Skills and NPC tabs, which understand each
one's format.

This tab is for what those do not cover: looking at a file, comparing two
versions, taking an `.ini` to another editor, or giving back to the client a
file you worked on elsewhere.


## When it goes wrong

**"not a client package"** — the header matches no known version. Usually it is
a pack with protection of its own: the file is encrypted, but with a header
outside the standard that no outside reader recognises.

**It opened, but the contents came out scrambled** — the decryption ran with the
wrong key. On `Ver121` this happens when the file was renamed at some point,
because the key comes from the name.
