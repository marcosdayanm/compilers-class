# Plan para implementar el analizador semantico de C-

## Objetivo

Implementar el Proyecto 3 con un archivo `semantica.py` que exponga exactamente la interfaz pedida:

```python
def tabla(tree, imprime=True)
def semantica(tree, imprime=True)
```

`tabla` construira e imprimira la tabla o tablas de simbolos a partir del AST generado por `Parser.py`.  
`semantica` llamara a `tabla` y despues hara la revision de tipos y de declaraciones.

La implementacion se hara sobre el AST actual, sin cambiar la interfaz del lexer ni del parser, para que el script de evaluacion de la especificacion siga funcionando:

```python
from globalTypes import *
from Parser import *
from semantica import *

globales(programa, posicion, progLong)
AST = parser(True)
semantica(AST, True)
```

## Contexto revisado

Archivos base del proyecto:

- `lexer.py`: scanner por DFA, con posiciones de linea y columna.
- `Parser.py`: parser descendente recursivo que produce nodos `ASTNode`.
- `globalTypes.py`: enums de tokens, tipos de nodos sintacticos y conjuntos FIRST/recovery.
- `main.py`: wrapper actual para correr el parser.
- `Proyecto 3 Analizador Semántico.pdf`: pide `semantica.py`, `tabla(tree, imprime=True)`, `semantica(tree, imprime=True)`, tablas por bloque y errores semanticos con linea/caret.

Referencias revisadas:

- `4. Analizador Semántico.pdf`: recomienda construir la ST en preorden y hacer type checking bottom-up/postorden usando reglas logicas de inferencia.
- `4.0 Tabla de Simbolos.pdf`: recomienda una tabla por bloque y operaciones `enter`, `local lookup`, `global lookup`.
- `4.1 Ejemplo de creación ST y TC.pdf`: muestra scope global, scope por funcion, parametros dentro del scope de funcion y busqueda subiendo por scopes.
- `tiny/SemanticaTiny`: ejemplo con `symtab.py` y `analyze.py`, util para el estilo general, aunque C- requiere scopes y funciones.

## Criterio para interpretar el AST actual

El parser no crea nodos terminales separados para cada token. En su lugar, guarda los terminales relevantes en el campo `value` de nodos gramaticales de tipo `SyntaxNodeType`. Por eso, un nodo con `value` no debe interpretarse automaticamente como "nodo terminal"; debe interpretarse como un nodo del AST que lleva pegado el lexema terminal importante para ese constructo.

Ejemplos confirmados en `Parser.py`:

- `VAR_DECLARATION.value`: nombre de variable o arreglo, por ejemplo `x` o `x[10]`.
- `TYPE_SPECIFIER.value`: `int` o `void`.
- `FUN_DECLARATION.value`: nombre de la funcion.
- `PARAMS.value`: `void` cuando la funcion no recibe parametros.
- `PARAM.value`: nombre del parametro, por ejemplo `a` o `a[]`.
- `EXPRESSION.value`: operador `=` en asignaciones.
- `VAR.value`: uso de variable, por ejemplo `x` o `x[]`.
- `RELOP`, `ADDOP`, `MULOP`: operador relacional, aditivo o multiplicativo.
- `FACTOR.value`: numero literal o `()` para expresion agrupada.
- `CALL.value`: nombre de la funcion llamada.

Criterio de implementacion: el analizador semantico usara `node.node_type` para decidir que regla semantica aplicar, y usara `node.value` como el lexema/token asociado cuando ese nodo lo tenga. Las posiciones `line` y `column` del mismo nodo se usaran para reportar errores con caret.

## Arquitectura propuesta

Crear `semantica.py` con clases pequenas, siguiendo el estilo actual del proyecto: `dataclass`, `Enum`/constantes claras, metodos auxiliares y funciones globales publicas al final.

Componentes:

- `SymbolKind`: `VARIABLE`, `ARRAY`, `FUNCTION`, `PARAMETER`.
- `SemanticType`: `INT`, `VOID`, `ERROR`.
- `SymbolEntry`: entrada de simbolo con nombre, tipo, kind, scope, linea, columna, tamano de arreglo y firma de parametros si aplica.
- `SymbolTable`: una tabla local con `scope_id`, referencia al padre y diccionario de simbolos.
- `SymbolTableStack` o `ScopeManager`: administra scopes, insercion local, busqueda local y busqueda global/subiendo por padres.
- `SemanticAnalyzer`: clase principal con estado:
  - `root`
  - lista de scopes creados
  - lista de errores
  - funcion actual para validar `return`
  - utilidades para extraer lineas de codigo desde `Parser.programa`

Funciones publicas:

- `tabla(tree, imprime=True)`: instancia el analizador, construye scopes, imprime tablas si se pide y regresa la estructura de tablas.
- `semantica(tree, imprime=True)`: construye tablas, hace chequeo de tipos, imprime errores semanticos y regresa el resultado del analisis.
- Opcional: `getSemanticErrors()` para poder probar facilmente sin depender de stdout.

## Construccion de tablas de simbolos

El AST actual no es un AST "limpio"; conserva nodos como `declaration_list_prime`, `local_declarations_prime`, `statement_list_prime`, `empty`, etc. Por eso se necesitan helpers para recorrer listas recursivas y encontrar nodos importantes sin reescribir el parser.

Reglas de scope:

1. Crear scope 0 global al iniciar.
2. En scope global insertar:
   - variables globales
   - arreglos globales
   - funciones
3. Por cada `fun_declaration`:
   - insertar la funcion en el scope global con tipo de retorno y firma.
   - crear un nuevo scope hijo para la funcion.
   - insertar sus parametros en el scope de la funcion.
   - insertar sus variables locales en ese mismo scope.
   - analizar declaraciones y statements del `compound_stmt` sin crear scope adicional para el cuerpo inicial de la funcion.
4. Para `compound_stmt` anidados dentro de `if`, `while` u otros statements:
   - propuesta conservadora: crear un nuevo scope de bloque, porque C- usa `{...}` como bloque y el PDF pide una tabla por cada bloque.
   - si el profesor espera el comportamiento del ejemplo `4.1`, se puede ajustar a no crear scopes para cuerpos anidados porque en su ejemplo no se cambian scopes dentro de `while`/`if`.
   - mi recomendacion para este proyecto: scope global + scope por funcion + scope por bloque compuesto anidado, ya que el PDF del proyecto dice "una por cada bloque" y la gramatica permite `compound_stmt` como statement.

Validaciones durante insercion:

- No permitir dos simbolos con el mismo nombre en el mismo scope.
- No permitir variables o arreglos de tipo `void`.
- No permitir parametros de tipo `void` salvo el caso especial `params -> VOID`, que significa cero parametros.
- Guardar tamano de arreglo en declaraciones `ID[NUM]`.
- Guardar firma de funciones como lista de parametros: tipo base y si es arreglo.

Formato de impresion propuesto:

```text
Tabla de simbolos

Scope 0 (global)
Nombre          Clase       Tipo    Extra        Lineas
main            function    void    void         3
x               array       int     size=10      1

Scope 1 (function main)
Nombre          Clase       Tipo    Extra        Lineas
i               variable    int                  5
```

Si conviene imitar mas el ejemplo de clase, se puede simplificar a columnas tipo:

```text
Scope 0
main | void | void
x    | int  | arr | 10
```

## Chequeo semantico y reglas de tipos

El type checking se hara bottom-up sobre expresiones, como sugieren las presentaciones. Cada funcion auxiliar regresara un tipo semantico, normalmente `INT`, `VOID` o `ERROR`. El tipo `ERROR` servira para recuperarse y evitar cascadas de errores.

Reglas principales:

### Identificadores

- Si `x` aparece como variable, debe existir en algun scope visible.
- Si `x` aparece como variable, no puede ser una funcion.
- Si `f(...)` aparece como llamada, `f` debe existir y ser funcion.
- Si un identificador no existe, reportar error y continuar con tipo `ERROR`.

### Variables y arreglos

- `x` escalar usado como expresion produce tipo `int`.
- `a[i]` requiere que `a` sea arreglo.
- El indice `i` de `a[i]` debe ser `int`.
- `a` sin indice, si es arreglo:
  - valido como argumento cuando el parametro esperado es arreglo.
  - error si se usa como entero escalar en operaciones aritmeticas, comparaciones o asignacion escalar.
- `x[i]` donde `x` no es arreglo produce error.

### Asignacion

- `var = expression` requiere que `var` sea asignable.
- El lado izquierdo no puede ser una funcion.
- El lado izquierdo debe ser escalar `int` o una posicion de arreglo `int`.
- El lado derecho debe ser `int`.
- La asignacion produce tipo `int` para poder participar como expresion si aparece anidada.

Regla:

```text
O |- var : int    O |- expr : int
---------------------------------
O |- var = expr : int
```

### Operadores aritmeticos

`+`, `-`, `*`, `/` requieren operandos `int` y producen `int`.

```text
O |- e1 : int    O |- e2 : int
------------------------------
O |- e1 + e2 : int
```

### Operadores relacionales

`<`, `<=`, `>`, `>=`, `==`, `!=` requieren operandos `int`. Para C- se tratara el resultado como `int`, porque el lenguaje no tiene token/tipo `bool` en `globalTypes.py`. Esto permite usar condiciones como expresiones enteras, que es el comportamiento tipico de C/C-.

```text
O |- e1 : int    O |- e2 : int
------------------------------
O |- e1 < e2 : int
```

### `if` y `while`

- La condicion debe tener tipo `int`.
- Los cuerpos se revisan semanticamente en su scope correspondiente.

```text
O |- cond : int
--------------------------
O |- if (cond) stmt : void
```

### `return`

- En funcion `int`, `return expr;` requiere `expr:int`.
- En funcion `int`, `return;` es error.
- En funcion `void`, `return;` es valido.
- En funcion `void`, `return expr;` es error.
- Opcional recomendado: advertir/error si una funcion `int` no contiene ningun `return expr;` en su cuerpo. Este punto puede ser estricto o relajado segun lo que espere el profesor.

### Llamadas a funciones

- La funcion llamada debe existir.
- La cantidad de argumentos debe coincidir con la firma.
- Cada argumento debe coincidir con el parametro:
  - parametro `int`: argumento escalar `int`.
  - parametro `int[]`: argumento arreglo sin indice.
- Una funcion `void` llamada dentro de una expresion aritmetica/relacional/asignacion produce error porque no puede producir valor `int`.
- Una llamada a funcion `int` produce `int`.

### `main`

Regla opcional recomendada:

- Validar que exista `main`.
- Validar que `main` sea funcion.
- Validar que `main` tenga firma `void main(void)`.

La especificacion del PDF no lo dice explicitamente en el extracto, asi que lo dejaria implementado como chequeo semantico normal pero facil de desactivar si el profesor no lo requiere.

## Reporte y recuperacion de errores

Formato alineado con el PDF:

```text
Linea 22: Error semantico: descripcion del error
if (contador + fact(n)) then
              ^
```

Para obtener la linea fuente se usara `Parser.programa`, que ya contiene el programa completo en el flujo de evaluacion. Los nodos del AST ya guardan `line` y `column`, asi que el caret puede apuntar al identificador, operador o llamada donde se detecta el problema.

Recuperacion:

- Al detectar un error, registrar el mensaje y regresar tipo `ERROR`.
- Si una subexpresion ya es `ERROR`, no repetir errores derivados salvo que sea una validacion independiente.
- Para simbolos no declarados, insertar simbolos ficticios no es necesario; basta regresar `ERROR` y continuar.

## Cambios propuestos por archivo

### Crear `semantica.py`

Contenido principal:

- dataclasses de simbolos y scopes.
- clase `SemanticAnalyzer`.
- helpers para listas recursivas del AST:
  - declaraciones globales
  - parametros
  - declaraciones locales
  - statements
  - argumentos
  - colas de expresiones aditivas/multiplicativas
- funciones publicas `tabla`, `semantica`, `getSemanticErrors`.

### Mantener `Parser.py` sin cambios

No planeo cambiar el parser de entrada porque ya cumple la interfaz del Proyecto 2 y entrega lineas/columnas. Solo si aparece una limitacion fuerte durante la implementacion, propondria un cambio pequeno y compatible.

### Mantener `globalTypes.py` sin cambios inicialmente

Los tipos semanticos se pueden definir en `semantica.py` para no mezclar tipos sintacticos con tipos semanticos. Si despues conviene compartirlos para pruebas, se podria agregar un enum, pero no es necesario.

### Opcional: actualizar `main.py`

No es requerido por la especificacion. Se podria agregar una opcion local para correr parser + semantica desde terminal, pero lo dejaria fuera al inicio para no afectar el flujo de calificacion.

### Crear `REGLAS_SEMANTICAS.md`

Como parte de la entrega del Proyecto 3, crear un documento Markdown separado con:

- Las reglas logicas de inferencia de tipos usadas por la implementacion.
- La explicacion de la estructura de la tabla de simbolos y su stack/arbol de scopes.
- Una tabla de referencias que indique de donde salio cada decision:
  - `Proyecto 3 Analizador Semántico.pdf`: interfaz requerida, salida esperada, tablas por bloque, errores con linea y caret.
  - `4. Analizador Semántico.pdf`: type checking bottom-up/postorden, ambientes de tipos y reglas logicas de inferencia.
  - `4.0 Tabla de Simbolos.pdf`: operaciones de tabla de simbolos, scopes, stack de tablas, busqueda local/global.
  - `4.1 Ejemplo de creación ST y TC.pdf`: ejemplo practico de creacion de scopes, parametros, funciones y busqueda en scopes padre.
  - `tiny/SemanticaTiny`: referencia de estilo de implementacion para tabla y chequeo de tipos.
- Una nota explicita de que no se usaron fuentes de internet para definir las reglas semanticas, salvo que despues se autorice o haga falta consultar una referencia externa.

## Pruebas propuestas

Crear archivos `.c-` temporales o una carpeta `tests_semantica/` solo si autorizas pasar a implementacion. Casos minimos:

1. Programa correcto simple:
   - `void main(void) { int x; x = 1; }`
2. Variable no declarada:
   - `x = 1;`
3. Variable duplicada en el mismo scope.
4. Shadowing valido en scope hijo, si aprobamos scopes por bloque.
5. Variable `void` invalida.
6. Funcion `int` con `return;` invalido.
7. Funcion `void` con `return 1;` invalido.
8. Llamada a funcion no declarada.
9. Llamada con numero incorrecto de argumentos.
10. Llamada con argumento arreglo/escalar incompatible.
11. Uso de funcion `void` dentro de expresion.
12. Uso de arreglo sin indice en expresion escalar.
13. Indice de arreglo no entero o intento de indexar escalar.

Verificacion manual inicial:

```bash
python3 - <<'PY'
from Parser import globales, parser
from semantica import semantica

with open("sample.c-", "r", encoding="utf-8") as f:
    programa = f.read()

progLong = len(programa)
programa = programa + "$"
globales(programa, 0, progLong)
AST = parser(False)
semantica(AST, True)
PY
```

## Riesgos y decisiones pendientes

1. **Scopes de bloques anidados**: el PDF dice tabla por bloque, pero el ejemplo de clase enfatiza no crear scope en cuerpos de `while`/`if` para ese ejemplo. Yo implementaria scope por `compound_stmt` anidado, excepto el cuerpo raiz de cada funcion, porque es lo mas fiel a "una por cada bloque".
2. **Tipo de relacionales**: C- no tiene `bool`, entonces los relacionales produciran `int`. Esto evita introducir un tipo que no existe en la gramatica.
3. **`main` obligatorio**: recomendable, pero no confirmado en el PDF del proyecto. Lo puedo implementar como validacion final simple.
4. **Funcion `int` sin return**: semanticamente util, pero puede ser mas estricta que lo pedido. La dejaria como chequeo opcional o advertencia si prefieres.
5. **AST concreto**: hay que escribir helpers cuidadosos para no depender de indices magicos de hijos mas de lo necesario. Aun asi, algunas posiciones son parte de la estructura actual del parser.

## Orden de implementacion cuando apruebes

1. Crear `semantica.py` con estructuras de datos, manejo de scopes y reporte de errores.
2. Implementar extraccion/normalizacion de nodos del AST actual.
3. Implementar `tabla(tree, imprime=True)` y validaciones de declaraciones.
4. Implementar type checking bottom-up para expresiones, statements, returns y llamadas.
5. Probar con `sample.c-` y casos pequenos de error.
6. Ajustar formato de impresion de tablas/errores para que sea legible y compatible con lo pedido.
7. Crear `REGLAS_SEMANTICAS.md` con las reglas logicas de inferencia, la estructura de la ST/scope stack y las referencias exactas usadas.
