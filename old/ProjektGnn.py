import random
import csv
import os
import time
from mininet.topo import Topo
from mininet.net import Mininet
from mininet.node import Node
from mininet.cli import CLI
from mininet.log import setLogLevel
from mininet.link import TCLink

# tworzenie macierzy sąsiedztwa 
def generate_adjacency_matrix(n):
    # zapewnienie spójności topologii
    matrix = [[0]*n for _ in range(n)]
    nodes = list(range(n))
    random.shuffle(nodes)

    for i in range(1, n):
        a = nodes[i]
        b = random.choice(nodes[:i])
        matrix[a][b] = matrix[b][a] = 1

    # dodanie losowych krawędzi
    for i in range(n):
        for j in range(i+1, n):
            if matrix[i][j] == 0 and random.random() < 0.2:
                matrix[i][j] = matrix[j][i] = 1

    return matrix


def save_matrix_to_csv(matrix, filename="adjacency_matrix.csv"):
    with open(filename, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerows(matrix)

class FRRRouter(Node):
    def config(self, **params):
        super().config(**params)
        self.cmd("sysctl -w net.ipv4.ip_forward=1")
        self.frr_dir = f"/tmp/frr/{self.name}"
        os.makedirs(self.frr_dir, exist_ok=True)

        self.daemons = f"""zebra=yes
bgpd=no
ospfd=yes
"""
        with open(f"{self.frr_dir}/daemons", "w") as f:
            f.write(self.daemons)

    def start_frr(self):
        self.cmd(f"zebra -f {self.frr_dir}/frr.conf -d -z {self.frr_dir}/zebra.api -i {self.frr_dir}/zebra.pid")
        self.cmd(f"ospfd -f {self.frr_dir}/frr.conf -d -z {self.frr_dir}/zebra.api -i {self.frr_dir}/ospfd.pid")

class OSPFFRRTopo(Topo):
    def __init__(self, matrix):
        super().__init__()
        self.matrix = matrix
        self.routers = []
        self.ip_map = {}
        self.build_topology()

    def build_topology(self):
        num_routers = len(self.matrix)
        self.routers = [self.addHost(f"r{i+1}", cls=FRRRouter) for i in range(num_routers)]
        subnet_id = 1
        for i in range(num_routers):
            for j in range(i+1, num_routers):
                if self.matrix[i][j]:
                    r1, r2 = self.routers[i], self.routers[j]
                    self.addLink(r1, r2)
                    self.ip_map[(r1, r2)] = (f"10.{subnet_id}.0.1/30", f"10.{subnet_id}.0.2/30")
                    subnet_id += 1


# konfiguracja frr
def configure_frr(net, topo):
    for r in net.hosts:
        router = r
        intf_cfg = []
        ospf_cfg = []

        for intf in router.intfList():
            if not router.name in str(intf): continue
            peer = intf.link.intf1.node if intf.link.intf1.node != router else intf.link.intf2.node
            ip1, ip2 = topo.ip_map.get((router.name, peer.name)) or topo.ip_map.get((peer.name, router.name))
            ip = ip1 if router.name < peer.name else ip2

            router.setIP(ip.split('/')[0], prefixLen=30, intf=intf)
            print(f"{router.name} {intf} -> {ip}") 
            intf_cfg.append(f"interface {intf}\n ip address {ip}\n!")
            ospf_cfg.append(f" network {ip.split('/')[0]}/30 area 0")


        config = f"""hostname {router.name}
password zebra
!
{"".join(intf_cfg)}
router ospf
{"".join(ospf_cfg)}
!
line vty
"""
        with open(f"{router.frr_dir}/frr.conf", "w") as f:
            f.write(config.strip())

        router.start_frr()
        time.sleep(0.5)

def main():
    setLogLevel("info")
    num_routers = random.randint(10, 15) # liczba urzadzen
    matrix = generate_adjacency_matrix(num_routers)
    save_matrix_to_csv(matrix)
    topo = OSPFFRRTopo(matrix)
    net = Mininet(topo=topo, link=TCLink, controller=None)
    net.start()
    configure_frr(net, topo)
    CLI(net)
    net.stop()

if __name__ == "__main__":
    main()