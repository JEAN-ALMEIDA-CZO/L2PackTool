# Client texts: system messages, interface and NPC lines

Everything the game writes on screen that is not an item or skill name lives in
three `system` tables:

| File | What it holds | Example |
| --- | --- | --- |
| `systemmsg-e.dat` | system message | `You have been disconnected from the server.` |
| `sysstring-e.dat` | interface text | `Equipment`, `Quest Item` |
| `npcstring-e.dat` | NPC line with a variable in it | `Hello! I am $s1.` |

That is **11,499 texts** in a High Five client and **3,764** in a C5 one.
`npcstring-e` only exists from Freya on; where it is missing, the screen says so
and works with the other two.

Server owners touch this for two reasons: **translating**, and **making the game
say what their server says** — the server name in the login message, an
explanation of a custom system, an event notice.


## Search is the point of the screen

Eleven thousand rows are not browsed by scrolling. Type into the search box the
text **as it appears in game** — "disconnected", "Equipment", "Welcome" — and the
list closes in around it. The box also takes an id, when you already know it.

Two helpers beside it:

- **table** — narrows to one of the three;
- **only those with $s1** — shows only the lines with a placeholder, which are
  the ones the server fills in.


## The placeholder matters more than the words

`$s1`, `$s2`, `$c1` are the **holes where the server puts** a number, a player
name or an item:

```
The server will be coming down in $s1 second(s).
```

The server sends `60`; the client writes `60` where `$s1` was. There are 1,135
lines with placeholders in High Five.

Rewriting the line **without the placeholder** raises no error anywhere: it still
shows up, it just arrives without the value it was announcing — "The server will
be coming down in second(s)". So the screen counts the placeholders before and
after, and asks when one goes missing. If you meant it, confirm; if not, the text
goes back as it was.

When you pick a line, the label above the field says how many placeholders it has
and which ones.


## The second line

Only the **system message** has a second line (`sub_msg`) — what the game writes
under the main one. In the other two tables that field is greyed out, instead of
accepting text that would go nowhere.

The rest of each row — colour, sound, group — **is left alone**. A message with a
changed colour still works; a message without its placeholder does not. The
screen handles what matters and leaves the rest exactly as it was.


## The path: apply, generate, install

Three steps, deliberately separate:

1. **Apply** keeps the new text in memory. Nothing has been written yet.
2. **Generate the tables** writes the `.dat` files into a folder of their own
   (`textos_gerados`), so you can look at the result before the client depends on
   it.
3. **Install into the client** copies them into `system`. The first time, the
   originals are kept in `system/backup_textos`, and **Restore originals** brings
   them back from there.

Close the client before installing — Windows will not let you write to a file the
game is reading.


## Proof, before anything is written

On loading, each table is opened, **rebuilt** and compared byte for byte with the
original binary. If the round trip does not reproduce the original, the
definition does not describe this client: the table can be read, and writing to
it is blocked.

The three tables come back identical in eleven clients here, from C3 to High
Five. Interlude went in without that proof — there is no extracted client of it
here to measure — and the program does not claim otherwise.


## What this does not do

- **It does not translate anything for you.** The new text is whatever you type.
- **It does not touch item or skill names.** Those live in `itemname-e` and
  `skillname-e`, on the Items and Skills tabs.
- **It does not create new texts.** The ids are the ones the client knows; an
  invented id would be a text the server never asks for.
