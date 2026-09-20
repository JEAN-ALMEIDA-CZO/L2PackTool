# Comprobar Cliente: lo que las tablas piden y no está

El cliente no avisa cuando falta algo. Si falta la textura, dibuja el muñeco
blanco y sigue. Si falta el paquete entero, muestra el ítem sin modelo y no
escribe nada en ningún lado.

Esta pantalla responde tres preguntas, en este orden — que es el orden en que
aparecen para quien arma un cliente:

1. **¿qué falta?** — la comprobación, que solo lee
2. **¿dónde encuentro eso?** — la búsqueda en una carpeta con otros clientes
3. **instálamelo** — la copia hacia dentro del cliente


## La comprobación

`Cargar` lee las tablas del cliente, junta toda referencia a paquete que hacen —
malla, textura, icono, sonido — y las comprueba una por una contra lo que está
en las carpetas.

El resumen sale en tarjetas, para leerse de lejos antes de cualquier lista. Solo
después viene el informe, separado por situación:

| situación | qué significa |
| --- | --- |
| **paquetes que faltan** | el cliente pide el archivo y no está en ninguna carpeta |
| **objetos que faltan** | el archivo está, pero no contiene lo que la tabla pide |
| **presentes, contenido no abierto** | paquete `Lineage2Ver111`, que solo abre entero — la comprobación confirma que el archivo existe y se detiene ahí |

El informe sale **completo**, sin abreviar. Si un paquete es pedido por 86
referencias, aparecen las 86 — existe para ser comprobado, y media lista no
comprueba nada.


## Leer el informe

Cada bloque de paquete ausente trae el nombre, cuántas referencias lo piden, y
de qué tabla viene el pedido:

```
ArmorSet_Custom                   86 referencias   (armorgrp.dat)
    ArmorSet_Custom.Drop_Custom_CAP_b_m00
    ArmorSet_Custom.FD_Custom_CAP_b_m00
    ...
```

La tabla entre paréntesis dice dónde buscar el origen. `armorgrp.dat` es
armadura; `weapongrp.dat`, arma; `npcgrp.dat`, NPC.

**Un paquete ausente con muchas referencias** suele ser un pack que se instaló a
medias — las tablas llegaron, los archivos no.

**Un objeto ausente dentro de un paquete presente** es más estrecho: alguien
cambió el paquete por una versión que no tiene ese objeto, o la tabla apunta a
un nombre mal escrito.


## Buscar e instalar

Apuntando a una carpeta con otros clientes, la pantalla busca en ella los
archivos que faltan y muestra lo que encontró. De ahí se pueden copiar hacia
dentro del cliente.

La copia es siempre **hacia dentro**: el cliente de origen no se toca.


## Lo que la comprobación no hace

No abre un paquete `Ver111` para mirar el contenido. Esos solo abren enteros, y
hacerlo para cada referencia costaría minutos por archivo. Por eso existe la
categoría "presentes, contenido no abierto": ahí la comprobación confirma que el
archivo existe y se detiene.

Tampoco comprueba el servidor. Para cruzar cliente y servidor — un ítem que
existe de un lado y no del otro — el camino es el `Cargar` de esta pestaña con
el proyecto apuntando a los dos.
