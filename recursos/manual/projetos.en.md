# Projects: the two folders in one place

A project holds three things: a name, the **client folder** and the **server
folder**. Choosing the project in the header points both of them in every tab.


## Why this exists

Each tab used to ask for the two folders again. That was eighteen fields for the
same path, and one of them left behind — after working on a copy of the client,
say — was enough for a screen to write to the wrong place without warning.

Anyone working on two servers at once changed eighteen fields per switch. Now
they change one.


## Creating

**Projects…**, in the header, opens the window. On the left, the projects that
exist; on the right, the name and the two folders.

- **client folder** — the game root, the one with `system` inside. You can point
  at `system` itself: the program finds the root from there.
- **server folder** — the emulator's data folder, the one with `xml` or
  `data/xml` inside.

**Save** stores it and selects the project straight away. **New** clears the
fields to create another. **Delete** removes the project from the list — the
folders are not touched, only the shortcut to them.

The name takes letters, numbers and spaces. `[` and `]` are not allowed, because
the project file is an `.ini` and they would break the section.


## Switching

The selector appears in two places: in the header and at the top of each tab.
They are the same control — changing one changes the other immediately, and the
tabs receive the new paths without needing to reload anything.

Beside it the two folders are written out in full. That is the answer to "which
server am I working on", and it needs to be in sight of whoever is about to save
something.


## When a folder is missing

Each tab's `Load` checks before working, and says what is missing:

```
No project selected. Create one under Projects… with the client
folder and the server folder.

The client folder of project Interlude no longer exists: D:\old-client
```

The folder is checked **on disk**, not just in the project file. The common case
is a client that was moved or renamed: without that check the error would turn
up deep inside, talking about something else.


## Where this is kept

In a `projetos.ini` beside the program. It is plain text, and it can be copied
between machines.

Anyone who used the program before projects existed loses nothing: on the first
run, the folders from the old configuration become a project named `Default`.


## What a project does not do

It points at folders. It does not copy, move or install anything. Switching
project touches no file at all — it only changes where the tabs are looking.
