# Projekt B
### Konfiguracja środowiska
1. Pobieram obraz ubuntu ze skonfigurowanym mininet i FRRouting </br>
Link: [dysk ova](https://drive.google.com/file/d/1qmQGnk1J11RhiNZUg0BECKoWKEUtc5I3/view)
2. Przy pomocy obrazu tworzę maszynę wirtualną
3. Korzystam z systemu i skonfigurowanego minineta.

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

---

Podziękowania dla Pana James Wanderer, za stworzenie artykułu, który pomógł w stworzeniu środowiska i wstępnemy zapoznaniu z narzędziem FRRouting. </br>
Artykuł: [Fun with Routing Protocols](https://medium.com/@jmwanderer/fun-with-routing-protocols-8a0677aab2fc)
