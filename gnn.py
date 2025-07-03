import os  # Operacje na systemie plików
import re  # Wyrażenia regularne
import csv  # Operacje na plikach CSV
import torch  # Główna biblioteka PyTorch
import torch.nn.functional as F  # Funkcje pomocnicze dla trenowania modeli
import numpy as np  # Operacje na tablicach numerycznych
import matplotlib.pyplot as plt  # Wizualizacja wykresów
from torch.nn import Linear  # Warstwa liniowa (fully connected)
from torch_geometric.data import Data  # Struktura danych grafowych
from torch_geometric.loader import DataLoader  # Loader do grafowych danych
from torch_geometric.nn import GCNConv  # Warstwa GCN (Graph Convolutional Network)
from sklearn.metrics import classification_report, confusion_matrix  # Ewaluacja modelu
from sklearn.model_selection import train_test_split  # Podział danych na train/test
import seaborn as sns  # Wizualizacja macierzy pomyłek

# === PARAMETRY ===
BASE_DIR = "podsumowanie"  # Główny folder z danymi
CAPACITY = 100.0  # Maksymalna przepustowość (do przeliczeń)
regex = re.compile(r"(\d+\.\d+)\s+Mbits/sec")  # Wzorzec do wyciągania wartości throughput

# === FUNKCJA DO WCZYTANIA GRAFU Z FOLDERU ===
def load_graph_from_folder(folder_path):
    # Ścieżki do odpowiednich plików
    demand_path = os.path.join(folder_path, "macierz_zapotrzebowania.csv")
    sasiedztwo_path = os.path.join(folder_path, "macierz_sasiedztwa.csv")
    wynikowa_path = os.path.join(folder_path, "macierz_wynikowa.csv")
    wyniki_path = os.path.join(folder_path, "wyniki")

    # Sprawdzenie, czy wszystkie wymagane pliki istnieją
    if not os.path.exists(demand_path) or not os.path.exists(sasiedztwo_path) or not os.path.isdir(wyniki_path):
        return None

    # Wczytanie danych z plików CSV
    demand = np.loadtxt(demand_path, delimiter=",", dtype=int)
    sasiedztwo = np.loadtxt(sasiedztwo_path, delimiter=",", dtype=int)
    num_nodes = demand.shape[0]  # Liczba węzłów w grafie
    measured_throughput = np.zeros_like(demand, dtype=float)  # Macierz przepustowości

    # Parsowanie plików wynikowych z przepustowościami
    for fname in os.listdir(wyniki_path):
        match = re.match(r"h(\d+)_client_to_h(\d+)\.txt", fname)
        if not match:
            continue
        i, j = int(match.group(1)) - 1, int(match.group(2)) - 1  # Indeksy węzłów
        with open(os.path.join(wyniki_path, fname), "r") as f:
            for line in reversed(f.readlines()):  # Szukanie ostatniego pasującego wiersza
                m = regex.search(line)
                if m:
                    measured_throughput[i][j] = float(m.group(1))  # Zapisanie przepustowości
                    break

    # Tworzenie macierzy wynikowej: 1 oznacza przeciążenie
    wynikowa = np.zeros_like(demand, dtype=int)
    for i in range(num_nodes):
        for j in range(num_nodes):
            if i != j and demand[i][j] > 0:
                if measured_throughput[i][j] < 0.2 * demand[i][j]:
                    wynikowa[i][j] = 1

    # Zapis macierzy wynikowej do pliku
    with open(wynikowa_path, "w", newline="") as f:
        csv.writer(f).writerows(wynikowa)

    edge_index = []  # Lista krawędzi (i, j)
    edge_attr = []  # Atrybuty krawędzi
    edge_labels = []  # Etykiety krawędzi

    for i in range(num_nodes):
        for j in range(num_nodes):
            if i != j and demand[i][j] > 0:
                edge_index.append([i, j])
                usage_ratio = demand[i][j] / CAPACITY
                throughput = measured_throughput[i][j]
                deficit = demand[i][j] - throughput
                attr = [demand[i][j], deficit, CAPACITY, usage_ratio, throughput]  # 5 cech
                edge_attr.append(attr)
                edge_labels.append(wynikowa[i][j])

    # Konwersja danych do tensorów
    edge_index = torch.tensor(edge_index, dtype=torch.long).t().contiguous()
    edge_attr = torch.tensor(edge_attr, dtype=torch.float)
    edge_labels = torch.tensor(edge_labels, dtype=torch.long)
    x = torch.eye(num_nodes, dtype=torch.float)  # Macierz jednostkowa jako cechy węzłów

    return Data(x=x, edge_index=edge_index, edge_attr=edge_attr, y=edge_labels)

# === WCZYTANIE WSZYSTKICH GRAFÓW ===
data_list = []
for folder in sorted(os.listdir(BASE_DIR), key=lambda x: int(x) if x.isdigit() else -1):
    folder_path = os.path.join(BASE_DIR, folder)
    data = load_graph_from_folder(folder_path)
    if data:
        data_list.append(data)

# === PODZIAŁ NA TRAIN/TEST ===
train_data, test_data = train_test_split(data_list, test_size=0.2, random_state=42)
train_loader = DataLoader(train_data, batch_size=1, shuffle=True)
test_loader = DataLoader(test_data, batch_size=1, shuffle=False)

# === DEFINICJA MODELU GNN ===
class GNNModel(torch.nn.Module):
    def __init__(self):
        super().__init__()
        self.conv1 = GCNConv(5, 64)  # Pierwsza warstwa GCN: 5 wejść -> 64 wyjścia
        self.conv2 = GCNConv(64, 32)  # Druga warstwa GCN
        self.fc1 = Linear(32, 16)  # Warstwa liniowa (32 -> 16)
        self.fc2 = Linear(16, 2)  # Wyjście: klasyfikacja binarna (OK/przeciążenie)

    def forward(self, data):
        x, edge_index, edge_attr = data.x, data.edge_index, data.edge_attr
        x = self.conv1(edge_attr, edge_index)  # Przejście przez pierwszą warstwę GCN
        x = F.relu(x)  # Aktywacja ReLU
        x = self.conv2(x, edge_index)  # Druga warstwa GCN
        x = F.relu(x)
        x = self.fc1(x)  # Pierwsza warstwa FC
        x = F.relu(x)
        return self.fc2(x)  # Ostateczne wyjście

# === TRENING ===
model = GNNModel()  # Inicjalizacja modelu
optimizer = torch.optim.Adam(model.parameters(), lr=0.001)  # Optymalizator
losses = []  # Lista strat

for epoch in range(100):  # Liczba epok
    model.train()  # Tryb treningu
    total_loss = 0
    total_edges = 0
    for data in train_loader:  # Iteracja po danych treningowych
        optimizer.zero_grad()  # Zerowanie gradientów
        out = model(data)  # Przejście przez model
        loss = F.cross_entropy(out, data.y, reduction='sum')  # Obliczenie straty
        loss.backward()  # Backpropagation
        optimizer.step()  # Aktualizacja wag
        total_loss += loss.item()
        total_edges += data.y.size(0)
    avg_loss = total_loss / total_edges if total_edges > 0 else 0  # Średnia strata
    losses.append(avg_loss)
    if epoch % 10 == 0:  # Logowanie co 10 epok
        print(f"Epoch {epoch}, Loss: {avg_loss:.4f}")

# === WYKRES STRATY ===
plt.figure(figsize=(8, 5))
plt.plot(losses, label='Średni Loss per epoka')
plt.xlabel('Epoka')
plt.ylabel('Loss')
plt.title('Krzywa uczenia')
plt.grid(True)
plt.legend()
plt.tight_layout()
plt.show()

# === EWALUACJA ===
model.eval()  # Tryb ewaluacji
y_true = []  # Etykiety prawdziwe
y_pred = []  # Etykiety przewidywane

with torch.no_grad():  # Bez obliczania gradientów
    for data in test_loader:
        logits = model(data)  # Przewidywania
        preds = logits.argmax(dim=1)  # Wybór klasy
        y_true.extend(data.y.tolist())
        y_pred.extend(preds.tolist())

print("\n KLASYFIKACJA KRAWĘDZI:")
print(classification_report(y_true, y_pred, digits=4))  # Raport klasyfikacji

# === MACIERZ POMYŁEK ===
cm = confusion_matrix(y_true, y_pred)  # Obliczenie macierzy pomyłek
plt.figure(figsize=(5, 4))
sns.heatmap(cm, annot=True, fmt='d', cmap='Blues', xticklabels=['OK', 'PRZECIĄŻONY'], yticklabels=['OK', 'PRZECIĄŻONY'])
plt.xlabel('Predykcja')
plt.ylabel('Rzeczywiste')
plt.title('Macierz pomyłek')
plt.tight_layout()
plt.show()