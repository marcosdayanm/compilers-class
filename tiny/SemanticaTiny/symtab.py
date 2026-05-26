# the hash table
BucketList = {}

# Procedure st_insert inserts line numbers and
# memory locations into the symbol table
# loc = memory location is inserted only the
# first time, otherwise ignored
def st_insert(name, lineno, loc):
    if name in BucketList:
        BucketList[name].append(lineno)
    else:
        BucketList[name] = [loc, lineno]

# Function st_lookup returns the memory 
# location of a variable or -1 if not found
def st_lookup(name):
    if name in BucketList:
        return BucketList[name][0]
    else:
        return -1

# Procedure printSymTab prints a formatted 
# listing of the symbol table contents 
# to the listing file
def printSymTab():
    print("Variable Name  Location   Line Numbers")
    print("-------------  --------   ------------")
    for name in BucketList:
        print(f'{name:15}{BucketList[name][0]:8d}', end = '')
        for i in range(len(BucketList[name])-1):
            print(f'{BucketList[name][i+1]:4d}', end = '')
        print()
