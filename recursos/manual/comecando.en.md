# Getting started

This program works on two separate things, and almost every beginner's problem
comes from mixing them up.

**The client** is what the player has on their machine. It knows how to **draw**
things: mesh, texture, icon, sound, the name that shows on screen. Those are
`.dat`, `.u`, `.utx` and `.ukx` files inside the game folder.

**The server** is the emulator. It knows **what the thing is**: how much HP a
mob has, what it drops, how much an item costs, what a skill does. Those are XML
files and database tables, and none of it exists in the client.

An item that exists only on the server shows up in game with no name and no
picture. An item that exists only in the client never reaches anyone's hands.
The two halves have to match, and that is what the tabs of this program do.


## The first step is the project

Before anything else, open **Projects…** in the header and create one: a name,
the client folder and the server folder.

Choosing the project points both folders in **every tab at once**. Anyone
working on more than one server switches project in the header instead of
fixing eighteen fields.

With no project set, each tab's `Load` button says what is missing and where to
solve it — it does not just go grey without explaining.


## The second step is loading

Each tab has **one** `Load` button. It brings in everything that tab uses: the
client tables, the server data, or both.

The first read of the client tables takes a while — it is nearly ten thousand
items and three thousand skills. After that it is kept, and the tabs share the
same catalogue: what the Items tab read serves the mob's drop list and the
multisell list.


## The map of the tabs

| tab | works on | side |
| --- | --- | --- |
| Texture Upscaler | textures in a `.utx` package | client |
| NPC | creating an NPC: mesh, name, effect | client |
| NPC — server side | stats, drop, spawn, shop for that NPC | server |
| Lobby Video | the login screen video | client |
| Items | creating and editing an item | both |
| Skills | creating and editing a skill | both |
| Glow | the weapon's glow and the enchant | client |
| Multisell | an NPC's trade list | server |
| Mob | stats, skills and drop of an existing mob | server |
| Check Client | what the tables ask for and is not installed | client |
| L2Crypt | opening and closing a client file | client |


## What never happens on its own

- **Nothing is installed unless you say so.** Generate and install are two
  different buttons, in every tab. What is generated sits in an output folder
  until you decide.
- **Whatever gets overwritten is copied first.** Client files go to
  `system/backup_*`; server XML gets a dated copy beside it.
- **What the program does not understand, it does not touch.** Editing a mob's
  HP does not rewrite the rest of the file, and blocks this program does not
  know come back byte for byte.


## After installing

Client-side work needs the client closed while installing, and open again
afterwards. Server-side work needs a command in game:

```
//reload npc          after working on a mob or an NPC
//reload multisell    after working on a multisell
```

Each tab's manual page names its own command.
