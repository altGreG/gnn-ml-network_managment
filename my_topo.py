#!/usr/bin/python3
# https://graphonline.top/  - wizualizacja sieci
from mininet.topo import Topo
from mininet.net import Mininet
from mininet.node import Node
from mininet.log import setLogLevel, info
from mininet.cli import CLI
from mininet.link import TCLink
import random
import numpy as np
import csv
import os
import sys
import re
import shutil
import subprocess
import re
from collections import defaultdict
import ipaddress
from collections import defaultdict
import time

# Ustalanie liczby ruterow w danej iteracji symulacji
folder_path = 'podsumowanie'
folders = [f for f in os.listdir(folder_path) if os.path.isdir(os.path.join(folder_path, f))]
if len(folders) % 6 == 0:
    number_of_routers = 5
elif len(folders) % 6 == 1:
    number_of_routers = 6
elif len(folders) % 6 == 2:
    number_of_routers = 7
elif len(folders) % 6 == 3:
    number_of_routers = 8
elif len(folders) % 6 == 4:
    number_of_routers = 9
else:
    number_of_routers = 10

print(f"Wylosowana liczba ruterow: {number_of_routers}")
def create_router_dirs(num_routers):  # Funkcja tworzy foldery i pliki konfiguracyjne dla podanej liczby ruterów
    script_dir = os.path.dirname(os.path.abspath(__file__))  # Ścieżka do katalogu, w którym znajduje się ten skrypt
    daemons_template_path = os.path.join(script_dir, "daemons_template")  # Ścieżka do szablonu pliku "daemons"

    if not os.path.isfile(daemons_template_path):  # Sprawdzenie, czy plik szablonu istnieje
        print("Błąd: Nie znaleziono pliku 'daemons_template' w folderze skryptu.")  # Komunikat błędu
        return  # Przerwanie funkcji, jeśli pliku nie ma

    for i in range(1, num_routers + 1):  # Iteracja od 1 do num_routers (włącznie)
        folder_name = f"r{i}"  # Nazwa folderu dla rutera, np. "r1", "r2", ...
        os.makedirs(folder_name, exist_ok=True)  # Tworzenie folderu (jeśli nie istnieje)

        # vtysh.conf
        vtysh_content = f"service integrated-vtysh-config\nhostname vm-r{i}\n"  
        # Treść pliku vtysh.conf: konfiguracja zintegrowanego trybu VTYSH + nazwa hosta
        with open(os.path.join(folder_name, "vtysh.conf"), "w") as vtysh_file:  # Zapis do pliku vtysh.conf
            vtysh_file.write(vtysh_content)

        # daemons – kopiowanie z szablonu
        shutil.copyfile(daemons_template_path, os.path.join(folder_name, "daemons"))  
        # Kopiowanie gotowego pliku daemons do folderu rutera

        # frr.conf
        frr_conf_content = f"""  # Bazowa zawartość pliku frr.conf — konfiguracja FRRouting
frr version 9.1-MyOwnFRRVersion
frr defaults traditional
hostname vm-r{i}
log syslog informational
ip forwarding
no ipv6 forwarding
service integrated-vtysh-config
!
""".lstrip()  # Usunięcie wiodących pustych linii

        with open(os.path.join(folder_name, "frr.conf"), "w") as frr_file:  # Zapis do pliku frr.conf
            frr_file.write(frr_conf_content)  # Zapisanie treści konfiguracyjnej FRR do pliku



def update_node_line(filename, num_nodes):  # Funkcja modyfikuje plik konfiguracyjny, aktualizując listę ruterów w 4. linijce
    # Pełna ścieżka do pliku config_frr.conf
    script_dir = os.path.dirname(os.path.abspath(__file__))  # Ścieżka do folderu, w którym znajduje się ten skrypt
    file_path = os.path.join(script_dir, filename)  # Pełna ścieżka do pliku, który modyfikujemy

    if not os.path.isfile(file_path):  # Sprawdzenie, czy plik istnieje
        print(f"Plik '{filename}' nie istnieje w folderze skryptu.")  # Komunikat błędu
        return  # Przerywamy działanie funkcji, jeśli plik nie istnieje

    with open(file_path, "r") as f:  # Otwieramy plik do odczytu
        lines = f.readlines()  # Wczytujemy wszystkie linie pliku jako listę

    # Generowanie nowej 4. linijki
    node_line = "for NODE in " + " ".join([f"r{i}" for i in range(1, num_nodes + 1)]) + "\n"  
    # Tworzymy nową linijkę z listą wszystkich ruterów: for NODE in r1 r2 r3 ...

    while len(lines) < 4:  # Jeśli plik ma mniej niż 4 linijki, dodajemy puste, aby móc nadpisać 4.
        lines.append("\n")

    # Podmień czwartą linijkę (indeks 3)
    lines[3] = node_line  # Zamieniamy 4. linijkę na wygenerowaną linię z ruterami

    with open(file_path, "w") as f:  # Otwieramy plik do zapisu
        f.writelines(lines)  # Zapisujemy zmodyfikowane linie do pliku

    print(f"Podmieniono 4. linijkę w pliku '{filename}' na:\n{node_line.strip()}")  # Informacja dla użytkownika


class LinuxRouter(Node):  # Definicja klasy ruterów jako specjalnych węzłów (Node) w Mininecie
    def config(self, **params):  # Metoda konfiguracji — może przyjmować dowolne parametry
        super(LinuxRouter, self).config(**params)  # Wywołanie metody `config` z klasy bazowej (Node)

    def terminate(self):  # Metoda wykonywana przy zamykaniu rutera
        super(LinuxRouter, self).terminate()  # Wywołanie domyślnego zachowania z klasy nadrzędnej


def generuj_macierz_sasiedztwa(n_ruterow):  # Funkcja losowo generuje macierz sąsiedztwa ruterów
    if not (3 <= n_ruterow <= 20):  # Sprawdzenie, czy liczba ruterów mieści się w dozwolonym zakresie
        raise ValueError("Liczba ruterów musi być między 3 a 20.")  # Jeśli nie — zgłoszenie błędu

    macierz = np.zeros((n_ruterow, n_ruterow), dtype=int)  # Inicjalizacja pustej macierzy sąsiedztwa (zerami)

    print("Połączenia między ruterami:")  # Informacja pomocnicza w konsoli
    for i in range(n_ruterow):  # Iteracja po wierszach macierzy
        for j in range(i + 1, n_ruterow):  # Iteracja tylko po połowie macierzy (symetryczna)
            polaczenie = random.choice([0, 1])  # Losowo decydujemy, czy połączenie istnieje (1) czy nie (0)
            macierz[i][j] = macierz[j][i] = polaczenie  # Ustawiamy wartość w obu miejscach (symetryczność)
            if polaczenie == 1:  # Jeśli połączenie istnieje
                print(f"  r{i+1} <--> r{j+1}")  # Wypisujemy je na ekran

    return macierz  # Zwracamy wygenerowaną macierz sąsiedztwa



def save_matrix_to_csv(macierz, nazwa_pliku):  # Funkcja zapisuje przekazaną macierz do pliku CSV
    with open(nazwa_pliku, mode='w', newline='') as plik:  # Otwiera plik do zapisu (tryb nadpisania)
        writer = csv.writer(plik)  # Tworzy obiekt zapisujący do CSV
        for wiersz in macierz:  # Iteruje po każdym wierszu macierzy
            writer.writerow(wiersz)  # Zapisuje wiersz do pliku


def load_matrix_from_csv(nazwa_pliku):  # Funkcja wczytuje macierz z pliku CSV i zwraca jako numpy array
    macierz = []  # Lista do przechowywania wczytanych wierszy
    with open(nazwa_pliku, mode='r') as plik:  # Otwiera plik do odczytu
        reader = csv.reader(plik)  # Tworzy obiekt odczytujący z CSV
        for wiersz in reader:  # Iteruje po każdym wierszu pliku
            macierz.append([int(x) for x in wiersz])  # Konwertuje każdy element do int i dodaje do listy
    return np.array(macierz)  # Zwraca macierz jako obiekt numpy


def generate_ipv4_addressing_24bit(adj_matrix):  # Funkcja przypisuje adresy IP w formacie /24 dla każdej krawędzi w sieci
    num_routers = len(adj_matrix)  # Liczba ruterów wynika z rozmiaru macierzy sąsiedztwa

    links = []  # Lista do przechowywania par połączeń (np. r1 <-> r2, r1 <-> h1)
    for i in range(num_routers):  # Iteracja po każdym ruterze
        links.append((f"r{i+1}", f"h{i+1}"))  # Dodanie połączenia ruter-host dla każdego rutera
        for j in range(i + 1, num_routers):  # Iteracja po pozostałych ruterach (część nad przekątną)
            if adj_matrix[i][j] == 1:  # Jeśli w macierzy sąsiedztwa istnieje połączenie
                links.append((f"r{i+1}", f"r{j+1}"))  # Dodajemy parę ruter-ruter do listy linków

    addressing = {}  # Słownik do przechowywania przypisanych adresów IP dla każdego linku
    subnet_third_octet = 0  # Licznik dla trzeciego oktetu adresów IP w podsieciach 10.0.X.0/24

    for (r1, r2) in links:  # Iteracja po wszystkich linkach
        if r2.startswith("h"):  # Jeśli drugie urządzenie to host (h1, h2, ...)
            # Tymczasowe adresy IP dla ruter-host (nadpisane później w generate_frr_config)
            ip1 = f"1.1.1.1/24"
            ip2 = f"1.1.1.1/24"
            addressing[(r1, r2)] = (ip1, ip2)  # Przypisujemy takie same adresy tymczasowo
        else:
            # Dla połączeń ruter-ruter przypisujemy unikalną podsieć /24
            ip1 = f"10.0.{subnet_third_octet}.1/24"  # Adres IP pierwszego rutera
            ip2 = f"10.0.{subnet_third_octet}.2/24"  # Adres IP drugiego rutera
            addressing[(r1, r2)] = (ip1, ip2)  # Przypisujemy IP obu urządzeniom
            subnet_third_octet += 1  # Zwiększamy licznik podsieci

    return addressing  # Zwracamy słownik z przypisaną adresacją IP dla każdego linku


def generate_frr_config(adj_matrix):  # Funkcja generuje konfigurację interfejsów IP dla ruterów na podstawie macierzy sąsiedztwa
    addressing = generate_ipv4_addressing_24bit(adj_matrix)  # Pobieramy adresację IP dla wszystkich połączeń (ruter-ruter i ruter-host)
    num_routers = len(adj_matrix)  # Liczba ruterów w topologii

    router_interfaces = {f"r{i+1}": [] for i in range(num_routers)}  
    # Tworzymy słownik: kluczem jest nazwa rutera, a wartością lista jego interfejsów (nazwa + adres IP)

    iface_counters = {f"r{i+1}": 0 for i in range(num_routers)}  
    # Licznik interfejsów dla każdego rutera — pozwala numerować eth1, eth2, itd.

    for (r1, r2), (ip1, ip2) in addressing.items():  # Iteracja po parach połączeń i przypisanych adresach IP
        if r2.startswith("h"):  # Jeśli połączenie dotyczy hosta (np. h1)
            eth1 = f"eth0"  # Ruterowi przypisujemy pierwszy interfejs jako eth0
            number = int(r2[1:])  # Wyciągamy numer hosta z nazwy, np. "h3" → 3
            router_interfaces[r1].append((eth1, f"192.168.{number}.1/24"))  
            # Dodajemy interfejs do rutera, z adresem w sieci 192.168.X.0/24
        else:
            eth1 = f"eth{iface_counters[r1]+1}"  # Tworzymy nazwę interfejsu dla r1, np. eth1, eth2, ...
            router_interfaces[r1].append((eth1, ip1))  # Przypisujemy adres IP do tego interfejsu
            iface_counters[r1] += 1  # Zwiększamy licznik interfejsów dla r1

            eth2 = f"eth{iface_counters[r2]+1}"  # To samo dla r2
            router_interfaces[r2].append((eth2, ip2))  # Przypisujemy IP drugiemu ruterowi
            iface_counters[r2] += 1  # Zwiększamy licznik interfejsów dla r2

    return router_interfaces  # Zwracamy słownik: ruter → [(interfejs, IP), ...]


def append_interfaces_to_frr_conf(router_interfaces):  # Funkcja dopisuje konfigurację interfejsów do plików frr.conf
    for router, interfaces in router_interfaces.items():  # Iteracja po każdym ruterze i jego liście interfejsów
        folder = router  # Nazwa folderu rutera to jego nazwa (np. "r1", "r2", ...)
        file_path = os.path.join(folder, "frr.conf")  # Ścieżka do pliku konfiguracyjnego frr.conf

        # Sprawdź czy folder istnieje
        if not os.path.isdir(folder):  # Jeśli folder nie istnieje (np. coś poszło nie tak wcześniej)
            print(f"Folder {folder} nie istnieje. Pomijam...")  # Informacja w konsoli
            continue  # Pomijamy ten ruter

        # Przygotuj linie do dopisania
        lines_to_append = []  # Lista linii do dopisania do pliku
        for iface, ipaddr in interfaces:  # Dla każdego interfejsu i przypisanego adresu IP
            lines_to_append.append(f"interface {iface}")  # Definicja interfejsu
            lines_to_append.append(f" ip address {ipaddr}")  # Przypisanie adresu IP do interfejsu
            lines_to_append.append("!")  # Zakończenie bloku konfiguracji interfejsu
        lines_to_append.append("")  # Pusta linia na końcu dla czytelności

        # Dopisz do pliku frr.conf
        with open(file_path, "a") as f:  # Otwieramy plik w trybie dopisania
            f.write("\n".join(lines_to_append))  # Dopisujemy przygotowane linie

        print(f"Dopisano konfigurację interfejsów do {file_path}")  # Informacja o sukcesie


def add_ospf_config(num_routers):  # Funkcja generuje konfigurację OSPF dla każdego z ruterów
    for i in range(1, num_routers + 1):  # Iterujemy po wszystkich ruterach (r1, r2, ..., rn)
        folder = f"r{i}"  # Nazwa folderu z konfiguracją rutera
        frr_path = os.path.join(folder, "frr.conf")  # Ścieżka do pliku frr.conf danego rutera

        if not os.path.isfile(frr_path):  # Sprawdzenie, czy plik istnieje
            print(f"Plik {frr_path} nie istnieje, pomijam.")  # Jeśli nie, pomijamy
            continue

        with open(frr_path, "r") as f:  # Otwieramy plik konfiguracyjny do odczytu
            lines = f.readlines()  # Czytamy wszystkie linie

        networks = set()  # Zbiór do przechowywania wykrytych podsieci /24 dla OSPF
        for idx, line in enumerate(lines):  # Iterujemy po liniach
            if line.strip().startswith("interface eth"):  # Szukamy interfejsów (np. interface eth1)
                # następna linia powinna mieć ip address
                if idx + 1 < len(lines):  # Upewniamy się, że jest kolejna linia
                    next_line = lines[idx + 1].strip()  # Pobieramy kolejną linię
                    match = re.match(r"ip address (\d+\.\d+\.\d+\.\d+)/(\d+)", next_line)  # Szukamy adresu IP
                    if match:  # Jeśli znaleziono pasujący adres
                        ip_str = match.group(1)  # IP bez maski (np. 10.0.1.1)
                        prefix = int(match.group(2))  # Maska (np. 24)
                        # wyciągamy podsieć
                        ip_parts = ip_str.split(".")  # Dzielimy IP na części
                        # podsieć to 10.0.X.0 dla /24
                        if prefix == 24:  # Upewniamy się, że to sieć /24
                            network = f"{ip_parts[0]}.{ip_parts[1]}.{ip_parts[2]}.0/24"  # Tworzymy wpis sieci
                            networks.add(network)  # Dodajemy sieć do zbioru
                        else:
                            pass  # Inne maski są pomijane (np. /30, /16)

        # Generujemy konfigurację OSPF
        if not networks:  # Jeśli nie znaleziono żadnych sieci
            print(f"Nie znaleziono żadnych sieci w {frr_path}, pomijam OSPF.")  # Informacja
            continue

        ospf_lines = ["router ospf"]  # Sekcja OSPF
        ospf_lines.append(f"ospf router-id 10.{i}.0.1")  # Router ID (unikalny)
        ospf_lines.append("maximum-paths 1")  # Ograniczenie do jednej ścieżki routingu
        for net in sorted(networks):  # Dla każdej znalezionej sieci
            ospf_lines.append(f" network {net} area 0")  # Dodajemy do area 0 (domyślna domena OSPF)
        ospf_lines.append("!")  # Zakończenie sekcji
        ospf_lines.append("")  # Pusta linia

        # Dopisujemy na końcu pliku
        with open(frr_path, "a") as f:  # Otwieramy plik do dopisania
            f.write("\n".join(ospf_lines))  # Zapisujemy całą sekcję OSPF

        print(f"Dopisano konfigurację OSPF do {frr_path}")  # Potwierdzenie w konsoli


CONFIG_ROOT = "./"  # katalog główny z folderami r1, r2, ...

def parse_frr_conf(filepath):  # Parsuje plik frr.conf i wyciąga przypisane adresy IP do interfejsów
    interfaces = {}  # Słownik: interfejs → adres IP
    current_iface = None  # Przechowuje nazwę aktualnie analizowanego interfejsu

    with open(filepath) as f:  # Otwiera plik konfiguracyjny
        for line in f:  # Iteruje po liniach
            line = line.strip()  # Usuwa białe znaki z początku i końca
            if line.startswith("interface"):  # Jeśli linia definiuje interfejs
                current_iface = line.split()[1]  # Wyciąga nazwę interfejsu (np. eth1)
            elif line.startswith("ip address") and current_iface:  # Jeśli podano adres IP i znany interfejs
                ip_addr = line.split()[2]  # Wyciąga adres IP (np. 10.0.1.1/24)
                interfaces[current_iface] = ip_addr  # Dodaje do słownika
                current_iface = None  # Resetuje, bo zakończono opis tego interfejsu
    return interfaces  # Zwraca słownik interfejsów i ich IP


def collect_all_interfaces():  # Zbiera informacje o wszystkich interfejsach z folderów r1, r2, ...
    router_interfaces = {}  # Słownik: ruter → {interfejs: IP}
    for entry in os.listdir(CONFIG_ROOT):  # Iteruje po wszystkich plikach i folderach w katalogu głównym
        path = os.path.join(CONFIG_ROOT, entry)  # Pełna ścieżka do wpisu
        if os.path.isdir(path) and re.match(r"r\d+", entry):  # Jeśli to folder i pasuje do nazwy rutera (np. "r3")
            frr_path = os.path.join(path, "frr.conf")  # Ścieżka do pliku frr.conf
            if os.path.exists(frr_path):  # Sprawdzenie, czy plik istnieje
                interfaces = parse_frr_conf(frr_path)  # Parsowanie pliku, by dostać interfejsy
                router_interfaces[entry] = interfaces  # Dodanie wpisu do słownika
    return router_interfaces  # Zwraca pełną mapę ruterów i ich interfejsów


def find_links(router_interfaces):  # Funkcja identyfikuje fizyczne połączenia między ruterami na podstawie adresów IP
    network_map = defaultdict(list)  # Mapa: sieć → lista (ruter, interfejs, IP)

    for router, ifaces in router_interfaces.items():  # Iterujemy po ruterach i ich interfejsach
        for iface, ip in ifaces.items():  # Iterujemy po każdym interfejsie i jego adresie IP
            net = str(ipaddress.ip_interface(ip).network)  # Obliczamy adres sieci (np. 10.0.1.0/24)
            network_map[net].append((router, iface, ip))  # Przypisujemy interfejs do odpowiedniej sieci

    links = []  # Lista wykrytych połączeń
    for net, devices in network_map.items():  # Iterujemy po sieciach i urządzeniach w nich
        if len(devices) == 2:  # Jeśli dokładnie dwa urządzenia — traktujemy to jako połączenie ruter-ruter
            (r1, if1, ip1), (r2, if2, ip2) = devices  # Rozpakowanie danych o obu ruterach
            links.append((r1, r2, if1, ip1, if2, ip2))  # Dodanie połączenia do listy
        else:  # W innym przypadku coś jest nie tak (np. 1 lub więcej niż 2 urządzenia w jednej podsieci)
            print(f"Ostrzeżenie: sieć {net} zawiera {len(devices)} interfejsów (pomijana lub wymaga dodatkowej obsługi): {devices}")
    return links  # Zwraca listę wykrytych połączeń


def generate_addlink_calls(links):  # Funkcja generuje linijki kodu Python do dodania linków w Mininecie
    lines = []  # Lista do przechowywania wygenerowanych instrukcji addLink()

    for r1, r2, if1, ip1, if2, ip2 in links:  # Iterujemy po wszystkich wykrytych połączeniach
        call = (  # Budujemy formatowaną linijkę addLink w stylu Minineta
            f"        self.addLink({r1},\n"  # Nazwa pierwszego urządzenia (ruter)
            f"                     {r2},\n"  # Nazwa drugiego urządzenia (ruter)
            f"                     intfName1='{if1}',\n"  # Nazwa interfejsu po stronie r1
            f"                     params1={{'ip': '{ip1}'}},\n"  # IP przypisane do interfejsu r1
            f"                     intfName2='{if2}',\n"  # Nazwa interfejsu po stronie r2
            f"                     params2={{'ip': '{ip2}'}})"  # IP przypisane do interfejsu r2
        )
        lines.append(call)  # Dodajemy wygenerowaną linijkę do listy

    return lines  # Zwracamy listę gotowych instrukcji addLink()

def extract_link_info(text):  # Funkcja wyciąga dane z tekstowego wywołania self.addLink(...) (jako string)
    pattern = re.compile(  # Tworzymy wyrażenie regularne, które dopasowuje całe wywołanie addLink(...)
        r"self\.addLink\(\s*(\w+)\s*,\s*(\w+)\s*,.*?"  # Urządzenie 1, Urządzenie 2
        r"intfName1\s*=\s*'(\w+)'.*?"  # Nazwa interfejsu 1 (np. eth1)
        r"params1\s*=\s*\{\s*'ip'\s*:\s*'([\d./]+)'\s*\}.*?"  # Adres IP 1 (np. 10.0.0.1/24)
        r"intfName2\s*=\s*'(\w+)'.*?"  # Nazwa interfejsu 2
        r"params2\s*=\s*\{\s*'ip'\s*:\s*'([\d./]+)'\s*\}",  # Adres IP 2
        re.DOTALL  # Umożliwia dopasowanie wieloliniowe
    )

    match = pattern.search(text)  # Przeszukuje cały przekazany tekst według wzorca

    if match:  # Jeśli znaleziono dopasowanie
        device1, device2, intf1, ip1, intf2, ip2 = match.groups()  # Rozpakowujemy wszystkie dane z dopasowania
        return {  # Zwracamy je jako słownik z informacjami o obu urządzeniach
            'device1': {'name': device1, 'interface': intf1, 'ip': ip1},
            'device2': {'name': device2, 'interface': intf2, 'ip': ip2},
        }
    else:
        return None  # Jeśli nie udało się dopasować — zwracamy None


def get_router_by_name(name, router_list):  # Funkcja zwraca obiekt rutera z listy router_list na podstawie jego nazwy, np. "r3"
    # Wyciągamy numer z nazwy np. "r2" -> 2
    index = int(name[1:]) - 1  # Obcinamy literkę 'r', konwertujemy na int i przekształcamy na indeks (0-based)
    return router_list[index]  # Zwracamy odpowiedni obiekt rutera z listy


class NetworkTopo(Topo):  # Definicja klasy topologii dziedziczącej po klasie Topo z Minineta
    global number_of_routers  # Używamy zmiennej globalnej ustalającej liczbę ruterów

    # Tworzenie folderów na pliki konfiguracyjne ruterów (vtysh.conf, frr.conf, daemons)
    create_router_dirs(number_of_routers)
    print(f"Utworzono {number_of_routers} katalogów z plikami konfiguracyjnymi.")

    # Modyfikacja skryptu bash (config_frr.conf), który rozsyła pliki konfiguracyjne do ruterów
    update_node_line("config_frr.conf", number_of_routers)

    # Generowanie losowej macierzy sąsiedztwa (topologia ruter-ruter)
    macierz_sasiedztwa = generuj_macierz_sasiedztwa(number_of_routers)
    save_matrix_to_csv(macierz_sasiedztwa, "macierz_sasiedztwa.csv")  # Zapisujemy ją na dysk

    # Podgląd wygenerowanej macierzy
    print("\nWylosowana macierz sąsiedztwa:")
    print(macierz_sasiedztwa)

    # Generujemy przypisanie adresów IP do interfejsów oraz strukturę interfejsów
    router_interfaces = generate_frr_config(macierz_sasiedztwa)
    append_interfaces_to_frr_conf(router_interfaces)  # Dopisujemy interfejsy do plików frr.conf

    # Automatyczna konfiguracja protokołu OSPF w każdym ruterze
    add_ospf_config(number_of_routers)

    # Wysyłamy konfiguracje do Minineta przez uruchomienie skryptu bash
    current_dir = os.path.dirname(os.path.abspath(__file__))  # Ścieżka do katalogu skryptu
    script_path = os.path.join(current_dir, 'config_frr.conf')  # Ścieżka do skryptu bash
    subprocess.run(['bash', script_path])  # Uruchamiamy skrypt
    print("Dokonano propagacji konfiguracji ruterow do mininet!")

    def build(self, **_opts):  # Metoda budująca topologię (nadpisuje build z klasy Topo)
        global number_of_routers

        # Dodanie ruterów do sieci Mininet jako hosty z klasą LinuxRouter
        routers = list()
        for i in range(1, number_of_routers + 1):
            routers.append(self.addHost(f'r{i}', cls=LinuxRouter, ip=None))
        print(routers)  # Wyświetlenie listy obiektów ruterów

        # Zebranie interfejsów i adresów IP z konfiguracji frr.conf
        router_interfaces = collect_all_interfaces()
        links = find_links(router_interfaces)  # Znalezienie połączeń między ruterami na podstawie wspólnych podsieci
        addlink_calls = generate_addlink_calls(links)  # Generacja kodu .addLink dla tych połączeń

        # Dodanie hostów do każdego rutera
        hosts = list()
        for i in range(1, number_of_routers + 1):
            hosts.append(self.addHost(name=f"h{i}",  # Nazwa hosta
                          ip=f"192.168.{i}.2/24",  # Adres IP hosta
                          defaultRoute=f"via 192.168.{i}.1"))  # Brama domyślna do rutera

        # Dodanie linków host ↔ ruter z określoną przepustowością (1000 Mbit/s)
        for i in range(1, number_of_routers + 1):
            self.addLink(routers[i-1], hosts[i-1],
                intfName1="eth0",  # Interfejs po stronie rutera
                params1={'ip':f"192.168.{i}.1/24"},  # IP po stronie rutera
                intfName2="eth0",  # Interfejs po stronie hosta
                params2={'ip':f"192.168.{i}.2/24"}, bw=1000)  # IP + przepustowość

        print("Rzeczywiste dodawanie linków pomiędzy ruterami:\n")
        for call in addlink_calls:  # Iterujemy po każdej wygenerowanej linijce .addLink(...)
            print(call + "\n")  # Wypisujemy ją (debug)
            info = extract_link_info(call)  # Parsujemy dane z tekstu (nazwa, interfejs, IP)

            # Dodanie linku między odpowiednimi ruterami
            self.addLink(get_router_by_name(info['device1']['name'], routers),
                         get_router_by_name(info['device2']['name'], routers),
                         intfName1=info['device1']['interface'],
                         params1={'ip': info['device1']['ip']},
                         intfName2=info['device2']['interface'],
                         params2={'ip': info['device2']['ip']}, bw=100)  # Link ruter↔ruter z BW = 100 Mbit/s


def generate_demand_matrix(num_routers):  # Funkcja generuje macierz zapotrzebowania na przepustowość (host → host)
    min_demand = 50  # Minimalne zapotrzebowanie na ruch w Mbit/s
    max_demand = 100  # Maksymalne zapotrzebowanie

    demand_matrix = np.zeros((num_routers, num_routers), dtype=int)  
    # Inicjalizacja macierzy (host x host) wypełnionej zerami

    for i in range(num_routers):  # Iteracja po hostach źródłowych (hosty przypisane ruterom)
        # Losujemy liczbę docelowych hostów: od 2 do 5
        max_targets = 5  # Maksymalna liczba hostów, do których dany host będzie wysyłał dane
        num_targets = np.random.randint(2, max_targets + 1)  # Losowa liczba celów (min. 2, max. 5)

        # Wybieramy losowo cele, do których ruter będzie wysyłał dane
        possible_targets = [j for j in range(num_routers) if j != i]  # Wszystkie inne hosty oprócz źródłowego
        selected_targets = np.random.choice(possible_targets, size=num_targets, replace=False)  
        # Wybieramy unikalnie cele

        # Przypisujemy losowe wartości zapotrzebowania
        for j in selected_targets:  # Dla każdego wybranego celu
            demand_matrix[i][j] = np.random.randint(min_demand, max_demand + 1)  
            # Losujemy wartość zapotrzebowania na ruch od min do max

    return demand_matrix  # Zwracamy gotową macierz

def run():
    global number_of_routers  # Używamy globalnej liczby ruterów

    topo = NetworkTopo()  # Tworzymy obiekt topologii — wykonuje wszystkie wcześniejsze kroki konfiguracyjne
    net = Mininet(topo=topo, link=TCLink)  # Tworzymy sieć Mininet z tą topologią, używając TCLink (obsługa parametrów łącza)

    # Rozpoczęcie działania demona FRRouting na każdym ruterze
    for i in range(1, number_of_routers+1):
        info(net[f'r{i}'].cmd(f"/usr/lib/frr/frrinit.sh start 'r{i}'"))  # Start demona frr dla każdego rutera

    net.start()  # Uruchamiamy sieć
    print("Czekam na zbieżność routingu...")
    time.sleep(45)  # Dajemy czas na stabilizację OSPF

    # Tworzenie folderu na wyniki (jeśli nie istnieje)
    os.makedirs("podsumowanie", exist_ok=True)    

    # Tworzymy nowy podfolder z numerem = liczba już istniejących folderów
    folder_path = 'podsumowanie'
    folders = [f for f in os.listdir(folder_path) if os.path.isdir(os.path.join(folder_path, f))]
    print(f"Liczba folderów w podsumowanie: {len(folders)+1}")
    results_dir = f'podsumowanie/{len(folders)}/wyniki'
    os.makedirs(results_dir, exist_ok=True)  # Tworzymy folder na wyniki `iperf`

    # Generowanie macierzy zapotrzebowania i zapisanie jej do podfolderu
    demand_matrix = generate_demand_matrix(number_of_routers)
    save_matrix_to_csv(demand_matrix, f"podsumowanie/{len(folders)}/macierz_zapotrzebowania.csv")

    # Zapisujemy również wcześniej stworzoną macierz sąsiedztwa
    adj_matrix = load_matrix_from_csv("macierz_sasiedztwa.csv")
    save_matrix_to_csv(adj_matrix, f"podsumowanie/{len(folders)}/macierz_sasiedztwa.csv")

    num_hosts = len(demand_matrix)  # Liczba hostów = liczba ruterów

    # Start serwerów iperf na wszystkich hostach (port domyślny: 5001)
    for i in range(num_hosts):
        host = net.get(f'h{i+1}')
        server_log = os.path.join(results_dir, f'h{i+1}_server.txt')
        host.cmd(f'iperf -s -i 1 > {server_log} 2>&1 &')  # Uruchamiamy serwer iperf w tle

    time.sleep(5)
    print("Wystartowano iperf na klientach!")

    # Uruchomienie klientów iperf na podstawie macierzy zapotrzebowania
    for i in range(num_hosts):
        for j in range(num_hosts):
            if i != j and demand_matrix[i][j] > 0:  # Jeśli ruch między i a j istnieje
                src_host = net.get(f'h{i+1}')  # Host wysyłający
                dst_host = net.get(f'h{j+1}')  # Host odbierający
                dst_ip = dst_host.IP()  # IP odbiorcy
                client_log = os.path.join(results_dir, f'h{i+1}_client_to_h{j+1}.txt')
                src_host.cmd(f'iperf -c {dst_ip} -t 10 -i 1 -b {demand_matrix[i][j]}M> {client_log} 2>&1 &')
                # Uruchamiamy klienta iperf z odpowiednim pasmem
                print(f"Host h{i+1} sends with {demand_matrix[i][j]}Mbps bandwidth to Host h{j+1}")

    print("Rozpoczęto iperf na klientach!")
    print("Oczekiwanie na zakończenie iperfa")
    time.sleep(15)  # Czekamy aż iperf zakończy działanie

    # Zatrzymanie demonów FRR po zakończeniu testu
    for k in range(1, number_of_routers+1):
        info(net[f'r{k}'].cmd(f"/usr/lib/frr/frrinit.sh stop 'r{k}'"))

    net.stop()  # Wyłączamy sieć Mininet

if __name__ == '__main__':  # Blok uruchamiany tylko, jeśli plik wywoływany bezpośrednio (nie importowany)
    setLogLevel('info')  # Ustawiamy poziom logów Minineta na "info"
    run()  # Wywołujemy funkcję run(), która odpala całą symulację

    base_dir = os.path.dirname(os.path.abspath(__file__))  # Ścieżka do katalogu skryptu
    pattern = re.compile(r"^r\d+$")  # Wzorzec nazw folderów tymczasowych ruterów (r1, r2, ...)

    # Usuwamy katalogi tymczasowe ruterów po zakończeniu symulacji
    for item in os.listdir(base_dir):  # Iterujemy po zawartości katalogu
        full_path = os.path.join(base_dir, item)
        if os.path.isdir(full_path) and pattern.match(item):  # Jeśli to folder rutera
            print(f"Usuwam katalog: {full_path}")
            shutil.rmtree(full_path)  # Trwałe usunięcie katalogu