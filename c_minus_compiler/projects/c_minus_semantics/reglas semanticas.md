# Reglas semánticas de C-

Estas son las reglas semánticas consideradas para `semantica.py`. La base principal es la sección de semántica de C- del documento `Lenguaje C-.pdf`. Para la tabla de símbolos y el chequeo de tipos también se usaron las presentaciones de análisis semántico y tabla de símbolos.

## Programa y declaraciones

Un programa es una secuencia de declaraciones. Cada declaración puede ser de variable o de función.

Reglas usadas:

- Debe existir al menos una declaración.
- Las variables y funciones deben declararse antes de usarse.
- La última declaración del programa debe ser una función llamada `main`.
- C- no tiene prototipos: declarar una función también es definirla.

## Variables

Una declaración de variable puede declarar:

- una variable entera simple
- un arreglo de enteros

Reglas usadas:

- Solo se permite `int` en declaraciones de variables.
- `void` solo se permite como tipo de retorno de función o como lista vacía de parámetros.
- Solo se declara una variable por declaración.
- Un arreglo `a[n]` tiene índices de `0` a `n - 1`.
- El analizador revisa que el índice usado en `a[expr]` sea entero.

## Funciones y parámetros

Una función tiene tipo de retorno, nombre, parámetros y un cuerpo.

Reglas usadas:

- Una función puede regresar `int` o `void`.
- Una función `void` no debe regresar valor.
- Una función `int` debe regresar un valor entero cuando aparece `return expression;`.
- `void` en la lista de parámetros significa que la función no recibe parámetros.
- Los parámetros simples `int x` se tratan como enteros.
- Los parámetros `int a[]` se tratan como arreglos.
- Los parámetros de arreglo deben recibir como argumento una variable de arreglo sin índice.
- No hay parámetros de tipo función.
- Los parámetros tienen el mismo ámbito que el cuerpo de la función.

Funciones predefinidas en el ambiente global:

```text
int input(void)
void output(int x)
```

## Bloques y alcance

Una sentencia compuesta tiene declaraciones locales y después una lista de sentencias.

Reglas usadas:

- Las declaraciones locales solo valen dentro del bloque donde se declaran.
- Una declaración local puede ocultar una declaración global.
- No se permite declarar dos veces el mismo nombre dentro del mismo scope.
- Primero se procesan declaraciones y luego sentencias, de acuerdo con la gramática.

La tabla de símbolos se maneja por scopes:

- scope global
- scope por función
- scope por bloque compuesto anidado

Cada símbolo guarda nombre, tipo, clase, scope, líneas de uso, tamaño si es arreglo y parámetros si es función.

## Sentencias

### Expression statement

Una expresión seguida de `;` se evalúa por su efecto. En C- se usa principalmente para asignaciones y llamadas de función.

### If

La condición se evalúa como entero:

- valor distinto de `0`: se ejecuta el primer statement
- valor `0`: se ejecuta el `else`, si existe

En el analizador se revisa que la condición tenga tipo entero.

### While

La condición se evalúa repetidamente:

- valor distinto de `0`: ejecuta el cuerpo
- valor `0`: termina el ciclo

En el analizador se revisa que la condición tenga tipo entero.

### Return

Reglas usadas:

- En función `int`, `return expression;` debe regresar una expresión entera.
- En función `int`, `return;` es error.
- En función `void`, `return;` es válido.
- En función `void`, `return expression;` es error.

## Expresiones

### Asignación

Una asignación tiene la forma:

```text
var = expression
```

Reglas usadas:

- El lado izquierdo debe ser una variable simple o una posición de arreglo.
- No se permite asignar a una función.
- No se permite asignar a un arreglo completo.
- El lado derecho debe ser entero.
- El valor de toda la asignación es el valor asignado.

### Variables y arreglos

Reglas usadas:

- Una variable simple tiene tipo `int`.
- Una posición de arreglo `a[i]` tiene tipo `int`.
- El índice `i` debe ser entero.
- Un arreglo sin índice solo se permite como argumento cuando el parámetro esperado es arreglo.

### Operadores relacionales

Los operadores relacionales son:

```text
<=  <  >  >=  ==  !=
```

Reglas usadas:

- Cada lado debe ser entero.
- El resultado se maneja como entero: `1` si es verdadero, `0` si es falso.
- No se aceptan comparaciones encadenadas sin paréntesis, porque la gramática solo permite un operador relacional por `simple-expression`.

### Operadores aritméticos

Operadores:

```text
+  -  *  /
```

Reglas usadas:

- Los operandos deben ser enteros.
- El resultado es entero.
- La división `/` es división entera.

### Factores

Un factor puede ser:

- una expresión entre paréntesis
- una variable
- una llamada a función
- un número

Reglas usadas:

- Un número tiene tipo `int`.
- Una llamada a función tiene el tipo de retorno de esa función.
- Una función `void` no puede usarse como valor dentro de una expresión.
- Una variable de arreglo debe estar indexada, excepto cuando se pasa como argumento a un parámetro arreglo.

## Llamadas a función

Una llamada tiene la forma:

```text
f(arg1, arg2, ...)
```

Reglas usadas:

- La función debe estar declarada antes de llamarse.
- El identificador llamado debe ser una función.
- El número de argumentos debe coincidir con el número de parámetros.
- Cada argumento debe coincidir con su parámetro.
- Si el parámetro es arreglo, el argumento debe ser un identificador de arreglo sin índice.

## AST usado por el semántico

El parser guarda lexemas importantes en `node.value`. Por ejemplo:

- `FUN_DECLARATION.value`: nombre de función.
- `VAR_DECLARATION.value`: nombre de variable o arreglo.
- `VAR.value`: uso de variable o arreglo.
- `CALL.value`: nombre de función llamada.
- `EXPRESSION.value`: operador `=`.

Por eso el analizador decide la regla con `node.node_type` y usa `node.value` como dato del token.

## Reporte de errores

Los errores semánticos se imprimen con:

- número de línea
- mensaje
- línea fuente
- caret apuntando al token más cercano

Cuando una expresión ya tiene error, se propaga un tipo `error` para continuar el recorrido sin generar demasiados errores derivados.

## Referencias

- `Lenguaje C-.pdf`
- `Proyecto 3 Analizador Semántico.pdf`
- `4. Analizador Semántico.pdf`
- `4.0 Tabla de Símbolos.pdf`
- `4.1 Ejemplo de creación ST y TC.pdf`
- `tiny/SemanticaTiny`
