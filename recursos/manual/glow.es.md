# Glow: el brillo del arma

El **glow** es el efecto de partícula pegado a un arma — la estela de luz que
acompaña la hoja, el halo del arco, el aura de las armas de boss. Es del
**cliente**: vive en el `weapongrp.dat`, no en el servidor. Quien equipa el
arma ve el brillo porque su cliente tiene la tabla alterada; un jugador con el
cliente original no ve nada.

Eso tiene una consecuencia práctica: **el glow tiene que ir en el patch del
cliente**, junto con las texturas y las mallas. Tocar solo el servidor no sirve.


## Dónde están los números

Cada arma tiene lugar para **dos** efectos, cada uno con cinco ajustes:

```
efecto            LineageEffect.c_u006   qué partícula
a lo largo de la hoja                    de la empuñadura a la punta
altura                                   sube y baja
lado                                     hacia los costados
tamaño                                   cuánto crece el efecto
intensidad                               cuánto brilla
```

En este cliente, **282 de 1.346 armas** ya tienen glow, en 48 combinaciones
distintas de esos cinco números — es decir, están ajustados arma por arma, y no
copiados de un patrón.

El rango que el juego usa en sus propias armas:

| ajuste                | del juego      |
|-----------------------|----------------|
| a lo largo de la hoja | -20 a 4        |
| tamaño                | 0,80 a 1,55    |
| intensidad            | 0,20 a 1,00    |

**No son límites.** Son referencia: si escribe 40 en el largo, el programa lo
acepta, y el efecto termina fuera del arma. La regla avisa cuando eso pasa.


## La regla

A la derecha está la **hoja acostada**, con la empuñadura de un lado y la punta
del otro. Los dos números de las puntas no son inventados: salen de la **malla
de esta arma**, exportada del paquete del cliente y medida vértice a vértice.

Un arma se acuesta sobre su eje más largo. La Dragon Slayer, por ejemplo, va de
**-17,8 a 40,8** en el eje X: la empuñadura queda detrás del cero, toda la hoja
adelante. Es ese el eje sobre el que se mueve el ajuste *a lo largo de la
hoja* — por eso el círculo naranja se desplaza mientras escribe.

El tamaño del círculo sigue al campo **tamaño**.

**La regla no dibuja el efecto.** Las partículas de Unreal Engine 2 solo las
dibuja el motor del juego — ni el umodel las abre. La regla dice **dónde** va a
quedar el brillo; cómo *se ve*, solo en el juego.


## Ver el arma en 3D

El botón **Ver el arma en 3D** abre la malla en el visor del umodel: se puede
girar, ver la forma y entender dónde está la punta. Sirve para elegir el valor
de *a lo largo de la hoja* con alguna noción, sobre todo en armas largas.

El glow **no** aparece ahí, por el motivo de arriba.


## Elegir el efecto

La lista de la derecha empieza con la casilla **solo los que el juego usa en
arma** marcada -- y así debería quedarse la mayoría de las veces.

El cliente tiene **1.812 efectos instalados**, y la abrumadora mayoría no fue
hecha para arma: son auras de NPC, efectos de suelo, magias. Puestos en una
espada quedan del tamaño equivocado, en el lugar equivocado, o simplemente no
aparecen. Varios son de crónicas más nuevas y no funcionan en Interlude -- es el
aviso que da el tutorial de la comunidad, y tiene razón.

> **No todo efecto de la lista completa es compatible.** La lista marcada
> muestra los que **este cliente ya dibuja en armas** -- no es opinión, es un
> conteo de su propio `weapongrp.dat`.

### Cómo se arma la sugerencia

El programa cuenta, en su cliente, qué efecto usa el juego en cada tipo de
arma. Si el cliente puso `c_u002` en nueve dagas y en nada más, ese es el
efecto de la daga -- y funciona, porque el juego lo dibuja todos los días.

En este cliente el conteo da:

| efecto | dónde lo usa el juego |
| --- | --- |
| `c_u001` | puño (22) |
| `c_u002` | daga (9) |
| `c_u003` / `c_u008` | arco (9 y 20) |
| `c_u004` | espada, daga, mandoble, dual (54 en total) |
| `c_u005` / `c_u007` | maza, martillo, lanza |
| `c_u006` | espada (18) |
| `c_u000` | mandoble (5) |
| `e_u092_a` … `e_u092_k` | el **hero glow**, uno por tipo de arma |
| `SHEV_weapon_shadow_*` | shadow weapons de un pack custom |

La correspondencia del hero glow coincide con la que publica el tutorial --
a = espada, b = mandoble, g = daga, h = puño, i = arco, j = espada dual. La
diferencia es que aquí fue **medida en su cliente**, no copiada.

Al elegir un arma, los efectos de ese tipo suben al tope, con la columna **usado
en** diciendo en cuántas armas iguales el juego usa cada uno.

### Copiar de un arma que ya funciona

Los cinco números no se aciertan adivinando. El efecto sale de lugar -- queda en
medio del cuerpo, detrás del arma, demasiado grande -- y no hay forma de saber
cuál de los cinco está mal.

Si algún arma del juego ya tiene el glow en su lugar, **sus números son la
respuesta**. `Copiar de otra arma…` abre la lista de armas del cliente, con
icono y filtro, y trae el efecto y los cinco ajustes de aquella a los campos.

Es el camino más corto cuando lo que quiere es "igual a aquella, en otro color".

El registro avisa cuando el arma de origen es de **otro tipo** -- copiar de un
mandoble a una dual, por ejemplo. Los números siguen siendo válidos, pero una
malla no tiene el tamaño de la otra, y el encuadre puede no valer.

### Los cinco números vienen junto

Al poner un efecto sugerido, los cinco ajustes se rellenan con **los que el
juego usa con ese efecto** -- no con 0 y 1. El glow nace encuadrado en la hoja
en vez de encogido en la empuñadura.

Al desmarcar la casilla, la lista vuelve a mostrar los 1.812. Vale para quien
sabe lo que busca.


## Crear un arma nueva, en vez de tocar una que existe

Poner un glow en un arma del juego cambia **esa arma para todo el mundo**. Quien
equipe una Dragon Slayer, cualquiera, va a ver el brillo nuevo. A veces es lo
que se quiere; la mayoría de las veces, no.

**Crear un arma nueva…** copia el arma elegida a un id propio, ya con el glow
que está en la pantalla. La original no se toca.

La ventana pregunta el id, el nombre, la descripción y el icono. La copia lleva
la línea entera del `weapongrp.dat`: malla, textura, sonido, tipo, peso y los
números del cliente vienen de la base.

Use un id **por encima de 30000**, lejos del rango del juego. Escribir encima de
un ítem que existe es el error más caro aquí.

Sale al lado el `<id>-item.xml` del servidor -- pero **solo con lo que se puede
leer del cliente**: tipo, parte del cuerpo, peso, material, grado, tiros. Daño,
defensa y precio no existen en el `weapongrp.dat`; son del servidor.

Para completarlo, vaya a la pestaña **Ítems**, marque el arma nueva en la lista
y use la ventana **Nuevo ítem**, que tiene las páginas de Números, Estados y
Skills. Ese es el lugar, y tener dos sitios que hacen lo mismo daría dos sitios
que arreglar cuando cambie.

## La página "Armas creadas"

Lista las armas del cliente con id **por encima de 30000** -- el rango que el
juego no usa. Sale del propio `weapongrp.dat`, y no de un registro guardado
aparte: un registro envejecería cuando cambiara de cliente, restaurara un
backup o copiara la carpeta a otra máquina, y la pantalla pasaría a mostrar
armas que no existen y a esconder las que existen.

Eso también muestra armas custom hechas por otros programas -- y está bien:
quien abre esta página quiere ver las armas custom del cliente, no solo las que
pasaron por aquí.

| columna | qué dice |
| --- | --- |
| tipo | espada, arco, daga… leído del cliente |
| glow | el efecto que tiene hoy |
| XML | si ya existe uno, en la carpeta de salida o en la del servidor |

**Editar el glow de esta** lleva el arma a la otra página, ya elegida y con el
glow que tiene.

**Ver el XML** arma el XML en el momento, a partir de la línea del cliente, y lo
muestra. Lleva solo lo que se puede leer de ahí -- daño, defensa y precio son
del servidor.

**Escribir el XML en el servidor** escribe en su carpeta de ítems. Dónde está
esa carpeta sale del propio servidor: el programa lee sus archivos para
descubrirlo. Si no lo logra, avisa y no escribe -- mejor no escribir que
escribir en el lugar equivocado. Después, en el juego: `//reload item`.

**La subcarpeta importa.** `custom` es la convención de los datapacks L2J, pero
no la de todos: hay packs que reparten la carpeta de ítems por tipo --
`weapons`, `armors`, `accessories`, `etcitems` -- y que **no leen armas de
`custom`**. Escribir ahí entrega el archivo a una carpeta que el servidor
ignora, y el síntoma es "creé el arma y no existe".

La casilla al lado del campo Servidor lista las subcarpetas que **existen** en
su servidor y ya marca la que casa con el tipo del ítem -- `weapons` para arma,
cuando está. La elección se recuerda.

**Borrar** saca el arma de las tablas en memoria, y borra el XML del servidor
junto. El cliente solo cambia en **Instalar en el cliente**, así que hasta ahí
se puede deshacer cerrando el programa sin generar.

Marcando **escribir el XML en el servidor** arriba en la pantalla, el XML del
arma nueva se entrega directo en la creación.

## Generar e instalar

Como en las otras pestañas, son dos pasos a propósito:

1. **Generar** escribe el `weapongrp.dat` alterado en una carpeta aparte. No se
   copia nada al cliente.
2. **Instalar en el cliente** copia. La primera vez, el original va a
   `backup_itens/`, y **Restaurar originales** deshace todo.

Antes de escribir cualquier cosa, la tabla se rearma a partir de la definición
y se compara con el binario original **byte a byte**. Si la vuelta no reproduce
la ida, la definición no describe este cliente y no se escribe nada — eso es lo
que impide que un `weapongrp.dat` roto llegue al cliente.

El cliente lee el `weapongrp.dat` **solo al arrancar**. Después de instalar,
cierre y abra el juego.


## La página "Encantamiento"

> **Esto vale para TODAS las armas del servidor.** No es un ajuste de ítem.

El glow de las otras páginas es **del arma**: una Dragon Slayer con `c_u000`
brilla siempre, ya en +0. El brillo de **encantamiento** es otro -- es el halo
que cualquier arma gana al ser refinada, el azul del +4, el dorado del +7 -- y
vive en el `env.int`, un archivo solo para todo el cliente.

### Los dos números

| campo | qué hace | en el juego original |
| --- | --- | --- |
| `EnchantMeshShow` | del +N en adelante el arma toma color | 4 |
| `EnchantEffectShow` | del +N en adelante aparece la llama | 7 |

Son independientes: el arma puede tomar color sin llama, y al revés. **Por
debajo del primer número, cambiar el color de ese nivel no cambia nada en
pantalla** -- es el motivo más común de "lo edité y no pasó nada".

Bajando el segundo a 4, toda arma +4 pasa a brillar. Los dos son
independientes: la malla puede cambiar sin brillo, y al revés.

### El color de cada nivel

El cliente de fábrica trae **21 niveles**, `Enchant0` a `Enchant20`, con dos
colores cada uno -- el juego hace variar el brillo entre ellos -- más opacidad
e intensidad.

**La franja de arriba** los muestra todos de una vez, cada uno partido en sus
dos colores. En este cliente se ve la progresión entera de un vistazo: gris
hasta el +3, azul del +4 al +15, rojo del +16 al +20. Haga clic en una columna
para editar ese nivel.

### Por encima del +20

Justo debajo de la serie hay una línea **`Enchant=`**, sin número. Es lo que el
cliente usa para **cualquier encantamiento por encima del último nivel
escrito**. En este cliente es igual al +20 -- y por eso un +40 hoy tiene el
mismo color que el +20.

Un servidor que encanta más alto tiene dos caminos:

1. **Tocar solo el `Enchant=`.** Marque la casilla `este es el Enchant=`, elija
   el color y guarde. Una línea resuelve todo por encima del +20.
2. **Dar color propio a cada nivel**, hasta el **+60**. Elija el nivel en el
   campo y edite normalmente. El programa escribe `Enchant21` en adelante en el
   archivo, en orden, justo antes del `Enchant=`.

En la franja, los niveles **punteados** todavía no tienen línea propia: el
color que aparece en ellos está prestado del `Enchant=`. Al entrar en uno, los
campos ya vienen con ese color -- es lo que ese nivel tiene hoy, y no un blanco.

> **Una salvedad.** Que el cliente *lea* `Enchant21` en adelante no se puede
> probar fuera del juego -- solo probándolo. Lo que sí se puede afirmar es que
> escribirlos no rompe nada: una clave desconocida en un `.int` de Unreal se
> ignora, y si se ignora sigue valiendo el `Enchant=`, exactamente como hoy.

**Copiar a los de arriba** repite el nivel actual en todos los de encima **y en
la línea `Enchant=`** -- el camino corto para "del +20 en adelante todo
dorado".

### Elegir el color

> **Qué hace el juego con los dos colores, este manual no lo afirma** -- no se
> puede probar fuera del juego, y afirmar sin probar ya salió caro aquí.
>
> Lo que se sabe, y cómo:
>
> - En los 21 niveles de fábrica el color 2 es **siempre el mismo color del 1,
>   un poco más oscuro** -- `(40,87,126)` y `(30,70,110)` en el +7, `(220,0,0)`
>   y `(195,0,0)` en el +20. Vale para los 21, sin excepción.
> - El `env.int` apunta al material
>   `LineageEffectsTextures.Etc.Enchant_Aura001_Shader01`, cuya cadena pasa por
>   un `FadeColor` -- la clase de Unreal que va y viene entre dos colores.
>   **Pero los colores grabados en ese FadeColor son otros**:
>   `(7,20,69)`/`(5,15,48)`, `(24,41,46)`/`(34,45,47)`,
>   `(90,122,128)`/`(80,109,115)`. Ninguno es el color de nivel alguno. El
>   material tiene su propia pulsación, con sus propios colores.
> - `EnchantMeshShow`, `EnchantEffectShow` y las líneas `Enchant*` **no están en
>   la tabla de nombres de ningún `.u`**: las lee el código nativo del
>   ejecutable, no UnrealScript. No hay nada que leer.
>
> Para descubrirlo: ponga dos colores bien distintos en un nivel que el cliente
> seguro lee y mire en el juego. Es la única respuesta que vale.

**Si cambió el color y no pasó nada**, el motivo más probable no es el color --
es el archivo. Vea la sección siguiente.

### Líneas en el lugar equivocado

Una versión anterior de este programa escribía los niveles nuevos **antes del
primer encabezado del archivo**, fuera de toda sección, donde el juego nunca los
lee. El síntoma era exactamente "lo edité y no cambió nada".

Al leer un `env.int` así, la pantalla avisa y dice cuántas líneas están fuera de
lugar. **Generar e instalar de nuevo limpia el archivo** y pone todo dentro de
`[EnchantEffect]`. Para empezar de cero: **Restaurar original** y rehacerlo.

Cada color tiene una muestra y tres barras -- rojo, verde y azul. La barra
escribe el número y el número mueve la barra: son el mismo valor, y no dos
copias de él.

Abajo, **la línea del archivo se escribe sola**, a cada movimiento:

```
Enchant7=(R1=40,G1=87,B1=126,R2=30,G2=70,B2=110,Opacity=0.4,Num=0.3)
```

Es exactamente lo que se va a grabar. **Copiar** la pone en el portapapeles,
para quien quiera llevarla a otro lado.

Nada de esto toca el archivo todavía: **Guardar el nivel** lo guarda en
memoria, **Volver al original** deshace solo ese nivel con lo que el archivo
tenía cuando se leyó, y **Copiar a los de arriba** repite el nivel actual en
todos los de encima -- el camino corto para "del +7 en adelante todo rojo" sin
tocar catorce niveles a mano.

### Opacidad e intensidad

Van de 0,1 a 1 -- y **el juego nunca pasa de 1** en los dos. En este cliente:

| nivel | opacidad | intensidad |
| --- | --- | --- |
| +0 a +6 | 0,1 | 0,1 |
| +7 | 0,4 | 0,3 |
| +10 | 0,7 | 0,8 |
| +13 en adelante | 1 | 1 |

Hay tutoriales por ahí que sugieren valores muy por encima de eso, con el aviso
de que "puede lagear el servidor". La parte del valor alto es correcta; la del
servidor, no. Una partícula la dibuja el **cliente**, cada cuadro, en toda arma
encantada que esté en pantalla -- el costo cae en la máquina de quien juega,
más aún en una ciudad llena.

### Generar, instalar, restaurar

Los mismos tres pasos de las otras páginas, con una comprobación más: antes de
dar el archivo por listo, se **cifra y se descifra de vuelta**, y el resultado
se compara con lo que se quería escribir. Si no cuadra, no se instala nada.

Eso importa más aquí que en las tablas: un `env.int` roto deja el cliente **sin
iluminación ninguna**, y el síntoma no se parece a la causa.

El original va a `backup_env/` en la primera instalación, y **Restaurar
original** lo trae de vuelta byte a byte.

El cliente lee el `env.int` **solo al arrancar**.

## Lo que esta pantalla no hace

**No crea efectos nuevos.** La lista muestra lo que el cliente ya tiene. Un
efecto inédito es un paquete de partícula nuevo, hecho fuera de aquí.


## Costo

Una partícula se dibuja **cada cuadro**, en **toda arma igual a esta** que esté
en pantalla. *Tamaño* e *intensidad* altos en un arma común, en un servidor
lleno, pesan más que en un arma de boss que carga una sola persona. Conviene
probarlo con gente reunida antes de soltarlo.
