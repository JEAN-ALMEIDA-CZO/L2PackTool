# Texture Upscaler: ampliar las texturas de un paquete

Esta pestaña toma un paquete de texturas del cliente, amplía cada imagen con una
red neuronal y rearma el paquete. El camino completo es este:

```
.utx cifrado
  -> descifra
  -> extrae las texturas
  -> convierte a PNG
  -> amplía (upscayl)
  -> comprime en DXT5 con mipmaps
  -> rearma el paquete
  -> cifra de vuelta
```

Cada paso es una herramienta aparte, y todas están en `ferramentas/`. Si falta
alguna, la pestaña dice cuál al momento de procesar.


## Abriendo un paquete

**Abrir un .utx…** elige un archivo. **Lote: elegir carpeta…** procesa todos los
`.utx` de una carpeta de una vez.

Abierto el paquete, la lista muestra cada textura con su tamaño. Al hacer clic
en una, la vista previa aparece a la derecha, con los botones para cambiar la
imagen, mejorar solo esa o exportarla.


## La escala es la decisión que importa

> **El cliente de Lineage 2 es de 32 bits.** La escala 2x **cuadruplica** la
> memoria de textura; 4x la multiplica por dieciséis.
>
> No es cuestión de disco: es la memoria que el proceso del juego puede
> direccionar. Pasado ese punto, el cliente se cierra solo — y se cierra al
> entrar en un área concreta, no al cargar el paquete, lo que hace difícil
> ligar la causa con el efecto.

En la práctica: marca **lo que el jugador ve de cerca** — arma, armadura, rostro
— y deja el escenario y lo lejano como está. Un paquete entero en 4x es la
receta más común de cliente que se cierra.


## El modelo

`upscayl-standard-4x` es el predeterminado y el mejor punto de partida. Los
otros sirven a materiales distintos: unos preservan superficies lisas, otros
suavizan piedra y tela. La descripción de cada uno aparece al elegirlo.

La escala del modelo y la escala pedida son cosas distintas — un modelo `4x`
usado en escala `2x` amplía y reduce de vuelta, lo que suele dar mejor resultado
que ampliar directo en 2x.


## Procesar

**Marcar todas** / **Desmarcar todas** y después **Procesar**. El avance muestra
en qué textura va y cuánto falta.

Solo se amplían las texturas marcadas. Las otras entran en el paquete rearmado
tal como estaban — nada se pierde por no haber sido marcado.

El resultado sale en una carpeta de trabajo. El paquete del cliente no se toca
hasta que instales.


## Lo que sale distinto de lo que entró

Solo cambian las texturas que marcaste. Las demás siguen byte a byte como
estaban: el paquete se edita en el lugar, no se rearma desde cero.

El archivo crece un poco más allá del tamaño de las texturas nuevas — lo
viejo sigue dentro, sin uso, y las tablas se reescriben al final. Es el
precio de no mover nada de lo que ya funcionaba.

Una textura con transparencia mantiene su canal alfa. Una textura que ya está en
DXT se descomprime, se amplía y se comprime de nuevo — y recomprimir siempre
cuesta un poco de calidad, lo que es un argumento más para marcar solo lo que
importa.
