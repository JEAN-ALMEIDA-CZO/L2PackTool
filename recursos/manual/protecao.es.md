# Protección: cerrar el cliente con tu propia clave

Todo cliente de Lineage II guarda sus tablas cerradas, y la "contraseña" que
las abre es la misma en todos ellos — está en las herramientas públicas desde
hace veinte años. Por eso cualquiera abre el `itemname` de cualquier servidor
con dos clics.

Esta pantalla cambia esa contraseña por la **tuya**: una clave generada a
partir de una frase que solo vos conocés, escrita dentro de tu cliente.
Después de eso, nadie produce un archivo que tu cliente acepte sin tener la
frase.


## Qué protege, y qué no

**Protege la escritura.** Sin tu frase, nadie genera un `itemname-e.dat` que
tu cliente vaya a cargar. Quien quiera cambiar una tabla de tu servidor
necesita la frase — o rehacer el cliente entero.

**No protege la lectura**, y ningún programa lo haría. Para jugar, el cliente
necesita abrir los archivos: lleva dentro de sí lo necesario para abrirlos.
Quien tenga tu cliente puede llegar ahí — este mismo programa llega en
milisegundos.

Lo que cambia es el costo. Tu servidor pasa de *"cualquiera lo abre con un
clic en una herramienta pública"* a *"quien sepa buscar"*. Es un escalón real,
y es el único escalón que existe de este lado.


## La frase

**Generar clave** sortea una frase fuerte — treinta caracteres en grupos de
cinco, sin los que se confunden al leer (nada de `O` y `0`, `I` y `l`). Una
frase inventada en el momento suele ser el nombre del servidor más el año, y
esa la adivina cualquiera.

La misma frase da siempre la misma clave, en cualquier máquina. **No se guarda
en ningún lado**: ni en el programa, ni en la configuración, ni en el cliente.
Si perdés la frase, perdés la capacidad de generar archivos nuevos para ese
cliente — lo ya instalado sigue funcionando, y la copia de respaldo también.

**Guardar…** escribe la frase en un archivo de texto, con la marca de la clave
y la fecha. Guardarla **dentro de la carpeta del cliente está rechazado**:
desde ahí el archivo viajaría junto con el cliente hacia los jugadores.

La *marca* son ocho dígitos del comienzo y del final de la clave. Sirve para
confirmar que estás usando la clave correcta sin mostrar la frase.


## Qué se puede proteger

| forma | qué toma |
| --- | --- |
| **grupos** | ítems y armas, habilidades, NPCs, mundo y textos |
| **Elegir…** | archivo por archivo, incluso tablas que no están en ningún grupo |
| **Todos los .dat** | todas las tablas de una vez |

Lo que el botón protege es la **unión** de los grupos con la lista. Un archivo
fuera de la carpeta del cliente queda afuera: la clave grabada en el
ejecutable es la de ese cliente, y un archivo de otro lado cerrado con ella no
lo leería ningún cliente.


## Convertir los paquetes

Las tablas (`.dat`) ya vienen en un formato que acepta clave. Los paquetes —
`.utx`, `.u`, `.int` — usan un formato **sin clave**: su contraseña es fija, o
sale del propio nombre del archivo. Ahí no hay clave que cambiar.

Marcando **convertir**, se los convierte al formato que acepta clave. El
cliente elige el descifrador por el encabezado del archivo, y no por la
extensión — en tu propio cliente el mismo `.ini` aparece en dos formatos, uno
al lado del otro.

Esa opción viene **apagada**, y el motivo es honesto: ningún cliente original
trae un `.utx` en ese formato, así que esta parte no se puede probar acá.
**Convertí un archivo, abrí el juego, verificá, y recién entonces convertí el
resto.**


## `.dll` y `.exe` quedan afuera

A un `.dll` lo carga Windows, no el cliente. El candado de este programa lo
lee el cliente, que descifra antes de usar; Windows no sabe nada de eso. Un
`Engine.dll` cifrado no carga, y el juego ni siquiera abre. Por eso esos
archivos son **rechazados**, con el motivo — no aceptados con una advertencia.

Para ellos está la **huella digital**: el programa anota el resumen de cada
`.dll` y `.exe` del cliente en un archivo, fuera del cliente, y después
compara. No impide el cambio, pero responde en segundos la pregunta que
importa cuando pasa algo raro en el servidor: *¿cambiaron algo?* La
verificación dice qué cambió, qué desapareció y qué apareció.


## El orden del trabajo, y por qué es ese

1. el original se copia a `backup_protecao`;
2. el archivo se abre con la clave actual;
3. se cierra con la clave nueva;
4. se **abre de nuevo y se compara** con el paso 2;
5. recién entonces reemplaza al original.

La clave del ejecutable se cambia **al final**, y solo si todos los archivos
pasan. Al revés, un error en el medio dejaría al cliente entero sin abrir
nada; así, el peor caso es un archivo sin cambiar.

Un archivo que no vuelve idéntico no se instala, y el motivo aparece en el
registro.

**Volver al original** deshace todo, incluso la clave del ejecutable.


## Dónde funciona

Parte de los clientes guarda la clave dentro del ejecutable, y ahí se puede
cambiar. En los más nuevos llega por *loader*, en memoria, y cambiarla
exigiría un loader propio — que este programa no escribe. La pantalla te dice
en cuál caso está tu cliente **antes** de que elijas archivos.


## Antes de tocar lo que está en línea

Hacelo primero en una copia del cliente. Protegé un archivo, abrí el juego,
verificá, y recién entonces tratá el cliente que usan los jugadores. *Volver
al original* existe justamente porque el primer intento suele enseñar algo.
