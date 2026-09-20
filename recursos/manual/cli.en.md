# Command line: doing in bulk what the screen does one at a time

`L2PackTool-cli.exe` is the program's own engine without the interface. It
exists for what repeats: opening a hundred client files, upscaling a whole
folder of textures, checking a client from inside a script.

With no arguments at all, it lists what it can do:

```
L2PackTool-cli
```


## The commands

| command | what it does |
| --- | --- |
| `upscale` | enlarges the textures of a `.utx` and rebuilds the package |
| `abrir` | decrypts a client file — `.dat`, `.utx`, `.u`, `.unr`, `.ini` |
| `fechar` | encrypts it back, under the name the game expects |
| `extrair` | pulls the textures out of a package, as images |
| `listar` | shows a package's version and its objects |
| `conferir` | checks the client and says which file is missing |
| `lobby` | puts the video on a lobby's login screen, camera fixed |
| `ferramentas` | says which tools were found, and where |
| `ajuda` | the list; `ajuda <command>` details one of them |

`<command> -h` shows that command's options. Every command takes **a file or a
folder**: point it at a folder and it works through everything inside, in name
order.


## Opening and closing

```
L2PackTool-cli abrir "C:\Lineage II\system\itemname-e.dat" -o .\aberto
L2PackTool-cli fechar .\aberto\itemname-e.dat -o .\fechado
```

The original is **never touched**: what comes out is a new copy, in the `-o`
folder.

On opening, the method comes from the file's own header. On closing it comes
from the **extension** — an opened file records nowhere what it was. `--versao`
forces another method, for when you know more than the extension does.

> **The output file's name matters.** On version 121 the key derives from it:
> the same contents saved under two names produce two different files. To give
> a file back to the client, keep the name it had.

Every closed file is checked by the round trip: it is opened again and compared
with what went in. If they differ, `[a ida e volta nao confere]` appears beside
the name.


## Upscale

```
L2PackTool-cli upscale Fantasy.utx -s 2
L2PackTool-cli upscale C:\texturas -s 2 -o C:\saida
```

| option | what it is |
| --- | --- |
| `-s` | the scale: 2, 3 or 4 |
| `-n` | the upscayl model |
| `-o` | where to write the finished `.utx` files |
| `-t` | the working folder |
| `--parar-em` | stops after `descriptografar`, `extrair` or `comprimir` |

> **Scale 2x quadruples texture memory; 4x multiplies it by sixteen.** The
> client is 32-bit, and past that point it closes by itself — on entering an
> area, not on loading the package. The Texture Upscaler page explains what is
> worth ticking.

Anyone who called it with a plain path still can:

```
L2PackTool-cli C:\texturas -s 2
```

With no known command in front, the request is an upscale, as it always was.


## Listing and extracting

```
L2PackTool-cli listar Fantasy.utx
L2PackTool-cli extrair Fantasy.utx -o .\texturas
```

`listar` reads the package **even closed**: version 121 is decrypted in memory.
Version 111 only opens whole, and that one needs `abrir` first.

`extrair` writes the images into a subfolder named after the package.


## Checking

```
L2PackTool-cli conferir "C:\Lineage II" -o relatorio.txt
```

The same report as the Check Client tab, complete. Without `-o` it goes to the
screen.

**The exit code is meant for scripts:** `0` when there is no problem, `1` when
something is missing. So it chains:

```
L2PackTool-cli conferir "C:\Lineage II" -o faltando.txt || notepad faltando.txt
```


## When a tool is missing

```
L2PackTool-cli ferramentas
```

Lists each tool and the path it was found at, or `NAO ENCONTRADA`. The search is
by name inside `ferramentas/`, beside the program — which is why the folder
works wherever it is copied to.

Each command demands only what it uses: `abrir` and `fechar` need `l2encdec`,
`extrair` needs `umodel`, and `upscale` needs them all.


## What the command line does not do

Editing mobs, multisells, items and skills, and creating NPCs. Those are jobs of
choosing on screen and seeing the effect before saving — as command parameters
they would become a long list with no way to check it.


## The lobby

```
L2PackTool-cli lobby "C:\Lineage II" -p L2PackTool
```

Builds the login screen in the lobby's map: camera fixed at the point, screen
at the right size and a black panel behind it. The map's original is kept the
first time and is the starting point on later runs — installing twice does not
leave two screens.

| option | what it does |
| --- | --- |
| `-p` | name of the installed video package, without `.usx` |
| `--formato` | the tallest window to cover, width ÷ height (default 1.25) |
| `--escala` | the screen scale by hand, instead of the computed one |
| `--camera` | `x,y,z` or `x,y,z,yaw` — moves the camera point |

The output says what it covers, screen by screen.
