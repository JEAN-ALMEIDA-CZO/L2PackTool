# Crear un item: que rellenar

Un item de Lineage 2 existe en dos sitios a la vez, y los dos tienen que estar
de acuerdo:

- el **cliente** sabe dibujarlo — malla, textura, icono, sonido;
- el **servidor** sabe lo que hace — dano, defensa, peso, precio.

Lo que ata a los dos es el **id**. Si solo un lado tiene el item, no aparece
ningun error: aparece confusion. Item sin nombre, icono en blanco, o un item que
el servidor entrega y el cliente no dibuja.

Esta pestana se ocupa de los dos lados. Las tablas del cliente salen listas para
instalar; el XML del servidor sale con ellas, y tu lo copias a la carpeta de
items de tu servidor.


## Editar o crear

La pantalla tiene un **modo**, escrito en letras grandes arriba del panel de la
derecha:

```
Editando el item 1 — Short Sword
Item nuevo 30000, copiado del 1
```

**Hacer clic en un item de la lista edita ese item.** Los campos se llenan con
sus datos, el id queda fijo en el suyo, y el boton pasa a **Reescribir el
item**. El id se fija a proposito: cambiar el numero ahi seria, en realidad,
crear otro.

**Crear pasa por la ventana Item nuevo…** Pregunta el id (con Sugerir), nombre,
descripcion e icono; rechaza un id que ya exista sin la marca de sustituir;
avisa si el id cae en el rango del juego. Lo que sale de ella llena el panel, y
los campos siguen editables.

Despues de generar, la pantalla pasa a **editar lo que acaba de salir**.


## 1. Elige el item base

Todo item nuevo nace como copia de uno que ya funciona. No es pereza: una fila
del `armorgrp.dat` tiene **332 columnas**, y la mayoria no tiene nada que ver
con la apariencia — peso, sonido al equipar, tipo de cristal, y la malla y la
textura de cada una de las doce combinaciones de raza y sexo. Inventar esos
valores da un item que existe y esta mal.

Busca en la lista por el nombre, por el id o por el nombre del icono. Pulsa una
fila: el icono aparece en la esquina, y los campos del XML se rellenan con lo
que se puede leer de la tabla del cliente.

**Elige una base parecida a lo que quieres.** Una espada nueva copiada de una
espada hereda la forma de sujetarla, el sonido del golpe y la animacion. Copiada
de un sombrero, no.


## 2. Identificacion

### id

El numero que el cliente y el servidor usan para hablar del mismo item.

**Sugerir** busca el primer id libre a partir de **30000**, lejos del rango del
juego original. Usalo. Un id dentro del rango del juego sobrescribe un item de
verdad — y entonces la espada que creaste se convierte en la Adena de alguien.

El programa avisa cuando el id elegido queda por debajo de 30000.

### nombre

Lo que lee el jugador. Viene puesto con el nombre del item base; cambialo.

### descripcion

El texto que aparece al dejar el raton sobre el item, en el inventario. Puede
quedar vacio.

### icono

La referencia tiene la forma `paquete.objeto` — por ejemplo
`icon.weapon_long_sword_i00`. Es el dibujo de 32×32 que aparece en el
inventario.

En la ventana **Item nuevo…** el icono se elige **viendo**: hay una rejilla de
miniaturas a la derecha, con el arte al tamano en que el juego lo dibuja. Haz
clic en una para elegirla.

La rejilla abre en los iconos **parecidos al del item base** — copiando una
espada, empieza en las armas — y muestra 240 por vez; la etiqueta dice cuantos
quedaron fuera y la busqueda reduce. Nada queda escondido: el campo de busqueda
alcanza los 13.690.

El icono no tiene que ser el del item base. Cambiar solo el icono es la forma
mas barata de darle cara nueva a un item copiado, sin tocar ningun modelo.

Justo debajo de la rejilla, **Usar una imagen mia** acepta un dibujo tuyo: mira
la ultima seccion.

### sustituir si el id ya existe

Dejalo **sin marcar**. Marcado, borra el item que este en ese id en vez de
negarse — lo que solo sirve cuando estas rehaciendo un item que creaste antes.


## 3. XML del servidor

Lo que quede en blanco **no se escribe**. El servidor tiene un valor por defecto
para cada campo, y un campo ausente vale ese valor. Rellenar solo lo que importa
deja el archivo legible.

### tipo en el servidor

`Weapon`, `Armor` o `EtcItem`. Viene puesto.

Un caso que confunde: **el escudo esta en el `weapongrp` del cliente, pero para
el servidor es `Armor`**. El programa lo detecta por el item base y ya marca el
tipo correcto. Marcado como `Weapon`, el personaje empuna el escudo como arma.

### accion al pulsar

Lo que pasa al hacer doble clic en el inventario. `equip` para arma y armadura;
`skill_reduce` para pocion; `none` para material y objeto de mision.

### parte del cuerpo

Donde se lleva el item:

| valor | donde |
| --- | --- |
| `rhand` | mano derecha — arma de una mano |
| `lrhand` | las dos manos — mandoble, arco, lanza |
| `lhand` | mano izquierda — escudo |
| `chest`, `legs`, `feet`, `gloves`, `head` | las piezas de la armadura |
| `fullarmor` | pecho y piernas en la misma pieza |
| `neck` | collar |
| `rfinger;lfinger` | anillo |
| `rear;lear` | pendiente |
| `none` | no se lleva puesto |

### material

De que esta hecho el item. No es decoracion: el material decide el sonido al ser
golpeado, y cuenta para algunas resistencias. Viene del cliente y acierta en el
100% de los items comprobados.

### grado

`D`, `C`, `B`, `A`, `S`, o vacio para item sin grado. Controla que cristales
devuelve el item y a partir de que nivel se puede usar.

### peso

En unidades del juego — la Short Sword pesa `1600`. Viene puesto.

### precio

Lo que cobra el NPC. **No sale del cliente**, asi que viene vacio: rellenalo o
dejalo en cero.

### cristales

Cuantos cristales devuelve el item al romperse.

### tipo de arma

`SWORD`, `BLUNT`, `DAGGER`, `BOW`, `POLE`, `DUAL`, `DUALFIST`, `FIST`,
`BIGSWORD`, `BIGBLUNT`, `ETC`, `FISHINGROD`.

Decide que habilidad puede usar el personaje con el item en la mano y que
animacion de ataque toca. Viene puesto, y el programa ya separa espada de
mandoble por el numero de manos.

### tipo de armadura

`LIGHT`, `HEAVY`, `MAGIC`. Decide las penalizaciones de clase: un mago con
armadura pesada pierde regeneracion de mana.

### dano aleatorio, soulshots, spiritshots

Salen del cliente. `soulshots` y `spiritshots` son cuantos tiros consume el item
por golpe.

### negociable, soltable, vendible, destruible, almacenable

Dejalos en blanco para el valor por defecto (todo permitido). Pon `false` en lo
que quieras bloquear — un item de evento suele ser `is_tradable false` y
`is_dropable false`.


## Leer del servidor

El cliente guarda apariencia, peso y material. **El dano, la defensa y el precio
no existen en el.** El boton **Leer del servidor**, en la pestana XML, busca el
item en la carpeta de datos del servidor y trae los campos y los estados.

Lee el item **marcado en la lista** -- y no el del campo **id nuevo**. El
campo dice adonde va el item; la lista dice de donde viene. Para releer un item
que creaste, marcalo en la lista: esta ahi despues de generar.

Si no esta ahi, avisa que el item todavia no existe del lado del servidor. No
es un error: es el caso de rellenar y generar.

Funciona en los dos formatos. En los cores de banco las columnas de combate
(`p_dam`, `p_def`, `critical`) vuelven al bloque de estados, que es donde el XML
las pone.

## 4. Estados que el item da al jugador

Es esta parte la que hace que el item **valga algo**. Sin ella, la espada nueva
tiene la apariencia correcta y ningun dano.

Cada fila tiene tres partes: **operacion**, **estado** y **valor**.

### La operacion

Dice como entra el valor en la cuenta:

| operacion | que hace |
| --- | --- |
| `add` | suma al total ya calculado |
| `baseadd` | suma a la base, antes de los multiplicadores |
| `sub` | resta |
| `mul` | multiplica (`1.1` = un 10% mas) |
| `basemul` | multiplica la base |
| `div` | divide |
| `set` | fija el valor, ignorando lo que habia |
| `enchant` | la parte que crece con cada encantamiento |

**En la practica**, siguiendo lo que hace el propio juego:

- arma: `set` para `pAtk`, `mAtk`, `rCrit` y `pAtkSpd`;
- armadura: `baseadd` para `pDef` o `mDef`, y `enchant` para la parte que sube
  con el encantamiento;
- escudo: `set` para `sDef` y `rShld`, `sub` para `rEvas`;
- accesorio: `baseadd` para `mDef`, `add` para bonus como `maxMp`.

### El orden

Al lado de la operacion esta el **orden**: en que momento de la cuenta entra ese
valor. Se rellena solo, con lo que el juego usa para cada operacion:

| operacion | orden | que significa |
| --- | --- | --- |
| `set` | `0x08` | fija la base |
| `enchant` | `0x0C` | lo que crece con cada +1, justo despues de la base |
| `add` / `sub` | `0x10` | suma antes de los multiplicadores |
| `mul` / `basemul` | `0x30` | multiplica |
| — | `0x40` | suma **despues** de los multiplicadores |

Los numeros no son una eleccion de estilo: salen de contar el datapack, donde
`set` aparece con `0x08` en los 4.736 estados, sin una sola excepcion.

**Es obligatorio.** El servidor lee el atributo sin comprobar que exista:

```java
String order = n.getAttributes().getNamedItem("order").getNodeValue();
```

Si falta, la lectura revienta y la **tabla de items entera** deja de cargar.
Quien tenga un item generado por una version anterior de este programa, con
estados y sin orden, necesita volver a grabarlo.

Toquelo solo si sabe por que. `0x40` sirve para un bono que debe entrar despues
de las cuentas de clase -- es lo que el juego hace con `maxMp` de accesorio.

### El estado

Elige de la lista. Esta agrupada por asunto — vida y mana, ataque y defensa,
tasas y evasion, atributos, PvP, resistencias, vulnerabilidades, reflejo, contra
tipo de criatura, limites.

Los mas usados:

| estado | que es |
| --- | --- |
| `pAtk` / `mAtk` | ataque fisico / magico |
| `pDef` / `mDef` | defensa fisica / magica |
| `pAtkSpd` / `mAtkSpd` | velocidad de ataque / de magia |
| `rCrit` | tasa de critico (10 = 1%) |
| `cAtk` | dano critico |
| `accCombat` / `rEvas` | precision / evasion |
| `maxHp` / `maxMp` / `maxCp` | vida, mana y CP maximos |
| `regHp` / `regMp` | regeneracion |
| `runSpd` | velocidad de carrera |
| `sDef` / `rShld` | defensa y tasa de bloqueo del escudo |
| `STR`, `CON`, `DEX`, `INT`, `WIT`, `MEN` | atributos |

**Por que importa**: un nombre de estado que el servidor no conoce no se
ignora. Tumba la carga de la **tabla de items entera** — todos los items del
servidor, no solo el nuevo.

La lista es del programa, y no todo core tiene todos sus nombres. El boton
**Comprobar con el servidor** lee la carpeta que apuntaste y marca con ⚠ los que
el tuyo no tiene. Cuando el codigo fuente esta junto a la carpeta de datos, la
respuesta sale de su `Stats.java` y es completa; cuando solo hay los `.jar`,
sale de los `stat="..."` que usa el datapack — menor, pero todo nombre ahi es
prueba de que carga.

### El valor

Un numero. Puede llevar decimales con punto (`1.15`) y puede ser negativo para
una penalizacion.

Cuidado con la escala: `rCrit` cuenta en decimas de por ciento (`80` es 8%), y
`pAtkSpd` es un numero absoluto (un arma normal ronda `379`). Ante la duda, mira
un item parecido en tu servidor.

### Ver el XML

Muestra el archivo listo antes de generar. Siempre vale la pena mirarlo antes de
instalar.


## 5. Skills que el item lleva

Un arma puede dar una habilidad a quien la equipa, o disparar una en el golpe.
En este servidor eso **no** es un `<skill>` dentro del item: son campos `<set>`,
con el id y el nivel escritos juntos.

| campo | cuando vale | cuantas |
| --- | --- | --- |
| `item_skill` | mientras el item este equipado | varias, separadas por `;` |
| `enchant4_skill` | desde el +4 | una |
| `oncrit_skill` | al dar un critico | una |
| `oncast_skill` | al castear | una |

El valor es `id-nivel`: `3599-1`. Para varias, `3599-1;3600-2`.

### La chance, que se traga en silencio

`oncrit_skill` y `oncast_skill` **exigen** la chance al lado --
`oncrit_chance`, `oncast_chance`, en por ciento. El servidor hace:

```java
if (id > 0 && level > 0 && chance > 0)
```

Sin la chance, o con ella en cero, la skill se **descarta sin una linea de
log**. No da error, el servidor arranca normal, y el arma simplemente no hace
nada. Quien pruebe va a culpar a la habilidad, y no al campo que falto. Por eso
existe el boton **Comprobar**, y por eso la ventana pregunta antes de dejarlo
pasar.


## 6. Los numeros del cliente (arma)

En la ventana **Nuevo item**, cuando la base es un arma, aparece la pagina
**Numeros**. Son las columnas del `weapongrp.dat` -- **lo que muestra el tooltip
del inventario**.

Eso es distinto de los Estados. Los Estados son del servidor: lo que el golpe
hace de verdad. Los Numeros son del cliente: lo que el jugador lee. **Los dos
pueden discrepar sin que ninguno se queje.** La Draconic Bow de este cliente
muestra 581 de P.Atk en el tooltip; el servidor usa 561.

Al lado de cada casilla esta el nombre gris del estado correspondiente:

| cliente | servidor |
| --- | --- |
| `patt` / `matt` | `pAtk` / `mAtk` |
| `critical` | `rCrit` |
| `speed` | `pAtkSpd` |
| `hit_mod` | `accCombat` |
| `avoid_mod` | `rEvas` |
| `shield_pdef` / `shield_rate` | `sDef` / `rShld` |

`hit_mod` y `avoid_mod` son los unicos con signo en el cliente. Del lado del
servidor el signo se vuelve la **operacion**: `-3` en el cliente es
`<sub stat="accCombat" val="3">`.

El boton **Copiar a los Stats** hace esa traduccion y lo escribe todo en la
pagina Estados, ya con la operacion y el orden correctos. Es el camino corto
para que los dos lados cuenten la misma historia.


## 7. Generar, instalar, y el siguiente item

**Generar** escribe las tablas cambiadas y el `<id>-item.xml` en una carpeta
aparte. **Todavia no cambia nada en el cliente.**

**Instalar en el cliente** pone las tablas en su sitio. La primera vez, las
originales van a `system/backup_itens`; **Restaurar originales** las trae de
vuelta y deshace todo de una vez.

El XML lo copias a mano a la carpeta de items del servidor — normalmente
`data/xml/items/` — y reinicias el gameserver.

Despues de generar, la pantalla ya se prepara para el siguiente: sugiere el id
libre siguiente, limpia nombre, descripcion y estados, y mantiene el item base
marcado. Diez items creados seguidos salen en un solo `weapongrp.dat`,
instalado de una vez.

**Cierra el cliente antes de instalar.** El juego abierto mantiene las tablas en
memoria y escribe encima al salir.



## 8. Icono propio

En la ventana de elegir icono, la pestana **Imagen propia** acepta un dibujo
tuyo — PNG, JPG, BMP, TGA, DDS.

Lo que pasa: la imagen se ajusta a 32x32 (sin estirar: si no es cuadrada, entra
centrada en un cuadrado transparente), se comprime en DXT, se monta en un
paquete `.utx`. El campo del icono recibe ya la referencia lista.

El paquete queda **preparado, no instalado**: sale en la carpeta de salida junto
con las tablas y entra en `systextures` en el mismo **Instalar en el cliente**.
Una accion, un lugar: instalar al momento dejaria un icono dentro del cliente
mientras el resto todavia no existe en ningun lado.

**El paquete es tuyo.** El programa nunca escribe dentro del `Icon.utx` ni del
`Icon.u` del juego, y se niega si lo intentas: un error en tu propio paquete
cuesta un icono; en el del juego costaria los catorce mil. No se pierde nada —
el cliente carga tantos paquetes de icono como haya, y el tuyo ya tiene varios.

Anadir un segundo icono al mismo paquete **remonta el paquete entero**, con los
que ya estaban dentro. Es mas lento y es la unica forma honesta: media remonta
perderia los antiguos.

El nombre del paquete y el del icono aceptan letras, numeros y guion bajo. El
nombre del archivo importa de verdad — la clave de cifrado del `.utx` deriva de
el — asi que renombrar el paquete despues de creado lo corrompe. Si necesitas
otro nombre, crealo de nuevo.

## Si algo sale mal

**"La vuelta no reproduce el original"** — la definicion de las tablas no
describe este cliente, y grabar queda bloqueado a proposito. Normalmente el
cliente es de otra cronica. No se escribio nada.

**Item sin nombre en el juego** — las tablas se instalaron a medias. Se emparejan
por el id y tienen que ir juntas. Usa **Restaurar originales** y genera de nuevo.

**El servidor no arranca despues del XML** — casi siempre es un nombre de estado
o de material escrito a mano fuera de la lista. Mira el log del gameserver: dice
el nombre que no reconocio.

**El item aparece sin icono** — la referencia del icono apunta a un objeto que no
existe. Usa **Elegir…** en vez de escribir, o pasa la pestana **Verificar
Cliente**, que lista todo lo que las tablas piden y no esta instalado.

**El icono no aparece en la pantalla, pero sí en el juego** — hay packs cuyo
paquete de iconos viene protegido: una cabecera fuera del estándar que ningún
lector externo abre. El juego lo abre porque tiene la clave; el programa no.

El icono queda entonces **vacío**, y el registro dice qué paquete no abrió:

```
o pacote PacoteCustom nao abriu; os icones dele nao vao aparecer
```

El programa no toma el dibujo de otro paquete para tapar el hueco. El objeto
suele existir en `Icon.u` con el mismo nombre, pero nada garantiza que sea la
misma arte — y un dibujo equivocado con cara de correcto borraría la única
señal de que hay un paquete por resolver. Descifra el paquete y reconstrúyelo
como `.utx`, y el icono aparece.
