# Los textos del cliente: mensajes, interfaz y frases de NPC

Todo lo que el juego escribe en pantalla y no es nombre de ítem ni de habilidad
vive en tres tablas del `system`:

| Archivo | Qué guarda | Ejemplo |
| --- | --- | --- |
| `systemmsg-e.dat` | mensaje del sistema | `You have been disconnected from the server.` |
| `sysstring-e.dat` | texto de interfaz | `Equipment`, `Quest Item` |
| `npcstring-e.dat` | frase de NPC con variable dentro | `Hello! I am $s1.` |

Son **11.499 textos** en un cliente de High Five y **3.764** en uno de C5. El
`npcstring-e` solo existe de Freya en adelante; donde no está, la pantalla lo dice
y trabaja con los otros dos.

Quien monta servidor toca esto por dos motivos: **traducir** y **hacer que el
juego diga lo que dice su servidor** — el nombre del servidor en el mensaje de
entrada, la explicación de un sistema propio, el aviso de un evento.


## La búsqueda es el centro de la pantalla

Once mil líneas no se recorren desplazando. Escribí en la búsqueda el texto **como
aparece en el juego** — "disconnected", "Equipment", "Welcome" — y la lista se
cierra a su alrededor. El campo también acepta el id, cuando ya lo conocés.

Dos ayudas al lado:

- **tabla** — limita a una de las tres;
- **solo las que tienen $s1** — muestra únicamente las frases con marca, que son
  las que el servidor completa.


## La marca vale más que el texto

`$s1`, `$s2`, `$c1` son los **huecos donde el servidor encaja** un número, un
nombre de jugador o un ítem:

```
The server will be coming down in $s1 second(s).
```

El servidor manda el `60`; el cliente escribe `60` en lugar del `$s1`. Son 1.135
frases con marca en High Five.

Reescribir la frase **sin la marca** no da error en ningún lado: sigue
apareciendo, solo llega sin el dato que anunciaba — "El servidor va a caer en
segundo(s)". Por eso la pantalla cuenta las marcas antes y después, y pregunta
cuando alguna se pierde. Si fue a propósito, confirmá; si no, el texto vuelve como
estaba.

Cuando marcás una frase, el rótulo arriba del campo dice cuántas marcas tiene y
cuáles son.


## La segunda línea

Solo el **mensaje del sistema** tiene una segunda línea (`sub_msg`) — lo que el
juego escribe debajo de la principal. En las otras dos el campo queda apagado, en
vez de aceptar un texto que no iría a ninguna parte.

El resto de cada línea — color, sonido, grupo — **no se toca**. Un mensaje con el
color cambiado sigue funcionando; un mensaje sin su marca, no. La pantalla se
ocupa de lo que importa y deja el resto exactamente como estaba.


## El camino: aplicar, generar, instalar

Tres pasos, separados a propósito:

1. **Aplicar** guarda el texto nuevo en memoria. Todavía no se escribió nada.
2. **Generar las tablas** escribe los `.dat` en una carpeta aparte
   (`textos_gerados`), para poder mirar el resultado antes de que el cliente
   dependa de él.
3. **Instalar en el cliente** los copia al `system`. La primera vez los originales
   quedan guardados en `system/backup_textos`, y **Restaurar originales** los trae
   de vuelta de ahí.

Cerrá el cliente antes de instalar — Windows no deja escribir en un archivo que el
juego está leyendo.


## La prueba, antes de grabar

Al cargar, cada tabla se abre, se **rearma** y se compara byte a byte con el
binario original. Si la vuelta no reproduce la ida, la definición no describe este
cliente: la tabla se puede leer, y grabar en ella queda bloqueado.

Las tres tablas vuelven idénticas en once clientes de acá, de C3 a High Five. El
Interlude entró sin esa prueba — no hay cliente suyo extraído acá para medir — y
el programa no dice lo contrario.


## Lo que esto no hace

- **No traduce nada solo.** El texto nuevo es el que escribas.
- **No toca nombres de ítem ni de habilidad.** Esos están en el `itemname-e` y en
  el `skillname-e`, en las pestañas de Ítems y Habilidades.
- **No crea textos nuevos.** Los ids son los que el cliente conoce; un id
  inventado sería un texto que el servidor nunca pide.
