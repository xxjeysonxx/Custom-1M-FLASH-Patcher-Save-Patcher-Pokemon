# Custom 1M FLASH Patcher Save Patcher Pokemon — arregla la "partida eliminada" de Pokémon gen 3 en cartuchos bootleg de 64 KB

Parchea un `.sav` de Pokémon Esmeralda / Rubí / Zafiro para que un cartucho
bootleg con chip de **64 KB** pueda restaurarlo sin que el juego diga
**"partida eliminada"**.

> **¿Te suena esto?** El cartucho arranca y el juego entra bien, pero en cuanto
> guardas, o en cuanto le metes otro `.sav` con GodMode9i, aparece
> **"partida eliminada"**, **"archivo de guardado inválido"** o **"save file
> erased"**. Cartucho repro / bootleg de Pokémon Esmeralda, Rubí, Zafiro, Rojo
> Fuego o Verde Hoja. No está roto el cartucho ni el save: es el chip de 64 KB.

Vale para volcados del propio cartucho, saves de emulador y saves editados con
PKHeX. Solo Python, sin dependencias.

```
FixSave.py
```

![Python 3.6+](https://img.shields.io/badge/python-3.6%2B-blue)
![Sin dependencias](https://img.shields.io/badge/dependencias-ninguna-brightgreen)
![Licencia GPL-3.0](https://img.shields.io/badge/licencia-GPL--3.0-blue)

---

## ¿Es este tu cartucho?

El caso que originó la herramienta: **PCB de bootleg de Hong Kong, 2003**.

| Serigrafía / detalle | Qué es |
|---|---|
| `GAB-E05-01` + `©2003 Hihihoo` | Referencia de la placa. Va en la cara de componentes |
| `M36XXX_32A_16A_TT` | Huella de la ROM (NOR flash ST M36xxx, TSOP). Puede ir vacía |
| `32A-16A` | La otra huella de ROM, la que lleva el glóbulo de epoxy |
| `1M-SRAM` | Huella de SRAM de 1 Mbit. **Vacía**, sin estaño: no hay chip ni pila |
| Chip de guardado | Flash NOR de **64 KB (512 Kbit)**. Sin referencia legible: grabado al láser desgastado o bajo epoxy |

Cómo saber si el tuyo es el mismo:

- **No lleva pila de botón.** Si tuviera SRAM con pila, este problema no existiría.
- El juego es **Esmeralda, Rubí, Zafiro, Rojo Fuego o Verde Hoja** en un cartucho repro.
- Al inyectar un `.sav` con GodMode9i sale **"partida eliminada"**.
- El cartucho **arranca bien y la partida original funciona**, lo cual despista: no está roto, solo no le cabe un save entero.
- Si lo vuelcas, **las dos mitades de 64 KB son idénticas**. Esa es la prueba: 128 KB de lectura sobre un chip de 64 KB.

La trampa de esta placa: la ROM lleva dentro la cadena `FLASH1M_V103`, o sea que
**el juego cree que tiene 1 Mbit (128 KB) de flash**. El chip real es de 512 Kbit.
El juego escribe como si hubiera 128 KB y la mitad se sale del chip.

Si tu cartucho tiene pila y SRAM de verdad, esto no es lo tuyo: ese guarda con
batería y no tiene este problema.

## El problema en una frase

Un save de gen 3 ocupa **128 KB** porque guarda **dos ranuras** de 14 sectores
cada una, una en cada mitad del chip. Un cartucho bootleg lleva un chip de
**64 KB**: la segunda mitad no existe, las dos ranuras se solapan y el juego
acaba leyendo una partida incompleta o directamente basura.

GodMode9i escribe igualmente 128 KB (ignora el banco), el cartucho se queda con
lo que cabe, y al arrancar el juego no encuentra 14 sectores coherentes en
ninguna ranura → **"partida eliminada"**.

## Qué hace el fix

1. Lee el `.sav` y localiza los sectores válidos (firma `0x08012025` + checksum).
2. Elige la mejor ranura: la completa con el contador más alto; si ninguna está
   completa, **fusiona** bloque a bloque tomando la copia más reciente de cada uno.
3. Reconstruye **una sola ranura** con los 14 sectores, **contador par** y
   coloca cada sector en su posición física dentro de `0x0000–0xDFFF`.
4. Rellena la segunda mitad entera con `0xFF`.
5. Verifica la salida antes de darla por buena.

Contador par porque solo la mitad baja existe físicamente, y alto (≥ 1000) para
que el juego elija siempre esta ranura aunque quede algo de la partida anterior
en el chip.

## Uso

```
python FixSave.py
```

o doble clic. Requiere Python 3.6+ con tkinter (el instalador oficial de
python.org lo trae).

1. **Buscar...** → eliges tu `.sav`. El panel de diagnóstico te dice qué hay
   dentro: ranuras encontradas, contador de cada una, cuántos sectores válidos y
   el nombre del entrenador de cada ranura.
2. **APLICAR FIX** → escribe `<nombre>_cartucho.sav` al lado del original.
   **El original nunca se modifica.**

## Flujo correcto

```
1. Volcar el cartucho          (GodMode9i / pkmn-chest / lo que uses)
2. Editar en PKHeX             (opcional)
3. APLICAR FIX                 <-- este programa
4. Inyectar <nombre>_cartucho.sav en el cartucho
```

El paso 3 va **después** de PKHeX, no antes. PKHeX reescribe el fichero y
recalcula todo; si parcheas primero y editas después, vuelves al punto de
partida.

## Qué NO hace

- **No inventa partidas.** Si faltan los bloques 0–4 (entrenador, equipo, flags)
  el programa se niega: ahí no hay nada que rescatar.
- **No toca el fichero de entrada.** Escribe siempre un fichero nuevo.
- **No arregla un save corrupto de verdad.** Solo reordena y completa lo que ya
  está ahí con checksum válido.
- **No es un editor.** Para cambiar Pokémon, usa PKHeX.

## Por qué la segunda mitad va en `0xFF` y no es una copia

GodMode9i escribe 128 KB sobre un chip de 64 KB: el comando de banco se ignora,
así que el segundo pase reprograma **las mismas celdas físicas**. Programar
flash solo puede bajar bits a `0` (`nuevo = viejo AND dato`), y `0xFF AND x == x`,
o sea que escribir `0xFF` no cambia nada. Duplicar la mitad también funcionaba
en el cartucho, pero dejaba **dos ranuras con el mismo contador** — un estado que
un save real de 128 KB nunca tiene.

PKHeX se apoya en que los contadores sean distintos (`N` y `N-1`) para saber qué
bloque va dónde. Con contadores duplicados colocaba los bloques mal y **el nombre
del entrenador acababa en blanco**. De ahí el `0xFF`.

## Las cajas que faltan

En un cartucho de 64 KB es normal que falten un par de sectores de caja. El fix
los rellena con un sector a cero, que es exactamente como los ve la consola:
30 huecos vacíos, checksum `0x0000`.

En el cartucho de referencia esos sectores estaban **a cero** en el volcado
bueno, así que rellenarlos reconstruye la partida byte a byte. Verificado: los
14 sectores de datos de la salida son idénticos a los del volcado original.

Los bloques 0–4 nunca se rellenan. Si falta uno, el programa para.

## Comprobado con

| Entrada | Resultado |
|---|---|
| Volcado bueno, contador 4 | contador 1000, entrenador `Jeyson`, 14/14 |
| `All Shiny Fixed.sav`, ranuras 1658/1657 | usa 1658, entrenador `NICK`, 14/14 |
| Save pasado por PKHeX, contador 1659 | contador 1660, gana la edición |
| Volcado del cartucho, faltan bloques 11 y 12 | rellena `[11, 12]`, 14/14, sale idéntico al original |
| Igual pero sin el bloque 0 | **rechazado**, faltan bloques críticos |
| Nombre de entrenador en blanco en la salida | **bloqueado**, no deja inyectar |

## Si algo va mal

**"partida eliminada" al arrancar.**
No aplicaste el fix, o inyectaste el fichero equivocado. Comprueba que el
`.sav` que restauras es el `*_cartucho.sav` y que pesa 131072 bytes.

**PKHeX no abre el save.**
Tiene que ser de 128 KB. Si tu volcado es de 64 KB, ábrelo con el fix primero:
la salida siempre son 128 KB.

**GodMode9i se queda colgado en "Restore save".**
El cartucho no termina de borrar. El fix no lo provoca, pero es la razón por la
que conviene tener paciencia antes de apagar la consola: si cortas a medias, el
chip queda con basura.

**El nombre del entrenador sale en blanco en el diagnóstico.**
El save de origen no tiene el bloque 0 en condiciones. No lo inyectes: el
programa te lo bloquea justamente por eso.

## Detalles técnicos

Estructura de un sector (4 KB):

| Offset | Tamaño | Qué hay |
|---|---|---|
| `0x000` | `0xFF4` | datos del bloque |
| `0xFF4` | 2 | id de sector (u16 LE) |
| `0xFF6` | 2 | checksum del bloque (u16 LE) |
| `0xFF8` | 4 | firma `0x08012025` (u32 LE) |
| `0xFFC` | 4 | contador de guardado (u32 LE) |

Checksum: suma de los `0xFF4` bytes leídos como u32 little-endian, plegada con
`((s >> 16) + (s & 0xFFFF)) & 0xFFFF`.

Posición física del sector `id` con contador `counter`:

```
phys = 14 * (counter & 1) + ((id + counter) % 14)
```

- contador par → `phys` en `0..13` → `0x0000–0xDFFF` (mitad baja)
- contador impar → `phys` en `14..27` → `0xE000–0x1BFFF` (mitad alta, **no existe en 64 KB**)

El juego elige la ranura con 14 sectores válidos y contador más alto. El fix
fuerza que esa ranura sea siempre la de la mitad baja.

## Licencia

**GNU General Public License v3.0** (o cualquier versión posterior, a tu
elección). El texto completo está en [`LICENSE`](LICENSE).

```
FixSave — arregla la "partida eliminada" de Pokemon gen 3 en cartuchos bootleg de 64 KB
Copyright (C) 2026

Este programa es software libre: puedes redistribuirlo y/o modificarlo bajo
los terminos de la Licencia Publica General de GNU, version 3 o (a tu
eleccion) cualquier version posterior.

Se distribuye con la esperanza de que sea util, pero SIN NINGUNA GARANTIA,
ni siquiera la garantia implicita de COMERCIABILIDAD o IDONEIDAD PARA UN FIN
CONCRETO. Consulta la Licencia Publica General de GNU para mas detalles.

Deberias haber recibido una copia de la Licencia Publica General de GNU junto
con este programa. Si no es asi, consulta <https://www.gnu.org/licenses/>.
```

En corto: si publicas una versión modificada, tiene que seguir siendo libre y
con el código a la vista. No puedes cerrarlo ni meterlo en algo propietario.
