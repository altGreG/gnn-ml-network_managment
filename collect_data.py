import subprocess
import time
import os

password = "ubuntu"
for i in range(1):
    print(f"Iteracja nr.: {i}")

    command = ["sudo", "-S", "mn", "-c"]
    process = subprocess.run(command, input=password + "\n",capture_output=True, text=True)
    if process.returncode != 0:
        print("Error")
        print(process.stderr)
    else:
        print("Sukces, zrestartowano konfigurację mininet!")

    time.sleep(1)

    command = ["sudo", "-S", "python3", "./my_topo.py"]
    process = subprocess.run(command, input=password + "\n",capture_output=True, text=True)
    if process.returncode != 0:
        print("Error")
        print(process.stderr)
    else:
        folder_path = 'podsumowanie'
        # Lista tylko folderów w folderze "podsumowanie"
        folders = [f for f in os.listdir(folder_path) if os.path.isdir(os.path.join(folder_path, f))]
        folder_number = len(folders)
        print("Sukces, stworzono topologię i zasymulowano ruch!")
        
        output_path = f"./podsumowanie/{folder_number-1}"  # albo np. "./output"
        file_name = "mininet_output.txt"
        file_path = os.path.join(output_path, file_name)
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(process.stdout)

    time.sleep(0.1)