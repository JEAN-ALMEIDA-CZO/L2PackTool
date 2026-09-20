# NPC: crear un NPC en el cliente

Esta pestaña crea un NPC nuevo en el **cliente** — su apariencia: qué malla usa,
qué nombre muestra y qué efecto brilla a su alrededor. Lo que el NPC **es** —
vida, drop, spawn, tienda — está en la pestaña de abajo, `2 - Servidor`.

La pantalla tiene tres partes, en el orden en que se usan:

1. los NPCs que el cliente ya tiene, para elegir de quién copiar la apariencia
2. los efectos que el cliente ya tiene, para elegir qué va a brillar
3. el formulario del NPC nuevo, con los dos botones


## Elegir de quién copiar

`Cargar` lee el `npcgrp.dat` y lista los NPCs del cliente con la malla de cada
uno. La columna de la derecha dice qué tiene ese NPC: `Mesh x2, Sprite x1`
significa dos mallas y un efecto.

Copiar de un NPC que ya funciona es el camino corto: la malla, la textura y las
animaciones vienen listas, y lo que cambias es el id, el nombre y el efecto.


## El efecto

La lista de efectos sale de los paquetes del propio cliente. `Añadir el efecto
seleccionado` sujeta un efecto al NPC nuevo; `Aplicar al marcado` lo pone en uno
que ya existe.

La **altura (Z)** mueve el efecto hacia arriba o hacia abajo respecto al hueso
elegido. El dibujo al lado muestra dónde queda en la malla — un efecto con la
`Z` equivocada sale de los pies o flota por encima de la cabeza.

**Obedecer a la altura** hace que el efecto escale junto con la malla. Sin eso,
un efecto dibujado para un personaje de tamaño normal queda diminuto en un
gigante.


## Script o rápido

| modo | qué hace |
| --- | --- |
| **Script (compila)** | genera una clase propia y compila un paquete `FX_<id>.u` |
| **Rápido (solo el .dat)** | escribe solo la línea en el `npcgrp.dat` |

El modo rápido es más simple y no crea un archivo nuevo, pero no permite sujetar
un efecto. El modo script es el que permite efecto, y por eso es el
predeterminado cuando hay un efecto elegido.

> Un NPC con clase propia suele aparecer como `NoNameNPC` en el visualizador,
> incluso con el nombre grabado en el `npcname-e.dat`. No es un defecto: el
> visualizador resuelve el nombre de otra forma que el juego. La salida es
> marcar **el servidor manda el nombre y el título** en la pestaña del servidor.


## Ver en el juego

El visualizador abre la malla con textura y ejecuta las animaciones. **No
muestra el efecto**: un emisor de partículas no está entre los recursos que
abre, y ningún visualizador de Lineage 2 dibuja partículas de Unreal Engine 2 —
eso solo lo hace el motor del juego.

Para ver el efecto de verdad, el camino es el modo de desarrollo del propio
cliente. Los comandos que reconoce están listados en la pestaña.


## Generar e instalar

Son pasos separados a propósito.

**Generar** escribe todo en una carpeta de salida y no toca el cliente. Ves lo
que salió — las tablas, el paquete, el nombre — y solo entonces lo autorizas.

**Instalar en el cliente** lo copia dentro. Lo que se sobrescriba va antes a
`system/backup_npc`.

Quien instala por error en un cliente que usa para jugar descubre el problema al
entrar en el juego, que ya es tarde.


## NPCs creados en este cliente

El botón abre la lista de lo que este programa ya puso en este cliente, con la
opción de quitar. Quitar saca la línea del `npcgrp.dat`, el nombre del
`npcname-e.dat` y el paquete `FX_<id>.u` — todo con copia previa.

Del lado del servidor sigue estando el XML de ese NPC, que hay que borrar a mano
y seguir con `//reload npc`. La ventana lo dice en el momento.
