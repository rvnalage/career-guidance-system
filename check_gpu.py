import torch

print("\n=== GPU Detection ===\n")
print(f"PyTorch Version: {torch.__version__}")
print(f"CUDA Available: {torch.cuda.is_available()}")
print(f"CUDA Device Count: {torch.cuda.device_count()}")

if torch.cuda.is_available():
    print(f"\n✅ GPU DETECTED:")
    for i in range(torch.cuda.device_count()):
        print(f"  Device {i}: {torch.cuda.get_device_name(i)}")
        cap = torch.cuda.get_device_capability(i)
        print(f"  Compute Capability: {cap[0]}.{cap[1]}")
        mem = torch.cuda.get_device_properties(i).total_memory / 1e9
        print(f"  Total Memory: {mem:.1f} GB")
else:
    print(f"\n❌ No NVIDIA GPU detected")
    print(f"   Training will run on CPU (slower but feasible)")
    print(f"\n   Estimated time for 1 epoch:")
    print(f"   - With GPU: 5-10 minutes")
    print(f"   - On CPU: 45-90 minutes")
