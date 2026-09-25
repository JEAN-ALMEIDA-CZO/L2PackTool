# Protection: locking the client with your own key

Every Lineage II client keeps its tables locked, and the "password" that opens
them is the same in all of them — it has been in public tools for twenty
years. That is why anyone can open any server's `itemname` with two clicks.

This screen swaps that password for **yours**: a key derived from a phrase
only you know, written into your own client. After that, nobody produces a
file your client will accept without having the phrase.


## What it protects, and what it does not

**It protects writing.** Without your phrase, nobody generates an
`itemname-e.dat` that your client will load. Whoever wants to swap a table on
your server needs the phrase — or needs to rebuild the whole client.

**It does not protect reading**, and no program would. To play, the client has
to open the files: it carries inside itself what is needed to open them.
Whoever has your client can get there — this very program gets there in
milliseconds.

What changes is the cost. Your server moves from *"anyone opens it with one
click in a public tool"* to *"whoever knows how to look"*. That is a real
step, and it is the only step that exists on this side.


## The phrase

**Generate key** draws a strong phrase — thirty characters in groups of five,
without the ones that get misread (no `O` and `0`, no `I` and `l`). A phrase
invented on the spot is usually the server name plus the year, and that one
anybody guesses.

The same phrase always yields the same key, on any machine. **It is not stored
anywhere**: not in the program, not in the configuration, not in the client.
Lose the phrase and you lose the ability to generate new files for that client
— what is already installed keeps working, and so does the backup.

**Save…** writes the phrase to a text file, with the key's fingerprint and the
date. Saving it **inside the client folder is refused**: from there the file
would travel with the client to the players.

The *fingerprint* is eight digits from each end of the key. It lets you check
you are using the right key without showing the phrase.


## What can be protected

| way | what it takes |
| --- | --- |
| **groups** | items and weapons, skills, NPCs, world and text |
| **Choose…** | file by file, including tables in no group at all |
| **All .dat** | every table at once |

What the button protects is the **union** of the groups with the list. A file
outside the client folder is left out: the key written into the executable
belongs to that client, and a file from elsewhere locked with it would be read
by no client at all.


## Converting packages

Tables (`.dat`) already come in a format that takes a key. Packages — `.utx`,
`.u`, `.int` — use a format **without a key**: their password is fixed, or is
derived from the file's own name. There is no key to swap in them.

With **convert** ticked, they are converted to the format that takes a key.
The client picks the decoder by the file's header, not by its extension — in
your own client the same `.ini` shows up in two different formats side by
side.

That option ships **off**, and the reason is honest: no original client ships
a `.utx` in that format, so this part cannot be proven here. **Convert one
file, open the game, check, and only then convert the rest.**


## `.dll` and `.exe` are out

A `.dll` is loaded by Windows, not by the client. The lock this program writes
is read by the client, which decrypts before using; Windows knows nothing
about it. An encrypted `Engine.dll` does not load, and the game will not even
start. So those files are **refused**, with the reason — not accepted with a
warning.

For them there is the **fingerprint**: the program records a digest of every
`.dll` and `.exe` in the client to a file, kept outside the client, and
compares later. It does not prevent a swap, but it answers in seconds the
question that matters when something odd happens on the server: *did anything
change?* The check reports what changed, what disappeared and what is new.


## The order of work, and why it is that one

1. the original is copied to `backup_protecao`;
2. the file is opened with the current key;
3. it is closed with the new key;
4. it is **opened again and compared** with step 2;
5. only then it replaces the original.

The executable's key is swapped **last**, and only if every file passes. The
other way round, an error in the middle would leave the whole client unable to
open anything; this way, the worst case is one file left untouched.

A file that does not come back identical is not installed, and the reason
shows up in the progress log.

**Restore original** undoes everything, including the executable's key.


## Where it works

Some clients keep the key inside the executable, and there it can be swapped.
Newer ones receive it through a *loader*, in memory, and swapping it would
require a loader of our own — which this program does not write. The screen
tells you which case your client is in **before** you pick any files.


## Before touching what is live

Do it on a copy of the client first. Protect one file, open the game, check,
and only then treat the client your players use. *Restore original* exists
precisely because the first attempt usually teaches you something.
