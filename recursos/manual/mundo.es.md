# NPC y tienda: el lado del servidor

El cliente sabe **dibujar** el NPC — malla, textura, sonido. Eso es trabajo de la
pestana de NPC Effects. Lo que no sabe es **que es el NPC**: cuanta vida tiene,
que suelta al morir, donde nace, que vende. Nada de eso existe en el cliente.

Esta pestana genera esa mitad.


## Elige el servidor primero

El cliente de Lineage 2 es uno solo; el emulador no.

| Formato | Quien lo usa | Donde guarda |
| --- | --- | --- |
| **XML** | aCis, L2jServer, Mobius, Lisvus | `data/xml/npcs`, `data/xml/multisell` |
| **Banco** | L2jFrozen y los cores de datapack antiguo | tablas `npc`, `droplist`, `spawnlist` |

No es solo el formato: los nombres cambian. Donde aCis escribe
`<set name="pAtk" val="700"/>`, el banco tiene una columna `patk`. Donde aCis
dice `type="Monster"`, el banco dice `L2Monster`.

La caja **Servidor** de arriba elige, y el mismo formulario sale en el formato
correcto.

Su primera opcion no es un core: **Detectar por el servidor** lee la carpeta que
apuntaste y monta el perfil a partir de ella: en que carpetas viven las cosas,
si el objetivo de la habilidad lleva prefijo, como se escribe la gaveta de drop,
en que unidad va la probabilidad. Tarda unos dos segundos, y **lo que vio
aparece al lado de la caja**.

Es la opcion de partida porque "cual es mi core?" no suele tener respuesta
simple: quien monta un servidor toma un core, le cambia el nombre y toca lo que
quiere. Un servidor con nombre propio puede ser aCis por debajo, con cuatro
diferencias, y esas diferencias estan escritas en sus propios archivos.

Los cores hechos siguen en la lista, y elegir uno manda. Detectar es el valor
por defecto, no una imposicion.

**Un core que no esta en la lista** tambien se agrega dejando un `.json` en
`recursos/servidores/`. El archivo dice el formato, las carpetas o tablas, y el
de-para de los campos. No hay codigo que tocar.

Una cosa que vale saber: el `INSERT` sale con **los nombres de las columnas**, y
no por posicion. El esquema de un emulador no es fijo, y una columna de mas en
medio haria que un insert posicional pusiera el precio donde va el peso -- sin
error y sin aviso.


## Leer del servidor

El boton **Leer del servidor**, arriba del paso 2, busca este NPC en la carpeta
de datos del servidor y trae lo que tiene: atributos, drop, spawn y tienda.

Lee el NPC **marcado en la lista** -- y no el del campo **id nuevo**. El campo
dice adonde va el NPC; la lista dice de donde viene. Asi se copian los atributos
de un monstruo que ya funciona: el cliente nunca guardo vida ni ataque, y asi no
hay que escribirlos.

Si no esta ahi, el programa avisa que el NPC todavia no existe del lado del
servidor. No es un error: es el caso de rellenar y generar.

Funciona en los dos formatos. En un `INSERT` que no nombra las columnas — y casi
todo `.sql` que circula es asi — el programa usa el orden de columnas declarado
en el perfil. Si el perfil no lo trae, dice que no supo leer, en vez de adivinar
por posicion.

El nombre y el titulo vuelven al paso 1. Lo que **tu escribiste** nunca se
borra; lo que vino de una lectura anterior se sustituye.

## Atributos

Elige el NPC base de la lista — sirve de referencia de apariencia y de id. Los
campos vienen con valores de partida plausibles para un NPC de nivel 70;
ajustalos.

El **id** debe coincidir con el del cliente. Si creaste el NPC en la pestana de
NPC Effects, usa el mismo id aqui: es lo que ata los dos lados.

**tipo** decide el comportamiento: `Monster` ataca, `Folk` se queda quieto y
habla, `Merchant` abre tienda, `Teleporter` teletransporta, `RaidBoss` es jefe.
En el servidor de banco el nombre sale con el prefijo `L2` automaticamente.

**vida, mana, ataque, defensa** son los numeros de combate. Para un NPC que solo
habla no importan; para un monstruo lo son todo.

**radio y altura de colision** vienen del tamano del muneco. Equivocados, el
personaje atraviesa al NPC o se queda atascado lejos de el.

**experiencia y SP** es lo que gana el jugador al matarlo. Cero en un NPC de
ciudad.

**radio de agresion** en cero hace que el NPC no ataque por su cuenta.


## Drop

Lo que el NPC suelta al morir.

La **probabilidad es porcentual**: `2.5` es 2,5%. Para el servidor de banco el
numero se convierte a su escala (donde 1.000.000 es 100%) — tu escribes en por
ciento en los dos casos.

El **cajon** separa:

| cajon | que es |
| --- | --- |
| `DROP` | el item cae al suelo al morir |
| `CURRENCY` | adena — el item 57 |
| `SPOIL` | solo sale con la habilidad de spoil |

La adena es el item **57**. Un monstruo normal tiene una fila `CURRENCY` con
adena y algunas filas `DROP`.


## Spawn

Donde nace el NPC. Las coordenadas se sacan en el juego, con el comando que
muestra la posicion.

**direccion** es hacia donde mira, de 0 a 65535. **renace en** es en segundos.

Marca **generar el spawn tambien** para que salga el archivo. Sin marcarlo solo
se genera el NPC — que es lo que quieres cuando vas a colocarlo en el juego con
el comando de spawn.


## Tienda

El multisell: lo que el jugador paga y lo que recibe.

Es XML en los dos formatos de servidor — hasta los cores de banco guardan la
tienda en archivo.

**La adena es el item 57.** Una venta normal es pagar adena y recibir el item.
Un trueque es pagar un item y recibir otro. Puedes poner varias filas; cada una
es una opcion en la ventana de la tienda.

El **id de la tienda** es el nombre del archivo. Para que el NPC abra la tienda,
el servidor tiene que saberlo — normalmente por un script o por el tipo
`Merchant` con la tienda atada al id. Eso varia de core a core y queda fuera de
lo que esta pantalla genera.


## Generar

**Ver lo que sale** lo muestra todo antes. **Generar** graba en la carpeta
elegida.

Lo que sale:

- `<id>-npc.xml` o `<id>-npc.sql` — el NPC, con el drop dentro en el caso del XML
- `<id>-spawn.xml` o `.sql` — si lo marcaste
- `<id de la tienda>.xml` — el multisell

Copialos a las carpetas del servidor; si es de banco, ejecuta el `.sql` en el. El
gameserver tiene que reiniciarse.

**Esta pestana no escribe nada en el cliente.** Solo escribe el lado del
servidor.
