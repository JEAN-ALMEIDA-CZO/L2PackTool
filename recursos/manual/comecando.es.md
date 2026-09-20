# Comenzando

Este programa trabaja sobre dos cosas separadas, y casi todo problema de quien
empieza viene de confundirlas.

**El cliente** es lo que el jugador tiene en su máquina. Sabe **dibujar**:
malla, textura, icono, sonido, el nombre que aparece en pantalla. Son archivos
`.dat`, `.u`, `.utx` y `.ukx` dentro de la carpeta del juego.

**El servidor** es el emulador. Sabe **qué es la cosa**: cuánta vida tiene un
mob, qué suelta al morir, cuánto cuesta un ítem, qué hace una habilidad. Son XML
y tablas de base de datos, y nada de eso existe en el cliente.

Un ítem que solo existe en el servidor aparece en el juego sin nombre y sin
dibujo. Un ítem que solo existe en el cliente nunca llega a manos de nadie. Las
dos mitades tienen que coincidir, y eso es lo que hacen las pestañas de este
programa.


## El primer paso es el proyecto

Antes que nada, abre **Proyectos…** en el encabezado y crea uno: un nombre, la
carpeta del cliente y la carpeta del servidor.

Elegir el proyecto apunta las dos carpetas en **todas las pestañas a la vez**.
Quien trabaja en más de un servidor cambia de proyecto en el encabezado en vez
de ajustar dieciocho campos.

Sin proyecto, el botón `Cargar` de cada pestaña dice qué falta y dónde
resolverlo — no se queda gris sin explicar.


## El segundo paso es cargar

Cada pestaña tiene **un** botón `Cargar`. Trae todo lo que esa pestaña usa: las
tablas del cliente, los datos del servidor, o ambos.

La primera lectura de las tablas del cliente tarda — son casi diez mil ítems y
tres mil habilidades. Después queda guardada, y las pestañas comparten el mismo
catálogo: lo que leyó la pestaña de Ítems sirve al drop del mob y a la lista de
la multisell.


## El mapa de las pestañas

| pestaña | trabaja en | lado |
| --- | --- | --- |
| Texture Upscaler | texturas de un paquete `.utx` | cliente |
| NPC | crear NPC: malla, nombre, efecto | cliente |
| NPC — lado del servidor | status, drop, spawn, tienda de ese NPC | servidor |
| Lobby Vídeo | el vídeo de la pantalla de login | cliente |
| Ítems | crear y editar un ítem | ambos |
| Habilidades | crear y editar una habilidad | ambos |
| Glow | el brillo del arma y el encantamiento | cliente |
| Multisell | la lista de intercambios de un NPC | servidor |
| Mob | status, skills y drop de un mob existente | servidor |
| Comprobar Cliente | lo que las tablas piden y no está instalado | cliente |
| L2Crypt | abrir y cerrar un archivo del cliente | cliente |


## Lo que nunca ocurre solo

- **Nada se instala sin que lo ordenes.** Generar e instalar son dos botones
  distintos, en cada pestaña. Lo generado queda en una carpeta de salida hasta
  que decidas.
- **Lo que se sobrescribe se copia antes.** Los archivos del cliente van a
  `system/backup_*`; el XML del servidor recibe una copia fechada al lado.
- **Lo que el programa no entiende, no lo toca.** Editar el HP de un mob no
  reescribe el resto del archivo, y los bloques que este programa no conoce
  vuelven byte a byte.


## Después de instalar

Lo del cliente pide el cliente cerrado al instalar, y abierto de nuevo después.
Lo del servidor pide un comando en el juego:

```
//reload npc          después de tocar un mob o un NPC
//reload multisell    después de tocar una multisell
```

El manual de cada pestaña dice cuál es su comando.
