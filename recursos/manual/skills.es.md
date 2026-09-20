# Crear una habilidad: que rellenar

Una habilidad vive en los mismos dos sitios que un item — el **cliente** sabe
dibujarla, el **servidor** sabe lo que hace — y el **id** ata a los dos.

La diferencia que lo cambia todo: la habilidad tiene **niveles**. No es una
fila, es un bloque de filas, una por nivel, en cada tabla:

| Archivo | Que guarda |
| --- | --- |
| `skillgrp.dat` | icono, mana, alcance, tiempo de uso — por nivel |
| `skillname-e.dat` | nombre y descripcion — por nivel |

En este cliente son 3.067 habilidades en 42.019 filas. Copiar una habilidad
copia todos sus niveles, en las dos tablas, de una vez. Media copia da la
habilidad que existe hasta el nivel 12 y desaparece en el 13.


## Editar o crear

La pantalla tiene un **modo**, escrito en letras grandes arriba del panel de la
derecha:

```
Editando la habilidad 1086 — Might
Nueva habilidad 90000, copiada de la 1086
```

**Hacer clic en una habilidad de la lista edita esa habilidad.** Los campos se
llenan con sus datos, el id queda fijo en el suyo, y el boton pasa a
**Reescribir la habilidad**. El id se fija a proposito: cambiar el numero ahi
seria, en realidad, crear otra.

**Crear pasa por la ventana Nueva habilidad…** Pregunta el id (con Sugerir),
nombre, descripcion, icono y el corte de nivel; rechaza un id que ya exista sin
la marca de sustituir; avisa si el id cae en el rango del juego. Lo que sale de
ella llena el panel, y los campos siguen editables: es un comienzo guiado, no
una cerca.

Despues de generar, la pantalla pasa a **editar lo que acaba de salir**: es lo
que se hace a continuacion, ver como quedo y ajustarlo.


## 1. Elige la habilidad base

La lista muestra **una fila por habilidad**, no por nivel — serian 42 mil filas
con la misma habilidad repetida cuarenta veces. La columna "niveles" dice
cuantos se llevara la copia.

Busca por nombre, por id o por nombre de icono. Elige una base parecida a lo que
quieres: el modo (activa, pasiva, alternable), el tiempo de uso y la animacion
vienen de ella.


## 2. Identificacion

### id

**Sugerir** busca el primero libre a partir de **90000**. Ese rango queda lejos
de dos cosas: de los ids del juego y de las **rutas de encantamiento**, que
ocupan los 50000 en adelante.

### nombre y descripcion

El nombre va igual en todos los niveles, que es como lo hace el juego.

La descripcion del juego cambia de nivel a nivel — es el "Power 25" que pasa a
"Power 27". Dejando la descripcion en blanco, cada nivel hereda la del mismo
nivel de la habilidad base, que suele ser lo mas cercano a lo correcto.
Escribiendo una, va igual en todos.

### icono

`paquete.objeto`, como en el item — los iconos de habilidad suelen ser
`icon.skill0003`.

En la ventana **Nueva habilidad…** el icono se elige **viendo**: hay una
rejilla de miniaturas a la derecha, que abre en los `icon.skill*` porque parte
del icono de la habilidad base. Muestra 240 por vez; la etiqueta dice cuantos
quedaron fuera y la busqueda reduce: nada queda escondido.

Justo debajo, **Usar una imagen mia** acepta un dibujo tuyo; mira la ultima
seccion.

### copiar hasta el nivel

En blanco, la copia se lleva todos los niveles.

Rellenalo cuando la base tenga muchos niveles y solo quieras los primeros. Las
habilidades con miles de niveles son las rutas de encantamiento, y clonar 6.410
filas por error dobla la tabla sin servir de nada — el programa avisa por encima
de 100.


## 3. XML del servidor

**Ya viene puesto** lo que esta en el `skillgrp`: modo, mana por uso, alcance y
tiempo de uso. El `hit_time` del cliente va en segundos y el servidor cuenta en
milisegundos; la conversion se hace sola.

El resto lo eliges tu, siempre de una lista.

### tipo de efecto

Lo que hace la habilidad. Es el campo mas importante — decide que codigo del
servidor se ejecuta.

| tipo | que es |
| --- | --- |
| `PDAM` | dano fisico |
| `MDAM` | dano magico |
| `BLOW` | golpe por la espalda |
| `DRAIN` | dano que devuelve vida |
| `HEAL` / `HOT` | cura, al momento o con el tiempo |
| `MANAHEAL` / `MANARECHARGE` | recupera mana |
| `BUFF` | mejora un estado un tiempo |
| `DEBUFF` | empeora un estado del objetivo |
| `PASSIVE` | vale siempre, sin usarse |
| `CONT` | efecto continuo mientras esta activa |
| `STUN`, `ROOT`, `SLEEP`, `FEAR`, `PARALYZE` | control |
| `POISON`, `BLEED` | dano con el tiempo |
| `RESURRECT` | resucita |
| `AGGDAMAGE` / `AGGDEBUFF` | provocacion |

### modo

`ACTIVE` se usa pulsando; `PASSIVE` vale siempre; `TOGGLE` se enciende y apaga y
consume mana mientras esta encendida. Viene del cliente.

### objetivo

`SELF` en uno mismo, `ONE` en un objetivo, `PARTY` en el grupo, `CLAN` en el
clan, `AURA` en todo alrededor, `AREA` en una zona desde el objetivo. Hay 28
opciones en la lista.

### poder

Para dano es el dano base; para cura es cuanto cura; para efecto de control es
la probabilidad. Lo que significa depende del tipo de efecto.

### nivel magico

El nivel del personaje a partir del cual la habilidad tiene eficacia completa.
Usar una habilidad de nivel magico muy por encima del tuyo reduce el efecto.

### mana por uso, mana al empezar, vida por uso

Coste. `mana al empezar` es lo que sale al iniciar el gesto — el resto sale al
completarlo.

### alcance, alcance del efecto, radio

`alcance` es desde donde se puede usar. `alcance del efecto` es hasta donde
llega. `radio` es el tamano de la zona en las habilidades de area.

### tiempo de uso, tiempo final, recarga

En milisegundos. `tiempo de uso` es la animacion; `tiempo final` es el bloqueo
justo despues; `recarga` es cuanto falta para volver a usarla.

### elemento

`FIRE`, `WATER`, `WIND`, `EARTH`, `HOLY`, `DARK`. Hace que el dano cuente contra
la resistencia correspondiente del objetivo.

### armas permitidas

Restringe la habilidad a un tipo de arma en la mano — `SWORD`, `BOW`, `DUAL`. En
blanco, cualquier arma sirve.

### es magia

`true` hace que la habilidad cuente como magia: se interrumpe al recibir dano y
usa spiritshot en vez de soulshot.

### provocacion

Cuanto odio genera la habilidad en los monstruos.


## Leer del servidor

**El poder, la recarga y el tipo de efecto no existen en el cliente.** El
`skillgrp` guarda icono, mana, alcance y tiempo de uso, y nada mas.

El boton **Leer del servidor**, en la pestana XML, trae el resto. Lee la
habilidad **marcada en la lista** -- y no la del campo **id nuevo**. El campo
dice adonde va la habilidad; la lista dice de donde viene. Para releer una que
creaste, marcala en la lista: esta ahi despues de generar.

Si no esta ahi, avisa que la habilidad todavia no existe del lado del
servidor.

Aparece un aviso cuando la habilidad usa valor por nivel: el `<set>` trae el
apodo (`#power`) y la tabla queda fuera de la pantalla. El apodo se muestra tal
cual.

## 4. Estados que da la habilidad

El bloque `<for>`, igual que en los items: **operacion**, **estado**, **valor**.

Es lo que hace que un `BUFF` valga algo. Un soplo que sube el ataque es
`skillType BUFF` mas `mul` en `pAtk` con valor `1.15` — un 15% mas.

Para `PASSIVE` suele ser `add` o `mul` directo en el estado.

**Doble clic en una fila de la tabla** devuelve operacion, estado y valor a los
campos de arriba, y el boton pasa a **Guardar**. Cambiar `1.30` por `1.25` ya no
exige quitar la fila y escribir los tres campos de nuevo.

**Cuidado con la escala**: `mul` multiplica (`1.15` = un 15% mas), `add` suma el
numero crudo. Un `add` de `1.15` en `pAtk` suma un punto de ataque, no un 15%.

La lista de estados es la misma de los items, y por el mismo motivo es cerrada:
un nombre que el servidor no conoce tumba la carga de toda la tabla de
habilidades.


## Valor por nivel

El juego escribe la progresion con `<table>`: el "Power 25" que pasa a "Power
27" no es un numero, es una lista con un valor por nivel.

**Basta escribir los valores separados por espacio**, en cualquier campo del XML
o en la columna `valor` de un estado:

```
431 458 486 516 547
```

El programa monta la tabla y hace que el `<set>` apunte a ella:

```xml
<table name="#power"> 431 458 486 516 547 </table>
<set name="power" val="#power"/>
```

La coma y el punto y coma valen como espacio. Un campo con texto, como
`SWORD,BLUNT`, sigue siendo un solo valor: eso es una lista de armas, no una
progresion.

**La cuenta tiene que coincidir con el numero de niveles.** Una tabla con menos
valores de los que tiene la habilidad no da error al guardar: es el servidor el
que tumba la habilidad, o entrega el nivel equivocado, mucho despues. El
programa lo comprueba y avisa antes de generar.

**Leer del servidor abre las tablas.** El `#power` vuelve como sus numeros, que
es lo que el campo acepta de vuelta: se puede leer una habilidad hecha, tocar el
nivel 5 y reescribirla.


## 5. Lo que esta pantalla no hace

**Efectos.** Un `<effect>` dentro del `<for>` — veneno que quita vida cada
segundo, transformacion, invocacion — tambien queda fuera. El XML generado es la
base correcta; el efecto se anade encima.

**Condiciones.** El `<cond>` que exige arma, clase o estado no se genera.


## 6. Generar, instalar, y la siguiente

**Generar** escribe las tablas y el `<id>-skill.xml` en una carpeta aparte.
Todavia no cambia nada en el cliente.

**Instalar en el cliente** pone las tablas en su sitio, guardando las originales
en `system/backup_skills` la primera vez. **Restaurar originales** lo deshace.

El XML va a mano a la carpeta de habilidades del servidor — normalmente
`data/xml/skills/` — y se reinicia el gameserver.

Despues de generar, la pantalla se prepara para la siguiente: sugiere el id
siguiente y limpia nombre, descripcion, corte de nivel y estados.

**Cierra el cliente antes de instalar.**


## 7. Icono propio

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
