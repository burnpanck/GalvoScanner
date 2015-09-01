""" ScanHook.py - A simple language to describe complex scans

This file contains code that parses a simple script language, extracted from patricks original code.
To date, it's use is unknown.
"""

__author__ = 'yves'

# container class for holding attributes
class EmptyObject:
    pass


# helper class for callable list
class CallableList(list):
    def __call__(self):
        for entry in self:
            entry()


def callbackFactory(self, callback, args):
    return lambda: getattr(self, callback.strip())(args)


def parseHook(self, hookFile):
    keywords = {}
    # compile a regular expression, so that we have fname(**args) and then call the appropriate function
    # or match variable declarations var = value
    import re

    functionCallPattern = re.compile("\w+\s*\([\s\w\/\,\.\_\-\!\$\?]*\)")
    assignPattern = re.compile("\w+\s*=\s*\w+")
    tmpObject = EmptyObject()
    body = CallableList()
    for line in open(hookFile).readlines():
        match = functionCallPattern.search(line)
        if match is not None:
            # we got a function call, so split at the first bracket
            index = match.group().find("(")
            if index > -1:
                functionName = match.group()[:index]
                if hasattr(self, functionName):
                    arguments = match.group()[index + 1:-1]
                    # call function if it is a class funcion
                    if (arguments == ""):
                        args = None
                    else:
                        args = arguments.split(",")
                    # print(arguments)
                    if args is not None:
                        if functionName == "plot3dmap":
                            body += [self.callbackFactory(functionName, args)]
                        else:
                            body += [self.callbackFactory(functionName, *args)]
                    else:
                        body += [getattr(self, functionName)]
                else:
                    # see if we have defined a own call
                    print(functionName)
                    if functionName in keywords:
                        print("custom function")
                        arguments = match.group()[index + 1:-1]
                        # call function if it is a class funcion
                        args = ",".join(arguments)
                        body += [lambda: keywords[functionName](args)]
        match = assignPattern.search(line)
        print(match)
        if match is not None:
            # we have a assignment
            name, value = match.group().split("=")
            setattr(tmpObject, name.strip(), value.strip())

        if not hasattr(tmpObject, "name"):
            setattr(tmpObject, "name", hookFile)
        tmpObject.body = body
        return tmpObject
