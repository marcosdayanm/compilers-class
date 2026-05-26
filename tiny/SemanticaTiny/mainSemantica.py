from globalTypes import *
from Parser import *
from analyze import *

fileName = "prueba"
f = open(fileName + '.tny', 'r')
program = f.read() 		# lee todo el archivo a compilar
f.close()                       # cerrar el archivo con programa fuente
progLong = len(program) 	# longitud original del programa
program = program + '$' 	# agregar un caracter $ que represente EOF
position = 0 			# posición del caracter actual del string

Error = False
recibeParser(program, position, progLong) # para mandar los globales al parser
syntaxTree, Error = parse(False)

if not(Error):
    print()
    print("Building Symbol Table...")
    buildSymtab(syntaxTree, True)
    print()
    print("Checking Types...")
    typeCheck(syntaxTree)
    print()
    print("Type Checking Finished")

