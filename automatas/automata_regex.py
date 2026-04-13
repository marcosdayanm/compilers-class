def reconoce_2026_04_07(string: str):
    state = 0
    for char in string:
        if state == 0:
            if char == 'a':
                state = 0
            elif char == 'b':
                state = 1
            else:
                return False
        elif state == 1:
            if char == 'a':
                state = 0
            elif char == 'b':
                state = 2
            else:
                return False
        elif state == 2:
            if char == '$':
                return True
            if char not in {'a', 'b', "$"}:
                return False
    return state == 2


def reconoce_tabla_2026_04_07(string: str):
    tabla = [
        [0, 1],
        [0, 2],
        [2, 2],
    ]
    dic = {'a': 0, 'b': 1}

    estado = 0
    for c in string:
        if c not in "ab$":
            return False
        
        elif c == '$':
            return estado == 2
        
        estado = tabla[estado][dic[c]]
    
    return estado == 2
        


def reconoce_hash_table_2026_04_07(string: str):
    transition_table = {
        0: {'a': 0, 'b': 1},
        1: {'a': 0, 'b': 2},
        2: {'$': 3}
    }
    
    state = 0
    for char in string:
        if char in transition_table[state]:
            state = transition_table[state][char]
        else:
            return False
    return state == 3




def reconoce_hash_table(string: str, alphabet: set, transition_table: dict[int, dict[str, int]], initial_state: int, accepting_states: set):
    state = initial_state
    for char in string:
        if char in alphabet and char in transition_table[state]:
            state = transition_table[state][char]
        else:
            return False
    return state in accepting_states
            

if __name__ == "__main__":
    # test_strings = [
    #     "bb$",
    #     "abb",
    #     "aaabbb$",
    #     "baba",
    #     "abab$",
    #     "aaaa",
    #     "bbb$",
    #     "aabb"
    # ]
    
    # for s in test_strings:
    #     # result = reconoce_2026_04_07(s)
    #     result = reconoce_tabla_2026_04_07(s)
    #     print(f"{s}: {'Accepted' if result else 'Rejected'}")


    table = {
        0: {'0': 1, '1': 3},
        1: {'0': 0, '1': 2},
        2: {'0': 3, '1': 1},
        3: {'0': 2, '1': 0}
    }

    casos = [
        "1010", # Accepted
        "1100", # Accepted
        "0000", # Accepted
        "1111", # Accepted
        "1011", # Rejected
        "1101", # Rejected
        "11111", # Rejected
        "11110", # Rejected
        "0101", # Accepted
        "2" # Rejected
    ]

    for caso in casos:
        result = reconoce_hash_table(caso, {'0', '1'}, table, 0, {0})
        print(f"{caso}: {'Accepted' if result else 'Rejected'}")