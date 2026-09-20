# Línea de comandos: hacer en lote lo que la pantalla hace de a uno

`l2upscale-cli.exe` es el mismo motor del programa, sin la interfaz. Existe
para lo que se repite: abrir cien archivos del cliente, ampliar las texturas de
una carpeta entera, comprobar un cliente dentro de un script.

Sin ningún argumento, lista lo que sabe hacer:

```
l2upscale-cli
```


## Los comandos

| comando | qué hace |
| --- | --- |
| `upscale` | amplía las texturas de un `.utx` y rearma el paquete |
| `abrir` | descifra un archivo del cliente — `.dat`, `.utx`, `.u`, `.unr`, `.ini` |
| `fechar` | cifra de vuelta, con el nombre que el juego espera |
| `extrair` | saca las texturas de un paquete, como imágenes |
| `listar` | muestra la versión y los objetos de un paquete |
| `conferir` | comprueba el cliente y dice qué archivo falta |
| `lobby` | pone el vídeo en la pantalla de login de un lobby, cámara fija |
| `ferramentas` | dice qué herramientas se encontraron, y dónde |
| `ajuda` | la lista; `ajuda <comando>` detalla uno de ellos |

`<comando> -h` muestra las opciones de ese comando. Todo comando acepta **un
archivo o una carpeta**: apuntando a la carpeta, trabaja sobre todo lo que haya
dentro, en orden de nombre.


## Abrir y cerrar

```
l2upscale-cli abrir "C:\Lineage II\system\itemname-e.dat" -o .\aberto
l2upscale-cli fechar .\aberto\itemname-e.dat -o .\fechado
```

El original **nunca se toca**: lo que sale es una copia nueva, en la carpeta de
`-o`.

Al abrir, el método viene del encabezado del propio archivo. Al cerrar viene de
la **extensión** — un archivo abierto no guarda en ningún lado lo que era.
`--versao` fuerza otro método, cuando sabes más que la extensión.

> **El nombre del archivo de salida importa.** En la versión 121 la clave deriva
> de él: el mismo contenido guardado con dos nombres genera dos archivos
> distintos. Para devolverlo al cliente, conserva el nombre que tenía.

Todo archivo cerrado se comprueba por la ida y vuelta: se abre otra vez y se
compara con lo que entró. Si no coinciden, aparece `[a ida e volta nao confere]`
al lado del nombre.


## Upscale

```
l2upscale-cli upscale Fantasy.utx -s 2
l2upscale-cli upscale C:\texturas -s 2 -o C:\saida
```

| opción | qué es |
| --- | --- |
| `-s` | la escala: 2, 3 o 4 |
| `-n` | el modelo del upscayl |
| `-o` | dónde grabar los `.utx` finales |
| `-t` | la carpeta de trabajo |
| `--parar-em` | se detiene tras `descriptografar`, `extrair` o `comprimir` |

> **La escala 2x cuadruplica la memoria de textura; 4x la multiplica por
> dieciséis.** El cliente es de 32 bits, y pasado ese punto se cierra solo — al
> entrar en un área, no al cargar el paquete. La página del Texture Upscaler
> explica qué vale la pena marcar.

Quien ya lo llamaba con la ruta directa puede seguir:

```
l2upscale-cli C:\texturas -s 2
```

Sin un comando conocido delante, el pedido es de upscale, como siempre fue.


## Listar y extraer

```
l2upscale-cli listar Fantasy.utx
l2upscale-cli extrair Fantasy.utx -o .\texturas
```

`listar` lee el paquete **incluso cerrado**: la versión 121 se descifra en la
memoria. La 111 solo abre entera, y esa pide `abrir` antes.

`extrair` graba las imágenes en una subcarpeta con el nombre del paquete.


## Comprobar

```
l2upscale-cli conferir "C:\Lineage II" -o relatorio.txt
```

El mismo informe de la pestaña Comprobar Cliente, completo. Sin `-o` sale en la
pantalla.

**El código de salida sirve a un script:** `0` cuando no hay problema, `1`
cuando falta algo. Así se encadena:

```
l2upscale-cli conferir "C:\Lineage II" -o faltando.txt || notepad faltando.txt
```


## Cuando falta una herramienta

```
l2upscale-cli ferramentas
```

Lista cada herramienta y la ruta en que fue encontrada, o `NAO ENCONTRADA`. La
búsqueda es por nombre dentro de `ferramentas/`, al lado del programa — por eso
la carpeta funciona al copiarse a cualquier lugar.

Cada comando exige solo lo que usa: `abrir` y `fechar` necesitan `l2encdec`,
`extrair` el `umodel`, y `upscale` las necesita todas.


## Lo que la línea de comandos no hace

Editar mob, multisell, ítem y skill, y crear NPC. Son trabajos de elegir en la
pantalla y ver el efecto antes de grabar — como parámetros de comando se
volverían una lista larga sin comprobación posible.


## El lobby

```
l2upscale-cli lobby "C:\Lineage II" -p L2PackTool
```

Monta la pantalla de login en el mapa del lobby: cámara fija en el punto,
pantalla del tamaño correcto y panel negro detrás. El original del mapa se
guarda la primera vez y sirve de punto de partida en las siguientes — instalar
dos veces no deja dos pantallas.

| opción | qué hace |
| --- | --- |
| `-p` | nombre del paquete de vídeo instalado, sin `.usx` |
| `--formato` | la ventana más alta a cubrir, ancho ÷ alto (por defecto 1,25) |
| `--escala` | la escala de la pantalla a mano, en vez de la calculada |
| `--camera` | `x,y,z` o `x,y,z,giro` — cambia el punto de la cámara |

La salida dice qué cubre, pantalla por pantalla.
