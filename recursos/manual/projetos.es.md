# Proyectos: las dos carpetas en un solo lugar

Un proyecto guarda tres cosas: un nombre, la **carpeta del cliente** y la
**carpeta del servidor**. Elegir el proyecto en el encabezado apunta las dos en
todas las pestañas.


## Por qué existe esto

Cada pestaña pedía las dos carpetas otra vez. Eran dieciocho campos para la
misma ruta, y bastaba con que uno quedara atrás — después de trabajar en una
copia del cliente, por ejemplo — para que una pantalla grabara en el lugar
equivocado sin avisar.

Quien trabaja en dos servidores a la vez cambiaba dieciocho campos por cada
cambio. Ahora cambia uno.


## Creando

**Proyectos…**, en el encabezado, abre la ventana. A la izquierda los proyectos
que existen; a la derecha el nombre y las dos carpetas.

- **carpeta del cliente** — la raíz del juego, la que tiene `system` dentro.
  Puedes apuntar directo a `system`: el programa encuentra la raíz desde ahí.
- **carpeta del servidor** — la carpeta de datos del emulador, la que tiene
  `xml` o `data/xml` dentro.

**Guardar** graba y ya elige el proyecto. **Nuevo** limpia los campos para crear
otro. **Borrar** quita el proyecto de la lista — las carpetas no se tocan, solo
el atajo hacia ellas.

El nombre acepta letras, números y espacios. `[` y `]` no sirven, porque el
archivo de proyectos es un `.ini` y romperían la sección.


## Cambiando

El selector aparece en dos lugares: en el encabezado y arriba de cada pestaña.
Son el mismo control — mover uno cambia el otro al instante, y las pestañas
reciben las rutas nuevas sin necesidad de recargar nada.

A su lado están las dos carpetas escritas por completo. Es la respuesta a "en
qué servidor estoy trabajando", y tiene que estar a la vista de quien va a
grabar algo.


## Cuando falta una carpeta

El `Cargar` de cada pestaña comprueba antes de trabajar, y dice qué falta:

```
Ningún proyecto elegido. Crea uno en Proyectos… con la carpeta
del cliente y la del servidor.

La carpeta del cliente del proyecto Interlude ya no existe: D:\cliente-antiguo
```

La carpeta se comprueba **en el disco**, y no solo en el archivo de proyectos.
El caso común es que el cliente haya sido movido o renombrado: sin esa
comprobación el error aparecería más adentro, hablando de otra cosa.


## Dónde queda guardado esto

En un `projetos.ini` al lado del programa. Es texto, y se puede copiar entre
máquinas.

Quien ya usaba el programa antes de los proyectos no pierde nada: en la primera
ejecución, las carpetas que estaban en la configuración antigua se convierten en
un proyecto llamado `Predeterminado`.


## Lo que el proyecto no hace

Apunta carpetas. No copia, no mueve y no instala nada. Cambiar de proyecto no
toca archivo alguno — solo cambia hacia dónde están mirando las pestañas.
