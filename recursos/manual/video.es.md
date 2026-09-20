# Lobby Vídeo: la pantalla de entrada del cliente

Aquí cambias la pantalla que aparece antes de elegir el personaje. Puedes usar
uno de los lobbys listos o poner un vídeo tuyo.


## Dos caminos

**Instalar lobby** pone en el cliente el lobby elegido, tal como es — mapa,
escenario, texturas y su música. Los de C1 a C6 son los originales de cada
crónica.

**Generar vídeo e instalar** monta tu película en el lobby del L2PackTool. Es
el único con pantalla de vídeo; si eliges otro de la lista y pulsas aquí, el
programa usa el del L2PackTool y lo dice en el registro.

Los lobbys viajan comprimidos dentro del programa. Solo se abre el elegido, y
solo al instalar.


## El vídeo

Formatos: MP4, AVI, MKV, MOV, WEBM, GIF y WEBP animado. El vídeo entra entero
y centrado.

El tamaño de la pantalla se calcula para llenar la ventana del juego, de una
4:3 a una ultraancha. Llenarla cuesta los bordes de la película: en una
pantalla de portátil ves cerca del 70% de su altura. Detrás queda un panel
negro, para que no asome escenario en lo que sobre.


## El tramo

Las dos reglas marcan inicio y fin; **Vídeo entero** las devuelve a los
extremos.

La cantidad de cuadros sale de la cadencia del vídeo, y es lo que mantiene la
velocidad original. Cada cuadro ocupa unos 2 MB en el paquete; pasado el
límite, la cadencia baja sola — la película queda más entrecortada, pero el
paquete carga.

La vista previa muestrea el vídeo entero y la regla elige la parte, así que el
ritmo que ves es el que llega al juego.

**Repetir sin parar** hace que la película vuelva al inicio. Sin eso suena una
vez y se congela en el último cuadro.


## El logo

Una imagen tuya sobre el vídeo. Arrástrala con el ratón en la vista previa;
donde quede es donde va.


## Instalar

El cliente tiene que estar cerrado — el juego mantiene abiertos los archivos
del lobby mientras corre. Lo que se sobrescriba va antes a `backup_lobby`.

Generar el vídeo tarda: cada cuadro se convierte y se comprime, y el paquete
pasa de cien megabytes. La ventana puede parecer detenida; sigue la barra.

Después de instalar, el programa comprueba si el cliente tiene todo lo que el
mapa del lobby busca, y dice qué falta.


## Por qué no es una textura animada

La primera versión de esta pestaña animaba una textura con la cadena
`AnimNext`, que es como el cliente anima fuego y agua. Pasaba todo lo que se
puede comprobar desde fuera, y en pantalla no pasaba nada.

La película es un `MaterialSequence`: el material hecho para reproducir una
lista en el tiempo, sobre una malla plana frente a la cámara. Es lo que esta
pestaña genera.
