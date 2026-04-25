```json
1. program -> declaration_list

2. declaration_list -> declaration declaration_list_prime

3. declaration_list_prime -> declaration declaration_list_prime | empty

4. declaration -> var_declaration | fun_declaration

5. var_declaration -> type_specifier ID SEMI
                  | type_specifier ID LBRACKET NUM RBRACKET SEMI

6. type_specifier -> INT | VOID

7. fun_declaration -> type_specifier ID LPAREN params RPAREN compound_stmt

8. params -> param_list | VOID

9. param_list -> param param_list_prime

10. param_list_prime -> COMMA param param_list_prime | empty

11. param -> type_specifier ID
          | type_specifier ID LBRACKET RBRACKET

12. compound_stmt -> LBRACE local_declarations statement_list RBRACE

13. local_declarations -> local_declarations_prime

14. local_declarations_prime -> var_declaration local_declarations_prime | empty

15. statement_list -> statement_list_prime

16. statement_list_prime -> statement statement_list_prime | empty

17. statement -> expression_stmt
              | compound_stmt
              | selection_stmt
              | iteration_stmt
              | return_stmt

18. expression_stmt -> expression SEMI
                    | SEMI

19. selection_stmt -> IF LPAREN expression RPAREN statement
                   | IF LPAREN expression RPAREN statement ELSE statement

20. iteration_stmt -> WHILE LPAREN expression RPAREN statement

21. return_stmt -> RETURN SEMI
                | RETURN expression SEMI

22. expression -> var ASSIGN expression
               | simple_expression

23. var -> ID
        | ID LBRACKET expression RBRACKET

24. simple_expression -> additive_expression simple_expression_prime

25. simple_expression_prime -> relop additive_expression | empty

26. relop -> LTE | LT | GT | GTE | EQ | NEQ

27. additive_expression -> term additive_expression_prime

28. additive_expression_prime -> addop term additive_expression_prime | empty

29. addop -> PLUS | MINUS

30. term -> factor term_prime

31. term_prime -> mulop factor term_prime | empty

32. mulop -> TIMES | OVER

33. factor -> LPAREN expression RPAREN
           | var
           | call
           | NUM

34. call -> ID LPAREN args RPAREN

35. args -> arg_list | empty

36. arg_list -> expression arg_list_prime

37. arg_list_prime -> COMMA expression arg_list_prime | empty
```
