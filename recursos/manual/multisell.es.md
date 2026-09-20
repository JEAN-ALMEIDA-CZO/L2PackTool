# Multisell: la lista de intercambios de un NPC

Una **multisell** es la lista que se abre al hablar con un NPC de intercambio:
de un lado lo que el jugador **paga**, del otro lo que **recibe**. Adena por un
arma, materiales por una armadura, un ítem +0 por otro +8.

Es un archivo XML en el servidor, y nada más. **Del lado del cliente no hay
archivo** -- el cliente solo dibuja lo que el paquete manda.


## El nombre del archivo es la clave

Esto sale del código de su propio servidor, y no es obvio:

```java
final int id = file.getName().replaceAll(".xml", "").hashCode();
```

**No existe campo de id dentro del XML.** El identificador de la lista es el
nombre del archivo. Es con él que el NPC la abre:

```
multisell 1000          en el bypass del HTML del NPC
exc_multisell 1000      solo muestra lo que el jugador ya tiene encima
```

Tres consecuencias prácticas:

- **Renombrar cambia la identidad de la lista.** El bypass viejo deja de
  encontrarla.
- **Dos listas con el mismo nombre son la MISMA lista**, incluso en carpetas
  distintas: la segunda en cargar borra la primera.
- El nombre no tiene que ser un número. Use letras, dígitos, `-` y `_` -- un
  espacio no sirve, porque el bypass se rompería.

La pantalla muestra el bypass listo al lado del campo del nombre, para copiar.


## Armando un intercambio

El cuadro **El intercambio** tiene los dos lados. En cada uno:

- **+ ítem** abre la lista de ítems del cliente, con icono, nombre y filtro
- **Cantidad…** cambia el número y el encantamiento del ítem marcado
- **Quitar** lo saca

La cantidad es **por intercambio**: `1000` de Adena quiere decir que cada clic
le cuesta mil al jugador.

El **encantamiento** en cero no se escribe en el archivo -- es el valor por
defecto del servidor. En un ítem que el jugador *recibe*, sale ya refinado; en
uno con el que *paga*, solo sirve el ítem en ese +N exacto.

Un lado puede llevar varios ítems: `500.000 Adena + 5 Blessed SoE → 1 Dragon
Slayer` es un solo intercambio.

**Poner en la lista** manda el intercambio al checkout de abajo. Doble clic en
uno del checkout lo trae de vuelta para editar; **Subir** y **Bajar** cambian el
orden en que el jugador los ve.

Cada línea del checkout muestra los dos lados, con el icono al lado del nombre
de cada ítem:

```
3 ▸  [] Gold Bar x 30  +  [] Dark Ticket x 30.000   →   [] Saint Spear x 1 +5
```

Un intercambio con muchos ítems no cabe en una línea, y el último nombre
saldría cortado. El **triángulo** al frente del número abre la lista:

```
1 ▾  5 ítems                                        →   1 ítem
        [] Titanium Breastplate x 1                        [] Dark Coin x 1
        [] Event Coin Lv.1 x 50
        [] Golden Enchant: Armor x 500
        [] Tournament Point's Lv.1 x 1.000
        [] Dark Ticket x 50.000
```

El triángulo solo aparece donde hay algo que abrir: un intercambio de uno por
uno ya lo dice todo en su propia línea. Hacer clic en el triángulo abre y
cierra; hacer clic en el resto de la línea solo marca el intercambio, y el
doble clic lo manda de vuelta para editar.


## Los NPCs

El campo **NPCs** lleva los ids que pueden abrir esta lista, separados por
espacio o coma.

> **En blanco, CUALQUIER NPC la abre.** Así es en el core:
>
> ```java
> public boolean isNpcAllowed(int npcId) {
>     return _npcsAllowed == null || _npcsAllowed.contains(npcId);
> }
> ```
>
> La lista solo queda restringida cuando tiene al menos un NPC. Y, estando
> restringida, deja de poder abrirse **sin** NPC -- desde un panel de la
> comunidad, por ejemplo.


## Las dos opciones

| opción | qué hace |
| --- | --- |
| `cobrar la tasa del castillo` | descuenta la tasa de la región |
| `mantener el encantamiento` | el ítem recibido sale con el mismo +N del dado |

`mantener el encantamiento` sirve para cambio de arma por arma: quien entrega
una +8 recibe la nueva +8. Sin ella, el ítem sale en el +N que diga el
intercambio.


## La comprobación, y lo que atrapa

**Comprobar** cruza la lista con las tablas del cliente y avisa de:

- un ítem que **no existe en el cliente** -- en el juego esa línea saldría sin
  nombre y sin dibujo, y nadie sabría por qué
- una cantidad de cero o menos
- un intercambio con un solo lado
- un nombre de archivo inválido, o **ya usado por otra lista**

Por eso vale la pena abrir las tablas del cliente antes: sin ellas la pantalla
funciona solo con los ids, y se pierde esta comprobación.


## Generar e instalar

**Ver el XML** muestra el archivo listo, con un comentario legible en cada
intercambio:

```xml
<!-- 500000 Adena + 5 Blessed Scroll of Escape -> 1 Dragon Slayer -->
<item>
    <ingredient id="57" count="500000"/>
    <ingredient id="1538" count="5"/>
    <production id="81" count="1" enchant="8"/>
</item>
```

**Instalar en el servidor** escribe en su carpeta de multisell -- dónde está
sale del propio servidor, leído de sus archivos. Una copia queda siempre en
`multisell_gerada/`, para recuperar si alguien toca la del servidor a mano.

Después, en el juego:

```
//reload multisell
```

Y el bypass en el HTML del NPC, que la pantalla muestra listo.


## Dónde entra el cliente

No hay archivo de multisell en el cliente. Lo que el cliente necesita es
**conocer los ítems** usados: id, nombre e icono. Un ítem creado en la pestaña
de Ítems aparece aquí por su nombre, con su dibujo, en cuanto se abren las
tablas.

Si arma un intercambio con un ítem que solo existe en el servidor, la
comprobación avisa -- y en el juego esa línea aparecería vacía.
