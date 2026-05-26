from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

import Parser as parser_module
from globalTypes import SyntaxNodeType


class SymbolKind(Enum):
    VARIABLE = "variable"
    ARRAY = "array"
    FUNCTION = "function"
    PARAMETER = "parameter"
    BUILTIN = "builtin"


class SemanticType(Enum):
    INT = "int"
    VOID = "void"
    ERROR = "error"


@dataclass(frozen=True)
class ParameterInfo:
    name: str
    semantic_type: SemanticType
    is_array: bool = False

    def display(self) -> str:
        """Regresa el tipo del parametro en formato legible."""
        suffix = "[]" if self.is_array else ""
        return f"{self.semantic_type.value}{suffix}"


@dataclass
class SymbolEntry:
    name: str
    semantic_type: SemanticType
    kind: SymbolKind
    scope_id: int
    line: int
    column: int
    is_array: bool = False
    array_size: int | None = None
    parameters: list[ParameterInfo] = field(default_factory=list)
    lines: list[int] = field(default_factory=list)

    def __post_init__(self) -> None:
        """Registra la linea de declaracion como primer uso del simbolo."""
        if self.line > 0 and self.line not in self.lines:
            self.lines.append(self.line)

    def signature(self) -> str:
        """Construye la firma visible en la impresion de la tabla."""
        if self.kind not in {SymbolKind.FUNCTION, SymbolKind.BUILTIN}:
            if self.is_array:
                size = "" if self.array_size is None else str(self.array_size)
                return f"arr[{size}]"
            return ""
        if not self.parameters:
            return "void"
        return ", ".join(param.display() for param in self.parameters)


@dataclass
class SymbolTable:
    scope_id: int
    name: str
    parent: SymbolTable | None = None
    symbols: dict[str, SymbolEntry] = field(default_factory=dict)
    children: list[SymbolTable] = field(default_factory=list)

    def insert(self, entry: SymbolEntry) -> bool:
        """Inserta un simbolo solo si no existe en el scope local."""
        if entry.name in self.symbols:
            return False
        self.symbols[entry.name] = entry
        return True

    def local_lookup(self, name: str) -> SymbolEntry | None:
        """Busca un simbolo solo en esta tabla."""
        return self.symbols.get(name)

    def lookup(self, name: str) -> SymbolEntry | None:
        """Busca un simbolo desde este scope hacia sus padres."""
        scope: SymbolTable | None = self
        while scope is not None:
            entry = scope.local_lookup(name)
            if entry is not None:
                return entry
            scope = scope.parent
        return None


@dataclass(frozen=True)
class TypeInfo:
    semantic_type: SemanticType
    is_array: bool = False
    entry: SymbolEntry | None = None

    @property
    def is_error(self) -> bool:
        """Indica si una expresion ya produjo error semantico."""
        return self.semantic_type == SemanticType.ERROR

    @property
    def is_int_scalar(self) -> bool:
        """Indica si el tipo es exactamente int escalar."""
        return self.semantic_type == SemanticType.INT and not self.is_array


class SemanticAnalyzer:
    def __init__(self, tree) -> None:
        """Inicializa el analizador y el scope global."""
        self.tree = tree
        self.scopes: list[SymbolTable] = []
        # Se guarda el scope que corresponde a cada nodo de bloque del AST.
        self.compound_scopes: dict[int, SymbolTable] = {}
        self.function_scopes: dict[int, SymbolTable] = {}
        self.errors: list[str] = []
        self.current_function: SymbolEntry | None = None
        self.global_scope = self._new_scope("global", None)
        self._install_builtins()

    def build_tables(self) -> list[SymbolTable]:
        """Construye la tabla de simbolos a partir de las declaraciones."""
        # Primer recorrido: declaraciones globales, funciones y scopes locales.
        for declaration in self._global_declarations(self.tree):
            if self._actual_type(declaration) == SyntaxNodeType.VAR_DECLARATION:
                self._declare_variable(self._unwrap(declaration), self.global_scope)
            elif self._actual_type(declaration) == SyntaxNodeType.FUN_DECLARATION:
                self._declare_function(self._unwrap(declaration), self.global_scope)
        return self.scopes

    def check(self) -> list[str]:
        """Revisa tipos y usos de identificadores con la tabla ya creada."""
        # Segundo recorrido: usa la tabla ya construida para revisar tipos.
        self._check_main()
        for declaration in self._global_declarations(self.tree):
            function_node = self._unwrap(declaration)
            if function_node.node_type == SyntaxNodeType.FUN_DECLARATION:
                self._check_function(function_node)
        return self.errors

    def print_symbol_tables(self) -> None:
        """Imprime todas las tablas de simbolos creadas."""
        print("Tabla de simbolos")
        for scope in self.scopes:
            parent = "-" if scope.parent is None else str(scope.parent.scope_id)
            print()
            print(f"Scope {scope.scope_id} ({scope.name})  Padre: {parent}")
            print(f"{'Nombre':15} {'Clase':10} {'Tipo':6} {'Extra':18} Lineas")
            print(f"{'-' * 15} {'-' * 10} {'-' * 6} {'-' * 18} {'-' * 10}")
            for entry in scope.symbols.values():
                lines = " ".join(str(line) for line in entry.lines if line > 0)
                print(
                    f"{entry.name:15} {entry.kind.value:10} "
                    f"{entry.semantic_type.value:6} {entry.signature():18} {lines}"
                )

    def _install_builtins(self) -> None:
        """Agrega input y output al scope global."""
        # Funciones predefinidas de C- segun la especificacion del lenguaje.
        builtins = [
            SymbolEntry("input", SemanticType.INT, SymbolKind.BUILTIN, self.global_scope.scope_id, 0, 0),
            SymbolEntry(
                "output",
                SemanticType.VOID,
                SymbolKind.BUILTIN,
                self.global_scope.scope_id,
                0,
                0,
                parameters=[ParameterInfo("value", SemanticType.INT)],
            ),
        ]
        for entry in builtins:
            self.global_scope.insert(entry)

    def _new_scope(self, name: str, parent: SymbolTable | None) -> SymbolTable:
        """Crea un scope nuevo y lo enlaza con su padre."""
        scope = SymbolTable(len(self.scopes), name, parent)
        if parent is not None:
            parent.children.append(scope)
        self.scopes.append(scope)
        return scope

    def _semantic_error(self, node, message: str) -> None:
        """Registra e imprime un error semantico con linea y caret."""
        line, column = self._node_position(node)
        source = self._source_line(line)
        pointer = " " * max(column - 1, 0) + "^"
        formatted = f"Linea {line}: Error semantico: {message}\n{source}\n{pointer}"
        self.errors.append(formatted)
        print(formatted)

    def _node_position(self, node) -> tuple[int, int]:
        """Obtiene la posicion mas cercana asociada a un nodo."""
        # Algunos nodos no tienen posicion propia, se usa el primer hijo con token.
        line = getattr(node, "line", None)
        column = getattr(node, "column", None)
        if line is not None and column is not None:
            return line, column
        for child in getattr(node, "children", []):
            child_line, child_column = self._node_position(child)
            if child_line != 1 or child_column != 1:
                return child_line, child_column
        return 1, 1

    def _source_line(self, line_number: int) -> str:
        """Obtiene la linea fuente usada para imprimir errores."""
        source = parser_module.programa
        if source.endswith("$"):
            source = source[:-1]
        lines = source.splitlines()
        if 1 <= line_number <= len(lines):
            return lines[line_number - 1]
        return ""

    def _unwrap(self, node):
        """Quita envolturas de declaration/statement del AST."""
        # El parser conserva envolturas gramaticales, semantica trabaja con el nodo real.
        if node.node_type == SyntaxNodeType.DECLARATION and node.children:
            return node.children[0]
        if node.node_type == SyntaxNodeType.STATEMENT and node.children:
            return node.children[0]
        return node

    def _actual_type(self, node) -> SyntaxNodeType:
        """Regresa el tipo real de un nodo posiblemente envuelto."""
        return self._unwrap(node).node_type

    def _is_empty(self, node) -> bool:
        """Indica si el nodo representa epsilon."""
        return node.node_type == SyntaxNodeType.EMPTY

    def _type_from_node(self, node) -> SemanticType:
        """Convierte un type_specifier del AST a tipo semantico."""
        if node.value == "int":
            return SemanticType.INT
        if node.value == "void":
            return SemanticType.VOID
        return SemanticType.ERROR

    def _parse_declared_name(self, value: str) -> tuple[str, bool, int | None]:
        """Separa nombre, forma de arreglo y tamano en una declaracion."""
        if value.endswith("]") and "[" in value:
            name, size_text = value[:-1].split("[", 1)
            try:
                size = int(size_text)
            except ValueError:
                size = None
            return name, True, size
        return value, False, None

    def _parse_used_name(self, value: str) -> tuple[str, bool]:
        """Separa nombre y uso indexado en una referencia."""
        if value.endswith("[]"):
            return value[:-2], True
        return value, False

    def _global_declarations(self, tree) -> list:
        """Extrae las declaraciones de nivel global."""
        program = self._unwrap(tree)
        if program.node_type != SyntaxNodeType.PROGRAM or not program.children:
            return []
        return self._declaration_list(program.children[0])

    # Helpers para aplanar las reglas recursivas *_prime producidas por el parser.
    def _declaration_list(self, node) -> list:
        """Aplana declaration_list."""
        if node.node_type == SyntaxNodeType.DECLARATION_LIST:
            declarations = [node.children[0]]
            declarations.extend(self._declaration_list_prime(node.children[1]))
            return declarations
        return []

    def _declaration_list_prime(self, node) -> list:
        """Aplana declaration_list_prime."""
        if not node.children or self._is_empty(node.children[0]):
            return []
        declarations = [node.children[0]]
        declarations.extend(self._declaration_list_prime(node.children[1]))
        return declarations

    def _local_declarations(self, compound_node) -> list:
        """Extrae declaraciones locales de un bloque."""
        if not compound_node.children:
            return []
        local_declarations = compound_node.children[0]
        if not local_declarations.children:
            return []
        return self._local_declarations_prime(local_declarations.children[0])

    def _local_declarations_prime(self, node) -> list:
        """Aplana local_declarations_prime."""
        if not node.children or self._is_empty(node.children[0]):
            return []
        declarations = [node.children[0]]
        declarations.extend(self._local_declarations_prime(node.children[1]))
        return declarations

    def _statements(self, compound_node) -> list:
        """Extrae statements de un bloque."""
        if len(compound_node.children) < 2:
            return []
        statement_list = compound_node.children[1]
        if not statement_list.children:
            return []
        return self._statement_list_prime(statement_list.children[0])

    def _statement_list_prime(self, node) -> list:
        """Aplana statement_list_prime."""
        if not node.children or self._is_empty(node.children[0]):
            return []
        statements = [node.children[0]]
        statements.extend(self._statement_list_prime(node.children[1]))
        return statements

    def _params(self, params_node) -> list[ParameterInfo]:
        """Extrae la firma de parametros de una funcion."""
        if params_node.value == "void":
            return []
        if not params_node.children:
            return []
        return self._param_list(params_node.children[0])

    def _param_list(self, node) -> list[ParameterInfo]:
        """Aplana param_list."""
        params = [self._param(node.children[0])]
        params.extend(self._param_list_prime(node.children[1]))
        return params

    def _param_list_prime(self, node) -> list[ParameterInfo]:
        """Aplana param_list_prime."""
        if not node.children or self._is_empty(node.children[0]):
            return []
        params = [self._param(node.children[0])]
        params.extend(self._param_list_prime(node.children[1]))
        return params

    def _param(self, node) -> ParameterInfo:
        """Convierte un nodo param a ParameterInfo."""
        semantic_type = self._type_from_node(node.children[0])
        name, is_array = self._parse_used_name(node.value or "")
        return ParameterInfo(name, semantic_type, is_array)

    def _args(self, args_node, scope: SymbolTable) -> list[TypeInfo]:
        """Calcula los tipos de los argumentos de una llamada."""
        if not args_node.children or self._is_empty(args_node.children[0]):
            return []
        return self._arg_list(args_node.children[0], scope)

    def _arg_list(self, node, scope: SymbolTable) -> list[TypeInfo]:
        """Aplana arg_list y revisa cada expresion."""
        args = [self._check_expression(node.children[0], scope)]
        args.extend(self._arg_list_prime(node.children[1], scope))
        return args

    def _arg_list_prime(self, node, scope: SymbolTable) -> list[TypeInfo]:
        """Aplana arg_list_prime."""
        if not node.children or self._is_empty(node.children[0]):
            return []
        args = [self._check_expression(node.children[0], scope)]
        args.extend(self._arg_list_prime(node.children[1], scope))
        return args

    def _declare_variable(self, node, scope: SymbolTable) -> SymbolEntry | None:
        """Declara una variable o arreglo en el scope indicado."""
        semantic_type = self._type_from_node(node.children[0])
        name, is_array, array_size = self._parse_declared_name(node.value or "")
        kind = SymbolKind.ARRAY if is_array else SymbolKind.VARIABLE
        if semantic_type == SemanticType.VOID:
            self._semantic_error(node, f"'{name}' no puede declararse con tipo void.")
        entry = SymbolEntry(
            name=name,
            semantic_type=semantic_type,
            kind=kind,
            scope_id=scope.scope_id,
            line=node.line or 1,
            column=node.column or 1,
            is_array=is_array,
            array_size=array_size,
        )
        if not scope.insert(entry):
            self._semantic_error(node, f"'{name}' ya fue declarado en este scope.")
            return scope.local_lookup(name)
        return entry

    def _declare_function(self, node, scope: SymbolTable) -> SymbolEntry | None:
        """Declara una funcion y prepara su scope local."""
        semantic_type = self._type_from_node(node.children[0])
        params = self._params(node.children[1])
        entry = SymbolEntry(
            name=node.value or "",
            semantic_type=semantic_type,
            kind=SymbolKind.FUNCTION,
            scope_id=scope.scope_id,
            line=node.line or 1,
            column=node.column or 1,
            parameters=params,
        )
        if not scope.insert(entry):
            self._semantic_error(node, f"'{entry.name}' ya fue declarado en este scope.")
            entry = scope.local_lookup(entry.name)
        function_scope = self._new_scope(f"function {node.value}", scope)
        # El bloque raiz de la funcion comparte el scope donde viven sus parametros.
        self.function_scopes[id(node)] = function_scope
        self.compound_scopes[id(node.children[2])] = function_scope
        self._declare_parameters(node.children[1], params, function_scope)
        self._declare_compound_contents(node.children[2], function_scope, create_nested_scopes=True)
        return entry

    def _declare_parameters(self, params_node, params: list[ParameterInfo], scope: SymbolTable) -> None:
        """Inserta los parametros como simbolos del scope de funcion."""
        if params_node.value == "void":
            return
        param_nodes = self._param_nodes(params_node)
        for param_node, param in zip(param_nodes, params):
            if param.semantic_type == SemanticType.VOID:
                self._semantic_error(param_node, f"El parametro '{param.name}' no puede tener tipo void.")
            entry = SymbolEntry(
                name=param.name,
                semantic_type=param.semantic_type,
                kind=SymbolKind.PARAMETER,
                scope_id=scope.scope_id,
                line=param_node.line or 1,
                column=param_node.column or 1,
                is_array=param.is_array,
            )
            if not scope.insert(entry):
                self._semantic_error(param_node, f"'{param.name}' ya fue declarado en este scope.")

    def _param_nodes(self, params_node) -> list:
        """Extrae los nodos param originales para reportar errores."""
        if params_node.value == "void" or not params_node.children:
            return []
        return self._param_node_list(params_node.children[0])

    def _param_node_list(self, node) -> list:
        """Aplana nodos param_list."""
        params = [node.children[0]]
        params.extend(self._param_node_list_prime(node.children[1]))
        return params

    def _param_node_list_prime(self, node) -> list:
        """Aplana nodos param_list_prime."""
        if not node.children or self._is_empty(node.children[0]):
            return []
        params = [node.children[0]]
        params.extend(self._param_node_list_prime(node.children[1]))
        return params

    def _declare_compound_contents(self, compound_node, scope: SymbolTable, create_nested_scopes: bool) -> None:
        """Declara variables locales y bloques internos de un compound_stmt."""
        for declaration in self._local_declarations(compound_node):
            self._declare_variable(declaration, scope)
        for statement in self._statements(compound_node):
            self._declare_nested_statement(statement, scope, create_nested_scopes)

    def _declare_nested_statement(self, statement_node, scope: SymbolTable, create_nested_scopes: bool) -> None:
        """Crea scopes para bloques anidados dentro de statements."""
        node = self._unwrap(statement_node)
        if node.node_type == SyntaxNodeType.COMPOUND_STMT:
            nested_scope = self._new_scope(f"block line {node.line}", scope) if create_nested_scopes else scope
            self.compound_scopes[id(node)] = nested_scope
            self._declare_compound_contents(node, nested_scope, create_nested_scopes=True)
        elif node.node_type == SyntaxNodeType.SELECTION_STMT:
            self._declare_nested_statement(node.children[1], scope, create_nested_scopes)
            if len(node.children) > 2:
                self._declare_nested_statement(node.children[2], scope, create_nested_scopes)
        elif node.node_type == SyntaxNodeType.ITERATION_STMT:
            self._declare_nested_statement(node.children[1], scope, create_nested_scopes)

    def _check_main(self) -> None:
        """Valida que exista void main(void)."""
        entry = self.global_scope.local_lookup("main")
        if entry is None:
            self._semantic_error(self.tree, "No se encontro la funcion 'main'.")
            return
        if entry.kind != SymbolKind.FUNCTION:
            self._semantic_error(self.tree, "'main' debe ser una funcion.")
            return
        if entry.semantic_type != SemanticType.VOID or entry.parameters:
            self._semantic_error(self.tree, "La funcion 'main' debe tener firma void main(void).")

    def _check_function(self, function_node) -> None:
        """Revisa semanticamente el cuerpo de una funcion."""
        entry = self.global_scope.local_lookup(function_node.value or "")
        if entry is None:
            return
        previous = self.current_function
        self.current_function = entry
        function_scope = self.function_scopes.get(id(function_node), self.global_scope)
        self._check_compound(function_node.children[2], function_scope)
        self.current_function = previous

    def _check_compound(self, compound_node, scope: SymbolTable) -> None:
        """Revisa los statements de un bloque con su scope correspondiente."""
        current_scope = self.compound_scopes.get(id(compound_node), scope)
        for statement in self._statements(compound_node):
            self._check_statement(statement, current_scope)

    def _check_statement(self, statement_node, scope: SymbolTable) -> None:
        """Despacha la revision semantica de un statement."""
        node = self._unwrap(statement_node)
        if node.node_type == SyntaxNodeType.COMPOUND_STMT:
            self._check_compound(node, self.compound_scopes.get(id(node), scope))
        elif node.node_type == SyntaxNodeType.EXPRESSION_STMT:
            if node.children:
                self._check_expression(node.children[0], scope)
        elif node.node_type == SyntaxNodeType.SELECTION_STMT:
            condition = self._check_expression(node.children[0], scope)
            self._require_int_scalar(node.children[0], condition, "La condicion del if debe ser int.")
            self._check_statement(node.children[1], scope)
            if len(node.children) > 2:
                self._check_statement(node.children[2], scope)
        elif node.node_type == SyntaxNodeType.ITERATION_STMT:
            condition = self._check_expression(node.children[0], scope)
            self._require_int_scalar(node.children[0], condition, "La condicion del while debe ser int.")
            self._check_statement(node.children[1], scope)
        elif node.node_type == SyntaxNodeType.RETURN_STMT:
            self._check_return(node, scope)

    def _check_return(self, node, scope: SymbolTable) -> None:
        """Valida que return coincida con el tipo de la funcion actual."""
        if self.current_function is None:
            return
        if not node.children:
            if self.current_function.semantic_type == SemanticType.INT:
                self._semantic_error(node, f"La funcion '{self.current_function.name}' debe regresar int.")
            return
        value_type = self._check_expression(node.children[0], scope)
        if self.current_function.semantic_type == SemanticType.VOID:
            self._semantic_error(node, f"La funcion '{self.current_function.name}' es void y no debe regresar valor.")
        elif not value_type.is_error:
            self._require_int_scalar(node.children[0], value_type, "El valor de return debe ser int.")

    def _check_expression(self, node, scope: SymbolTable) -> TypeInfo:
        """Calcula el tipo de una expresion."""
        # Las expresiones regresan ERROR despues de reportar, para evitar cascadas.
        if node.node_type == SyntaxNodeType.EXPRESSION and node.value == "=":
            left = self._check_var(node.children[0], scope)
            right = self._check_expression(node.children[1], scope)
            if left.is_array and not left.is_error:
                self._semantic_error(node.children[0], "No se puede asignar a un arreglo completo.")
            if not right.is_error:
                self._require_int_scalar(node.children[1], right, "El lado derecho de una asignacion debe ser int.")
            if not left.is_error:
                self._require_int_scalar(node.children[0], left, "El lado izquierdo de una asignacion debe ser int.")
            return TypeInfo(SemanticType.INT if not left.is_error and not right.is_error else SemanticType.ERROR)
        if node.node_type == SyntaxNodeType.EXPRESSION and node.children:
            return self._check_simple_expression(node.children[0], scope)
        if node.node_type == SyntaxNodeType.SIMPLE_EXPRESSION:
            return self._check_simple_expression(node, scope)
        return TypeInfo(SemanticType.ERROR)

    def _check_simple_expression(self, node, scope: SymbolTable) -> TypeInfo:
        """Revisa una expresion con posible operador relacional."""
        left = self._check_additive_expression(node.children[0], scope)
        prime = node.children[1]
        if not prime.children or self._is_empty(prime.children[0]):
            return left
        right = self._check_additive_expression(prime.children[1], scope)
        self._require_int_scalar(prime.children[0], left, "El operando izquierdo de una comparacion debe ser int.")
        self._require_int_scalar(prime.children[1], right, "El operando derecho de una comparacion debe ser int.")
        if left.is_error or right.is_error:
            return TypeInfo(SemanticType.ERROR)
        return TypeInfo(SemanticType.INT)

    def _check_additive_expression(self, node, scope: SymbolTable) -> TypeInfo:
        """Revisa sumas y restas."""
        left = self._check_term(node.children[0], scope)
        return self._check_additive_prime(node.children[1], left, scope)

    def _check_additive_prime(self, node, left: TypeInfo, scope: SymbolTable) -> TypeInfo:
        """Continua la revision de una cola aditiva."""
        if not node.children or self._is_empty(node.children[0]):
            return left
        right = self._check_term(node.children[1], scope)
        self._require_int_scalar(node.children[0], left, "El operando izquierdo de una operacion aritmetica debe ser int.")
        self._require_int_scalar(node.children[1], right, "El operando derecho de una operacion aritmetica debe ser int.")
        result = TypeInfo(SemanticType.ERROR if left.is_error or right.is_error else SemanticType.INT)
        return self._check_additive_prime(node.children[2], result, scope)

    def _check_term(self, node, scope: SymbolTable) -> TypeInfo:
        """Revisa multiplicaciones y divisiones."""
        left = self._check_factor(node.children[0], scope)
        return self._check_term_prime(node.children[1], left, scope)

    def _check_term_prime(self, node, left: TypeInfo, scope: SymbolTable) -> TypeInfo:
        """Continua la revision de una cola multiplicativa."""
        if not node.children or self._is_empty(node.children[0]):
            return left
        right = self._check_factor(node.children[1], scope)
        self._require_int_scalar(node.children[0], left, "El operando izquierdo de una operacion aritmetica debe ser int.")
        self._require_int_scalar(node.children[1], right, "El operando derecho de una operacion aritmetica debe ser int.")
        result = TypeInfo(SemanticType.ERROR if left.is_error or right.is_error else SemanticType.INT)
        return self._check_term_prime(node.children[2], result, scope)

    def _check_factor(self, node, scope: SymbolTable) -> TypeInfo:
        """Calcula el tipo de un factor."""
        if node.value == "()":
            return self._check_expression(node.children[0], scope)
        if node.value is not None and not node.children:
            return TypeInfo(SemanticType.INT)
        if not node.children:
            return TypeInfo(SemanticType.ERROR)
        child = node.children[0]
        if child.node_type == SyntaxNodeType.VAR:
            return self._check_var(child, scope)
        if child.node_type == SyntaxNodeType.CALL:
            return self._check_call(child, scope)
        if child.node_type == SyntaxNodeType.EXPRESSION:
            return self._check_expression(child, scope)
        return TypeInfo(SemanticType.ERROR)

    def _check_var(self, node, scope: SymbolTable) -> TypeInfo:
        """Revisa una referencia a variable o arreglo."""
        name, indexed = self._parse_used_name(node.value or "")
        entry = scope.lookup(name)
        if entry is None:
            self._semantic_error(node, f"'{name}' no esta declarado.")
            return TypeInfo(SemanticType.ERROR)
        self._record_use(entry, node.line)
        if entry.kind in {SymbolKind.FUNCTION, SymbolKind.BUILTIN}:
            self._semantic_error(node, f"'{name}' es una funcion y no puede usarse como variable.")
            return TypeInfo(SemanticType.ERROR)
        if indexed:
            if not entry.is_array:
                self._semantic_error(node, f"'{name}' no es un arreglo.")
                return TypeInfo(SemanticType.ERROR)
            index_type = self._check_expression(node.children[0], scope)
            self._require_int_scalar(node.children[0], index_type, "El indice de un arreglo debe ser int.")
            return TypeInfo(entry.semantic_type, is_array=False, entry=entry)
        return TypeInfo(entry.semantic_type, is_array=entry.is_array, entry=entry)

    def _check_call(self, node, scope: SymbolTable) -> TypeInfo:
        """Revisa una llamada a funcion y sus argumentos."""
        name = node.value or ""
        entry = scope.lookup(name)
        if entry is None:
            self._semantic_error(node, f"La funcion '{name}' no esta declarada.")
            return TypeInfo(SemanticType.ERROR)
        self._record_use(entry, node.line)
        if entry.kind not in {SymbolKind.FUNCTION, SymbolKind.BUILTIN}:
            self._semantic_error(node, f"'{name}' no es una funcion.")
            return TypeInfo(SemanticType.ERROR)
        args = self._args(node.children[0], scope)
        if len(args) != len(entry.parameters):
            self._semantic_error(
                node,
                f"La funcion '{name}' espera {len(entry.parameters)} argumento(s), pero recibio {len(args)}.",
            )
        for index, (arg, param) in enumerate(zip(args, entry.parameters), start=1):
            if arg.is_error:
                continue
            if param.semantic_type != arg.semantic_type:
                self._semantic_error(node, f"El argumento {index} de '{name}' debe ser {param.display()}.")
                continue
            if param.is_array != arg.is_array:
                expected = "arreglo" if param.is_array else "escalar"
                self._semantic_error(node, f"El argumento {index} de '{name}' debe ser {expected}.")
        return TypeInfo(entry.semantic_type, entry=entry)

    def _require_int_scalar(self, node, value_type: TypeInfo, message: str) -> None:
        """Reporta error si el tipo no es int escalar."""
        if value_type.is_error:
            return
        if not value_type.is_int_scalar:
            self._semantic_error(node, message)

    def _record_use(self, entry: SymbolEntry, line: int | None) -> None:
        """Agrega una linea de uso a un simbolo."""
        if line is None or line <= 0:
            return
        if line not in entry.lines:
            entry.lines.append(line)


_last_analyzer: SemanticAnalyzer | None = None
_last_errors: list[str] = []


def tabla(tree, imprime: bool = True):
    """Construye e imprime la tabla de simbolos si se solicita."""
    global _last_analyzer
    global _last_errors
    analyzer = SemanticAnalyzer(tree)
    analyzer.build_tables()
    _last_analyzer = analyzer
    _last_errors = list(analyzer.errors)
    if imprime:
        analyzer.print_symbol_tables()
    return analyzer.scopes


def semantica(tree, imprime: bool = True):
    """Ejecuta construccion de tabla y chequeo semantico."""
    global _last_analyzer
    global _last_errors
    tabla(tree, False)
    analyzer = _last_analyzer
    if analyzer is None:
        return []
    analyzer.check()
    _last_errors = list(analyzer.errors)
    if imprime:
        analyzer.print_symbol_tables()
    return analyzer.errors


def getSemanticErrors() -> list[str]:
    """Regresa los errores del ultimo analisis."""
    return list(_last_errors)
