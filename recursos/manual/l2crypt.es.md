# L2Crypt: abrir y cerrar un archivo del cliente

Casi todo en el cliente de Lineage 2 está cifrado: `.dat`, `.utx`, `.u`, `.unr`,
`.ini`. Ningún editor común abre eso. El programa ya necesitaba descifrar para
hacer el resto del trabajo — esta pestaña pone esa capacidad en tus manos, en
los dos sentidos.


## El original nunca se toca

Lo que entra se **lee**. Lo que sale es **una copia nueva, en otra carpeta**. No
hay camino en el que esta pestaña escriba encima del archivo que elegiste.


## Descifrar

Elige el archivo y la carpeta de salida. El método se reconoce por el encabezado
del propio archivo, que dice la versión:

| encabezado | cómo abre |
| --- | --- |
| `Lineage2Ver111` | Blowfish |
| `Lineage2Ver120` | XOR por la posición del byte |
| `Lineage2Ver121` | XOR con clave sacada del nombre del archivo |
| `Lineage2Ver411` a `414` | RSA, en bloques, con el contenido comprimido |

Un archivo ya abierto — sin ese encabezado — se copia tal como está.


## Cifrar

Aquí hay dos cosas que sorprenden, y las dos tienen el mismo motivo: **un
archivo abierto no guarda en ningún lado cómo era**.

> **El método sale de la extensión**, y no de lo que había en el archivo. Un
> `.utx` abierto a mano no registra en parte alguna que era `Ver121`; quien
> decide es la extensión del nombre que le diste.
>
> **El nombre del archivo de salida importa.** La clave del `Ver121` deriva de
> él. El mismo contenido guardado con dos nombres distintos genera dos archivos
> distintos, y el juego solo lee el que tenga el nombre que espera.

En la práctica: para devolver un archivo al cliente, guárdalo con **el mismo
nombre** que tenía.


## Qué hacer con el archivo abierto

Un `.dat` abierto sigue siendo binario — no se convierte en texto legible. Para
editar tablas del cliente están las pestañas de Ítems, Habilidades y NPC, que
entienden el formato de cada una.

Esta pestaña sirve para lo que aquellas no cubren: mirar un archivo, comparar
dos versiones, llevar un `.ini` a otro editor, o devolver al cliente un archivo
que tocaste por fuera.


## Cuando sale mal

**"no es un paquete del cliente"** — el encabezado no coincide con ninguna
versión conocida. Suele ser un pack con protección propia: el archivo está
cifrado, pero con un encabezado fuera del estándar que ningún lector externo
reconoce.

**Abrió, pero el contenido vino revuelto** — el descifrado corrió con la clave
equivocada. En `Ver121` eso pasa cuando el archivo fue renombrado en algún
momento, porque la clave viene del nombre.

## Windows 10 y 11

Las crónicas **C1 a C4** no abren en los Windows actuales: el `L2.exe` queda
quieto, sin ventana y sin log. La C3 y la C4, después de eso, además se detienen
en un cuadro "AGP is deactivated". El recuadro **Windows 10 y 11** muestra lo
que necesita el cliente del proyecto, y **Adaptar el cliente del proyecto** lo
corrige.

| archivo | el defecto | la corrección |
| --- | --- | --- |
| `Core.dll` | al cargar, intenta crear un objeto de Windows que no existe; en Windows 10 esa consulta se cuelga con el cargador de DLL bloqueado | el juego sigue el camino que ya tenía para "el objeto no existe" — tres bytes |
| `D3DDrv.dll` (C3, C4) | pregunta por la memoria AGP, que ninguna tarjeta actual declara, y espera el clic en un cuadro | salta solo el cuadro — un byte |

Nada tiene posición fija: el programa busca en el archivo la forma exacta de
cada fragmento y solo lo cambia si coincide entera. Los originales van a
`system\backup_win10`, y **Deshacer** los devuelve. C5, Interlude y las
crónicas del Chaotic Throne en adelante no tienen estos defectos, y el
recuadro lo dice.

Por la línea de comandos:

```
L2PackTool-cli win10 "C:\Lineage II C2\system" --so-ver
L2PackTool-cli win10 "C:\Lineage II C2\system"
L2PackTool-cli win10 "C:\Lineage II C2\system" --desfazer
```

El GameGuard de los clientes oficiales no se toca con esta función.
