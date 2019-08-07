# Samples of using PyInstaller

Here we will see some apps generated with PyInstaller.  

## How to generate:

1. make download
2. make build

## Problems:

macOS:

1. When execute **UniqueBibleApp** we receive error:  
```
Could not find QtWebEngineProcess
/bin/sh: line 1: 48279 Abort trap: 6
```

## Some hacks and TODOs:

1. Problems with shiboken2 on macOS. PyInstaller try to find **libshiboken2** into PySide2 folder. To solve it for now i do:  
```
cp /usr/local/lib/python3.7/site-packages/shiboken2/libshiboken2.abi3.5.13.dylib /usr/local/lib/python3.7/site-packages/PySide2/
```

2. UniqueBible required **gdown** (google drive module), but PyInstaller don't embed it. I try add it as hidden import, but don't change anything. To solve it i generate other **gui.py** file without this module (is in stuff folder).