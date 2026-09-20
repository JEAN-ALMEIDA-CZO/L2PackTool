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
