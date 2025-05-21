# Projekt B
### Konfiguracja środowiska
1. Tworzymy maszynę wirtualną z Ubuntu Desktop 20.04 LTS
2. Z poziomu katalogu home użytkownika wykonujemy następujące komendy:
```
sudo apt-get install git
sudo apt-get install build-essential

git clone https://github.com/mininet/mininet
cd mininet
git checkout -b mininet-2.3.0 2.3.0
```
3. Podmieniamy zawartość pliku install.sh w mininet/util/install.sh na zawartość pliku install.sh z tego repozytorium
4. Wykonujemy instalacje mininet:
```
sudo PYTHON=python3 util/install.sh -a
```

### Konfiguracja środowiska programistycznego
1. Pobieramy plik .deb do instalacji VSCode z https://code.visualstudio.com/download
```
sudo apt install ./code_1.100.2-1747260578_amd64.deb 
```
2. Tworzymy projekt w wybranym folderze i otwieramy w VSCode
3. Tworzymy wirtualne środowisko, przed tym krokiem instalujemy potrzebną paczkę
```
sudo apt install python3.8-venv
```
a następnie po utworzeniu środowiska instalujemy potrzebne zależności takie jak np.: numpy i networkx.

### Dodanie potrzebnych funkcjonalności
1. Instalacja FRRouting do rutingu
```
sudo apt-get install frr frr-pythontools
```
