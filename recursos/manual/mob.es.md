# Mob: el status, las skills y la lista de drop

Un mob del servidor vive en un `<npc>` dentro de `data/xml/npcs`, y cada
archivo carga hasta mil de ellos. Las tres cosas que se editan — el status, los
golpes y lo que suelta — quedan a cientos de líneas una de otra.

Esta pestaña abre ese bloque, edita las tres, y **reescribe solo ese bloque**.
Los otros mil NPCs del archivo no se tocan en ningún byte.


## Abriendo

**Servidor** es la carpeta del servidor, o directamente su carpeta `npcs` — la
pantalla encuentra el camino desde cualquiera de las dos. **Abrir los mobs** lo
lee todo:

```
4000 mobs en ...\data\xml\npcs.
```

El core lee `npcs` y después `raidboss`, `grandboss`, `farmzone`, `custom` y
`events`, en ese orden. **Un id repetido hace valer el último en cargar** — la
definición anterior se descarta en silencio. La pantalla avisa cuando encuentra
repetidos, porque es el tipo de cosa que tiene a alguien editando un mob toda
la tarde sin entender por qué el juego no cambia.

**Cliente** no es obligatorio, pero vale la pena: de ahí salen el nombre y el
dibujo de cada ítem de la lista de drop, y es lo que permite que la
comprobación avise cuando un drop apunta a un ítem que no existe.


## Encontrando el mob

La lista filtra por texto (nombre o id), por **tipo** y por **rango de nivel**.
Los tres se suman. La caja de tipo se llena con los tipos que tu pack realmente
usa — 79 en este caso, y no una lista fija.


## Status

El primer cuadro es la identidad; el segundo, los `<set>`; el tercero, el
`<ai>`.

Los status aparecen en el orden en que se piensa en ellos — nivel, tipo, exp,
HP, los atributos — y lo que tu mob tenga además de eso entra al final, en vez
de desaparecer.

> **El `<ai>` es la trampa silenciosa.** El core lee `type`, `ssCount`,
> `ssRate`, `spsCount`, `spsRate`, `aggro`, `canMove` y `seedable` **sin
> verificar si existen**:
>
> ```java
> set.set("canMove", Boolean.parseBoolean(attrs.getNamedItem("canMove").getNodeValue()));
> ```
>
> Si falta uno, eso es un `NullPointerException` al cargar. La comprobación
> exige los ocho. Si hay `clan`, `clanRange` pasa a ser obligatorio por el
> mismo motivo.


## Skills

La raza queda en un campo propio, y no en la lista de golpes. El motivo:

```java
if (skillId == L2Skill.SKILL_NPC_RACE)   // 4416
{
    set.set("raceId", level);
    continue;                            // no registra skill alguna
}
```

**La línea `<skill id="4416" level="9"/>` no es una skill.** El core lee su
`level` como la raza del mob — 9 es Demon — y sigue adelante. En medio de la
lista de golpes sería una invitación a borrar la raza creyendo que se quitaba
un ataque.

Los golpes de verdad están en la lista de abajo. Una skill que no existe en la
tabla del servidor se ignora con un aviso en el log — vale la pena revisar el
log después de recargar.


## Drop

Cada categoría es un cajón; dentro, los ítems con el icono al lado del nombre.

> **La chance es por millón.** `DropData.MAX_CHANCE` es `1000000`, entonces:
>
> | en el archivo | en la práctica |
> | --- | --- |
> | `1000000` | 100% |
> | `79637` | 7,9637% |
> | `5` | 0,0005% |
>
> Es el error más común de la lista de drop: escribir `5` queriendo 5% hace que
> el ítem no caiga nunca. En la ventana del drop los dos campos aparecen
> juntos, y mover uno corrige el otro.

**La categoría `-1` es spoil** (sweep), y el core siempre la visita. De `0`
hacia arriba son grupos de drop común, y el core sortea **un ítem por grupo** —
poner diez ítems en una sola categoría hace que compitan entre sí, en vez de
caer juntos.

Un drop de un ítem que el cliente no conoce es descartado por el core:

```java
if (ItemTable.getInstance().getTemplate(data.getItemId()) == null)
{
    _log.warning(" Droplist data for undefined itemId: " + data.getItemId());
    continue;
}
```

En el juego el mob simplemente no lo suelta, y sin leer el log nadie descubre
por qué. Abre las tablas del cliente y la comprobación lo detecta antes.


## Minions

Los mobs que nacen junto a este. El `id` es de otro NPC; `min` y `max` son
cuántos vienen.


## Lo que la pantalla no edita

`<petdata>` — la tabla de niveles del pet, con sus cien líneas — y `<teachTo>`
no se editan aquí. **Vuelven byte a byte.** Cuando existen, la pantalla lo dice
en la esquina:

```
preservado sin tocar: petdata
```

Es una promesa que vale la pena comprobar: `Ver el XML` muestra el bloque
entero tal como va a ser grabado.


## Grabar

**Comprobar** cruza el mob con el cliente y con lo que el core exige. **Ver el
XML** muestra el bloque listo. **Grabar en el servidor** reemplaza solo ese
`<npc>` dentro del archivo y deja una copia fechada al lado:

```
20000-20999.xml.20260917-174900.bak
```

Después, en el juego:

```
//reload npc
```
