import os
import psutil

print(f"Total CPU Cores (vCPUs): {os.cpu_count()}")
print(f"Total RAM: {round(psutil.virtual_memory().total / (1024**3), 2)} GB")